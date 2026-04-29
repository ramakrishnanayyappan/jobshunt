"""Strip terminal / bracketed-paste noise from user-provided text."""
from __future__ import annotations

import re


def sanitize_paste_artifacts(text: str) -> str:
    """Remove xterm bracketed paste markers and similar OSC junk from pasted content."""
    if not text:
        return ""
    t = text
    # Bracketed paste: ESC [ 200 ~ ... ESC [ 201 ~
    t = t.replace("\x1b[200~", "").replace("\x1b[201~", "")
    # Often pasted without ESC as literal "[200~" / "[201~"
    t = re.sub(r"\[200~", "", t)
    t = re.sub(r"\[201~", "", t)
    t = t.replace("\x07", "")
    return t
