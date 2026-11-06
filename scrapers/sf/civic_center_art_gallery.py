"""Marin Civic Center: the Civic Center Art Gallery (1st and 3rd floors) of the Marin County Civic Center,
3501 Civic Center Dr, San Rafael. Shown on the site as "Marin Civic Center" so it can't be mistaken for another city's.

One page describes the exhibit now on the 1st and 3rd floors: a title (h2), then a block with the
dates as an h3 ("October 1, 2026, to January 7, 2027"), the location as an h4 and the text. The
page returns a Cloudflare 403 to scripted requests, so it is fetched through the ZenRows proxy
(utils.PROXY_DOMAINS); the content is in the HTML, so no JavaScript rendering is needed.
"""
from utils import fetch_and_parse
from date_parsing import parse_date_text
from images import PageText, image_in_card
from scrapers.tor._common import publish
from processing import region_today
import logging

PAGE_URL = 'https://www.marincounty.gov/departments/cultural-services/art-exhibits/civic-center-art-gallery'
VENUE = 'Marin Civic Center'
_MAX_DESCRIPTION = 400


def scrape_civic_center_art_gallery(env='prod', region='sf'):
    """Scrape and process the exhibit(s) on the Marin Civic Center page."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("Marin Civic Center: could not fetch the gallery page; existing data kept.")
        return
    # An exhibit is a title followed by a block whose first heading is its dates. The "Gallery Location
    # and Hours" and "Related" blocks have no date heading and are not exhibits.
    exhibits = []
    for title in soup.select('h2.usa-paragraph__title'):
        prose = title.find_next('div', class_='marin-prose')
        date_tag = prose.find('h3') if prose is not None else None
        if date_tag is not None:
            exhibits.append((' '.join(title.get_text(' ').split()), prose, ' '.join(date_tag.get_text(' ').split())))
    names = [name for name, _, _ in exhibits]
    page = PageText(soup)
    found = 0
    seen = set()
    for name, prose, date_text in exhibits:
        start_date, end_date = parse_date_text(date_text, today)
        if not (start_date or end_date):
            logging.warning(f"Marin Civic Center: no readable dates for {name!r}")
            continue
        paragraphs = [' '.join(p.get_text(' ').split()) for p in prose.find_all('p')]
        description = ' '.join(p for p in paragraphs if p)[:_MAX_DESCRIPTION].rsplit(' ', 1)[0] or None
        # The picture sits in a slideshow beside the text; with several exhibits on the page it can't
        # be told whose it is, and image_in_card then finds none
        image = image_in_card(page, name, PAGE_URL, names, check_size=False)
        found += publish(env, region, VENUE, name, start_date, end_date, PAGE_URL, tag='gallery',
                         description=description, seen=seen, image=image)
    if not found:
        logging.warning("Marin Civic Center: no current or upcoming exhibit found; existing data kept.")
