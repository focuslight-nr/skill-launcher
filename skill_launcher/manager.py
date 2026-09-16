"""Activation (enable/disable), editing, profiles, and diagnostics.

Ownership rule: this tool may only create, modify, or delete an entry under
an activation target directory if that exact entry is recorded in
managed.json (written by this tool). Anything already present under
~/.claude/skills that is not in managed.json is treated as the user's own
and is never touched.

Activation targets: skills can be activated globally (~/.claude/skills) or
into a specific project's .claude/skills. The manifest is therefore keyed by
target directory first, then by entry name. Manifests written by older
versions (a flat name -> entry mapping for the global directory only) are
migrated on read.
"""
from __future__ import annotations

import datetime
import os
import shutil
from pathlib import Path
from typing import Literal

from . import config
from .scanner import Skill, render_frontmatter, sanitize_target_name

MANIFEST_VERSION = 2


class ManagerError(Exception):
    def __init__(self, message: str, code: str = "error"):
        super().__init__(message)
        self.code = code


TargetStatus = Literal["available", "enabled", "enabled_elsewhere", "external"]


# --- activation targets -----------------------------------------------------

DEFAULT_TARGET_ID = "default"


def list_targets() -> list[dict]:
    """The global target plus any project targets the user registered."""
    targets = [
        {
            "id": DEFAULT_TARGET_ID,
            "label": "ユーザーグローバル",
            "path": str(config.CLAUDE_SKILLS_DIR),
            "builtin": True,
        }
    ]
    for t in config.load_targets():
        targets.append({**t, "builtin": False})
    for t in targets:
        p = Path(t["path"]).expanduser()
        t["exists"] = p.is_dir()
    return targets


def resolve_target(target_id: str | None) -> Path:
    if not target_id or target_id == DEFAULT_TARGET_ID:
        return config.CLAUDE_SKILLS_DIR
    for t in config.load_targets():
        if t["id"] == target_id:
            return Path(t["path"]).expanduser()
    raise ManagerError(f"unknown activation target: {target_id}", code="unknown_target")


def _target_key(target_dir: Path) -> str:
    return str(Path(target_dir).expanduser())


# --- manifest ---------------------------------------------------------------


def load_manifest() -> dict:
    """Read managed.json, migrating the pre-v2 flat layout if needed."""
    raw = config.load_managed()
    if not raw:
        return {"version": MANIFEST_VERSION, "targets": {}}
    if raw.get("version") == MANIFEST_VERSION and "targets" in raw:
        return raw
    # v1: {name: {source, kind, enabled_at}} for the global target only.
    return {
        "version": MANIFEST_VERSION,
        "targets": {_target_key(config.CLAUDE_SKILLS_DIR): raw},
    }


def save_manifest(manifest: dict) -> None:
    config.save_managed(manifest)


def managed_for(target_dir: Path) -> dict:
    """target_name -> entry, for one activation target."""
    return load_manifest()["targets"].get(_target_key(target_dir), {})


def set_managed_for(target_dir: Path, mapping: dict) -> None:
    manifest = load_manifest()
    key = _target_key(target_dir)
    if mapping:
        manifest["targets"][key] = mapping
    else:
        manifest["targets"].pop(key, None)
    save_manifest(manifest)


def enabled_map(target_dir: Path | None = None) -> dict:
    return managed_for(target_dir or config.CLAUDE_SKILLS_DIR)


# --- enable / disable -------------------------------------------------------


def target_status(target_name: str, source_dir: Path, managed: dict, target_dir: Path) -> TargetStatus:
    target = Path(target_dir) / target_name
    entry = managed.get(target_name)
    if entry is not None:
        if os.path.realpath(entry["source"]) == os.path.realpath(str(source_dir)):
            return "enabled"
        return "enabled_elsewhere"
    if target.exists() or target.is_symlink():
        return "external"
    return "available"


def enable_skill(skill: Skill, target_dir: Path, target_name: str | None = None) -> dict:
    config.ensure_dirs()
    target_dir = Path(target_dir).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)

    managed = managed_for(target_dir)
    name = sanitize_target_name(target_name or skill.name or skill.dir.name)
    status = target_status(name, skill.dir, managed, target_dir)

    if status == "enabled":
        return {"target_name": name, "kind": managed[name]["kind"], "already": True}
    if status == "enabled_elsewhere":
        raise ManagerError(
            f"'{name}' is already enabled from a different source. Choose a different target name.",
            code="conflict_managed",
        )
    if status == "external":
        raise ManagerError(
            f"{target_dir}/{name} already exists and was not created by skill-launcher. "
            "Refusing to overwrite it — choose a different target name.",
            code="conflict_external",
        )

    target = target_dir / name
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
    set_managed_for(target_dir, managed)
    return {"target_name": name, "kind": kind, "already": False}


def disable_skill(target_name: str, target_dir: Path) -> None:
    target_dir = Path(target_dir).expanduser()
    managed = managed_for(target_dir)
    entry = managed.get(target_name)
    if entry is None:
        raise ManagerError(
            f"'{target_name}' is not managed by skill-launcher; refusing to remove it.",
            code="not_managed",
        )
    target = target_dir / target_name
    if target.is_symlink() or target.exists():
        if target.is_symlink() or target.is_file():
            target.unlink()
        else:
            shutil.rmtree(target)
    del managed[target_name]
    set_managed_for(target_dir, managed)


def find_enabled_target_for(source_dir: Path, managed: dict) -> str | None:
    real = os.path.realpath(str(source_dir))
    for target_name, entry in managed.items():
        if os.path.realpath(entry["source"]) == real:
            return target_name
    return None


# --- editing ----------------------------------------------------------------


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
        "mtime": skill.mtime,
        "issues": [i.to_json() for i in skill.issues],
    }


def _refresh_copies(skill: Skill) -> None:
    """Re-sync every copy-mode activation of this skill, across all targets.

    Symlinked activations see edits immediately; copies do not, so they are
    rebuilt here on save.
    """
    manifest = load_manifest()
    for target_key, mapping in manifest["targets"].items():
        target_name = find_enabled_target_for(skill.dir, mapping)
        if target_name is None or mapping[target_name].get("kind") != "copy":
            continue
        target = Path(target_key) / target_name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(str(skill.dir), str(target))


def write_skill_source(
    skill: Skill,
    name: str,
    description: str,
    body: str,
    expected_mtime: float | None = None,
) -> Path:
    """Overwrite a SKILL.md, refusing to clobber edits made since it was read.

    `expected_mtime` is the mtime the client saw when it opened the editor;
    if the file changed in the meantime (another editor, a git pull) the write
    is rejected instead of silently winning.
    """
    if not skill.path.is_file():
        raise ManagerError("Source SKILL.md no longer exists on disk.", code="missing")

    if expected_mtime is not None and abs(skill.mtime - expected_mtime) > 0.001:
        raise ManagerError(
            "このファイルは編集画面を開いたあとに別の場所で変更されています。"
            "再読み込みしてから保存し直してください。",
            code="stale",
        )

    backup_path = _backup(skill)

    fm = dict(skill.frontmatter)
    fm["name"] = name
    fm["description"] = description
    # Preserve key order preference: name, description, then any extra keys.
    ordered = {"name": fm.pop("name"), "description": fm.pop("description"), **fm}

    new_text = render_frontmatter(ordered) + "\n" + body.lstrip("\n")
    skill.path.write_text(new_text, encoding="utf-8")

    _refresh_copies(skill)
    return backup_path


def export_markdown(skills: list[Skill]) -> str:
    parts = []
    for s in skills:
        parts.append(f"## {s.name}\n\n_{s.description}_\n\n{s.body.strip()}\n")
    return "\n\n---\n\n".join(parts) + "\n"


# --- profiles ---------------------------------------------------------------
#
# Every enabled skill costs context permanently (its name + description sit in
# the system prompt), so the sustainable way to use a large skill library is to
# switch sets rather than leave everything on. A profile is a named set of
# source directories plus the target they apply to.


def list_profiles() -> dict:
    return config.load_profiles()


def save_profile(name: str, skills: list[Skill], target_id: str) -> dict:
    name = name.strip()
    if not name:
        raise ManagerError("プロファイル名を入力してください。", code="bad_name")
    profiles = config.load_profiles()
    entry = {
        "target_id": target_id,
        "skills": sorted({str(s.dir.resolve()) for s in skills}),
        "saved_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    profiles[name] = entry
    config.save_profiles(profiles)
    return entry


def delete_profile(name: str) -> None:
    profiles = config.load_profiles()
    if name not in profiles:
        raise ManagerError(f"プロファイル '{name}' がありません。", code="not_found")
    del profiles[name]
    config.save_profiles(profiles)


def apply_profile(name: str, all_skills: list[Skill], target_dir: Path) -> dict:
    """Make the target match the profile exactly: enable what's missing, disable the rest.

    Only entries this tool manages are ever disabled; skills placed by hand in
    the target directory are left alone, as everywhere else.
    """
    profiles = config.load_profiles()
    profile = profiles.get(name)
    if profile is None:
        raise ManagerError(f"プロファイル '{name}' がありません。", code="not_found")

    wanted = {os.path.realpath(p) for p in profile.get("skills", [])}
    by_real = {os.path.realpath(str(s.dir)): s for s in all_skills}

    enabled: list[str] = []
    disabled: list[str] = []
    errors: list[str] = []

    managed = managed_for(target_dir)
    for target_name, entry in list(managed.items()):
        if os.path.realpath(entry["source"]) not in wanted:
            try:
                disable_skill(target_name, target_dir)
                disabled.append(target_name)
            except ManagerError as e:
                errors.append(f"{target_name}: {e}")

    for real in sorted(wanted):
        skill = by_real.get(real)
        if skill is None:
            errors.append(f"{real}: 現在のソースに見つかりません（ソース未登録か移動済み）")
            continue
        try:
            result = enable_skill(skill, target_dir)
            if not result["already"]:
                enabled.append(result["target_name"])
        except ManagerError as e:
            errors.append(f"{skill.name}: {e}")

    return {"profile": name, "enabled": enabled, "disabled": disabled, "errors": errors}


# --- diagnostics ------------------------------------------------------------


def diagnose(all_skills: list[Skill]) -> list[dict]:
    """Find drift between the manifest, the activation targets, and the sources.

    Long-lived installs accumulate broken state: a source repo gets moved, a
    symlink is deleted by hand, a copy-mode activation goes stale. Each finding
    carries the information needed to fix it from the UI.
    """
    findings: list[dict] = []
    manifest = load_manifest()
    known_sources = {os.path.realpath(str(s.dir)) for s in all_skills}

    for target_key, mapping in manifest["targets"].items():
        target_dir = Path(target_key)
        for target_name, entry in sorted(mapping.items()):
            link = target_dir / target_name
            source = Path(entry["source"])
            base = {"target_dir": target_key, "target_name": target_name, "source": str(source)}

            if not link.is_symlink() and not link.exists():
                findings.append({**base, "level": "error", "code": "link_missing",
                                 "message": "有効化したはずのエントリが実際には存在しません（手動削除された可能性）。"})
                continue
            if not source.exists():
                findings.append({**base, "level": "error", "code": "source_missing",
                                 "message": "リンク先のソースフォルダが存在しません。"})
                continue
            if entry.get("kind") == "copy":
                src_md = source / "SKILL.md"
                dst_md = link / "SKILL.md"
                try:
                    if src_md.is_file() and dst_md.is_file() and src_md.stat().st_mtime > dst_md.stat().st_mtime + 1:
                        findings.append({**base, "level": "warn", "code": "copy_stale",
                                         "message": "コピー方式のため、ソース側の更新が反映されていません。"})
                except OSError:
                    pass
            if os.path.realpath(str(source)) not in known_sources:
                findings.append({**base, "level": "info", "code": "source_unregistered",
                                 "message": "有効化中ですが、現在登録中のソースからは見つかりません。"})

        if target_dir.is_dir():
            for child in sorted(target_dir.iterdir()):
                if child.name.startswith(".") or child.name in mapping:
                    continue
                findings.append({
                    "target_dir": target_key, "target_name": child.name, "source": "",
                    "level": "info", "code": "external",
                    "message": "skill-launcher の管理外エントリです（手動配置。変更しません）。",
                })

    return findings


def repair(target_dir: Path, target_name: str, action: str) -> dict:
    """Fix one diagnose() finding. `action` is 'forget' or 'relink'."""
    target_dir = Path(target_dir).expanduser()
    managed = managed_for(target_dir)
    entry = managed.get(target_name)
    if entry is None:
        raise ManagerError(f"'{target_name}' は管理対象ではありません。", code="not_managed")

    if action == "forget":
        del managed[target_name]
        set_managed_for(target_dir, managed)
        return {"target_name": target_name, "action": "forget"}

    if action == "relink":
        source = Path(entry["source"])
        if not source.is_dir():
            raise ManagerError("ソースが存在しないため再リンクできません。", code="source_missing")
        link = target_dir / target_name
        if link.is_symlink() or link.is_file():
            link.unlink()
        elif link.is_dir():
            shutil.rmtree(link)
        kind = "symlink"
        try:
            os.symlink(str(source.resolve()), str(link), target_is_directory=True)
        except OSError:
            kind = "copy"
            shutil.copytree(str(source), str(link))
        managed[target_name] = {**entry, "kind": kind}
        set_managed_for(target_dir, managed)
        return {"target_name": target_name, "action": "relink", "kind": kind}

    raise ManagerError(f"unknown repair action: {action}", code="bad_action")


# --- authoring --------------------------------------------------------------

TEMPLATE_BODY = """## いつ使うか

（このスキルが必要になる場面を書く）

## 手順

1. 
2. 
3. 

## 注意

- 
"""


def create_skill(source_root: Path, category: str, name: str, description: str, body: str | None = None) -> Path:
    """Scaffold a new SKILL.md under <source_root>/<category>/<name>/."""
    name = sanitize_target_name(name)
    category = sanitize_target_name(category) if category.strip() else ""
    root = Path(source_root).expanduser()
    if not root.is_dir():
        raise ManagerError(f"ソースフォルダがありません: {root}", code="missing")

    skill_dir = (root / category / name) if category else (root / name)
    if skill_dir.exists():
        raise ManagerError(f"すでに存在します: {skill_dir}", code="exists")

    skill_dir.mkdir(parents=True)
    text = render_frontmatter({"name": name, "description": description.strip()}) + "\n" + (body or TEMPLATE_BODY)
    (skill_dir / "SKILL.md").write_text(text, encoding="utf-8")
    return skill_dir / "SKILL.md"


def duplicate_skill(skill: Skill, new_name: str) -> Path:
    """Copy a skill folder next to the original under a new name."""
    new_name = sanitize_target_name(new_name)
    dest = skill.dir.parent / new_name
    if dest.exists():
        raise ManagerError(f"すでに存在します: {dest}", code="exists")

    shutil.copytree(str(skill.dir), str(dest), symlinks=True)
    md = dest / "SKILL.md"
    fm = dict(skill.frontmatter)
    fm["name"] = new_name
    ordered = {"name": fm.pop("name"), **fm}
    md.write_text(render_frontmatter(ordered) + "\n" + skill.body.lstrip("\n"), encoding="utf-8")
    return md


# --- skill folder contents --------------------------------------------------

MAX_LISTED_FILES = 200
MAX_INLINE_FILE_BYTES = 256 * 1024


def list_skill_files(skill: Skill) -> list[dict]:
    """Every file shipped with the skill, not just SKILL.md (references/, scripts/, ...)."""
    out: list[dict] = []
    for dirpath, dirnames, filenames in os.walk(skill.dir, followlinks=False):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fname in sorted(filenames):
            if fname.startswith("."):
                continue
            full = Path(dirpath) / fname
            try:
                size = full.stat().st_size
            except OSError:
                continue
            out.append({"rel": str(full.relative_to(skill.dir)), "size": size})
            if len(out) >= MAX_LISTED_FILES:
                return sorted(out, key=lambda f: f["rel"])
    return sorted(out, key=lambda f: f["rel"])


def read_skill_file(skill: Skill, rel: str) -> dict:
    """Read one file from inside a skill folder (text only, size-capped)."""
    target = (skill.dir / rel).resolve()
    root = skill.dir.resolve()
    if root != target and root not in target.parents:
        raise ManagerError("スキルフォルダの外は読み込めません。", code="outside")
    if not target.is_file():
        raise ManagerError(f"ファイルがありません: {rel}", code="missing")

    size = target.stat().st_size
    if size > MAX_INLINE_FILE_BYTES:
        return {"rel": rel, "size": size, "text": None, "reason": "too_large"}
    try:
        return {"rel": rel, "size": size, "text": target.read_text(encoding="utf-8")}
    except UnicodeDecodeError:
        return {"rel": rel, "size": size, "text": None, "reason": "binary"}
