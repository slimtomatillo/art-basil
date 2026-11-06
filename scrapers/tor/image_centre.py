from utils import fetch_and_parse
from scrapers.tor._common import Listing, page_lines
from scrapers.la._gallery import dated_headings
from processing import region_today
from urllib.parse import urljoin
import logging

GALLERY_URL = 'https://www.theimagecentre.ca/gallery/'
VENUE = 'The Image Centre'
STOPS = ('Current Exhibitions', 'Upcoming', 'Past', 'Exhibition Catalogues', 'Student Gallery', 'Upcoming Exhibitions')


def scrape_image_centre(env='prod', region='tor'):
    """Scrape and process the current and upcoming exhibitions at The Image Centre (Toronto Metropolitan University).
    Its server doesn't send its intermediate certificate; utils.verify_for supplies it."""
    today = region_today(region)
    soup = fetch_and_parse(GALLERY_URL)
    if soup is None:
        logging.warning("The Image Centre: could not fetch the gallery page; existing data kept.")
        return
    lines = page_lines(soup)
    # Each show has a "Learn more" link to /exhibition/<slug>, in the same order as the shows
    pages = []
    for a in soup.find_all('a', href=True):
        url = urljoin(GALLERY_URL, a['href'])
        if a.get_text(strip=True) == 'Learn more' and '/exhibition/' in url and url not in pages:
            pages.append(url)
    listing = Listing(env, region, VENUE, soup, GALLERY_URL)
    # "Tanya Marcuse: Portent | September 9–December 5, 2026 | Salah J. Bachir New Media Wall | Curator: Paul Roth | Learn more"
    shows = [(parts, start, end) for parts, start, end, _ in dated_headings(lines, today, stops=STOPS, limit=1) if parts]
    for n, (parts, start, end) in enumerate(shows):
        link = pages[n] if len(pages) == len(shows) else None
        listing.add(parts[0], start, end, link=link, tag='museum', extra_tags=('free',))
    if not listing.publish():
        logging.warning("The Image Centre: no exhibitions found; existing data kept.")
