"""Log-injection sanitiser.

CodeQL's ``py/log-injection`` query specifically recognises
``str.replace`` chains and ``urllib.parse.quote`` as sanitisers — it does
*not* generally trace into arbitrary helper functions. So this module
keeps the sanitiser body to those exact primitives, and we still wrap
every call site so the dataflow is broken at both ends.

Apply :func:`safe_for_log` to every untrusted string before passing it
to ``logger.info(..., extra={})`` or any ``%s`` formatter. The result is
a single-line, length-capped string safe to drop into operator logs.
"""

from __future__ import annotations

from urllib.parse import quote

_DEFAULT_MAX = 200


def safe_for_log(value: object, max_len: int = _DEFAULT_MAX) -> str:
    """Return a single-line printable form of ``value``, safe to log.

    Implementation note: uses ``str.replace`` to strip CR / LF / NUL and
    ``urllib.parse.quote`` to escape everything else dangerous — both
    are CodeQL-recognised sanitisers for ``py/log-injection``. We layer
    them so even if CodeQL only sees one, the alert still clears.
    """
    if value is None:
        return "<None>"
    text = str(value)
    # CodeQL-recognised step 1: explicit CR/LF/NUL strip via str.replace.
    text = text.replace("\r", "?").replace("\n", "?").replace("\x00", "?")
    # CodeQL-recognised step 2: percent-encode anything else that could
    # be interpreted as a control sequence. ``safe`` keeps printable
    # punctuation readable in logs.
    text = quote(text, safe=" -_.,:;/()[]{}@#$%^&*+=<>?!~`'\"\\|")
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text
