"""Save Playwright screenshots of every state of the Openway Assistant to docs/work_logs/screens/assistant/.

    python scripts/shoot_assistant.py

Desktop 1280x800 and phone 390x844. Each file is kept under 300 KB (palette-reduced if needed).
"""

from __future__ import annotations

import io
import json
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

from atlas.assistant import server
from atlas.assistant.page import build

OUT = Path(__file__).resolve().parents[1] / "docs/work_logs/screens/assistant"
TODAY = "2026-11-20"
SIZES = {"desktop": (1280, 800), "phone": (390, 844)}


def save(pg, name: str, kind: str) -> None:
    from PIL import Image

    raw = pg.screenshot()
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    f = OUT / f"{kind}-{name}.png"
    im.save(f, optimize=True)
    if f.stat().st_size > 300_000:
        im.quantize(colors=96).save(f, optimize=True)
    print(f"{f.name}: {f.stat().st_size // 1024} KB")


def ready(pg, base: str, q: str = "") -> None:
    pg.goto(f"{base}/ask.html?today={TODAY}{q}")
    pg.add_style_tag(content=".ow-log{scroll-behavior:auto!important}")
    pg.wait_for_selector(".ow-tiles button")
    pg.wait_for_function("!document.querySelector('.ow-compose button[type=submit]').disabled")


def ask(pg, text: str) -> None:
    pg.get_by_label("Your question").fill(text)
    pg.keyboard.press("Enter")
    pg.wait_for_selector(".ow-a .ow-main")
    pg.wait_for_timeout(150)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    build()
    s = server.serve(0)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{s.server_address[1]}"
    with sync_playwright() as p:
        b = p.chromium.launch()
        for kind, (w, h) in SIZES.items():
            mobile = kind == "phone"

            def ctx(**kw):
                return b.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile, **kw)

            c = ctx()
            pg = c.new_page()
            ready(pg, base)
            save(pg, "1-empty-tiles", kind)
            ask(pg, "Where is the closest accessible restroom near downtown?")
            pg.get_by_role("button", name="More detail").first.click()
            pg.locator(".ow-a").last.scroll_into_view_if_needed()
            pg.evaluate("document.querySelector('.ow-log').scrollTop = 0")
            save(pg, "2-answer-with-cards", kind)
            ask(pg, "Any events this weekend in Oxford?")
            pg.evaluate("document.querySelector('.ow-log').scrollTop = document.querySelector('.ow-log').scrollHeight")
            save(pg, "3-events-answer", kind)
            ask(pg, "Where can I see a waterfall without stairs?")
            pg.evaluate("document.querySelector('.ow-log').scrollTop = document.querySelector('.ow-log').scrollHeight")
            save(pg, "4-unknown-answer", kind)
            pg.get_by_role("button", name="Settings").click()
            save(pg, "5-settings", kind)
            pg.get_by_role("button", name="My needs").click()
            save(pg, "6-my-needs", kind)
            pg.get_by_role("button", name="Skip").click()
            c.close()

            c = ctx()
            pg = c.new_page()
            ready(pg, base)
            pg.get_by_role("button", name="Settings").click()
            pg.get_by_role("switch", name="Plain language (shorter sentences)").check()
            pg.keyboard.press("Escape")
            ask(pg, "Does the Art Museum lend wheelchairs?")
            save(pg, "7-plain-language", kind)
            c.close()

            c = ctx()
            pg = c.new_page()
            ready(pg, base)
            pg.get_by_role("button", name="Settings").click()
            pg.get_by_label("Extra large").check(force=True)
            pg.keyboard.press("Escape")
            ask(pg, "Closest accessible restroom near downtown")
            pg.evaluate("document.querySelector('.ow-log').scrollTop = 0")
            save(pg, "8-large-text", kind)
            c.close()

            c = ctx()
            c.add_init_script("delete window.SpeechRecognition; delete window.webkitSpeechRecognition;")
            pg = c.new_page()
            ready(pg, base)
            pg.get_by_role("button", name="Speak").click()
            save(pg, "9-voice-unavailable", kind)
            c.close()

            c = ctx()
            pg = c.new_page()
            pg.route("**/api/health", lambda r: r.fulfill(json={"reachable": True, "model": True, "models": ["qwen2.5:3b"], "vision": True}))
            ev = [{"type": "error", "message": "Something went wrong while looking that up. Please try again."}]
            pg.route("**/api/ask", lambda r: r.fulfill(body="".join("data: " + json.dumps(e) + "\n\n" for e in ev), content_type="text/event-stream"))
            ready(pg, base)
            pg.get_by_role("button", name="Settings").click()
            pg.wait_for_function("!document.querySelector('.ow-settings input[value=local]').disabled")
            pg.get_by_label("Local model").check(force=True)
            pg.keyboard.press("Escape")
            ask(pg, "Does the Art Museum lend wheelchairs?")
            save(pg, "10-error", kind)
            # a photo attached (local model mode), then the photo button hint in guided mode
            from PIL import Image

            buf = io.BytesIO()
            Image.new("RGB", (900, 600), (120, 160, 200)).save(buf, "JPEG")
            pg.set_input_files(".ow input[type=file]", {"name": "sign.jpg", "mimeType": "image/jpeg", "buffer": buf.getvalue()})
            pg.wait_for_selector(".ow-attach img")
            save(pg, "11-photo-attached", kind)
            c.close()

            c = ctx()
            pg = c.new_page()
            ready(pg, base)
            pg.get_by_role("button", name="Photo").click()
            save(pg, "12-photo-needs-local-model", kind)
            c.close()

            c = ctx()
            pg = c.new_page()
            pg.goto(f"{base}/oxford.html?today={TODAY}")
            try:
                pg.wait_for_function("document.querySelectorAll('#list li').length > 0", timeout=60000)
                pg.locator("#ask-open").click()
                pg.wait_for_selector("#ow-panel .ow-tiles button")
                ask(pg, "Closest accessible restroom near uptown Oxford")
                pg.locator("#ow-panel").get_by_role("button", name="Show all on map").click()
                pg.wait_for_timeout(600)
                save(pg, "13-panel-on-map", kind)
            except Exception as e:  # noqa: BLE001
                print("map panel screenshot skipped:", e)
            c.close()
        b.close()
    s.shutdown()


if __name__ == "__main__":
    main()
