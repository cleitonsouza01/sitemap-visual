#!/usr/bin/env python3
"""Collect a storefront's Google-findable pages for the SEO map design.

  build_data.py --base https://www.example.com [--slug myslug] [--langs en,es,pt] --out DIR

Reads <base>/sitemap.xml, fetches every page in every language (slowly: the
storefront answers bursts with 500s), and writes:
  DIR/pages.json     one row per page: kind, [title, description, url] per language,
                     price, and "sp" = the item's cell in the photo sheet
  DIR/sprite.jpg     every item photo, square-cropped, in one sheet (SPRITE_CELL px cells)
  DIR/icon.png       the site's own icon, 96px
  DIR/manifest.json  counts, languages, default page, sheet geometry

Only the standard library and Pillow are used.
"""
import argparse, html, io, json, re, sys, time, urllib.error, urllib.request
from datetime import date
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (sitemap-visual)"}
LANG_CODES = {"en", "es", "pt"}  # override with --langs
DEFAULT_LANG = "en"  # language of URLs without a prefix: the first of --langs
SPRITE_CELL = 96
SPRITE_COLS = 16


def fetch(url, binary=False, tries=4):
    """GET with backoff; the storefront rate-limits bursts and reports it as 5xx."""
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
                body = r.read()
                return body if binary else body.decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last = e
        except Exception as e:  # network hiccup
            last = e
        time.sleep(3 * (attempt + 1))
    print(f"  ! gave up on {url}: {last}", file=sys.stderr)
    return None


def meta(h, prop):
    m = re.search(r'<meta (?:property|name)="%s" content="([^"]*)"' % re.escape(prop), h)
    return html.unescape(m.group(1)) if m else None


def split_url(url, base, slug):
    """-> (lang, canonical path) for a sitemap URL."""
    path = url[len(base):] if url.startswith(base) else re.sub(r"^https?://[^/]+", "", url)
    segs = [s for s in path.split("/") if s]
    lang = DEFAULT_LANG
    if segs and segs[0] in LANG_CODES:
        lang, segs = segs[0], segs[1:]
    if slug and segs and segs[0] == slug:
        segs = segs[1:]
    return lang, "/" + "/".join(segs)


def kind_of(p):
    parts = [s for s in p.split("/") if s]
    if not parts:
        return "home"
    if parts[0] == "menu":
        return ["menuHub", "cat", "item"][min(len(parts), 3) - 1]
    if parts[0] == "delivery":
        return "deliveryHub" if len(parts) == 1 else "town"
    return "page"


def square(data, size):
    """Center-crop to a square and resize: one sprite cell."""
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("RGB")
    s = min(im.size)
    im = im.crop(((im.width - s) // 2, (im.height - s) // 2, (im.width + s) // 2, (im.height + s) // 2))
    return im.resize((size, size), Image.LANCZOS)


def collect(a):
    from PIL import Image
    global LANG_CODES, DEFAULT_LANG
    LANG_CODES = set(a.langs.split(","))
    DEFAULT_LANG = a.langs.split(",")[0]
    base = a.base.rstrip("/")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cells = []
    xml = fetch(base + "/sitemap.xml")
    if not xml:
        sys.exit("No sitemap at " + base + "/sitemap.xml")
    urls = [html.unescape(u) for u in re.findall(r"<loc>([^<]+)</loc>", xml)]
    if a.slug:  # platform host: its sitemap lists every merchant
        urls = [u for u in urls if re.search(r"/%s(/|$)" % re.escape(a.slug), u)]
    pages, langs = {}, []
    for u in urls:
        lang, p = split_url(u, base, a.slug)
        pages.setdefault(p, {})[lang] = u
        if lang not in langs:
            langs.append(lang)
    order = a.langs.split(",")
    langs.sort(key=lambda l: order.index(l) if l in order else len(order))
    print(f"{len(urls)} sitemap URLs -> {len(pages)} pages x {len(langs)} languages {langs}")

    rows, home_html = [], None
    for i, p in enumerate(sorted(pages), 1):
        row = {"p": p, "k": kind_of(p)}
        for lang in langs:
            u = pages[p].get(lang)
            if not u:
                continue
            h = fetch(u)
            time.sleep(a.delay)
            if not h:
                continue
            if p == "/" and lang == langs[0]:
                home_html = h
            t = re.search(r"<title>(.*?)</title>", h, re.S)
            d = (meta(h, "description") or "").replace("…", "").strip()
            if len(d) > 150:
                d = d[:150].rsplit(" ", 1)[0] + "…"
            row[lang] = [html.unescape(t.group(1)).strip() if t else p, d, u]
            if row["k"] == "item" and "sp" not in row and "photo_tried" not in row:
                row["photo_tried"] = True
                price = re.search(r'"price":"?([0-9.]+)', h)
                cur = re.search(r'"priceCurrency":"([A-Z]{3})"', h)
                if price:
                    row["$"] = price.group(1)
                    row["cur"] = cur.group(1) if cur else "USD"
                og = meta(h, "og:image")
                if og:
                    data = fetch(og + ".w400.webp", binary=True) or fetch(og, binary=True)
                    if data:
                        try:
                            cells.append(square(data, SPRITE_CELL))
                            row["sp"] = len(cells) - 1
                        except Exception as e:
                            print(f"  ! photo for {p}: {e}", file=sys.stderr)
        row.pop("photo_tried", None)
        if not any(l in row for l in langs):
            print(f"  ! skipped {p}: no language loaded", file=sys.stderr)
            continue
        rows.append(row)
        print(f"  [{i}/{len(pages)}] {p}")

    name = "Business"
    icon_file = None
    if home_html:
        name = meta(home_html, "og:site_name") or html.unescape(
            re.search(r"<title>(.*?)</title>", home_html, re.S).group(1)).split("|")[-1].strip()
        m = re.search(r'<link rel="(?:icon|apple-touch-icon)" href="([^"]+)"', home_html)
        if m:
            data = fetch(html.unescape(m.group(1)), binary=True)
            if data:
                try:
                    im = Image.open(io.BytesIO(data)).convert("RGBA")
                    im.thumbnail((96, 96))
                    im.save(out / "icon.png", "PNG")
                    icon_file = "icon.png"
                except Exception as e:
                    print(f"  ! icon: {e}", file=sys.stderr)

    sheet = None
    if cells:
        cols = min(SPRITE_COLS, len(cells))
        sheet_rows = (len(cells) + cols - 1) // cols
        img = Image.new("RGB", (cols * SPRITE_CELL, sheet_rows * SPRITE_CELL), (20, 53, 41))
        for i, c in enumerate(cells):
            img.paste(c, ((i % cols) * SPRITE_CELL, (i // cols) * SPRITE_CELL))
        img.save(out / "sprite.jpg", "JPEG", quality=78, optimize=True)
        sheet = {"file": "sprite.jpg", "cols": cols, "rows": sheet_rows, "cell": SPRITE_CELL, "photos": len(cells)}

    kinds = [r["k"] for r in rows]
    default = next((r["p"] for r in rows if r["k"] == "town"), None) or \
        next((r["p"] for r in rows if r["k"] == "item" and "sp" in r), None) or "/"
    manifest = {
        "business": name,
        "domain": re.sub(r"^https?://", "", base),
        "languages": langs,
        "pages": len(rows),
        "total": sum(sum(1 for l in langs if l in r) for r in rows),
        "counts": {k: kinds.count(k) for k in sorted(set(kinds))},
        "default": default,
        "checked": date.today().strftime("%-d %b %Y"),
        "icon": icon_file,
        "sprite": sheet,
        "missing_photo": [r["p"] for r in rows if r["k"] == "item" and "sp" not in r],
        "missing_price": [r["p"] for r in rows if r["k"] == "item" and "$" not in r],
        "home_title": rows[0].get(langs[0], [""])[0] if rows and rows[0]["p"] == "/" else "",
    }
    (out / "pages.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    missing = [r["p"] for r in rows if any(l not in r for l in langs)]
    print(json.dumps(manifest, ensure_ascii=False, indent=1))
    if missing:
        print(f"WARNING: {len(missing)} pages missing a language: {missing[:8]}", file=sys.stderr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--slug")
    ap.add_argument("--out", required=True)
    ap.add_argument("--langs", default="en,es,pt", help="language codes used as the first URL segment; the first is the default language")
    ap.add_argument("--delay", type=float, default=0.8)
    collect(ap.parse_args())
