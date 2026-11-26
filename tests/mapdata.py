"""The place data of a published map page, whichever app wrote it (the new map app or the legacy page)."""

import json


def page_data(html: str) -> dict:
    if "window.__MAPDATA=" in html:
        raw = html.split("window.__MAPDATA=", 1)[1]
        return json.JSONDecoder().raw_decode(raw.replace("\\u003c", "<"))[0]
    raw = html.split("const DATA = ", 1)[1].split(", RATINGS = ", 1)[0]
    return json.loads(raw.replace("\\u003c", "<"))
