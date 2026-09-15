"""Activation (enable/disable), editing, and export logic.

Ownership rule: this tool may only create, modify, or delete an entry under
CLAUDE_SKILLS_DIR if that exact entry is recorded in managed.json (written
by this tool). Anything already present under ~/.claude/skills that is not
in managed.json is treated as the user's own and is never touched.
"""
from __future__ import annotations

import datetime
import os
import shutil
from pathlib import Path
from typing import Literal

from . import config
from .scanner import Skill, render_frontmatter, sanitize_target_name


class ManagerError(Exception):
    def __init__(self, message: str, code: str = "error"):
        super().__init__(message)
        self.code = code


TargetStatus = Literal["available", "enabled", "enabled_elsewhere", "external"]


def target_status(target_name: str, source_dir: Path, managed: dict) -> TargetStatus:
    target = config.CLAUDE_SKILLS_DIR / target_name
    entry = managed.get(target_name)
    if entry is not None:
        if os.path.realpath(entry["source"]) == os.path.realpath(str(source_dir)):
            return "enabled"
        return "enabled_elsewhere"
    if target.exists() or target.is_symlink():
        return "external"
    return "available"


def enable_skill(skill: Skill, target_name: str | None = None) -> dict:
    config.ensure_dirs()
    managed = config.load_managed()
    name = sanitize_target_name(target_name or skill.name or skill.dir.name)
    status = target_status(name, skill.dir, managed)

    if status == "enabled":
        return {"target_name": name, "kind": managed[name]["kind"], "already": True}
    if status == "enabled_elsewhere":
        raise ManagerError(
            f"'{name}' is already enabled from a different source. Choose a different target name.",
            code="conflict_managed",
        )
    if status == "external":
        raise ManagerError(
            f"~/.claude/skills/{name} already exists and was not created by skill-launcher. "
            "Refusing to overwrite it — choose a different target name.",
            code="conflict_external",
        )

    target = config.CLAUDE_SKILLS_DIR / name
    kind = "symlink"
    try:
        os.symlink(str(skill.dir.resolve()), str(target), target_is_directory=True)
    except OSError:
        kind = "copy"
        shutil.copytree(str(skill.dir), str(target))

    managed[name] = {
        "source": str(skill.dir.resolve()),
        "kind": kind,
        "enabled_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    config.save_managed(managed)
    return {"target_name": name, "kind": kind, "already": False}


def disable_skill(target_name: str) -> None:
    managed = config.load_managed()
    entry = managed.get(target_name)
    if entry is None:
        raise ManagerError(
            f"'{target_name}' is not managed by skill-launcher; refusing to remove it.",
            code="not_managed",
        )
    target = config.CLAUDE_SKILLS_DIR / target_name
    if target.is_symlink() or target.exists():
        if target.is_symlink() or target.is_file():
            target.unlink()
        else:
            shutil.rmtree(target)
    del managed[target_name]
    config.save_managed(managed)


def enabled_map() -> dict:
    """target_name -> managed entry, for cross-referencing scanned skills to enabled state."""
    return config.load_managed()


def find_enabled_target_for(source_dir: Path, managed: dict) -> str | None:
    real = os.path.realpath(str(source_dir))
    for target_name, entry in managed.items():
        if os.path.realpath(entry["source"]) == real:
            return target_name
    return None


def _backup(skill: Skill) -> Path:
    config.ensure_dirs()
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    safe = skill.path.as_posix().strip("/").replace("/", "__")
    backup_path = config.BACKUPS_DIR / f"{ts}__{safe}"
    shutil.copy2(skill.path, backup_path)
    return backup_path


def read_skill_source(skill: Skill) -> dict:
    return {
        "name": skill.frontmatter.get("name", skill.name),
        "description": skill.frontmatter.get("description", skill.description),
        "extra_frontmatter": {k: v for k, v in skill.frontmatter.items() if k not in ("name", "description")},
        "body": skill.body,
        "path": str(skill.path),
    }


def write_skill_source(skill: Skill, name: str, description: str, body: str) -> Path:
    if not skill.path.is_file():
        raise ManagerError("Source SKILL.md no longer exists on disk.", code="missing")

    backup_path = _backup(skill)

    fm = dict(skill.frontmatter)
    fm["name"] = name
    fm["description"] = description
    # Preserve key order preference: name, description, then any extra keys.
    ordered = {"name": fm.pop("name"), "description": fm.pop("description"), **fm}

    new_text = render_frontmatter(ordered) + "\n" + body.lstrip("\n")
    skill.path.write_text(new_text, encoding="utf-8")

    # If this skill is activated via a copy (symlink fallback), refresh the copy
    # so the edit is actually reflected where Claude reads it from.
    managed = config.load_managed()
    target_name = find_enabled_target_for(skill.dir, managed)
    if target_name is not None and managed[target_name]["kind"] == "copy":
        target = config.CLAUDE_SKILLS_DIR / target_name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(str(skill.dir), str(target))

    return backup_path


def export_markdown(skills: list[Skill]) -> str:
    parts = []
    for s in skills:
        parts.append(f"## {s.name}\n\n_{s.description}_\n\n{s.body.strip()}\n")
    return "\n\n---\n\n".join(parts) + "\n"
