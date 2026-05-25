"""Log-injection sanitiser.

CodeQL ``py/log-injection`` flags any structured-log call whose value derives
from external input (HTTP form fields, manifest contents, peer-supplied ids,
…) because CR/LF in those values can forge log entries or smuggle ANSI
escape sequences past a tail-following operator.

:func:`safe_for_log` strips control characters and caps the length. Apply it
to every untrusted string before passing it to ``logger.info(..., extra={})``
or ``%s`` formatting. The output is always a short, printable, single-line
string.
"""

from __future__ import annotations

import re

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_DEFAULT_MAX = 200


def safe_for_log(value: object, max_len: int = _DEFAULT_MAX) -> str:
    """Return a single-line printable form of ``value``, safe to log.

    - Replaces CR / LF / NUL / other control bytes with ``?``.
    - Truncates to ``max_len`` characters, appending ``…`` on overflow.
    - Returns ``"<None>"`` for ``None`` rather than the bare word ``None``
      so an operator can grep for absence vs. literal "None".
    """
    if value is None:
        return "<None>"
    text = str(value)
    cleaned = _CONTROL_RE.sub("?", text)
    if len(cleaned) > max_len:
        return cleaned[: max_len - 1] + "…"
    return cleaned
