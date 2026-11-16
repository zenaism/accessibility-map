"""The browser fallback: load a page in headless Chromium when a plain download is not enough, open what is hidden,
and save the rendered page plus a screenshot (docs/crawler_plan.md 6.3).

Politeness still applies: one page at a time, at least `delay` seconds between loads of one host, and nothing is clicked
that could change anything (no links, no forms, no submit buttons). Browser requests to our own network are refused.
"""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import re
import socket
import time
from urllib.parse import urlsplit

from ..core import USER_AGENT
from . import clock

THIN_CHARS = 200
SHELL = re.compile(
    r"""<div[^>]+id=["']?(root|app|__next|__nuxt|svelte)["']?[^>]*>\s*</div>|enable javascript|javascript is (required|disabled)""",
    re.I,
)
MAX_SHOT_HEIGHT = 12000
# Everything below runs inside the page. It clicks only expanders (never links or forms), then scrolls to the end.
EXPAND_JS = r"""
async () => {
  const out = {expanded: 0, tabs: 0, more: 0, cookie: 0};
  const safe = el => !el.closest('form') && !(el.tagName === 'A' && el.getAttribute('href') && el.getAttribute('href') !== '#')
                     && el.getAttribute('type') !== 'submit';  // (a button's .type defaults to 'submit', so read the attribute)
  const click = el => { try { el.click(); return true; } catch (e) { return false; } };
  for (const b of [...document.querySelectorAll('button, [role=button]')]) {      // cookie banners: choose the most private option
    if (/^\s*(reject|decline|deny|only (strictly )?necessary|necessary only|essential only)/i.test(b.innerText || '') && safe(b)) { click(b); out.cookie++; break; }
  }
  for (let round = 0; round < 2; round++) {
    document.querySelectorAll('details:not([open])').forEach(d => { d.open = true; out.expanded++; });
    for (const el of [...document.querySelectorAll('[aria-expanded="false"]')].slice(0, 40)) if (safe(el) && click(el)) out.expanded++;
    for (const el of [...document.querySelectorAll('[role=tab][aria-selected="false"]')].slice(0, 20)) if (safe(el) && click(el)) out.tabs++;
    for (const el of [...document.querySelectorAll('button, [role=button], a')].slice(0, 400)) {
      if (out.more < 10 && /^\s*(show|view|read|see|load)\s+(more|all)|^\s*expand( all)?\s*$/i.test(el.innerText || '') && safe(el) && click(el)) out.more++;
    }
    await new Promise(r => setTimeout(r, 400));
  }
  let last = -1;
  for (let i = 0; i < 15 && document.body.scrollHeight !== last; i++) {              // lazy-loaded content
    last = document.body.scrollHeight; window.scrollTo(0, last); await new Promise(r => setTimeout(r, 300));
  }
  window.scrollTo(0, 0);
  return out;
}
"""


HIDDEN_HINTS = ("aria-expanded", 'role="tab"', "role='tab'", "onclick", "data-toggle", "data-bs-toggle")


def render_signal(text: str, html: bytes) -> str | None:
    """How strongly a plain download suggests a browser is needed.
    'strong': an app shell or collapsed sections that open on click (always worth a browser).
    'weak': only a short page with scripts (worth trying, but a host where it keeps adding nothing is not retried).
    None: a normal page."""
    n = len(text.strip())
    head = html[:200_000].decode("utf-8", "ignore").lower()
    if (n < 800 and SHELL.search(head)) or (n < THIN_CHARS and any(h in head for h in HIDDEN_HINTS)):
        return "strong"
    if n < THIN_CHARS and "<script" in head:
        return "weak"
    return None


def needs_render(text: str, html: bytes, mode: str = "auto") -> bool:
    """True when a plain download looks empty AND scripts could have built the page: almost no text plus a script
    tag, or a short page that is an app shell. A short static page (no scripts) never needs a browser."""
    if mode == "never":
        return False
    if mode == "always":
        return True
    return render_signal(text, html) is not None


def is_private_host(host: str) -> bool:
    try:
        return any(
            (ip := ipaddress.ip_address(i[4][0])).is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            for i in socket.getaddrinfo(host, None)
        )
    except (OSError, ValueError):
        return False


class Renderer:
    """One shared browser. Started on first use, recycled every `recycle` pages, closed when the crawl ends."""

    def __init__(
        self, delay: float = 2.0, allow_private: bool = False, recycle: int = 100, timeout_ms: int = 45_000
    ):
        self.delay, self.allow_private, self.recycle, self.timeout_ms = (
            delay,
            allow_private,
            recycle,
            timeout_ms,
        )
        self._pw = self._browser = None
        self._lock = asyncio.Lock()
        self._last: dict[str, float] = {}
        self.count = 0
        self.denied: list[str] = []

    async def _start(self):
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch()
        self.count = 0

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        self._browser = self._pw = None

    async def _route(self, route):
        req = route.request
        parts = urlsplit(req.url)
        if parts.scheme not in ("http", "https", "data", "blob", "about"):
            self.denied.append(req.url)
            return await route.abort()
        if (
            parts.scheme in ("http", "https")
            and not self.allow_private
            and is_private_host(parts.hostname or "")
        ):
            self.denied.append(req.url)  # a page pointing the browser at our own network
            return await route.abort()
        if req.resource_type in ("media", "websocket", "eventsource"):
            return await route.abort()
        await route.continue_()

    async def render(self, url: str) -> dict | None:
        """{html, final_url, status, screenshot, actions} or None if the page could not be rendered."""
        host = urlsplit(url).hostname or ""
        async with self._lock:  # one page at a time
            gap = self.delay - (time.time() - max(self._last.get(host, 0), clock.last.get(host, 0)))
            if gap > 0:
                await asyncio.sleep(gap)
            try:
                if self._browser is None or self.count >= self.recycle:
                    await self.close()
                    await self._start()
                self.count += 1
                return await asyncio.wait_for(self._render(url), timeout=self.timeout_ms / 1000 + 30)
            except Exception:
                await self.close()  # a crashed or hung browser is replaced on the next page
                return None
            finally:
                self._last[host] = time.time()

    async def _render(self, url: str) -> dict:
        ctx = await self._browser.new_context(user_agent=USER_AGENT, viewport={"width": 1400, "height": 1000})
        try:
            await ctx.route("**/*", self._route)
            page = await ctx.new_page()
            page.on("dialog", lambda d: asyncio.ensure_future(d.dismiss()))  # never leave an alert open
            resp = await page.goto(url, wait_until="load", timeout=self.timeout_ms)
            with contextlib.suppress(Exception):  # chatty pages never go idle: carry on
                await page.wait_for_load_state("networkidle", timeout=4000)
            actions = await page.evaluate(EXPAND_JS)
            html = (await page.content()).encode()
            height = await page.evaluate("document.body ? document.body.scrollHeight : 0")
            shot = await page.screenshot(
                full_page=height <= MAX_SHOT_HEIGHT,
                clip=None
                if height <= MAX_SHOT_HEIGHT
                else {"x": 0, "y": 0, "width": 1400, "height": MAX_SHOT_HEIGHT},
            )
            return {
                "html": html,
                "final_url": page.url,
                "status": resp.status if resp else 0,
                "screenshot": shot,
                "actions": actions,
            }
        finally:
            await ctx.close()
