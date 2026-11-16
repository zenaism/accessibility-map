"""The "Report a problem" form in a real browser, against a fake Supabase server (tests/ for src/atlas/report_ui.py)."""

import base64
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from playwright.sync_api import sync_playwright

from atlas.report_ui import CSS, JS

HARNESS = (
    """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>harness</title><style>
 :root{--ink:#111827;--muted:#6b7280;--line:#eceef1;--soft:#f6f7f9;--focus:#2563eb;--shadow:0 1px 2px rgba(0,0,0,.1)}
 body{font:15px/1.5 system-ui,sans-serif;margin:16px} [hidden]{display:none!important}
 button{font:inherit;font-size:14px;padding:9px 12px;border-radius:10px;border:1px solid var(--line);background:#fff;cursor:pointer}
 .ghost{border-color:transparent;background:transparent} .primary{background:#111827;color:#fff} svg.i{width:18px;height:18px}
 .vh{position:absolute!important;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}"""
    + CSS
    + """</style></head><body><button id="outside">outside</button><div id="host"></div><p class="rp-row" id="rp-map"></p><script>
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const RATECFG = {url: location.origin, key: 'sb_publishable_test'};
const store = {get(k){try{return localStorage.getItem(k)}catch(e){return null}}, set(k,v){try{localStorage.setItem(k,v)}catch(e){}}};
const DEVICE = '11111111-1111-4111-8111-111111111111';
function apiHeaders(extra = {}){ return Object.assign({apikey: RATECFG.key}, extra); }
const it = {i: 0, p: {link_id: 'test-place', name: 'Test <Museum>', region: 'oxford'}};
"""
    + JS
    + "\ndocument.getElementById('host').append(reportRow(it)); reportShow();</script></body></html>"
)


class Fake:
    """A stand-in for the Supabase REST API: records what the form sends and can be told to fail."""

    def __init__(self):
        self.ping_ok, self.fail, self.received, self.pings, self.deleted = True, [], [], 0, []
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body, ctype="application/json"):
                data = body.encode() if isinstance(body, str) else body
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self._send(200, HARNESS, "text/html")

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(n) or b"{}")
                if self.path.endswith("report_ping"):
                    fake.pings += 1
                    return (
                        self._send(200, '"ok"')
                        if fake.ping_ok
                        else self._send(404, '{"message":"not found"}')
                    )
                if self.path.endswith("submit_problem_report"):
                    if fake.fail:
                        code, msg = fake.fail.pop(0)
                        return self._send(code, json.dumps({"message": msg}))
                    fake.received.append(body)
                    return self._send(200, json.dumps(body["p_report_id"][:8].upper()))
                if self.path.endswith("delete_problem_report"):
                    fake.deleted.append(body)
                    return self._send(200, "true")
                self._send(404, "{}")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()


def photo_bytes(fmt="JPEG", size=(3000, 2000), with_exif=True) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", size, "#dddddd")
    d = ImageDraw.Draw(img)
    for i in range(0, size[0], 120):
        d.rectangle([i, 100, i + 60, size[1] - 100], fill=(i % 255, 90, 160))
    buf = io.BytesIO()
    if fmt == "JPEG" and with_exif:
        exif = Image.Exif()
        exif[271] = "SecretCameraMaker"
        exif[0x8825] = {1: "N", 2: (39.0, 7.0, 0.0), 3: "W", 4: (84.0, 30.0, 0.0)}
        img.save(buf, fmt, exif=exif)
    else:
        img.save(buf, fmt)
    return buf.getvalue()


@pytest.fixture(scope="module")
def pw():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def fake():
    f = Fake()
    yield f
    f.httpd.shutdown()


def page_for(browser, fake, mobile=False):
    ctx = browser.new_context(
        **(
            {"viewport": {"width": 390, "height": 760}, "has_touch": True, "is_mobile": True}
            if mobile
            else {}
        )
    )
    page = ctx.new_page()
    page.goto(fake.url)
    return ctx, page


def open_form(page):
    page.get_by_role("button", name="Report a problem").first.click()
    page.wait_for_selector("dialog[open]")


# ---- the button ------------------------------------------------------------------------------------------------------


def test_button_appears_only_when_the_database_is_ready(pw, fake):
    fake.ping_ok = False
    ctx, page = page_for(pw, fake)
    page.wait_for_timeout(500)
    assert page.locator(
        "[data-report]"
    ).first.is_hidden()  # the SQL has not been run: no button, no broken form
    ctx.close()
    fake.ping_ok = True
    ctx, page = page_for(pw, fake)
    page.wait_for_selector("[data-report]:visible")
    assert "Report a problem" in page.locator("[data-report]").first.inner_text()
    assert page.locator("#rp-map [data-report]").inner_text().strip().startswith("Report a problem")
    ctx.close()


# ---- opening, accessibility, validation ---------------------------------------------------------------------------------


def test_dialog_is_labelled_focused_and_closes_with_escape(pw, fake):
    ctx, page = page_for(pw, fake)
    page.wait_for_selector("[data-report]:visible")
    btn = page.locator("#host [data-report]")
    btn.click()
    page.wait_for_selector("dialog[open]")
    assert page.evaluate("document.activeElement.id") == "rp-title"
    assert page.evaluate("document.querySelector('dialog').getAttribute('aria-labelledby')") == "rp-title"
    assert page.get_by_role("radio").count() == 5
    for label in ("What happened?", "Your email or phone"):
        assert page.get_by_label(label, exact=False).count() >= 1  # every field has a real label
    assert (
        "Test <Museum>" in page.locator(".rp-place").inner_text()
    )  # the place name is shown as text, not as markup
    page.keyboard.press("Escape")
    page.wait_for_selector("dialog", state="detached")
    assert (
        page.evaluate("document.activeElement.className").find("report-btn") >= 0
    )  # focus returns to the button
    ctx.close()


def test_empty_form_explains_what_is_missing_and_sends_nothing(pw, fake):
    ctx, page = page_for(pw, fake)
    page.wait_for_selector("[data-report]:visible")
    open_form(page)
    page.get_by_role("button", name="Send report").click()
    summary = page.locator("#rp-errs")
    assert summary.is_visible() and "Please fix these 2 things" in summary.inner_text()
    assert (
        page.evaluate("document.activeElement.id") == "rp-errs"
    )  # the summary is focused so a screen reader reads it
    assert page.locator("#rp-text").get_attribute("aria-invalid") == "true"
    assert "Choose the kind of problem" in page.locator("#rp-kind-err").inner_text()
    assert fake.received == []
    summary.get_by_role("link", name="Tell us what happened").click()
    assert (
        page.evaluate("document.activeElement.id") == "rp-text"
    )  # the link in the summary jumps to the field
    ctx.close()


def test_targets_are_big_enough(pw, fake):
    ctx, page = page_for(pw, fake, mobile=True)
    page.wait_for_selector("[data-report]:visible")
    open_form(page)
    for sel in ("#rp-send", ".rp-actions button:nth-child(2)", ".rp-opt", ".rp-x", "[data-pick]"):
        h = page.locator(sel).first.bounding_box()["height"]
        assert h >= 44, (sel, h)
    box = page.locator("dialog").bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= 391  # fits the phone screen: no sideways scrolling
    ctx.close()


def test_camera_button_only_on_touch_devices(pw, fake):
    ctx, page = page_for(pw, fake)
    page.wait_for_selector("[data-report]:visible")
    open_form(page)
    assert (
        page.locator("[data-cam]").count() == 0
        and page.get_by_role("button", name="Choose a photo from this device").is_visible()
    )
    ctx.close()
    ctx, page = page_for(pw, fake, mobile=True)
    page.wait_for_selector("[data-report]:visible")
    open_form(page)
    assert (
        page.get_by_role("button", name="Take a photo").is_visible()
        and page.get_by_role("button", name="Choose a photo").is_visible()
    )
    assert page.locator("#rp-cam").get_attribute("capture") == "environment"
    ctx.close()


# ---- sending ----------------------------------------------------------------------------------------------------------


def fill(
    page,
    kind="Blocked or broken",
    text="The ramp at the north door is blocked by a bench.",
    contact="",
):
    page.get_by_text(kind, exact=False).first.click()
    page.get_by_label("What happened?", exact=False).fill(text)
    if contact:
        page.get_by_text("Want a reply?").click()
        page.get_by_label("Your email or phone", exact=False).fill(contact)


def test_report_with_a_photo_is_sent_and_location_data_is_removed(pw, fake):
    ctx, page = page_for(pw, fake)
    page.wait_for_selector("[data-report]:visible")
    open_form(page)
    fill(page, contact="  me@example.org ")
    page.set_input_files(
        "#rp-file", files=[{"name": "ramp.jpg", "mimeType": "image/jpeg", "buffer": photo_bytes()}]
    )
    page.wait_for_selector("#rp-prev img")
    assert "Photo ready" in page.locator("#rp-prev").inner_text()
    assert page.locator("#rp-prev img").get_attribute("alt")
    page.get_by_role("button", name="Send report").click()
    page.wait_for_selector(".rp-ok")
    assert page.locator(".rp-ref").inner_text() == fake.received[0]["p_report_id"][:8].upper()
    assert page.evaluate("document.activeElement.id") == "rp-title"
    sent = fake.received[0]
    assert (
        sent["p_category"] == "blocked_or_broken"
        and sent["p_description"] == "The ramp at the north door is blocked by a bench."
    )
    assert (
        sent["p_link_id"] == "test-place"
        and sent["p_place_name"] == "Test <Museum>"
        and sent["p_region"] == "oxford"
    )
    assert (
        sent["p_contact"] == "me@example.org"
        and sent["p_device_id"] == "11111111-1111-4111-8111-111111111111"
    )
    assert sent["p_website"] == ""
    jpg = base64.b64decode(sent["p_photo_b64"])
    assert jpg[:3] == b"\xff\xd8\xff" and len(jpg) <= 300_000  # a JPEG within the 300 KB the page promises
    assert b"Exif" not in jpg and b"SecretCameraMaker" not in jpg  # the camera data, including GPS, is gone
    from PIL import Image

    assert max(Image.open(io.BytesIO(jpg)).size) <= 1280
    assert page.evaluate("localStorage.getItem('atlas-report-draft-test-place')") in ("", None)
    ctx.close()


def test_report_without_photo_or_contact_works_and_general_reports_have_no_place(pw, fake):
    ctx, page = page_for(pw, fake)
    page.wait_for_selector("[data-report]:visible")
    page.locator("#rp-map [data-report]").click()
    page.wait_for_selector("dialog[open]")
    fill(page, kind="Something else", text="The website is hard to read on my phone.")
    page.get_by_role("button", name="Send report").click()
    page.wait_for_selector(".rp-ok")
    sent = fake.received[0]
    assert (
        sent["p_link_id"] is None
        and sent["p_place_name"] is None
        and sent["p_contact"] is None
        and sent["p_photo_b64"] is None
    )
    ctx.close()


def test_failed_send_keeps_everything_and_a_retry_is_the_same_report(pw, fake):
    fake.fail = [(500, "Too many reports from this device today")]
    ctx, page = page_for(pw, fake)
    page.wait_for_selector("[data-report]:visible")
    open_form(page)
    fill(page)
    page.set_input_files(
        "#rp-file",
        files=[{"name": "p.png", "mimeType": "image/png", "buffer": photo_bytes("PNG", (800, 600))}],
    )
    page.wait_for_selector("#rp-prev img")
    page.get_by_role("button", name="Send report").click()
    page.wait_for_selector("#rp-errs:not([hidden])")
    assert "Too many reports from this device today" in page.locator("#rp-errs").inner_text()
    assert (
        page.locator("#rp-text").input_value().startswith("The ramp")
        and page.locator("#rp-prev img").is_visible()
    )
    assert page.get_by_role("button", name="Send report").is_enabled()
    page.get_by_role("button", name="Send report").click()  # the server recovered
    page.wait_for_selector(".rp-ok")
    assert len(fake.received) == 1 and fake.received[0]["p_photo_b64"]
    ctx.close()


def test_retry_after_a_failure_reuses_the_report_id(pw, fake):
    fake.fail = [(503, "temporarily unavailable")]
    ctx, page = page_for(pw, fake)
    page.wait_for_selector("[data-report]:visible")
    open_form(page)
    fill(page)
    ids = []
    page.on(
        "request",
        lambda r: (
            ids.append(json.loads(r.post_data)["p_report_id"])
            if r.url.endswith("submit_problem_report")
            else None
        ),
    )
    page.get_by_role("button", name="Send report").click()
    page.wait_for_selector("#rp-errs:not([hidden])")
    page.get_by_role("button", name="Send report").click()
    page.wait_for_selector(".rp-ok")
    assert len(ids) == 2 and ids[0] == ids[1]  # the database ignores the second copy if the first had arrived
    ctx.close()


# ---- photos and drafts ------------------------------------------------------------------------------------------------


def test_a_file_that_is_not_a_photo_is_refused_in_words(pw, fake):
    ctx, page = page_for(pw, fake)
    page.wait_for_selector("[data-report]:visible")
    open_form(page)
    page.set_input_files(
        "#rp-file", files=[{"name": "notes.txt", "mimeType": "text/plain", "buffer": b"hello"}]
    )
    page.wait_for_selector("#rp-pmsg.err")
    assert (
        "not a photo" in page.locator("#rp-pmsg").inner_text() and page.locator("#rp-prev img").count() == 0
    )
    ctx.close()


def test_photo_can_be_removed(pw, fake):
    ctx, page = page_for(pw, fake)
    page.wait_for_selector("[data-report]:visible")
    open_form(page)
    page.set_input_files(
        "#rp-file",
        files=[{"name": "p.jpg", "mimeType": "image/jpeg", "buffer": photo_bytes(with_exif=False)}],
    )
    page.wait_for_selector("#rp-prev img")
    page.get_by_role("button", name="Remove photo").click()
    assert (
        page.locator("#rp-prev img").count() == 0 and "Photo removed" in page.locator("#rp-pmsg").inner_text()
    )
    ctx.close()


def test_closing_by_accident_keeps_the_text(pw, fake):
    ctx, page = page_for(pw, fake)
    page.wait_for_selector("[data-report]:visible")
    open_form(page)
    fill(page, text="The elevator button is out of reach.")
    page.keyboard.press("Escape")
    page.wait_for_selector("dialog", state="detached")
    open_form(page)
    assert page.locator("#rp-text").input_value() == "The elevator button is out of reach."
    assert page.get_by_role("radio", name="Blocked or broken", exact=False).is_checked()
    ctx.close()


def test_robot_trap_field_is_hidden_from_people_but_sent(pw, fake):
    ctx, page = page_for(pw, fake)
    page.wait_for_selector("[data-report]:visible")
    open_form(page)
    assert (
        page.locator(".rp-hp").get_attribute("aria-hidden") == "true"
        and page.locator("#rp-web").get_attribute("tabindex") == "-1"
    )
    fill(page)
    page.evaluate("document.getElementById('rp-web').value = 'http://spam.example'")  # what a robot would do
    page.get_by_role("button", name="Send report").click()
    page.wait_for_selector(".rp-ok")
    assert fake.received[0]["p_website"] == "http://spam.example"  # the database function drops it silently
    ctx.close()


def test_privacy_note_is_in_the_form_and_a_sent_report_can_be_deleted(pw, fake):
    ctx, page = page_for(pw, fake)
    page.wait_for_selector("[data-report]:visible")
    open_form(page)
    page.get_by_text("How we use your report").click()
    assert "24 months" in page.locator("details.priv").inner_text()
    fill(page)
    page.get_by_role("button", name="Send report").click()
    page.wait_for_selector(".rp-ok")
    page.get_by_role("button", name="Delete this report").click()
    page.wait_for_selector("text=Your report was deleted.")
    assert fake.deleted == [
        {
            "p_report_id": fake.received[0]["p_report_id"],
            "p_device_id": "11111111-1111-4111-8111-111111111111",
        }
    ]
    assert not page.get_by_role("button", name="Delete this report").is_visible()
    ctx.close()
