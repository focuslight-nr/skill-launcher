"""Scan registered source roots for SKILL.md files and parse metadata.

Symlinks are never followed while walking (followlinks=False). This is
deliberate: entries this tool itself creates under ~/.claude/skills are
symlinks pointing back into a source tree, so refusing to follow symlinks
prevents a source scan from re-discovering (and duplicating) skills that
were reached through one of our own activation links.
"""
from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)

CATEGORY_ICONS = {
    "web": "\U0001F310",
    "wireless": "\U0001F4F6",
    "auth": "\U0001F511",
    "active-directory": "\U0001F3E2",
    "cloud": "☁️",
    "mobile": "\U0001F4F1",
    "iot": "\U0001F50C",
    "infrastructure": "\U0001F3D7️",
    "exploit-dev": "\U0001F4A5",
    "fuzzing": "\U0001F41B",
    "recon": "\U0001F50D",
    "api": "\U0001F50C",
    "container": "\U0001F433",
    "cicd": "\U0001F504",
    "crypto": "\U0001F510",
    "privesc": "⬆️",
    "post-exploitation": "\U0001F6AA",
    "forensics": "\U0001F9EA",
    "supply-chain": "\U0001F4E6",
    "social-engineering": "\U0001F3AD",
    "network": "\U0001F578️",
    "ai": "\U0001F916",
    "utility": "\U0001F6E0️",
    "uncategorized": "\U0001F4C4",
}
DEFAULT_ICON = "\U0001F4C4"


def icon_for(category: str) -> str:
    return CATEGORY_ICONS.get(category.lower(), DEFAULT_ICON)


def make_id(skill_md_path: Path) -> str:
    raw = str(skill_md_path.resolve())
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def id_to_path(skill_id: str) -> Path:
    padded = skill_id + "=" * (-len(skill_id) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    return Path(raw)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body) for a SKILL.md's raw text."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    block = m.group(1)
    body = text[m.end():]
    try:
        data = yaml.safe_load(block)
        if not isinstance(data, dict):
            data = {}
    except yaml.YAMLError:
        data = {}
    return data, body


def render_frontmatter(fm: dict) -> str:
    dumped = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, default_flow_style=False).strip()
    return f"---\n{dumped}\n---\n"


@dataclass
class Skill:
    id: str
    path: Path
    dir: Path
    name: str
    description: str
    category: str
    source_id: str
    source_label: str
    frontmatter: dict = field(default_factory=dict)
    body: str = ""


def sanitize_target_name(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9._-]+", "-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-.")
    return name or "skill"


def scan_source(source: dict) -> list[Skill]:
    root = Path(source["path"]).expanduser()
    if not root.is_dir():
        return []
    results: list[Skill] = []
    seen_dirs: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Never descend into symlinked directories (see module docstring).
        dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
        skill_md = None
        for fname in filenames:
            if fname.lower() == "skill.md":
                skill_md = fname
                break
        if skill_md is None:
            continue
        skill_dir = Path(dirpath)
        real_dir = str(skill_dir.resolve())
        if real_dir in seen_dirs:
            continue
        seen_dirs.add(real_dir)

        skill_path = skill_dir / skill_md
        try:
            text = skill_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        fm, body = parse_frontmatter(text)
        name = str(fm.get("name") or skill_dir.name)
        description = fm.get("description") or ""
        if isinstance(description, list):
            description = " ".join(str(x) for x in description)
        description = str(description).strip()

        try:
            rel_parts = skill_dir.relative_to(root).parts
        except ValueError:
            rel_parts = (skill_dir.name,)
        if len(rel_parts) >= 2:
            category = rel_parts[0]
        else:
            category = "uncategorized"

        results.append(
            Skill(
                id=make_id(skill_path),
                path=skill_path,
                dir=skill_dir,
                name=name,
                description=description,
                category=category,
                source_id=source["id"],
                source_label=source.get("label") or root.name,
                frontmatter=fm,
                body=body,
            )
        )
    return results


def scan_all(sources: list[dict]) -> list[Skill]:
    out: list[Skill] = []
    for src in sources:
        out.extend(scan_source(src))
    return out
