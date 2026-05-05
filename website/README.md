# JobsHunt marketing site (`website/`)

Plain **HTML + CSS** and a small **`main.js`** for “copy command” buttons. No bundler, no framework—upload as-is for maximum speed.

## Files

- `index.html` — page
- `styles.css` — styles
- `main.js` — copy-to-clipboard for build-from-source terminal blocks
- `assets/JobsHunt_Favicon.png` — header mark, favicon, Apple touch icon
- `assets/JobsHunt_Logo.png` — header / nav wordmark in the floating pill
- `robots.txt`, `llms.txt` — crawlers / LLM hints

## Local preview

Open `index.html` in a browser, or serve the folder (so `fetch` isn’t blocked for relative assets if your browser is strict):

```bash
cd website
python3 -m http.server 8080
```

Then visit `http://127.0.0.1:8080/`.

## Deploy (Hostinger + jobshunt.ai)

Upload **the contents of `website/`** (not the parent repo) into the domain’s **document root** so `index.html` is at the site apex.

- **DNS:** At GoDaddy, point nameservers to Hostinger or set **A** records to your Hostinger IP (see hPanel).
- **SSL:** Enable free SSL in Hostinger for `jobshunt.ai`.

The GitHub stars badge loads from `img.shields.io` (small external image).

## Old Vite/React site

Removed. This folder is static only.
