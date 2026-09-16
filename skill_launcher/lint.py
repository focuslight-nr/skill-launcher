"""Frontmatter checks for SKILL.md files.

Most "my skill never fires" problems come from the frontmatter rather than
the body: no description, a name that does not match the folder Claude
looks the skill up by, or a description so long it gets rejected. These
checks run on every scan so the launcher can warn before you enable a skill.

Levels:
  error - the skill is likely to be rejected or ignored outright
  warn  - it will probably load, but something is off
  info  - stylistic / worth a look
"""
from __future__ import annotations

import re
from dataclasses import dataclass

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Limits documented for Agent Skills frontmatter.
MAX_NAME_LEN = 64
MAX_DESCRIPTION_LEN = 1024

# Keys commonly seen in SKILL.md frontmatter, plus the optional ones this
# launcher reads itself (category / tags / icon). Anything else is reported as
# info only - the set of recognised keys grows over time and we would rather
# not cry wolf about a key that is simply newer than this list.
KNOWN_KEYS = {
    "name",
    "description",
    "license",
    "allowed-tools",
    "metadata",
    "version",
    "category",
    "tags",
    "icon",
}


@dataclass
class Issue:
    level: str
    message: str

    def to_json(self) -> dict:
        return {"level": self.level, "message": self.message}


def lint_skill(frontmatter: dict, body: str, dir_name: str) -> list[Issue]:
    issues: list[Issue] = []

    if not frontmatter:
        issues.append(Issue("error", "YAMLフロントマター（--- で囲まれたブロック）がありません。"))
        return issues

    name = str(frontmatter.get("name") or "").strip()
    description = str(frontmatter.get("description") or "").strip()

    if not name:
        issues.append(Issue("error", "frontmatter に name がありません。"))
    else:
        if len(name) > MAX_NAME_LEN:
            issues.append(Issue("error", f"name が長すぎます（{len(name)} 文字 / 上限 {MAX_NAME_LEN}）。"))
        if not NAME_RE.match(name):
            issues.append(Issue("warn", "name は英小文字・数字・ハイフンのみ（例: my-skill）が推奨です。"))
        if name != dir_name:
            issues.append(Issue("warn", f"name「{name}」がフォルダ名「{dir_name}」と一致しません。"))

    if not description:
        issues.append(Issue("error", "description がありません。Claude はこれを見て起動判断をします。"))
    else:
        if len(description) > MAX_DESCRIPTION_LEN:
            issues.append(
                Issue("error", f"description が長すぎます（{len(description)} 文字 / 上限 {MAX_DESCRIPTION_LEN}）。")
            )
        elif len(description) < 20:
            issues.append(Issue("warn", "description が短すぎます。何をするか＋いつ使うかを書くと起動精度が上がります。"))

    if not body.strip():
        issues.append(Issue("warn", "本文が空です。手順や参照情報が無いとスキルとして機能しません。"))

    unknown = sorted(k for k in frontmatter if k not in KNOWN_KEYS)
    if unknown:
        issues.append(Issue("info", "見慣れない frontmatter キー: " + ", ".join(unknown)))

    return issues
