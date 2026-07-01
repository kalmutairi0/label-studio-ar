# SETUP

End-to-end guide for cloning this repo, resetting Label Studio to a clean slate, and running the bulk project creator — on **macOS / Linux** and **Windows**.

---

## 1. Clone and run

### Prerequisites

- **Git**
- **Docker Desktop** (macOS / Windows) or Docker Engine + Compose (Linux)
- **Python 3.9+** with `pip`

### Clone

```
git clone https://github.com/kalmutairi0/label-studio-ar.git
cd label-studio-ar
```

### Boot Label Studio (Arabized build)

```
docker compose up
```

First boot pulls the upstream Label Studio image and builds the runtime Arabic overlay. Subsequent boots are fast.

Open the UI at <http://localhost:8090>.

- Sign up (first user becomes the org owner).
- Go to **Account & Settings → Personal Access Token → Copy**.
- Save the token somewhere — you need it for the script.

### Stop Label Studio

```
docker compose down
```

Data is preserved in `postgres-data/` and `mydata/`. See section 2 to wipe.

---

## 2. Reset to a clean slate

Projects, users, tasks, annotations all live in the database. Uploaded audio and exports live in `mydata/`. Wiping (or renaming) these folders resets Label Studio to a fresh install on the next boot.

### macOS / Linux

```
cd label-studio-ar
docker compose down
mv postgres-data postgres-data.backup
mv mydata mydata.backup
docker compose up
```

To restore the old state later:

```
docker compose down
rm -rf postgres-data mydata
mv postgres-data.backup postgres-data
mv mydata.backup mydata
docker compose up
```

To wipe permanently (no rollback):

```
docker compose down
sudo rm -rf postgres-data mydata
docker compose up
```

### Windows (PowerShell)

```powershell
cd label-studio-ar
docker compose down
Rename-Item postgres-data postgres-data.backup
Rename-Item mydata mydata.backup
docker compose up
```

To restore:

```powershell
docker compose down
Remove-Item -Recurse -Force postgres-data, mydata
Rename-Item postgres-data.backup postgres-data
Rename-Item mydata.backup mydata
docker compose up
```

To wipe permanently:

```powershell
docker compose down
Remove-Item -Recurse -Force postgres-data, mydata
docker compose up
```

> After any reset you must sign up again in the UI and generate a **new** Personal Access Token — the old one dies with the old database.

---

## 3. Run the bulk project creator

The script lives in `project/bulk_create.py`. It reads case JSONs from `project/cases/`, matches each to an audio file in `project/audio/` by file stem, and creates one Label Studio project per case with the participants wired into the label config.

### Prepare inputs (both OSes)

Drop your files into the two folders. Match by name — everything before the extension must be identical.

```
project/cases/233333364.json     ←→     project/audio/233333364.wav
project/cases/233333365.json     ←→     project/audio/233333365.m4a
```

Supported audio extensions: `.wav .mp3 .m4a .ogg .flac`.

Case JSON shape:

```json
{
  "case_id": "233333364",
  "title": "قضية رقم 233333364 - نزاع تجاري",
  "description": "...",
  "participants": {
    "plaintiffs": ["اسم المدعي"],
    "defendants": ["اسم المدعى عليه"]
  }
}
```

### Run on macOS / Linux

```bash
cd project
pip3 install requests
export LS_URL=http://localhost:8090
export LS_TOKEN=paste-your-personal-access-token-here
python3 bulk_create.py
```

### Run on Windows (PowerShell)

```powershell
cd project
pip install requests
$env:LS_URL = "http://localhost:8090"
$env:LS_TOKEN = "paste-your-personal-access-token-here"
python bulk_create.py
```

### Run on Windows (CMD)

```cmd
cd project
pip install requests
set LS_URL=http://localhost:8090
set LS_TOKEN=paste-your-personal-access-token-here
python bulk_create.py
```

### Expected output

```
found 4 case JSON files in .../project/cases
  OK   233333364.json -> project 1 (audio: 233333364.m4a)
  OK   233333365.json -> project 2 (audio: 233333365.m4a)
  OK   233333366.json -> project 3 (audio: 233333366.m4a)
  OK   233333367.json -> project 4 (audio: 233333367.m4a)

done: created=4 skipped=0 failed=0 total=4
```

`SKIP` = a case JSON has no matching audio file. `FAIL` = the LS API rejected the request (see the printed message).

### Auth notes

The script auto-detects your token type:

- **Personal Access Token (JWT, LS 1.13+)** — recognized by two dots. If the JWT claims `token_type: refresh`, the script exchanges it for a short-lived access token via `POST /api/token/refresh/` and auto-refreshes on any `401` mid-run (so batches of hundreds don't die at the 5-minute access-token expiry).
- **Legacy DRF token (40-char hex, no dots)** — sent as `Authorization: Token <token>`.

If the LS API responds with `legacy token authentication has been disabled for this organization`, use a Personal Access Token instead, or re-enable legacy tokens:

```
docker compose exec app python label_studio/manage.py shell -c \
  "from organizations.models import Organization; o=Organization.objects.first(); o.jwt.legacy_api_tokens_enabled=True; o.jwt.save()"
```

### Common errors

| Message | Fix |
|---|---|
| `ModuleNotFoundError: requests` | `pip install requests` (or `pip3` on mac) |
| `LS_TOKEN env var required` | you forgot the `export` / `set` / `$env:` line |
| `Connection refused` | Label Studio isn't running, or the port in `LS_URL` is wrong |
| `HTTP 401` on every case | wrong token, expired, or wrong scheme — see auth notes |
| `SKIP: no matching audio` | audio file stem doesn't match the JSON file stem |

### Windows-specific gotchas

- `python` not found → install from <https://www.python.org/downloads/> and tick **Add python.exe to PATH** during setup. Fallback: `py -3 bulk_create.py`.
- Docker Desktop must be running before `docker compose up`.
- Paths in the code use `pathlib.Path` — Windows backslashes are handled automatically. Don't hard-code `/` or `\` anywhere in the JSON files.
