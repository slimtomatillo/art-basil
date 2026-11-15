"""Night Gallery: the exhibitions on https://www.nightgallery.ca/exhibitions, in Los Angeles and New York.

The site lists the current show on /exhibitions and the upcoming ones on /exhibitions/upcoming (it used to list both on the
first page, and the daily run found nothing for a week before this was noticed: WEBSITE-123); both are read.

The listing is one page for both cities (the gallery also has a viewing room in Tribeca, New York) and says
nothing about where a show is held; each show's own page gives the address near the top of its text ("61 Lispenard
St, 2nd Floor New York, NY"). This module reads the listing and each show's page and publishes the Los Angeles shows
under "Night Gallery"; scrapers/nyc/night_gallery_new_york.py publishes the New York ones (WEBSITE-120). A show whose
page can't be read or names no city is taken as Los Angeles, as every show was before.
"""
import logging
import re

import images
from utils import fetch_and_parse
from scrapers.tor._common import Listing, page_lines
from scrapers.la._gallery import dated_headings, join_name, next_year_if_past
from processing import region_today

EXHIBITIONS_URL = 'https://www.nightgallery.ca/exhibitions'
UPCOMING_URL = EXHIBITIONS_URL + '/upcoming'
VENUE = 'Night Gallery'

_NEW_YORK = re.compile(r'\bNew York,?\s*(?:NY|New York)\b|\bTribeca\b', re.IGNORECASE)
_LEAD_CHARS = 500          # the address is at the start of a show page's text


def _case(text):
    """The site prints artist names and dates in capitals ("TIDAWHITNEY LEK")."""
    return text.title() if text.isupper() else text


def show_city(url):
    """'nyc' when the show's own page puts it in New York (and not in Los Angeles), else 'la'."""
    soup = fetch_and_parse(url) if url else None
    if soup is None:
        return 'la'
    lead = ' '.join(m.get('content', '') for m in soup.find_all('meta')
                    if m.get('property') == 'og:description' or m.get('name') == 'description')
    if not lead.strip():
        lead = ' '.join(soup.get_text(' ').split())
    lead = lead[:_LEAD_CHARS]
    return 'nyc' if _NEW_YORK.search(lead) and 'los angeles' not in lead.lower() else 'la'


def read_shows(soup, today, page_url=EXHIBITIONS_URL):
    """[(name, start, end, anchor, link, city)] for the shows on a listing page, each placed by its own page.
    `link` is the show's own page when the listing's card for it can be found (else None)."""
    lines = page_lines(soup)
    # "ARTIST | Title | NOVEMBER 21 - JANUARY 30, 2026" (the page lists only current and upcoming
    # shows, and its New Year-crossing dates are written a year behind)
    shows = []
    for parts, start, end, _ in dated_headings(lines, today, stops=('Upcoming', 'Past', 'Exhibitions')):
        if parts:
            start, end = next_year_if_past(start, end, today)
            shows.append((join_name([_case(p) for p in parts]), start, end, parts[0]))
    links = images.card_links(soup, page_url, [name for name, _, _, _ in shows]) if shows else {}
    return [(name, start, end, anchor, links.get(name), show_city(links.get(name))) for name, start, end, anchor in shows]


def read_listings(today):
    """[(page_url, soup, shows)] for the current page and the upcoming page (shows as read_shows gives them; a show on both
    is kept once), or None when the current page can't be read. The upcoming page is best effort."""
    current = fetch_and_parse(EXHIBITIONS_URL)
    if current is None:
        return None
    pages = [(EXHIBITIONS_URL, current, read_shows(current, today, EXHIBITIONS_URL))]
    upcoming = fetch_and_parse(UPCOMING_URL)
    if upcoming is None:
        logging.warning("Night Gallery: could not fetch the upcoming exhibitions page; only the current page was read.")
    else:
        seen = {show[0] for show in pages[0][2]}
        pages.append((UPCOMING_URL, upcoming, [show for show in read_shows(upcoming, today, UPCOMING_URL) if show[0] not in seen]))
    return pages


def scrape_night_gallery(env='prod', region='la'):
    """Scrape and process the current and upcoming exhibitions at Night Gallery in Los Angeles."""
    today = region_today(region)
    pages = read_listings(today)
    if pages is None:
        logging.warning("Night Gallery: could not fetch the exhibitions page; existing data kept.")
        return
    stored = 0
    for page_url, soup, shows in pages:
        listing = Listing(env, region, VENUE, soup, page_url)
        for name, start, end, anchor, link, city in shows:
            if city != 'la':
                logging.info(f"Night Gallery: {name!r} is held in New York, not Los Angeles; left to the New York scraper.")
                continue
            listing.add(name, start, end, link=link, anchor=anchor)
        stored += listing.publish()
    if not stored:
        logging.warning("Night Gallery: no exhibitions found; existing data kept.")
