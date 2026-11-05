from utils import fetch_and_parse
from scrapers.tor._common import Listing, page_lines
from scrapers.la._gallery import dated_headings
from processing import region_today
import logging

EXHIBITIONS_URL = 'https://annalaudel.gallery/exhibitions/'
# annalaudel.com is an unrelated fashion agency; the gallery is at annalaudel.gallery
VENUE = 'Anna Laudel Istanbul'
STOPS = ('Upcoming', 'Past', 'Current', 'All', 'Archive', 'Fairs', 'Museums')


def _case(text):
    """The page prints names in capitals ("BİLAL HAKAN KARAKAYA"); the dotted capital İ is turned into a
    plain i before lower-casing, which would otherwise leave a stray combining dot."""
    return text.replace('İ', 'i').lower().title() if text.isupper() else text


def scrape_anna_laudel(env='prod', region='ist'):
    """Scrape and process the current and upcoming exhibitions at Anna Laudel's Istanbul gallery (not Düsseldorf, Ankara or Bodrum)."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Anna Laudel: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    listing = Listing(env, region, VENUE, soup, EXHIBITIONS_URL)
    seen = set()  # every show is listed twice
    # "ARTIST | TITLE | NOVEMBER 14, 2026 – JANUARY 3, 2027 | ISTANBUL"
    for parts, start, end, i in dated_headings(lines, today, stops=STOPS, limit=2, after=1):
        city = lines[i + 1] if i + 1 < len(lines) else ''
        if len(parts) == 2 and 'STANBUL' in city.upper():
            artist, title = _case(parts[0]), _case(parts[1])
            listing.add(f"{artist}: {title}", start, end, anchor=parts[0], tag='gallery', seen=seen)
    if not listing.publish():
        logging.warning("Anna Laudel: no Istanbul exhibitions found; existing data kept.")
