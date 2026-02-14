import re
from typing import Tuple, Optional

EPISODE_RANGE_RE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")
EPISODE_SINGLE_RE = re.compile(r"^\s*(\d+)\s*$")

def parse_episode_input(text: str) -> Optional[Tuple[int, Optional[int]]]:
    """
    Returns (start, end) where end may be equal to start or None on parse error.
    Examples:
      "10" -> (10, 10)
      "1-5" -> (1, 5)
    """
    if m := EPISODE_SINGLE_RE.match(text):
        n = int(m.group(1))
        return n, n
    if m := EPISODE_RANGE_RE.match(text):
        a, b = int(m.group(1)), int(m.group(2))
        if a > b:
            a, b = b, a
        return a, b
    return None

def short(text: str, length: int = 200) -> str:
    if not text:
        return ""
    return (text[:length].rsplit(" ", 1)[0] + "...") if len(text) > length else text
