#!/usr/bin/env python3
"""
Bulk-create Label Studio projects from a folder of court-case JSONs.

Layout (everything sits next to this script):

    project/
    ├── cases/
    │   ├── 233333364.json
    │   ├── 233333365.json
    │   └── ...
    ├── audio/
    │   ├── 233333364.wav
    │   ├── 233333365.mp3
    │   └── ...
    ├── label_template.xml
    └── bulk_create.py            <-- run this

Each case JSON is matched to an audio file by base name (file stem).
E.g. `cases/233333364.json` pairs with `audio/233333364.{wav|mp3|m4a|ogg|flac}`.

Each case JSON looks like:

    {
      "case_id":     "233333364",            # optional, defaults to file stem
      "title":       "...",                  # optional, defaults to case_id
      "description": "...",                  # optional
      "participants": {
        "judges":     [...],
        "assistants": [...],
        "plaintiffs": [...],
        "defendants": [...],
        "lawyers":    [...],
        "witnesses":  [...]
      }
    }

Roles with no names are skipped (no <Choices> block produced).

Usage:
    export LS_URL=http://localhost:8090
    export LS_TOKEN=<your token>
    python3 bulk_create.py
"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
from pathlib import Path

import requests


ROLES = [
    # JSON key,       label value (Arabic),  <Choices> name attribute
    ("plaintiffs",    "المدعي",              "plaintiff_name"),
    ("defendants",    "المدعى عليه",         "defendant_name"),
]

AUDIO_EXTENSIONS = (".wav", ".mp3", ".m4a", ".ogg", ".flac")

HERE = Path(__file__).resolve().parent
CASES_DIR = HERE / "cases"
AUDIO_DIR = HERE / "audio"
TEMPLATE = HERE / "label_template.xml"


def render_choices_block(case: dict) -> str:
    parts = case.get("participants") or {}
    blocks: list[str] = []
    for role_key, label, name_attr in ROLES:
        names = parts.get(role_key) or []
        if not names:
            continue
        choices_xml = "\n".join(f'      <Choice value="{n}"/>' for n in names)
        blocks.append(
            f'  <Choices\n'
            f'    name="{name_attr}"\n'
            f'    toName="audio"\n'
            f'    perRegion="true"\n'
            f'    choice="single-radio"\n'
            f'    visibleWhen="region-selected"\n'
            f'    whenTagName="speaker"\n'
            f'    whenLabelValue="{label}">\n'
            f'{choices_xml}\n'
            f'  </Choices>'
        )
    return "\n".join(blocks)


def render_label_config(case: dict, template: str) -> str:
    return template.replace("{{CHOICES}}", render_choices_block(case))


def find_audio_for(stem: str) -> Path | None:
    for ext in AUDIO_EXTENSIONS:
        candidate = AUDIO_DIR / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    return None


def create_project(session: requests.Session, base_url: str,
                   title: str, description: str, label_config: str) -> int:
    r = session.post(
        f"{base_url}/api/projects/",
        json={"title": title, "description": description, "label_config": label_config},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["id"]


def import_audio(session: requests.Session, base_url: str,
                 project_id: int, audio_path: Path) -> dict:
    mime = mimetypes.guess_type(str(audio_path))[0] or "application/octet-stream"
    with audio_path.open("rb") as fh:
        r = session.post(
            f"{base_url}/api/projects/{project_id}/import",
            files={"file": (audio_path.name, fh, mime)},
            timeout=300,
        )
    r.raise_for_status()
    return r.json()


def main() -> int:
    base_url = os.environ.get("LS_URL", "http://localhost:8090").rstrip("/")
    token = os.environ.get("LS_TOKEN")
    if not token:
        sys.stderr.write(
            "LS_TOKEN env var required "
            "(Label Studio -> Account & Settings -> Personal Access Token)\n"
        )
        return 2

    if not TEMPLATE.exists():
        sys.stderr.write(f"missing {TEMPLATE}\n")
        return 2
    template = TEMPLATE.read_text(encoding="utf-8")

    if not CASES_DIR.is_dir():
        sys.stderr.write(f"missing folder: {CASES_DIR}\n")
        return 2
    if not AUDIO_DIR.is_dir():
        sys.stderr.write(f"missing folder: {AUDIO_DIR}\n")
        return 2

    # JWT (personal access token) has two dots; legacy DRF token is 40 hex chars.
    scheme = "Bearer" if token.count(".") == 2 else "Token"
    session = requests.Session()
    session.headers["Authorization"] = f"{scheme} {token}"

    json_files = sorted(CASES_DIR.glob("*.json"))
    print(f"found {len(json_files)} case JSON files in {CASES_DIR}")

    created: list[tuple[str, int]] = []
    skipped: list[tuple[str, str]] = []
    failed: list[tuple[str, str]] = []

    for jf in json_files:
        stem = jf.stem
        audio_path = find_audio_for(stem)
        if audio_path is None:
            skipped.append((jf.name, f"no audio in {AUDIO_DIR} for stem '{stem}'"))
            print(f"  SKIP {jf.name}: no matching audio file for stem '{stem}'")
            continue

        try:
            case = json.loads(jf.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failed.append((jf.name, f"invalid JSON: {exc}"))
            print(f"  FAIL {jf.name}: invalid JSON ({exc})")
            continue

        title = case.get("title") or case.get("case_id") or stem
        description = case.get("description", "") or ""

        try:
            config = render_label_config(case, template)
            pid = create_project(session, base_url, title, description, config)
            import_audio(session, base_url, pid, audio_path)
        except requests.HTTPError as exc:
            body = exc.response.text[:300] if exc.response is not None else str(exc)
            failed.append((jf.name, f"{exc} :: {body}"))
            print(f"  FAIL {jf.name}: {exc} :: {body}")
            continue
        except requests.RequestException as exc:
            failed.append((jf.name, str(exc)))
            print(f"  FAIL {jf.name}: {exc}")
            continue

        created.append((jf.name, pid))
        print(f"  OK   {jf.name} -> project {pid} (audio: {audio_path.name})")

    print(
        f"\ndone: created={len(created)} skipped={len(skipped)} failed={len(failed)} "
        f"total={len(json_files)}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
