from utils import fetch_and_parse
from scrapers.tor._common import Listing, page_lines
from date_parsing import parse_date_text
from processing import region_today
import logging

EXHIBITIONS_URL = 'https://anatebgi.com/exhibitions/'
VENUE = 'Anat Ebgi Gallery'


def scrape_anat_ebgi_gallery(env='prod', region='la'):
    """Scrape and process the current and announced exhibitions at Anat Ebgi's Los Angeles gallery (not its New York one)."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("Anat Ebgi Gallery: could not fetch the exhibitions page; existing data kept.")
        return
    lines = page_lines(soup)
    if 'Current & Announced Exhibitions' not in lines:
        logging.warning("Anat Ebgi Gallery: no 'Current & Announced Exhibitions' section; existing data kept.")
        return
    begin = lines.index('Current & Announced Exhibitions')
    end = next((i for i, l in enumerate(lines) if i > begin and l == 'Past Exhibitions'), len(lines))
    listing = Listing(env, region, VENUE, soup, EXHIBITIONS_URL)
    # "Title | September 19, 2026 | — | January 16, 2027 | , | street address | neighbourhood"
    for i in range(begin + 1, end - 5):
        if lines[i + 2] != '—' or 'Los Angeles' not in lines[i + 5]:
            continue
        start, finish = parse_date_text(f"{lines[i + 1]} - {lines[i + 3]}", today)
        if start or finish:
            listing.add(lines[i], start, finish)
    if not listing.publish():
        logging.warning("Anat Ebgi Gallery: no Los Angeles exhibitions found; existing data kept.")
