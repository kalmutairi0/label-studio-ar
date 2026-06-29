# label-studio-ar

Arabic (RTL) localization overlay for [Label Studio](https://github.com/HumanSignal/label-studio), plus a bulk-create workflow for spinning up hundreds of audio-transcription projects from local JSON files.

This repo does **not** fork or modify Label Studio. It runs the official Docker image and mounts a small client-side script (`arabic.js`) over it at startup. The script walks the DOM, replaces English text from a built-in dictionary, and applies RTL. The architecture survives upstream version bumps with minimal maintenance.

Tested against `heartexlabs/label-studio:1.23.0`.

---

## Layout

```
label-studio-ar/
├── docker-compose.yml             # vendored upstream compose, image pinned
├── docker-compose.override.yml    # overlay bind-mounts; remaps ports to 8090/8091
├── label_studio/                  # the i18n overlay
│   ├── core/static/js/arabic.js   #   injection layer (translator + RTL + observer)
│   └── templates/
│       ├── base.html              #   patched upstream template (main app)
│       └── simple.html            #   patched upstream template (login/4xx)
├── ls-arabic-dict-OFFICIAL.js     # dictionary source-of-truth (894 entries)
├── project/                       # bulk-create workflow
│   ├── cases/                     #   drop one JSON per case here
│   ├── audio/                     #   drop matching audio files here (same stem)
│   ├── bulk_create.py             #   the script
│   ├── label_template.xml         #   per-project XML template
│   ├── README.md                  #   project-specific README
│   ├── WORKFLOW.txt               #   full step-by-step (read this first)
│   └── FIX_TEMPLATE_PROMPT.txt    #   paste into ChatGPT if template changes break the script
├── LICENSE
├── NOTICE
└── README.md                      # you are here
```

---

## Two workflows

### 1. Run translated Label Studio

```
git clone https://github.com/kalmutairi0/label-studio-ar.git
cd label-studio-ar
docker compose up
```

Open <http://localhost:8090>. On first launch, sign up to create the admin account (a fresh local Postgres is provisioned via Docker). Stop with `docker compose down`.

### 2. Bulk-create projects (one per court case)

Boot Label Studio (step 1), drop your JSONs into `project/cases/`, drop matching audio files into `project/audio/`, then:

```
pip install requests
cd project
export LS_TOKEN=<your Personal Access Token>
python3 bulk_create.py
```

Full step-by-step including how to get the token, how to handle template changes offline, and a troubleshooting section — see [`project/WORKFLOW.txt`](project/WORKFLOW.txt). Schema and template details in [`project/README.md`](project/README.md).

---

## How the translation works

1. Django serves `base.html` (or `simple.html`) which includes one `<script>` tag pointing to `/static/js/arabic.js`.
2. nginx serves `arabic.js` from `core/static_build/js/` (mounted via the override).
3. On load, `arabic.js` sets `<html dir="rtl" lang="ar">`, injects an RTL stylesheet, walks `document.body` for text nodes, swaps known English strings for Arabic from its embedded `dict`.
4. A `MutationObserver` translates dynamic content as React re-renders.
5. The annotation canvas (image/audio/video/richtext) is reset to LTR via targeted selectors so labeling content is not flipped. RTL on labeled text itself belongs in the project's labeling config, not here.

## Catching missed strings

```js
localStorage.LS_AR_DEBUG = '1'; location.reload();
// later in DevTools console:
copy(__ls_ar_dump(2));   // copies frequency-sorted misses to clipboard
```

Add the strings to `ls-arabic-dict-OFFICIAL.js` and sync into `arabic.js`'s embedded `dict` block, then bump the `?v=` cache buster in both templates.

## Pinning a different Label Studio version

Change the tag in `docker-compose.yml` and `docker-compose.override.yml` (search/replace `1.23.0`). On a major bump watch for:

- New text strings not yet in the dictionary — run the debug logger.
- Canvas container class drift — `arabic.js` resets `.video-canvas`, `.audio-tag`, `.richtext`, `.image-progress`, `[class*="ImageView"]`, `[class*="AudioUltra"]`, `[class*="VideoCanvas"]`, `[class*="RichText"]`, `[class*="Wave"]`, plus the legacy `.lsf-*` selectors. Inspect DevTools on a new version and extend the list in `arabic.js`'s `rtl()` function.
- `base.html` / `simple.html` structure changes — re-vendor and re-apply the one-line `<script>` injection.

## Skipped dictionary strings (27)

Intentional non-translations:

- **Brands / proper nouns**: Amazon S3, Azure Blob Storage, Google Cloud Storage, Redis Storage, Label Studio, Label Studio Enterprise, Slack, GitHub.
- **Audio DSP proper nouns**: Blackman, Hamming, Hann (window functions); Inferno, Magma, Plasma, Viridis (colormaps); Mel.
- **Keyboard key names**: Enter, Shift, Escape, Backspace — kept in Latin so hotkey hints remain grokkable.
- **Code fixtures and extractor artifacts**: `Math.abs(a - b)`, `Math.abs(x1 - x2)`, `Promise`, `There`.
- **Hotkey-hint templates** (`Save: [shift+enter]`, `Cancel skip: []`, etc.) — bracket placeholders that translating would mangle.

## License

Apache License 2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE). Label Studio itself is also Apache 2.0; this overlay does not relicense it.
