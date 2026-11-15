"""Oregon Contemporary (formerly Disjecta) and Carnation Contemporary, 8371 N Interstate Ave (WEBSITE-124).

Oregon Contemporary's "On view and upcoming" page lists its shows as lines of text under "On view and upcoming at Ox": the
title, the run without a year ("November 4th - December 19th"; the year is worked out from today) and a "Curated by" line.
Carnation Contemporary is a members' space in the same building (its studio 3) with its own site; its Exhibitions page names
the one current show: "CURRENT:", the title, the artists, the run ("November 7-29, 2026").
"""
import logging
import re

from processing import region_today
from scrapers.nyc._common import clean, parse_dates
from scrapers.tor._common import publish
from utils import fetch_and_parse

OC_URL = 'https://www.oregoncontemporary.org/on-view-and-upcoming'
OC_VENUE = 'Oregon Contemporary'
CARNATION_URL = 'https://www.carnationcontemporary.com/Exhibitions'
CARNATION_VENUE = 'Carnation Contemporary'
_ORDINAL = re.compile(r'(\d)(?:st|nd|rd|th)\b')
_RUN = re.compile(r'^(?:[A-Z][a-z]+ \d{1,2}(?:st|nd|rd|th)?(?:, \d{4})?|[A-Z][a-z]+ \d{1,2}(?:st|nd|rd|th)?[-–]\d{1,2}(?:, \d{4})?)'
                  r'(?:\s*[-–]\s*[A-Z][a-z]+ \d{1,2}(?:st|nd|rd|th)?(?:, \d{4})?)?$')


def _lines(soup):
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    return [clean(line) for line in soup.get_text('\n').split('\n') if clean(line)]


def _run(line, today):
    """(start, end) when the line is only a run of dates, else None."""
    text = _ORDINAL.sub(r'\1', line)
    if not _RUN.match(line):
        return None
    start, end = parse_dates(text, today)
    return (start, end) if (start or end) else None


def read_oregon_contemporary(lines, today):
    """[(title, start, end)] for the shows after the "On view and upcoming at Ox" heading: each is a title line followed by its
    run; the "Special Art on Loan" pieces (a title with a year in brackets, no run) are not shows."""
    try:
        at = next(i for i, line in enumerate(lines) if line.lower().startswith('on view and upcoming at'))
    except StopIteration:
        return []
    found = []
    for i in range(at + 1, len(lines) - 1):
        run = _run(lines[i + 1], today)
        if run and not _run(lines[i], today) and not lines[i].lower().startswith('curated'):
            found.append((lines[i], *run))
    return found


def read_carnation(lines, today):
    """[(title, start, end)]: the title is the line after "CURRENT:", the artists follow it, then the run."""
    try:
        at = next(i for i, line in enumerate(lines) if line.upper().startswith('CURRENT'))
    except StopIteration:
        return []
    for j in range(at + 1, min(at + 6, len(lines))):
        run = _run(lines[j], today)
        if run and j > at + 1:
            return [(lines[at + 1], *run)]
    return []


def _scrape(url, venue, reader, env, region, tag):
    today = region_today(region)
    soup = fetch_and_parse(url)
    if soup is None:
        logging.warning(f"{venue}: could not fetch the exhibitions page; existing data kept.")
        return 0
    found = 0
    seen = set()
    for name, start, end in reader(_lines(soup), today):
        found += publish(env, region, venue, name, start, end, url, tag=tag, seen=seen)
    if not found:
        logging.warning(f"{venue}: no current or upcoming exhibition found; existing data kept.")
    return found


def scrape_oregon_contemporary(env='prod', region='pdx'):
    """Scrape and process Oregon Contemporary's current and upcoming exhibitions."""
    return _scrape(OC_URL, OC_VENUE, read_oregon_contemporary, env, region, 'gallery')


def scrape_carnation_contemporary(env='prod', region='pdx'):
    """Scrape and process Carnation Contemporary's current exhibition."""
    return _scrape(CARNATION_URL, CARNATION_VENUE, read_carnation, env, region, 'gallery')
