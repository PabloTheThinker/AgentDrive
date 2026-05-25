"""Regression tests for the open-redirect guard in web/app.py._redirect.

CodeQL's "URL redirection from remote source" flagged the helper because
some call sites build the path from form input. The fix forces every
non-local path to collapse to ``/`` — this file pins that behavior so a
future refactor can't silently re-introduce the open-redirect.
"""

from __future__ import annotations

import pytest

from agentdrive.web.app import _is_local_path, _redirect


@pytest.mark.parametrize(
    "path",
    [
        "/dashboard",
        "/dna?agent=foo",
        "/peers?error=bad-name",
        "/",
    ],
)
def test_local_paths_pass_through(path: str) -> None:
    resp = _redirect(path)
    assert resp.headers["location"] == path


@pytest.mark.parametrize(
    "path",
    [
        "https://evil.example.com",
        "//evil.example.com",
        "/\\evil.example.com",
        "javascript:alert(1)",
        "ftp://evil/path",
        "",
        "no-leading-slash",
        "/with\r\nheader: injection",
    ],
)
def test_external_or_malformed_paths_collapse_to_root(path: str) -> None:
    resp = _redirect(path)
    assert resp.headers["location"] == "/"


def test_is_local_path_accepts_local() -> None:
    assert _is_local_path("/dashboard") is True


def test_is_local_path_rejects_protocol_relative() -> None:
    assert _is_local_path("//evil.com") is False


def test_is_local_path_rejects_absolute_url() -> None:
    assert _is_local_path("https://evil.com") is False


def test_is_local_path_rejects_crlf_injection() -> None:
    assert _is_local_path("/a\r\nb") is False
    assert _is_local_path("/a\nb") is False
