"""GearBox Gallery (770 W Grand Ave, Oakland), an artist-run gallery.

The home page lists the shows now on view as text: a title, the artist(s), then the run
("November 5 - December 19, 2026"), once for the main gallery and once for the Inner Room's special
exhibition. It is plain server-rendered Squarespace HTML (a "Past Exhibitions" page holds the rest).
"""
import logging
import re
from urllib.parse import urljoin

from utils import fetch_and_parse
from date_parsing import parse_date_text
from processing import region_today
from scrapers.tor._common import Listing, page_lines

HOME_URL = 'https://www.gearboxgallery.com/'
VENUE = 'GearBox Gallery'
_RANGE_RE = re.compile(r'^[A-Z][a-z]+ \d{1,2}(?:, \d{4})? [-–] [A-Z][a-z]+ \d{1,2}, \d{4}$')


def scrape_gearbox_gallery(env='prod', region='sf'):
    """Scrape and process the current and upcoming exhibitions at GearBox Gallery."""
    today = region_today(region)
    soup = fetch_and_parse(HOME_URL)
    if soup is None:
        logging.warning("GearBox Gallery: could not fetch the home page; existing data kept.")
        return
    # Each show has a page of its own, linked from the home page as "More About <title>"; it is the
    # better Event Page link, and where images.py finds the show's picture (the home page's pictures
    # are not next to the titles)
    show_pages = {re.sub(r'\W+', '', a.get_text().lower().replace('more about', '')): urljoin(HOME_URL, a['href'])
                  for a in soup.find_all('a', href=True) if a.get_text().strip().lower().startswith('more about')}
    lines = page_lines(soup)
    listing = Listing(env, region, VENUE, soup, HOME_URL)
    seen = set()
    # Each show reads: title / artist(s) / "November 5 - December 19, 2026" (then the reception)
    for i, line in enumerate(lines):
        if i < 2 or not _RANGE_RE.match(line):
            continue
        start_date, end_date = parse_date_text(line, today)
        title = lines[i - 2]
        listing.add(title, start_date, end_date, tag='gallery', seen=seen,
                    link=show_pages.get(re.sub(r'\W+', '', title.lower())))
    if not listing.publish():
        logging.warning("GearBox Gallery: no exhibitions found; existing data kept.")
