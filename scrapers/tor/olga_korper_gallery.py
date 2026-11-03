from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import page_lines, publish
from processing import region_today
import logging
import re

PAGE_URL = 'https://www.olgakorpergallery.com/exhibitions-page/'
_RANGE_RE = re.compile(r'^[A-Z][a-z]+ \d{1,2}, \d{4} [–-] [A-Z][a-z]+ \d{1,2}, \d{4}$')
# The list mixes the gallery's own shows with its art-fair booths
_FAIR_RE = re.compile(r'art toronto|armory|art hop|\bfair\b|expo|frieze|art basel|art cologne|miami', re.I)


def scrape_olga_korper_gallery(env='prod', region='tor'):
    """Scrape and process the current and upcoming exhibitions at Olga Korper Gallery."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Olga Korper Gallery: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    found = 0
    seen = set()
    # Each entry is artist(s) (or "Group Exhibition") / title / dates
    for i, line in enumerate(lines):
        if i < 2 or not _RANGE_RE.match(line):
            continue
        artist, title = lines[i - 2], lines[i - 1]
        if _FAIR_RE.search(title) or _FAIR_RE.search(artist) or len(artist) > 80:
            continue
        name = title if artist.lower() == 'group exhibition' else f'{artist}: {title}'
        start_date, end_date = parse_date_text(line, today)
        found += publish(env, region, 'Olga Korper Gallery', name, start_date, end_date, PAGE_URL,
                         tag='gallery', seen=seen)
    if not found:
        logging.warning("Olga Korper Gallery: no exhibitions found; existing data kept.")
