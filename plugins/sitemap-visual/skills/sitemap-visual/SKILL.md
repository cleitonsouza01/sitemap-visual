---
name: sitemap-visual
description: Turn a storefront's sitemap.xml into an interactive "<Business> on Google" map, a Claude Design canvas showing every page Google can find (products with photos, categories, delivery towns, business pages, every language) with a live Google-style result card for each one. Use when asked to show a business how many SEO or Google pages it has, visualize a sitemap, or make the sitemap map / SEO map for a business.
---

# Sitemap visual

One interactive canvas per business, built ONLY from what its live site
publishes: the sitemap, each page's real title and description, its photos and
prices. Never use an AI image model for this. Generated images invent things
(duplicate places, products the business doesn't sell), and real data is the
whole point of the map.

Paths below: `S=<this skill's folder>/scripts`, `W=<a scratch folder>/<business-slug>`.
Needs Python 3 with Pillow (`pip install pillow`) and Node.js.

## 1. Find the site

You need the base URL whose `/sitemap.xml` lists the business's pages.

- The business has its own domain: `--base https://www.example.com`.
- The business lives on a shared host where one sitemap lists many businesses
  (e.g. `https://store.example.com/<lang>/<slug>/...`): `--base https://store.example.com --slug <slug>`.

The map understands this URL shape (other paths still show, as business pages):

| Path | Shown as |
|---|---|
| `/` | Home, in the center |
| `/menu` | Menu hub |
| `/menu/<category>` | Category page |
| `/menu/<category>/<item>` | Item page, with its photo and price |
| `/delivery` | Delivery hub |
| `/delivery/<town>` | Delivery town page |
| anything else | Business page (about, contact, catering, policies…) |

An optional language prefix (`/es/…`, `/pt/…`) marks a translation of the same
page. Unprefixed URLs belong to the first language in `--langs` (default `en,es,pt`).

`--noun`: what the items are. Restaurants → `Dish`; shops, florists, bookstores →
`Product`; otherwise `Item`.

## 2. Collect (2–6 min; slow on purpose)

```bash
python3 $S/build_data.py --base <base> [--slug <slug>] [--langs en,es,pt] --out $W
```

Run it in the background for big catalogs. It fetches every page in every
language with a delay and retries (many storefronts answer bursts with 429/5xx;
those are rate limits, not broken pages), packs every item photo into ONE sheet
(`sprite.jpg`) and saves the site icon (`icon.png`).

Read the printed manifest: `pages`, `total` (= pages × languages), `counts`,
`languages`, `default`, `missing_photo`, `missing_price`. Stop and tell the user
if it warns about pages missing a language or prints `gave up on` lines.
Re-running is safe.

## 3. Create the canvas, upload two files

1. Create a canvas from the **Design** Artifact type: `Artifact` with
   `action: "quickstart", intent: "design"` gives the type link; then publish
   with that `type_url`, `title: "<Business> on Google"`,
   `auto_open: "after_first_write"`. Keep the new canvas `url`.
2. Look at `$W/icon.png` (Read it). It must be the business's own icon, not the
   hosting platform's. If it isn't, skip it (the card then shows the initial).
3. ONE upload call: `asset: true`, `url: <canvas>`,
   `file_paths: [$W/sprite.jpg, $W/icon.png]` → **sprite url**, **icon url**.
   No `sprite.jpg` exists when the business has no item photos.

## 4. Render, check, publish

```bash
python3 $S/render.py --work $W --sprite-url <sprite url> --icon-url <icon url> \
  --noun <Dish|Product|Item> --eyebrow "<Business> · <City, ST> · <a true fact>"
node $S/check.js $W/design/project/Main.dc.html
```

- Eyebrow: city and a fact taken from the business's OWN home-page title or
  description (manifest `home_title`, e.g. "since 1999"). Never invent claims.
- `--default`: the page the card opens on. The collector picks a delivery town,
  else an item with a photo.
- `check.js` runs the map's logic outside the canvas. It must end with `OK`, and
  `big` must equal the manifest `total` (and `pages` for one language). If it
  fails, fix the template, not the output.

Publish with `url` = the canvas, `root` = `$W/design`,
`file_path` = `$W/design/project/canvas.json`,
`files` = `{"project/Main.dc.html": "project/Main.dc.html"}`.
The page data is built into the artboard; nothing else is uploaded.

## 5. Hand over

Give the link. Canvases are private: the user must share it from the canvas's
Share menu before anyone else can open it. It is laid out for a laptop or
projector (1440×940), not a phone. Report what the collector found missing
(`missing_price`, `missing_photo`, pages that only answered after retries):
those are real gaps on the site. Do not screenshot or re-open the canvas to
check it unless the user asks.

A site whose sitemap has only a handful of pages makes an unconvincing map; say
so instead of publishing one.

## What the map shows

`template/Main.dc.html`, with one config object (`CFG`) injected by `render.py`:

- Rings: home in the center → menu and delivery hubs and business pages →
  category pages → items (photos) and delivery towns on the outer ring. Every
  dot is a sitemap page. Items whose category has no page connect straight to
  the menu hub.
- Dot size adapts to the page count. Towns get extra room when there are many
  items, and a label is dropped only when its text would overlap another one.
- Language chips (`All N` + each language) multiply the big counter.
  One-language sites hide them.
- Group chips highlight items, towns, menu sections or business pages.
- Hover or tap a dot → a Google-style card with that page's real title,
  description, URL, photo and price, in the chosen language.

Change the look (gradient, colors, the bottom brand pill) in the template, never
per business.
