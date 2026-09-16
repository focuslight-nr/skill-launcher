"""Test fixtures.

Every test runs against a throwaway config dir and a throwaway activation
target: the point of most of these tests is that the tool does not touch
anything it did not create, so they must never see the developer's real
~/.claude/skills.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skill_launcher import config, scanner  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    cfg = tmp_path / "config"
    target = tmp_path / "claude-skills"
    cfg.mkdir()
    target.mkdir()

    monkeypatch.setattr(config, "CONFIG_DIR", cfg)
    monkeypatch.setattr(config, "SOURCES_FILE", cfg / "sources.json")
    monkeypatch.setattr(config, "MANAGED_FILE", cfg / "managed.json")
    monkeypatch.setattr(config, "BACKUPS_DIR", cfg / "backups")
    monkeypatch.setattr(config, "PROFILES_FILE", cfg / "profiles.json")
    monkeypatch.setattr(config, "TARGETS_FILE", cfg / "targets.json")
    monkeypatch.setattr(config, "ICONS_FILE", cfg / "icons.json")
    monkeypatch.setattr(config, "CLAUDE_SKILLS_DIR", target)
    scanner.invalidate_cache()
    yield
    scanner.invalidate_cache()


def write_skill(
    root: Path,
    rel: str,
    name: str,
    description: str = "十分な長さの説明文をここに書きます。",
    body: str = "本文",
) -> Path:
    skill_dir = root / rel
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n", encoding="utf-8"
    )
    return skill_dir


@pytest.fixture
def source(tmp_path):
    """A registered source root holding two skills."""
    root = tmp_path / "skills"
    write_skill(root, "security/threat-modeling", "threat-modeling")
    write_skill(root, "dev/pytest-suite", "pytest-suite")
    src = {"id": "src1", "path": str(root), "label": "test-source"}
    config.save_sources([src])
    return src
