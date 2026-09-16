"""Activation, ownership, profiles and diagnostics."""
from __future__ import annotations

from pathlib import Path

import pytest

from skill_launcher import config, manager, scanner
from tests.conftest import write_skill


def skills(source) -> list[scanner.Skill]:
    return scanner.scan_all([source], force=True)


def by_name(source, name) -> scanner.Skill:
    return next(s for s in skills(source) if s.name == name)


# --- enable / disable -------------------------------------------------------


def test_enable_creates_symlink_and_manifest_entry(source):
    skill = by_name(source, "threat-modeling")
    result = manager.enable_skill(skill, config.CLAUDE_SKILLS_DIR)

    link = config.CLAUDE_SKILLS_DIR / "threat-modeling"
    assert result["kind"] == "symlink"
    assert link.is_symlink()
    assert link.resolve() == skill.dir.resolve()
    assert manager.managed_for(config.CLAUDE_SKILLS_DIR)["threat-modeling"]["source"] == str(skill.dir.resolve())


def test_enable_twice_is_idempotent(source):
    skill = by_name(source, "threat-modeling")
    manager.enable_skill(skill, config.CLAUDE_SKILLS_DIR)
    again = manager.enable_skill(skill, config.CLAUDE_SKILLS_DIR)
    assert again["already"] is True


def test_enable_refuses_to_overwrite_a_hand_placed_entry(source):
    hand_placed = config.CLAUDE_SKILLS_DIR / "threat-modeling"
    hand_placed.mkdir()
    (hand_placed / "SKILL.md").write_text("mine", encoding="utf-8")

    with pytest.raises(manager.ManagerError) as exc:
        manager.enable_skill(by_name(source, "threat-modeling"), config.CLAUDE_SKILLS_DIR)

    assert exc.value.code == "conflict_external"
    assert (hand_placed / "SKILL.md").read_text(encoding="utf-8") == "mine"


def test_enable_under_an_alternate_name_avoids_the_conflict(source):
    (config.CLAUDE_SKILLS_DIR / "threat-modeling").mkdir()
    result = manager.enable_skill(by_name(source, "threat-modeling"), config.CLAUDE_SKILLS_DIR, "threat-modeling-2")
    assert result["target_name"] == "threat-modeling-2"
    assert (config.CLAUDE_SKILLS_DIR / "threat-modeling-2").is_symlink()


def test_disable_refuses_entries_it_does_not_own(source):
    hand_placed = config.CLAUDE_SKILLS_DIR / "hand-placed"
    hand_placed.mkdir()

    with pytest.raises(manager.ManagerError) as exc:
        manager.disable_skill("hand-placed", config.CLAUDE_SKILLS_DIR)

    assert exc.value.code == "not_managed"
    assert hand_placed.is_dir()


def test_disable_removes_link_but_not_the_source(source):
    skill = by_name(source, "threat-modeling")
    manager.enable_skill(skill, config.CLAUDE_SKILLS_DIR)
    manager.disable_skill("threat-modeling", config.CLAUDE_SKILLS_DIR)

    assert not (config.CLAUDE_SKILLS_DIR / "threat-modeling").exists()
    assert (skill.dir / "SKILL.md").is_file()
    assert manager.managed_for(config.CLAUDE_SKILLS_DIR) == {}


# --- targets ----------------------------------------------------------------


def test_targets_are_independent(source, tmp_path):
    project = tmp_path / "proj" / ".claude" / "skills"
    project.mkdir(parents=True)
    config.save_targets([{"id": "p1", "path": str(project), "label": "proj"}])
    skill = by_name(source, "threat-modeling")

    manager.enable_skill(skill, manager.resolve_target("p1"))

    assert (project / "threat-modeling").is_symlink()
    assert not (config.CLAUDE_SKILLS_DIR / "threat-modeling").exists()
    assert manager.managed_for(config.CLAUDE_SKILLS_DIR) == {}
    assert "threat-modeling" in manager.managed_for(project)


def test_v1_manifest_is_migrated_to_the_global_target(source):
    config.save_managed({"old-skill": {"source": "/somewhere", "kind": "symlink", "enabled_at": "x"}})
    manifest = manager.load_manifest()
    assert manifest["version"] == 2
    assert "old-skill" in manifest["targets"][str(config.CLAUDE_SKILLS_DIR)]


# --- editing ----------------------------------------------------------------


def test_write_rejects_a_stale_mtime(source):
    skill = by_name(source, "threat-modeling")
    with pytest.raises(manager.ManagerError) as exc:
        manager.write_skill_source(skill, "threat-modeling", "新しい説明文です。", "本文", expected_mtime=1.0)
    assert exc.value.code == "stale"


def test_write_backs_up_and_preserves_extra_frontmatter(source):
    skill_dir = write_skill(Path(source["path"]), "dev/keeper", "keeper")
    (skill_dir / "SKILL.md").write_text(
        "---\nname: keeper\ndescription: 説明文です。十分な長さがあります。\nlicense: MIT\n---\n\n本文\n",
        encoding="utf-8",
    )
    skill = by_name(source, "keeper")

    backup = manager.write_skill_source(skill, "keeper", "新しい説明文です。", "新本文", expected_mtime=skill.mtime)

    assert backup.is_file()
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "license: MIT" in text
    assert "新本文" in text


# --- profiles ---------------------------------------------------------------


def test_apply_profile_switches_the_set_without_touching_foreign_entries(source):
    hand_placed = config.CLAUDE_SKILLS_DIR / "hand-placed"
    hand_placed.mkdir()

    threat = by_name(source, "threat-modeling")
    pytest_suite = by_name(source, "pytest-suite")
    manager.enable_skill(threat, config.CLAUDE_SKILLS_DIR)
    manager.save_profile("only-pytest", [pytest_suite], "default")

    result = manager.apply_profile("only-pytest", skills(source), config.CLAUDE_SKILLS_DIR)

    assert result["enabled"] == ["pytest-suite"]
    assert result["disabled"] == ["threat-modeling"]
    assert hand_placed.is_dir()
    assert set(manager.managed_for(config.CLAUDE_SKILLS_DIR)) == {"pytest-suite"}


def test_apply_profile_reports_missing_members(source):
    manager.save_profile("ghost", [], "default")
    config.save_profiles({"ghost": {"target_id": "default", "skills": ["/nope/gone"]}})

    result = manager.apply_profile("ghost", skills(source), config.CLAUDE_SKILLS_DIR)
    assert len(result["errors"]) == 1


# --- diagnostics ------------------------------------------------------------


def test_diagnose_flags_a_deleted_link_and_repair_restores_it(source):
    skill = by_name(source, "threat-modeling")
    manager.enable_skill(skill, config.CLAUDE_SKILLS_DIR)
    (config.CLAUDE_SKILLS_DIR / "threat-modeling").unlink()

    codes = [f["code"] for f in manager.diagnose(skills(source))]
    assert "link_missing" in codes

    manager.repair(config.CLAUDE_SKILLS_DIR, "threat-modeling", "relink")
    assert (config.CLAUDE_SKILLS_DIR / "threat-modeling").is_symlink()
    assert [f for f in manager.diagnose(skills(source)) if f["level"] != "info"] == []


def test_diagnose_reports_hand_placed_entries_as_info_only(source):
    (config.CLAUDE_SKILLS_DIR / "hand-placed").mkdir()
    findings = manager.diagnose(skills(source))
    assert [f["code"] for f in findings] == ["external"]
    assert findings[0]["level"] == "info"


# --- authoring --------------------------------------------------------------


def test_create_skill_scaffolds_a_valid_file(source):
    path = manager.create_skill(Path(source["path"]), "dev", "My New Skill", "作成テスト用の説明文です。")
    assert path.parent.name == "my-new-skill"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\nname: my-new-skill")


def test_create_skill_refuses_to_clobber(source):
    manager.create_skill(Path(source["path"]), "dev", "dup", "説明文です。")
    with pytest.raises(manager.ManagerError) as exc:
        manager.create_skill(Path(source["path"]), "dev", "dup", "説明文です。")
    assert exc.value.code == "exists"


def test_duplicate_skill_renames_the_copy(source):
    skill = by_name(source, "threat-modeling")
    path = manager.duplicate_skill(skill, "threat-modeling-v2")
    assert "name: threat-modeling-v2" in path.read_text(encoding="utf-8")
    assert (skill.dir / "SKILL.md").is_file()


def test_read_skill_file_stays_inside_the_skill_folder(source):
    skill = by_name(source, "threat-modeling")
    with pytest.raises(manager.ManagerError) as exc:
        manager.read_skill_file(skill, "../../escape.txt")
    assert exc.value.code == "outside"


def test_enable_restores_a_link_that_was_deleted_by_hand(source):
    skill = by_name(source, "threat-modeling")
    manager.enable_skill(skill, config.CLAUDE_SKILLS_DIR)
    (config.CLAUDE_SKILLS_DIR / "threat-modeling").unlink()

    result = manager.enable_skill(skill, config.CLAUDE_SKILLS_DIR)

    assert result["restored"] is True
    assert (config.CLAUDE_SKILLS_DIR / "threat-modeling").is_symlink()
