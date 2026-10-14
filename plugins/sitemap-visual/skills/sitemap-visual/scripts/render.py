#!/usr/bin/env python3
"""Fill the SEO map template for one business.

  render.py --work DIR --sprite-url /_blob/... [--icon-url /_blob/...]
            [--eyebrow "Casa Verde · Austin, TX · since 2004"]
            [--noun Dish|Product|Item] [--default /delivery/some-town]

Reads DIR/manifest.json and DIR/pages.json (from build_data.py) and writes
DIR/design/project/canvas.json + DIR/design/project/Main.dc.html, ready to
publish to a Design canvas with root DIR/design. The page data is built into
the artboard, so the only uploads are the photo sheet and the icon.
"""
import argparse, json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

ap = argparse.ArgumentParser()
ap.add_argument("--work", required=True)
ap.add_argument("--sprite-url", default="")
ap.add_argument("--icon-url", default="")
ap.add_argument("--eyebrow")
ap.add_argument("--noun", default="Dish")
ap.add_argument("--default")
a = ap.parse_args()

work = Path(a.work)
m = json.loads((work / "manifest.json").read_text())
pages = json.loads((work / "pages.json").read_text())
if m.get("sprite") and not a.sprite_url:
    raise SystemExit("This business has item photos: pass --sprite-url (upload sprite.jpg first).")

title = f"{m['business']} on Google"
cfg = {
    "business": m["business"],
    "eyebrow": a.eyebrow or f"{m['business']} · {m['domain']}",
    "domain": m["domain"],
    "checked": m["checked"],
    "iconUrl": a.icon_url,
    "sprite": {"cols": m["sprite"]["cols"]} if m.get("sprite") and a.sprite_url else None,
    "langs": m["languages"],
    "itemNoun": a.noun,
    "def": a.default or m["default"],
    "pages": pages,
}
# Site text goes inside a <script>: escape every "<" so it can never open or close a tag.
cfg_js = json.dumps(cfg, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")

tpl = (HERE / "template" / "Main.dc.html").read_text()
html = (tpl.replace("__TITLE__", title.replace("&", "&amp;").replace("<", "&lt;"))
           .replace("__SPRITE_URL__", a.sprite_url or "none")
           .replace("__CONFIG__", cfg_js))
for ph in ("__TITLE__", "__SPRITE_URL__", "__CONFIG__"):
    assert ph not in html, f"unfilled placeholder {ph}"

proj = work / "design" / "project"
proj.mkdir(parents=True, exist_ok=True)
(proj / "Main.dc.html").write_text(html)
(proj / "canvas.json").write_text(json.dumps({
    "v": 3,
    "createdOnFiles": {"v": 1, "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
    "title": title,
    "launch": {"view": "focused", "file": "Main.dc.html"},
    "pages": [],
    "boards": {"Main.dc.html": {"x": 0, "y": 0, "w": 1440, "h": 940, "title": title, "is_interactive": True}},
    "order": ["Main.dc.html"],
    "notes": {},
    "designSystems": [],
}))
print(f"wrote {proj}/canvas.json and Main.dc.html "
      f"({title}; {m['total']} pages; default {cfg['def']}; {len(html) // 1024} KB)")
