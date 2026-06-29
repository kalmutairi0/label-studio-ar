# scripts/

## `bulk_create.py`

Creates one Label Studio project per JSON file in a folder, generating each project's labeling config from the case participants and uploading the matching local audio file.

### Input

A folder of `.json` files, one per case. Each audio file sits next to its JSON. Schema:

```json
{
  "case_id": "2026-001",
  "title": "قضية رقم 1 لسنة 2026",
  "description": "نزاع تجاري - جلسة افتتاحية",
  "audio_file": "case_001.wav",
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

- Any role with no names → omit the key or use `[]`. Its `<Choices>` block is skipped.
- `audio_file` is relative to the cases folder.
- `title` and `description` are optional. Title defaults to `case_id`, then to the JSON file stem.

A working sample lives in `../cases-example/case_001.json`.

### Run

1. Boot Label Studio (`docker compose up` in the repo root).
2. Sign up at <http://localhost:8090>. Open **Account & Settings → Access Token**, copy the token.
3. Install Python deps:
   ```
   pip install -r scripts/requirements.txt
   ```
4. Drop your JSON files (and matching audio files) into a folder, e.g. `./cases`.
5. Run:
   ```
   export LS_URL=http://localhost:8090
   export LS_TOKEN=<paste your token>
   python3 scripts/bulk_create.py ./cases
   ```

Output lists `OK`, `SKIP` (missing audio), and `FAIL` (API error) per file. Exit code is non-zero if any case failed.

### Generated label config (per case)

The speaker `<Labels>` block is fixed across cases (Judge / Assistant / Plaintiff / Defendant / Lawyer / Witness). For each role that has names in the case JSON, a `<Choices>` block is appended that lists only those names and only appears when the user has selected an audio region tagged with that role. Roles with no names produce no choices block.
