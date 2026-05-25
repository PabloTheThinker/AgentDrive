"""Unit tests for the log-injection sanitiser used across structured-log
``extra={}`` payloads.

CodeQL's ``py/log-injection`` rule cleared on the production sites once
``safe_for_log`` was wrapped around every untrusted string. These tests pin
the contract so a future refactor can't silently widen the trust boundary.
"""

from __future__ import annotations

import pytest

from agentdrive.utils.log_safe import safe_for_log


def test_strips_crlf_and_nul_with_question_mark() -> None:
    # CR/LF/NUL stripped via str.replace before urllib.quote runs.
    assert safe_for_log("a\nb\rc") == "a?b?c"
    assert safe_for_log("x\x00y") == "x?y"


def test_other_control_chars_percent_encoded() -> None:
    # Anything not in the str.replace allowlist gets quoted.
    out = safe_for_log("tab\there")
    assert "\t" not in out
    assert "tab" in out and "here" in out


def test_preserves_printable_ascii() -> None:
    assert safe_for_log("hello-world_42") == "hello-world_42"


def test_unicode_is_percent_encoded() -> None:
    # quote() percent-encodes non-ascii — fine for logs; readable in any
    # terminal. The important guarantee is "no raw control bytes survive".
    out = safe_for_log("café 🎯")
    assert "\n" not in out and "\r" not in out
    assert "%" in out  # something got encoded


def test_truncates_with_ellipsis() -> None:
    out = safe_for_log("x" * 500, max_len=20)
    assert len(out) == 20
    assert out.endswith("…")


def test_none_renders_as_marker() -> None:
    assert safe_for_log(None) == "<None>"


def test_coerces_non_string_values() -> None:
    assert safe_for_log(42) == "42"
    assert safe_for_log({"k": "v"}) == "{'k': 'v'}"


@pytest.mark.parametrize(
    "attack",
    [
        "evil\nINFO admin login ok",
        "evil\r\nset-cookie: pwned",
        "evil\x1b[31mred ANSI",
    ],
)
def test_forge_attempts_collapse_to_safe_inline_value(attack: str) -> None:
    out = safe_for_log(attack)
    assert "\n" not in out
    assert "\r" not in out
    assert "\x1b" not in out
