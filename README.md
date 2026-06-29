# label-studio-ar

Arabic (RTL) localization overlay for [Label Studio](https://github.com/HumanSignal/label-studio).

This repo does **not** fork or modify Label Studio's source. It runs the official Docker image and mounts a small client-side script (`arabic.js`) over it at startup, which walks the DOM, replaces English text from a 894-entry dictionary, and applies RTL. The architecture survives upstream version bumps with minimal maintenance.

Tested against `heartexlabs/label-studio:1.23.0`.

## Run

```
git clone https://github.com/kalmutairi0/label-studio-ar.git
cd label-studio-ar
docker compose up
```

Open <http://localhost:8090>. On first launch, sign up to create the admin account (a fresh local Postgres is provisioned via `docker-compose.yml`).

To stop:
```
docker compose down
```

## What's in here

| File | Role |
|---|---|
| `label_studio/core/static/js/arabic.js` | The injection layer — translator, RTL CSS, MutationObserver |
| `ls-arabic-dict-OFFICIAL.js` | Source-of-truth dictionary (894 entries, 867 translated, 27 brand/code/key skips) |
| `label_studio/templates/base.html` | Vendored from upstream 1.23.0, patched to load `arabic.js` |
| `label_studio/templates/simple.html` | Same — used by login/signup/4xx pages |
| `docker-compose.yml` | Vendored from upstream, image tag pinned to `1.23.0` |
| `docker-compose.override.yml` | Bind-mounts the four files above into the running image; remaps ports to 8090/8091 |

Nothing else is needed. Docker pulls the image; the overlay is applied at container start.

## Bulk-creating projects

`project/` is a self-contained workspace for creating one Label Studio project per court case, complete with a per-case label config and the case audio uploaded as a task.

```
project/
├── cases/                 # one JSON per case
├── audio/                 # matching audio file (same stem)
├── label_template.xml
├── bulk_create.py
└── README.md
```

Drop your JSONs and audio files in (matched by file stem — `233333364.json` ↔ `233333364.wav`), set `LS_TOKEN`, run `python3 bulk_create.py`. Full instructions in [`project/README.md`](project/README.md).

## How translation works

1. Django serves `base.html` (or `simple.html`) which includes one `<script>` tag pointing to `/static/js/arabic.js`.
2. nginx serves `arabic.js` from `core/static_build/js/` (mounted via the override).
3. On load, `arabic.js` sets `<html dir="rtl" lang="ar">`, injects an RTL stylesheet, walks `document.body` for text nodes, swaps known English strings for Arabic from `dict`.
4. A `MutationObserver` translates dynamic content as React re-renders.
5. The annotation canvas (image/audio/video/richtext) is reset to LTR via targeted selectors so labeling content is not flipped. RTL on labeled text itself belongs in the project's labeling config, not here.

## Catching missed strings

Set the debug flag in DevTools, use the app, then dump:

```js
localStorage.LS_AR_DEBUG = '1'; location.reload();
// later:
copy(__ls_ar_dump(2));  // copies frequency-sorted misses to clipboard
```

PRs that add to `ls-arabic-dict-OFFICIAL.js` are welcome. Run the bundled merge script (or hand-edit + sync into `arabic.js`'s embedded `dict` block) and bump the `?v=` cache buster in both templates.

## Pinning a different Label Studio version

Change the tag in `docker-compose.yml` and `docker-compose.override.yml` (search/replace `1.23.0`). On a major bump, watch for:

- New text strings not yet in the dictionary — run the debug logger and add them.
- Canvas container class drift — `arabic.js` resets `.video-canvas`, `.audio-tag`, `.richtext`, `.image-progress`, `[class*="ImageView"]`, `[class*="AudioUltra"]`, `[class*="VideoCanvas"]`, `[class*="RichText"]`, `[class*="Wave"]` plus the legacy `.lsf-*` selectors. If a future version renames containers, inspect DevTools and extend the list in `arabic.js`'s `rtl()` function.
- `base.html` / `simple.html` structure changes — re-vendor and re-apply the one-line `<script>` injection.

## Skipped strings

The 27 dictionary entries marked `// skip` are intentional:

- **Brands / proper nouns**: Amazon S3, Azure Blob Storage, Google Cloud Storage, Redis Storage, Label Studio, Label Studio Enterprise, Labelstudio, Slack, GitHub.
- **Audio DSP proper nouns**: Blackman, Hamming, Hann (window functions); Inferno, Magma, Plasma, Viridis (colormaps); Mel.
- **Keyboard key names**: Enter, Shift, Escape, Backspace — kept in Latin so hotkey hints remain grokkable.
- **Code fixtures and extractor artifacts**: `Math.abs(a - b)`, `Math.abs(x1 - x2)`, `Promise`, `There`.
- **Hotkey-hint templates** (`Save: [shift+enter]`, `Cancel skip: []`, etc.) — keys contain bracket placeholders that translating would mangle.

## License

Apache License 2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE). Label Studio itself is also Apache 2.0; this overlay does not relicense it.
