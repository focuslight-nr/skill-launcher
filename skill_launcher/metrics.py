"""Rough token accounting for the always-on context cost of enabled skills.

Claude loads the `name` and `description` of every enabled skill into the
system prompt at all times (the body is only read when the skill fires), so
the number worth showing in the UI is the sum of those two fields across
enabled skills.

estimate_tokens() is a heuristic, not a tokenizer: CJK text tends to land
near one token per character, while Latin text averages around four
characters per token. Good enough to answer "am I spending 200 or 2000
tokens on descriptions?", which is the decision this number supports.
"""
from __future__ import annotations

CJK_RANGES = (
    (0x3000, 0x303F),   # CJK punctuation
    (0x3040, 0x30FF),   # hiragana + katakana
    (0x3400, 0x4DBF),   # CJK ext A
    (0x4E00, 0x9FFF),   # CJK unified
    (0xF900, 0xFAFF),   # CJK compatibility
    (0xFF00, 0xFFEF),   # full-width forms
)


def _is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in CJK_RANGES)


def estimate_tokens(text: str) -> int:
    """Approximate token count for `text` (CJK ~1 tok/char, other ~1 tok/4 chars)."""
    if not text:
        return 0
    cjk = sum(1 for ch in text if _is_cjk(ch))
    other = len(text) - cjk
    return int(round(cjk * 0.9 + other / 4))
