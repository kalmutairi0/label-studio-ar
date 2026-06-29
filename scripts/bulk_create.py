#!/usr/bin/env python3
"""
Bulk-create Label Studio projects for a folder of court-case JSON files.

Each case JSON looks like:

  {
    "case_id":     "2026-001",
    "title":       "...",                  # optional, falls back to case_id
    "description": "...",                  # optional
    "audio_file":  "case_001.wav",         # path relative to the cases folder
    "participants": {
      "judges":      [...names...],
      "assistants":  [...],
      "plaintiffs":  [...],
      "defendants":  [...],
      "lawyers":     [...],
      "witnesses":   [...]
    }
  }

Roles that don't apply to a case can be omitted or left as an empty array;
the corresponding <Choices> block is skipped in the generated label config.

Usage:
    export LS_URL=http://localhost:8090
    export LS_TOKEN=<your token from Account & Settings -> Access Token>
    python3 bulk_create.py ./cases
"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
from pathlib import Path

import requests


ROLES = [
    ("judges",     "قاضي",         "judge_name"),
    ("assistants", "مساعد",        "assistant_name"),
    ("plaintiffs", "المدعي",       "plaintiff_name"),
    ("defendants", "المدعى عليه",  "defendant_name"),
    ("lawyers",    "محامي",        "lawyer_name"),
    ("witnesses",  "شاهد",         "witness_name"),
]


def render_label_config(case: dict) -> str:
    parts = case.get("participants") or {}

    labels_xml = "\n".join(
        f'    <Label value="{label}"/>' for _, label, _ in ROLES
    )

    choice_blocks: list[str] = []
    for role_key, label, name_attr in ROLES:
        names = parts.get(role_key) or []
        if not names:
            continue
        choices_xml = "\n".join(f'      <Choice value="{n}"/>' for n in names)
        choice_blocks.append(
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
    choices_section = "\n".join(choice_blocks)

    return (
        '<View>\n'
        '  <Audio name="audio" value="$audio"/>\n'
        '  <Labels name="speaker" toName="audio">\n'
        f'{labels_xml}\n'
        '  </Labels>\n'
        f'{choices_section}\n'
        '  <TextArea\n'
        '    name="text"\n'
        '    toName="audio"\n'
        '    perRegion="true"\n'
        '    editable="true"\n'
        '    rows="3"\n'
        '    displayMode="region-list"\n'
        '  />\n'
        '</View>\n'
    )


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


def main(folder_arg: str) -> int:
    base_url = os.environ.get("LS_URL", "http://localhost:8090").rstrip("/")
    token = os.environ.get("LS_TOKEN")
    if not token:
        sys.stderr.write(
            "LS_TOKEN env var required (Label Studio -> Account & Settings -> Access Token)\n"
        )
        return 2

    folder = Path(folder_arg).resolve()
    if not folder.is_dir():
        sys.stderr.write(f"not a directory: {folder}\n")
        return 2

    # JWT (personal access token) has two dots; legacy DRF token is 40 hex chars.
    scheme = "Bearer" if token.count(".") == 2 else "Token"
    session = requests.Session()
    session.headers["Authorization"] = f"{scheme} {token}"

    json_files = sorted(folder.glob("*.json"))
    print(f"found {len(json_files)} case JSON files in {folder}")

    created: list[tuple[str, int]] = []
    failed: list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []

    for jf in json_files:
        try:
            case = json.loads(jf.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failed.append((jf.name, f"invalid JSON: {exc}"))
            print(f"  FAIL {jf.name}: invalid JSON")
            continue

        title = case.get("title") or case.get("case_id") or jf.stem
        description = case.get("description", "") or ""
        audio_rel = case.get("audio_file") or f"{jf.stem}.wav"
        audio_path = (folder / audio_rel).resolve()

        if not audio_path.exists():
            skipped.append((jf.name, f"audio not found: {audio_path}"))
            print(f"  SKIP {jf.name}: audio not found at {audio_path}")
            continue

        try:
            config = render_label_config(case)
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
        print(f"  OK   {jf.name} -> project {pid}")

    print(
        f"\ndone: created={len(created)} skipped={len(skipped)} failed={len(failed)} "
        f"total={len(json_files)}"
    )
    if failed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "./cases"))
