#!/usr/bin/env python3
"""Fill the phone Site Tree for one business.

  render_tree.py --work DIR [--eyebrow "Casa Verde · Austin, TX · since 2004"]
                 [--noun Dish|Product|Item] [--config FILE] [--url-order FILE]

Reads DIR/manifest.json, DIR/pages.json, DIR/sprite.jpg and DIR/icon.png (from
build_data.py) and writes:
  DIR/mobile/index.html  a whole page, for Cloudflare Pages or any static host
  DIR/tree-artifact.html the same page without the document shell, for an Artifact

Both are self-contained: the page text, the photo sheet and the icon are inside.

Sections come from pages.json: each /menu/<category> is one, /delivery is one, a
top-level folder with two or more pages under it is one, and everything else
goes under Business pages. --config can rename, reorder and caption them:

  {
    "sections": [{"key": "painting", "name": "Painting services", "item": "Service page"}],
    "sub": "Every service has its own page.",
    "search": "Find a page or service",
    "note": "Every row is a real page on the new site...",
    "noResults": "Try a city or a service.",
    "title": "Casa Verde Site Tree"
  }

Section keys: the category or folder slug, "delivery", or "pages". Listed sections
come first, in that order. --url-order takes any text file of URLs, such as the
site's navigation, and sorts pages inside a section by it.

Site text stays data: it is written into a JSON block and the page only ever
shows it as text. Do not print it into the conversation.
"""
import argparse, base64, json, re, statistics
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent.parent
COLORS = ["#7FD6B0", "#FFA6DA", "#86C8FF", "#FF8A6A", "#F2B441", "#C9B6FF", "#7EE0D6", "#FFC98A"]
SMALL = {"a", "an", "and", "de", "del", "da", "do", "for", "in", "la", "of", "the", "to"}
LNAME = {"en": "English", "es": "Español", "pt": "Português", "fr": "Français", "de": "Deutsch",
         "it": "Italiano", "nl": "Nederlands", "ja": "日本語", "zh": "中文"}
# A title that ends in a place: "... in Orlando, FL", "..., Orlando FL", "..., Orlando".
PLACE = re.compile(r"(?:\s+in\s+|,\s+)(?:[A-Z][\w.'-]*\s*){1,3}(?:,\s*[A-Z]{2}|\s+[A-Z]{2})?$")
ICON_WORDS = [("info", ("about", "story", "team")), ("star", ("review", "testimonial")), ("image", ("gallery", "portfolio", "projects", "photos")),
              ("phone", ("contact", "call")), ("chat", ("feedback", "faq", "help")), ("shield", ("privacy", "terms", "policy", "legal"))]

ap = argparse.ArgumentParser()
ap.add_argument("--work", required=True)
ap.add_argument("--eyebrow")
ap.add_argument("--noun", default="Item")
ap.add_argument("--config")
ap.add_argument("--url-order")
a = ap.parse_args()

work = Path(a.work)
m = json.loads((work / "manifest.json").read_text())
rows = json.loads((work / "pages.json").read_text())
cfg = json.loads(Path(a.config).read_text()) if a.config else {}
langs = m["languages"]
business = m["business"]
brand = business.split()[0].lower()


def title_case(slug):
    words = re.sub(r"-[a-z]{2}$", "", slug).split("-")
    return " ".join(w if i and w in SMALL else w.capitalize() for i, w in enumerate(words))


def sentence(slug):
    text = slug.replace("-", " ")
    return text[:1].upper() + text[1:]


def bare_title(title):
    """The page's own name, without the business after a separator."""
    head = re.split(r"\s+[|·]\s+", title)[0]
    parts = re.split(r"\s+[-–—]\s+", head)
    if len(parts) > 1 and parts[-1].lower().startswith(brand):
        head = head[: head.lower().rfind(parts[-1].lower())].rstrip(" -–—")
    return head.strip()


def safe_url(row, lang):
    url = row[lang][2]
    return url if urlparse(url).scheme in ("http", "https") else f"https://{m['domain']}{row['p']}"


def tree_key(row, folders):
    """-> (section key, is that section's own page) for one pages.json row."""
    parts = [s for s in row["p"].split("/") if s]
    k = row["k"]
    if k == "home":
        return "home", False
    if k in ("cat", "item"):
        return parts[1], k == "cat"
    if k in ("deliveryHub", "town"):
        return "delivery", k == "deliveryHub"
    if k == "page" and parts and parts[0] in folders:
        return parts[0], len(parts) == 1
    return "pages", False


# A top-level folder counts as a section once it holds two pages.
under = {}
for r in rows:
    parts = [s for s in r["p"].split("/") if s]
    if r["k"] == "page" and len(parts) > 1:
        under[parts[0]] = under.get(parts[0], 0) + 1
folders = {k for k, n in under.items() if n >= 2}

groups = {}
for r in rows:
    key, hub = tree_key(r, folders)
    r["_hub"] = hub
    groups.setdefault(key, []).append(r)
home = groups.pop("home", [])

given = {s["key"]: s for s in cfg.get("sections", [])}
unknown = sorted(set(given) - set(groups))
if unknown:
    raise SystemExit(f"--config names sections this site does not have: {unknown}. It has: {sorted(groups)}")
def is_long_tail(key):
    """A big or article-style section reads better after the short service lists."""
    titles = [len(bare_title(r[langs[0]][0])) for r in groups[key] if langs[0] in r]
    return len(groups[key]) > 40 or (bool(titles) and statistics.median(titles) > 40)


rest = sorted(k for k in groups if k not in given and k not in ("delivery", "pages"))
long_tail = [k for k in rest if is_long_tail(k)]
order = [k for k in given] + [k for k in rest if k not in long_tail]
order += [k for k in ("delivery",) if k in groups and k not in given]
order += long_tail + [k for k in ("pages",) if k in groups and k not in given]

rank = {}
if a.url_order:
    found = re.findall(r"https?://[^\s\"'<>)]+", Path(a.url_order).read_text())
    for i, url in enumerate(found):
        rank.setdefault(urlparse(url).path or "/", i)


def sort_key(r):
    path = urlparse(safe_url(r, next(l for l in langs if l in r))).path
    return (not r["_hub"], rank.get(path, 10_000), path)


def labels_for(key, items, lang):
    """Short row names for one section, in one language."""
    plain = [r for r in items if not r["_hub"] and lang in r]
    named = {}
    if key == "delivery":
        for r in plain:
            found = re.search(r"\b(?:in|to|em|en) ([^,|·]+), [A-Z]{2}\b", r[lang][0])
            named[id(r)] = found.group(1).strip() if found else title_case(r["p"].split("/")[-1])
        return named
    if key == "pages":
        for r in plain:
            seg = next((s for s in reversed(r["p"].split("/")) if s), "")
            text = bare_title(r[lang][0])
            named[id(r)] = text if len(text) <= 18 else title_case(seg)
        return named
    names = [bare_title(r[lang][0]) for r in plain]
    # Service pages repeat the city and often the trade. Drop what every row shares, and keep articles whole.
    if names and sum(bool(PLACE.search(n)) for n in names) / len(names) >= .6:
        names = [PLACE.sub("", n).strip() for n in names]
    last = [n.split()[-1] for n in names if len(n.split()) > 1]
    if len(names) >= 4 and last:
        word = max(set(last), key=last.count)
        if last.count(word) / len(names) >= .8:
            names = [re.sub(rf"\s+{re.escape(word)}$", "", n) for n in names]
    return {id(r): n for r, n in zip(plain, names)}


def icon_of(key, row):
    if row["_hub"]:
        return "list"
    if key == "delivery":
        return "pin"
    path = row["p"].lower()
    return next((name for name, words in ICON_WORDS if any(w in path for w in words)), "doc")


sections, pages = [], []
for r in home:
    tx = {l: ["Home", r[l][0], r[l][1], safe_url(r, l)] for l in langs if l in r}
    pages.append({"s": "home", "k": "Home page", "ic": "doc", "tx": tx})

for n, key in enumerate(order):
    items = sorted(groups[key], key=sort_key)
    spec = given.get(key, {})
    hub_row = next((r for r in items if r["_hub"]), None)
    default = "Business pages" if key == "pages" else sentence(key)
    if key == "delivery":
        where = urlparse(safe_url(hub_row, next(l for l in langs if l in hub_row))).path if hub_row else ""
        default = sentence(where.strip("/").split("/")[-1]) if where.strip("/") else "Delivery areas"
    name = spec.get("name") or default
    item_kind = spec.get("item") or {"delivery": "City page", "pages": "Business page"}.get(key, f"{a.noun} page")
    by_lang = {l: labels_for(key, items, l) for l in langs}
    first = [by_lang[langs[0]][id(r)] for r in items if id(r) in by_lang[langs[0]]]
    article = spec.get("article", bool(first) and statistics.median(len(t) for t in first) > 40)
    sections.append({"k": re.sub(r"[^a-z0-9-]", "", key.lower()) or f"s{n}", "name": name, "color": COLORS[n % len(COLORS)], "n": len(items), "article": article})
    for r in items:
        tx = {l: [name if r["_hub"] else by_lang[l][id(r)], r[l][0], r[l][1], safe_url(r, l)] for l in langs if l in r}
        page = {"s": sections[-1]["k"], "k": "Section page" if r["_hub"] else item_kind, "ic": icon_of(key, r), "tx": tx}
        if r["_hub"]:
            page["hub"] = 1
        if r.get("sp") is not None:
            page["sp"] = r["sp"]
        if r.get("$"):
            page["price"], page["cur"] = r["$"], r.get("cur", "USD")
        pages.append(page)


def join(names):
    return names[0] if len(names) < 2 else ", ".join(names[:-1]) + " and " + names[-1]


total = sum(len(p["tx"]) for p in pages)
towns = "delivery" in groups
claims = []
if any(k not in ("delivery", "pages") for k in groups):
    claims.append(f"every {a.noun.lower()}")
if towns:
    claims.append("every city")
every = (" and ".join(claims) + " has its own page.") if claims else ""
every = every[:1].upper() + every[1:]
if len(langs) > 1:
    sub = f"{len(pages)} pages, each one in {join([LNAME.get(l, l) for l in langs])}. {every}".strip()
else:
    sub = every or f"{len(pages)} pages."

title = cfg.get("title") or f"{business} Site Tree"
sprite_file = work / "sprite.jpg"
icon_file = work / "icon.png"
photos = bool(m.get("sprite")) and sprite_file.exists()
data = {
    "business": business,
    "eyebrow": a.eyebrow or f"{business} · {m['domain']}",
    "big": total,
    "lead": f"pages ready for Google that lead to {business}",
    "sub": cfg.get("sub") or sub,
    "search": cfg.get("search") or ("Find a page or city" if towns else "Find a page"),
    "noResults": cfg.get("noResults") or "Try another word from a page title.",
    "note": cfg.get("note") or f"Every row is a real page on {m['domain']}, with the title and description Google reads. Checked {m['checked']}.",
    "langs": langs,
    "spriteCols": m["sprite"]["cols"] if photos else 1,
    "sections": sections,
    "pages": pages,
}
# Site text sits inside a <script>: escape every "<" so it can never open or close a tag.
payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
b64 = lambda f: base64.b64encode(f.read_bytes()).decode()
sprite = f"data:image/jpeg;base64,{b64(sprite_file)}" if photos else ""
icon = f"data:image/png;base64,{b64(icon_file)}" if icon_file.exists() and m.get("icon") else ""
safe_title = title.replace("&", "&amp;").replace("<", "&lt;")

tpl = (HERE / "template" / "Tree.html").read_text()
page = (tpl.replace("__TITLE__", safe_title).replace("__DATA__", payload)
           .replace("__SPRITE__", sprite).replace("__ICON__", icon))
for ph in ("__TITLE__", "__DATA__", "__SPRITE__", "__ICON__"):
    assert ph not in page, f"unfilled placeholder {ph}"
head, body = page.split("<!--BODY-->")
head = head.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', "")
description = f"{total} pages of {business}, mapped for Google.".replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
favicon = f'<link rel="icon" href="{icon}">\n' if icon else ""

out = work / "mobile"
out.mkdir(parents=True, exist_ok=True)
# noindex: the page repeats the site's own titles and descriptions, and should never compete with them.
(out / "index.html").write_text(
    f'<!doctype html>\n<html lang="{langs[0]}">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
    '<meta name="robots" content="noindex">\n<meta name="theme-color" content="#17133F">\n'
    f'<meta name="description" content="{description}">\n{favicon}'
    '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
    'img{max-width:100%}[hidden]{display:none!important}</style>\n'
    f"{head}</head>\n<body>\n{body}</body>\n</html>\n")
(work / "tree-artifact.html").write_text(page.replace("<!--BODY-->\n", ""))
print(f"wrote {out}/index.html and {work}/tree-artifact.html ({title}; {len(pages)} pages x {len(langs)} languages = {total}; "
      f"{len(sections)} sections; {len(page) // 1024} KB)")
