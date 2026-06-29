# project/

Self-contained workspace for creating ~500 Label Studio projects in one shot, one project per court case, with a per-case label config and the case's audio uploaded as the single task.

## Folder layout

```
project/
├── cases/                 # drop one JSON per case here
│   ├── 233333364.json
│   ├── 233333365.json
│   └── ...
├── audio/                 # drop the matching audio file here (same stem)
│   ├── 233333364.wav
│   ├── 233333365.mp3
│   └── ...
├── label_template.xml     # the labeling-config template (edit if you want)
├── bulk_create.py         # the script
└── README.md
```

Files in `cases/` and `audio/` are matched by **file stem** (the name without the extension).
`233333364.json` ↔ `233333364.wav` is one case. Supported audio extensions: `.wav .mp3 .m4a .ogg .flac` (the first one that exists wins).

## JSON shape per case

```json
{
  "case_id":     "233333364",
  "title":       "قضية رقم 233333364",
  "description": "",
  "participants": {
    "judges":     ["محمد العلي"],
    "assistants": ["خالد المطيري"],
    "plaintiffs": ["عثمان السالم"],
    "defendants": ["عبدالله الراشد"],
    "lawyers":    ["فيصل الحربي", "نواف العنزي"],
    "witnesses":  ["سعد القحطاني"]
  }
}
```

- `case_id`, `title`, `description` are optional. Defaults: `title` → `case_id` → file stem.
- Any role with no names → omit the key or use `[]`. Its `<Choices>` block won't be emitted.

## Run

1. Boot Label Studio from the repo root:
   ```
   docker compose up
   ```
2. Sign up at <http://localhost:8090>. Open **Account & Settings → Personal Access Token** and copy a token.
3. Install the script's dependency:
   ```
   pip install requests
   ```
4. Drop your JSONs into `project/cases/` and your audio files into `project/audio/` (matched by stem).
5. Run:
   ```
   cd project
   export LS_URL=http://localhost:8090
   export LS_TOKEN=<paste your token>
   python3 bulk_create.py
   ```

Output reports `OK` / `SKIP` (no matching audio) / `FAIL` (API error) per case. Exit code is non-zero if any case failed.

## Editing the template

`label_template.xml` is rendered per case. The only placeholder is `{{CHOICES}}`, which the script replaces with one `<Choices>` block per role that has names in the case JSON. Everything else in the template is shipped as-is — feel free to change the `<TextArea>` rows, add `<Header>`, etc.

If you want to change the speaker role list (add `مترجم`, drop `مساعد`, etc.), edit both:
1. The `<Label value="..."/>` lines inside `label_template.xml`.
2. The `ROLES` table at the top of `bulk_create.py` — each row maps a JSON key to its Arabic label and the choices-block name attribute.

## Auth note (LS 1.23+)

The script auto-detects whether `LS_TOKEN` is a JWT Personal Access Token (3 segments separated by `.`) or a legacy 40-char DRF token, and sends the correct `Bearer` / `Token` scheme. If you see `legacy token authentication has been disabled for this organization`, either use a Personal Access Token instead, or re-enable legacy tokens for your org:

```
docker compose exec app python label_studio/manage.py shell -c \
  "from organizations.models import Organization; o=Organization.objects.first(); o.jwt.legacy_api_tokens_enabled=True; o.jwt.save()"
```
