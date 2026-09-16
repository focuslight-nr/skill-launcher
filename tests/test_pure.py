"""Unit tests for the pure helpers: sanitising, parsing, linting, estimating."""
from __future__ import annotations

import pytest

from skill_launcher.lint import lint_skill
from skill_launcher.metrics import estimate_tokens
from skill_launcher.scanner import parse_frontmatter, sanitize_target_name
from skill_launcher.security import hostname_of


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Hello World!", "hello-world"),      # disallowed runs collapse, trailing "-" stripped
        ("  My-Skill  ", "my-skill"),
        ("A.B-C_D", "a.b-c_d"),               # dot, hyphen and underscore are all allowed
        ("___test___", "___test___"),         # underscore is allowed, and strip() does not touch it
        ("Test--Name", "test-name"),
        ("-Start-End-", "start-end"),
        (".Start.End.", "start.end"),
        ("some  thing", "some-thing"),
        ("...---...", "skill"),               # strips down to empty -> fallback
        ("!!!", "skill"),
        ("", "skill"),
    ],
)
def test_sanitize_target_name(raw, expected):
    assert sanitize_target_name(raw) == expected


def test_parse_frontmatter_splits_metadata_from_body():
    fm, body = parse_frontmatter("---\nname: test\ndescription: hello\n---\nBody content")
    assert fm == {"name": "test", "description": "hello"}
    assert body == "Body content"


def test_parse_frontmatter_handles_crlf():
    fm, body = parse_frontmatter("---\r\nname: test\r\n---\r\nBody")
    assert fm == {"name": "test"}
    assert body == "Body"


def test_parse_frontmatter_without_a_block_returns_the_text_unchanged():
    text = "# Just a heading\n\nno frontmatter here"
    assert parse_frontmatter(text) == ({}, text)


@pytest.mark.parametrize("block", ["- a\n- b", "just a string", "name: [unclosed"])
def test_parse_frontmatter_falls_back_to_empty_dict(block):
    fm, body = parse_frontmatter(f"---\n{block}\n---\nBody")
    assert fm == {}
    assert body == "Body"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("", 0),
        ("abcd", 1),            # 4/4
        ("Hello World!", 3),    # 12/4
        ("日本語", 3),           # round(3 * 0.9) = round(2.7)
        ("ab日本語cd", 4),       # round(2.7 + 1.0) = round(3.7)
        ("Hello あいう", 4),     # round(6/4 + 2.7) = round(4.2)
    ],
)
def test_estimate_tokens(text, expected):
    assert estimate_tokens(text) == expected


def test_estimate_tokens_grows_with_length():
    short = "これは短い説明文です。"
    long = short * 5
    assert estimate_tokens(long) > estimate_tokens(short)


def test_estimate_tokens_weighs_cjk_more_than_ascii():
    assert estimate_tokens("あいうえお") > estimate_tokens("abcde")


@pytest.mark.parametrize(
    "header, expected",
    [
        ("127.0.0.1:8877", "127.0.0.1"),
        ("localhost:3000", "localhost"),
        ("localhost", "localhost"),
        ("[::1]:8877", "[::1]"),
        ("[::1]", "[::1]"),
        ("[::1", "[::1"),          # unterminated bracket is returned as-is
        ("  example.com  ", "example.com"),
    ],
)
def test_hostname_of(header, expected):
    assert hostname_of(header) == expected


VALID_FM = {"name": "my-skill", "description": "このスキルの使いどころを説明する十分な長さの文章。"}


def test_lint_accepts_a_well_formed_skill():
    assert lint_skill(VALID_FM, "本文があります", "my-skill") == []


def test_lint_reports_missing_frontmatter_once():
    issues = lint_skill({}, "本文", "my-skill")
    assert [i.level for i in issues] == ["error"]


@pytest.mark.parametrize(
    "frontmatter, dir_name, expected_levels",
    [
        ({**VALID_FM, "name": ""}, "my-skill", ["error"]),                   # missing name
        ({**VALID_FM, "name": "a" * 65}, "a" * 65, ["error"]),               # name too long
        ({**VALID_FM, "name": "My_Skill"}, "My_Skill", ["warn"]),            # not kebab-case
        ({**VALID_FM}, "other-folder", ["warn"]),                            # name != folder
        ({"name": "my-skill"}, "my-skill", ["error"]),                       # missing description
        ({**VALID_FM, "description": "短い"}, "my-skill", ["warn"]),          # description too short
        ({**VALID_FM, "description": "あ" * 1025}, "my-skill", ["error"]),    # description too long
        ({**VALID_FM, "surprise": 1}, "my-skill", ["info"]),                 # unknown key
    ],
)
def test_lint_rules_fire_independently(frontmatter, dir_name, expected_levels):
    issues = lint_skill(frontmatter, "本文があります", dir_name)
    assert [i.level for i in issues] == expected_levels


def test_lint_flags_an_empty_body_as_a_warning():
    issues = lint_skill(VALID_FM, "   \n  ", "my-skill")
    assert [i.level for i in issues] == ["warn"]
