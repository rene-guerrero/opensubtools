#!/usr/bin/env python3
"""Path ordering helpers."""

import re
from pathlib import Path
from typing import List, Union

_DIGITS_RE = re.compile(r'(\d+)')


def natural_sort_key(value: Union[str, Path]) -> List:
    """Sort key that orders embedded numbers by value instead of by text.

    Plain lexicographic order puts "S01E100" before "S01E11" because it
    compares "0" against "1" character by character. Splitting each run of
    digits into an int makes episode 100 sort after episode 99.
    """
    text = str(value)
    return [
        int(part) if part.isdigit() else part.lower()
        for part in _DIGITS_RE.split(text)
    ]


def sort_paths_naturally(paths) -> List[Path]:
    """Sort paths by folder, then by name, using natural number ordering."""
    return sorted(paths, key=lambda p: (natural_sort_key(p.parent), natural_sort_key(p.name)))
