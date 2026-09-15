"""Config/state paths and persistence helpers.

Everything skill-launcher itself owns lives under ~/.config/skill-launcher/:
  sources.json  - registered skill source roots (folders to scan)
  managed.json  - ownership manifest: which entries under ~/.claude/skills
                  this tool created (name -> {source, kind, enabled_at})
  backups/      - timestamped backups made before every SKILL.md edit

~/.claude/skills itself is never treated as "owned" storage - we only ever
add/remove the specific entries recorded in managed.json there.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(os.environ.get("SKILL_LAUNCHER_CONFIG_DIR", "~/.config/skill-launcher")).expanduser()
SOURCES_FILE = CONFIG_DIR / "sources.json"
MANAGED_FILE = CONFIG_DIR / "managed.json"
BACKUPS_DIR = CONFIG_DIR / "backups"

CLAUDE_SKILLS_DIR = Path(os.environ.get("SKILL_LAUNCHER_TARGET_DIR", "~/.claude/skills")).expanduser()


def ensure_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    CLAUDE_SKILLS_DIR.mkdir(parents=True, exist_ok=True)


def _atomic_write_json(path: Path, data: Any) -> None:
    ensure_dirs()
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def load_sources() -> list[dict]:
    if not SOURCES_FILE.exists():
        return []
    try:
        return json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_sources(sources: list[dict]) -> None:
    _atomic_write_json(SOURCES_FILE, sources)


def load_managed() -> dict:
    if not MANAGED_FILE.exists():
        return {}
    try:
        return json.loads(MANAGED_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_managed(managed: dict) -> None:
    _atomic_write_json(MANAGED_FILE, managed)
