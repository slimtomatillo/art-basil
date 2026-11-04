"""Shared pieces for the LA gallery scrapers that read exhibitions off a page's lines of text.

Most gallery sites print each show as a few short lines (artist, title, dates), so a scraper
finds the date lines and reads the heading lines above them. See Listing in scrapers/tor/_common.py
for storing the shows and finding their pictures.
"""
import datetime as dt
import re

from config import MONTH_TO_NUM_DICT
from date_parsing import parse_date_text

_MONTHS = '|'.join(sorted(MONTH_TO_NUM_DICT, key=len, reverse=True))
# "November 7 – December 19, 2026", "On view through December 19" (one site spells it "though")
_LABEL_START_RE = re.compile(rf'^(?:through\s+)?(?:{_MONTHS})\.?\s+\d', re.IGNORECASE)
FAIR_PREFIXES = ('frieze', 'art basel', 'the armory show', 'felix', 'nada', 'untitled art')


def date_label(line, today):
    """(start, end) if the line is just a date label such as 'Nov 7 - Dec 19, 2026', else None.
    Either date can be None ('On view through ...' has no start)."""
    text = re.sub(r'^on view thr?ough\s+', 'through ', line.strip(), flags=re.IGNORECASE)
    if len(text) > 70 or not _LABEL_START_RE.match(text):
        return None
    start, end = parse_date_text(text, today)
    return (start, end) if (start or end) else None


def dated_headings(lines, today, begin=0, end=None, stops=(), limit=2, after=0):
    """Yield (heading lines, start, end, index) for each date label in lines[begin:end].

    The heading is up to `limit` lines directly above the label, not reaching past a `stops` line
    or the `after` lines that follow the previous entry's label (a location, say)."""
    floor = begin
    for i in range(begin, len(lines) if end is None else end):
        label = date_label(lines[i], today)
        if not label:
            continue
        parts = []
        for j in range(i - 1, max(floor, i - limit) - 1, -1):
            if lines[j] in stops:
                break
            parts.insert(0, lines[j])
        yield parts, label[0], label[1], i
        floor = i + 1 + after


def join_name(parts):
    """['Chris Martin', 'In Memory of My Feelings'] -> 'Chris Martin: In Memory of My Feelings'."""
    parts = [p for p in parts if p]
    if not parts:
        return None
    return ' '.join(parts) if len(parts) > 1 and parts[0].endswith(':') else ': '.join(parts)


def is_fair(name):
    return name.lower().startswith(FAIR_PREFIXES)


def next_year_if_past(start, end, today):
    """For a page that only lists current and upcoming shows: one whose dates are already over has
    the wrong year (a show crossing New Year written 'Nov 21 - Jan 30, 2026' for 2026-27), so move it on a year."""
    if end and end < today:
        try:
            return (start.replace(year=start.year + 1) if start else None), end.replace(year=end.year + 1)
        except ValueError:
            pass
    return start, end


def index_of(lines, text, default=0):
    return lines.index(text) if text in lines else default
