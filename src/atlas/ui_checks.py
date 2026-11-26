# ruff: noqa: E501
"""Measured accessibility checks for the foundation, run in a real browser (Playwright + Chromium) on the generated
components page at 375 px and 1280 px, in Light and in Dark.

    python scripts/check_ui_foundation.py [--shots DIR]

Measures (WCAG 2.2 AA):
  contrast   text 4.5:1 (3:1 for large text), control borders 3:1, icons 3:1, placeholder 4.5:1, focus ring 3:1
  targets    every interactive element at least 44 x 44 px
  names      every interactive element has an accessible name
  requests   nothing leaves the page (only the local file server is used)
  scroll     no horizontal scroll
Inactive (disabled) controls are exempt from contrast, as WCAG allows. The checks read computed colours, so they follow
the real CSS, including color-mix. Results come back as plain dicts so tests and the command line share one code path.
"""

from __future__ import annotations

import contextlib
import functools
import http.server
import threading
from pathlib import Path

from .ui_components_page import build

VIEWS = [(375, 812), (1280, 800)]
THEMES = ["light", "dark"]

JS_MEASURE = r"""
() => {
  const out = {contrast: [], icons: [], borders: [], targets: [], names: [], counts: {}};
  const parse = (s) => {
    let m = s.match(/^rgba?\(([^)]+)\)$/);
    if (m) { const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; }
    m = s.match(/^color\(srgb ([^)]+)\)$/);
    if (m) { const p = m[1].split(/[ \/]+/).filter(Boolean).map(Number); return [p[0]*255, p[1]*255, p[2]*255, p.length > 3 ? p[3] : 1]; }
    return null;
  };
  const over = (top, bot) => { const a = top[3]; return [top[0]*a + bot[0]*(1-a), top[1]*a + bot[1]*(1-a), top[2]*a + bot[2]*(1-a), 1]; };
  const bgOf = (el) => {
    const chain = [];
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const c = parse(getComputedStyle(n).backgroundColor);
      if (c && c[3] > 0) { chain.push(c); if (c[3] >= 1) break; }
    }
    let base = [255, 255, 255, 1];
    for (let i = chain.length - 1; i >= 0; i--) base = over(chain[i], base);
    return base;
  };
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126*f(c[0]) + 0.7152*f(c[1]) + 0.0722*f(c[2]); };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const vis = (el) => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  const label = (el) => (el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).join('.') : '') + ' "' + (el.textContent || el.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 30) + '"');
  const scope = document.querySelector('.ax.portal') && window.__onlyPortal ? document.querySelector('.ax.portal') : document.body;
  const all = [...scope.querySelectorAll('*')].filter((e) => !e.closest('svg') || e.tagName.toLowerCase() === 'svg');

  // text
  for (const el of all) {
    if (el.tagName === 'SVG' || el.tagName === 'svg' || !vis(el)) continue;
    if (el.closest('[disabled]') || el.closest('.vh')) continue;
    const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    const isField = (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') && el.type !== 'radio' && el.type !== 'checkbox';
    if (!own && !isField) continue;
    const cs = getComputedStyle(el);
    if (isField) {
      if (el.value) {
        const fg = over(parse(cs.color), bgOf(el)), bg = bgOf(el); out.contrast.push({kind: 'text', el: label(el), ratio: ratio(fg, bg), need: 4.5});
      }
      const ph = getComputedStyle(el, '::placeholder'); const pc = parse(ph.color);
      if (el.placeholder && pc) { const bg = bgOf(el); out.contrast.push({kind: 'placeholder', el: label(el), ratio: ratio(over(pc, bg), bg), need: 4.5}); }
      continue;
    }
    const bg = bgOf(el), fgc = parse(cs.color); if (!fgc) continue;
    const size = parseFloat(cs.fontSize), bold = parseInt(cs.fontWeight, 10) >= 700;
    const large = size >= 24 || (size >= 18.66 && bold);
    out.contrast.push({kind: 'text', el: label(el), ratio: ratio(over(fgc, bg), bg), need: large ? 3 : 4.5});
  }
  // icons: colour against what is behind them
  for (const svg of scope.querySelectorAll('svg.ic')) {
    if (!vis(svg) || svg.closest('[disabled]')) continue;
    const fgc = parse(getComputedStyle(svg).color), bg = bgOf(svg.parentElement || svg);
    out.icons.push({el: label(svg.parentElement) + ' icon', ratio: ratio(over(fgc, bg), bg), need: 3});
  }
  // control borders against what surrounds them (not inactive controls)
  const ctl = '.btn-secondary,.btn-danger,.chip,.input,.select,.textarea,.search,.toggle .track,.choice,.seg .o,.star,.savedrow,.pin';
  for (const el of scope.querySelectorAll(ctl)) {
    if (!vis(el) || el.hasAttribute('disabled')) continue;
    const cs = getComputedStyle(el);
    const bc = parse(cs.borderTopColor), w = parseFloat(cs.borderTopWidth);
    if (!bc || w < 1) continue;
    const parentBg = bgOf(el.parentElement);
    out.borders.push({el: label(el), ratio: ratio(over(bc, parentBg), parentBg), need: 3});
  }
  // targets, names
  const sel = 'a[href],button,input:not([type=hidden]),select,textarea,summary,[role=switch],[role=radio],[role=link],[tabindex="0"]';
  for (const el of scope.querySelectorAll(sel)) {
    if (!vis(el)) continue;
    if (el.closest('.vh')) continue;
    const r = el.getBoundingClientRect();
    // The tap area is the control's box, or its invisible ::after hit-area box when that is larger (harbor.css, D-102).
    const pa = getComputedStyle(el, '::after');
    const ext = pa.content !== 'none' && pa.position === 'absolute';
    const w = Math.max(r.width, ext ? parseFloat(pa.width) || 0 : 0);
    const h = Math.max(r.height, ext ? parseFloat(pa.height) || 0 : 0);
    out.targets.push({el: label(el), w: Math.round(w * 10) / 10, h: Math.round(h * 10) / 10});
    let name = el.getAttribute('aria-label') || '';
    const lb = el.getAttribute('aria-labelledby');
    if (!name && lb) name = lb.split(' ').map((i) => (document.getElementById(i) || {}).textContent || '').join(' ');
    if (!name && el.labels && el.labels.length) name = [...el.labels].map((l) => l.textContent).join(' ');
    if (!name && el.tagName !== 'INPUT' && el.tagName !== 'TEXTAREA' && el.tagName !== 'SELECT') name = el.textContent;
    if (!name && el.placeholder) name = '';
    out.names.push({el: label(el), name: (name || '').trim()});
  }
  out.counts = {text: out.contrast.length, icons: out.icons.length, borders: out.borders.length, targets: out.targets.length};
  out.scroll = {sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth};
  out.themeAttr = document.documentElement.getAttribute('data-theme');
  return out;
}
"""

JS_RING = r"""
(el) => {
  const parse = (s) => { let m = s.match(/^rgba?\(([^)]+)\)$/); if (m) { const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; } m = s.match(/^color\(srgb ([^)]+)\)$/); if (m) { const p = m[1].split(/[ \/]+/).filter(Boolean).map(Number); return [p[0]*255, p[1]*255, p[2]*255, p.length > 3 ? p[3] : 1]; } return null; };
  const over = (t, b) => { const a = t[3]; return [t[0]*a + b[0]*(1-a), t[1]*a + b[1]*(1-a), t[2]*a + b[2]*(1-a), 1]; };
  const bgOf = (e) => { const chain = []; for (let n = e; n && n.nodeType === 1; n = n.parentElement) { const c = parse(getComputedStyle(n).backgroundColor); if (c && c[3] > 0) { chain.push(c); if (c[3] >= 1) break; } } let base = [255,255,255,1]; for (let i = chain.length - 1; i >= 0; i--) base = over(chain[i], base); return base; };
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126*f(c[0]) + 0.7152*f(c[1]) + 0.0722*f(c[2]); };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const label = (e) => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + ' "' + (e.textContent || e.getAttribute('aria-label') || e.value || '').trim().slice(0, 24) + '"';
  const cands = [el, el.nextElementSibling, el.closest('label'), el.closest('.search,.composer')].filter(Boolean);
  for (const c of cands) {
    const cs = getComputedStyle(c);
    if (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) >= 2) {
      const col = parse(cs.outlineColor), bg = bgOf(c.parentElement || c);
      return {el: label(el), visible: true, width: parseFloat(cs.outlineWidth), ratio: ratio(over(col, bg), bg)};
    }
  }
  return {el: label(el), visible: false, width: 0, ratio: 0};
}
"""


def _server(root: Path):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a, **k: None  # type: ignore[attr-defined]
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def find_axe() -> Path | None:
    here = Path(__file__).resolve().parents[2]
    for base in (here, here.parent / "accessibility-map", here.parent / "accessibility-map-assistant"):
        p = base / ".axe/node_modules/axe-core/axe.min.js"
        if p.exists():
            return p
    return None


def run(shots: Path | None = None, use_axe: bool = True, browser=None) -> dict:
    """Run every check. Returns {"views": [...per width and theme...], "failures": [str, ...]}."""
    from playwright.sync_api import sync_playwright

    page_path = build()
    srv = _server(page_path.parent)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    axe = find_axe() if use_axe else None
    result: dict = {"views": [], "failures": [], "axe": bool(axe)}
    try:
        with contextlib.ExitStack() as stack:
            if browser is None:
                browser = stack.enter_context(sync_playwright()).chromium.launch()
                stack.callback(browser.close)
            for width, height in VIEWS:
                for theme in THEMES:
                    ctx = browser.new_context(
                        viewport={"width": width, "height": height},
                        color_scheme="dark" if theme == "light" else "light",
                    )
                    # the device setting is the opposite of the choice on purpose: the app must not follow it
                    ctx.add_init_script(f"try{{localStorage.setItem('atlas.theme','{theme}')}}catch(e){{}}")
                    requests: list[str] = []
                    pg = ctx.new_page()
                    pg.on("request", lambda r, requests=requests: requests.append(r.url))
                    errors: list[str] = []
                    pg.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
                    pg.goto(f"{base}/components.html")
                    pg.wait_for_function("document.fonts.status === 'loaded'")
                    view = {"width": width, "theme": theme}
                    m = pg.evaluate(JS_MEASURE)
                    tag = f"{width}px {theme}"
                    view["counts"] = m["counts"]
                    view["theme_attr"] = m["themeAttr"]
                    view["theme_at_body_start"] = pg.evaluate("window.__themeAtBodyStart")
                    if m["themeAttr"] != theme or view["theme_at_body_start"] != theme:
                        result["failures"].append(
                            f"[{tag}] theme not applied before first paint: {view['theme_at_body_start']} / {m['themeAttr']}"
                        )
                    for kind, key in (("text", "contrast"), ("icon", "icons"), ("border", "borders")):
                        rows = m[key]
                        low = [r for r in rows if r["ratio"] < r["need"] - 1e-9]
                        view[f"min_{kind}"] = round(min((r["ratio"] for r in rows), default=0), 2)
                        for r in low:
                            result["failures"].append(
                                f"[{tag}] contrast {r.get('kind', kind)} {r['ratio']:.2f} < {r['need']}: {r['el']}"
                            )
                    small = [t for t in m["targets"] if t["w"] < 44 - 0.01 or t["h"] < 44 - 0.01]
                    view["min_target"] = min((min(t["w"], t["h"]) for t in m["targets"]), default=0)
                    for t in small:
                        result["failures"].append(f"[{tag}] target {t['w']}x{t['h']} < 44: {t['el']}")
                    for n in m["names"]:
                        if not n["name"]:
                            result["failures"].append(f"[{tag}] no accessible name: {n['el']}")
                    if m["scroll"]["sw"] > m["scroll"]["cw"]:
                        result["failures"].append(
                            f"[{tag}] horizontal scroll: {m['scroll']['sw']} > {m['scroll']['cw']}"
                        )
                    # focus ring on every focusable element, by keyboard
                    pg.keyboard.press("Tab")
                    rings = []
                    seen = set()
                    for _ in range(400):
                        el = pg.evaluate_handle("document.activeElement")
                        if pg.evaluate("(e) => e === document.body || e === document.documentElement", el):
                            break
                        key = pg.evaluate(
                            "(e) => e.outerHTML.slice(0, 160) + e.getBoundingClientRect().top", el
                        )
                        if key in seen:
                            break
                        seen.add(key)
                        rings.append(pg.evaluate(JS_RING, el))
                        pg.keyboard.press("Tab")
                    view["focus_stops"] = len(rings)
                    view["min_focus"] = round(min((r["ratio"] for r in rings), default=0), 2)
                    for r in rings:
                        if not r["visible"]:
                            result["failures"].append(f"[{tag}] no visible focus ring: {r['el']}")
                        elif r["ratio"] < 3:
                            result["failures"].append(f"[{tag}] focus ring {r['ratio']:.2f} < 3: {r['el']}")
                    # no external requests
                    ext = [u for u in requests if not u.startswith((base, "data:", "about:", "blob:"))]
                    view["requests"] = len(requests)
                    for u in ext:
                        result["failures"].append(f"[{tag}] external request: {u}")
                    # sheet and toast open: measure what is on top, check the trap
                    pg.evaluate("window.scrollTo(0,0)")
                    pg.get_by_role("button", name="Open a sheet").click()
                    pg.wait_for_selector(".sheet.modal")
                    pg.evaluate("window.__onlyPortal = true")
                    ms = pg.evaluate(JS_MEASURE)
                    pg.evaluate("window.__onlyPortal = false")
                    for key, kind in (("contrast", "text"), ("icons", "icon"), ("borders", "border")):
                        for r in ms[key]:
                            if r["ratio"] < r["need"] - 1e-9:
                                result["failures"].append(
                                    f"[{tag}] sheet contrast {kind} {r['ratio']:.2f} < {r['need']}: {r['el']}"
                                )
                    for t in ms["targets"]:
                        if t["w"] < 43.99 or t["h"] < 43.99:
                            result["failures"].append(
                                f"[{tag}] sheet target {t['w']}x{t['h']} < 44: {t['el']}"
                            )
                    inert = pg.evaluate(
                        "[...document.body.children].filter(c => !c.classList.contains('portal') && c.tagName !== 'SCRIPT' && c.tagName !== 'SVG' && c.tagName !== 'svg').every(c => c.inert)"
                    )
                    if not inert:
                        result["failures"].append(f"[{tag}] background not inert while the sheet is open")
                    for _ in range(8):
                        pg.keyboard.press("Tab")
                    if not pg.evaluate("document.activeElement.closest('.sheet.modal') !== null"):
                        result["failures"].append(f"[{tag}] focus left the sheet")
                    if shots:
                        shots.mkdir(parents=True, exist_ok=True)
                        pg.screenshot(path=str(shots / f"components-{width}-{theme}-sheet.png"))
                    pg.keyboard.press("Escape")
                    if pg.locator(".sheet.modal").count() != 0:
                        result["failures"].append(f"[{tag}] Escape did not close the sheet")
                    if shots:
                        pg.evaluate("window.scrollTo(0,0)")
                        pg.screenshot(path=str(shots / f"components-{width}-{theme}.png"), full_page=True)
                    if axe:
                        pg.add_script_tag(path=str(axe))
                        v = pg.evaluate(
                            "async () => (await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa','best-practice']}})).violations.map(v => v.id + ': ' + v.help + ' @ ' + v.nodes.map(n => n.target.join(' ')).slice(0,3).join(' | '))"
                        )
                        view["axe_violations"] = len(v)
                        for x in v:
                            result["failures"].append(f"[{tag}] axe {x}")
                    for e in errors:
                        result["failures"].append(f"[{tag}] page error: {e}")
                    result["views"].append(view)
                    ctx.close()
    finally:
        srv.shutdown()
        srv.server_close()
    return result


def report(result: dict) -> str:
    lines = ["view          text  icon  border focus  min target  stops  axe  requests"]
    for v in result["views"]:
        lines.append(
            f"{v['width']:>4}px {v['theme']:<5} {v['min_text']:>5} {v['min_icon']:>5} {v['min_border']:>6} {v['min_focus']:>5} {v['min_target']:>8}px {v['focus_stops']:>6} "
            f"{v.get('axe_violations', 'n/a'):>4} {v['requests']:>8}"
        )
    lines.append(
        f"axe-core: {'run' if result['axe'] else 'not installed (npm install axe-core@4.10.2 --no-save --prefix ./.axe)'}"
    )
    lines.append(f"failures: {len(result['failures'])}")
    lines += ["  " + f for f in result["failures"]]
    return "\n".join(lines)
