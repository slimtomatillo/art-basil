from utils import fetch_and_parse
from scrapers.tor._common import Listing, page_lines
from processing import region_today
import datetime as dt
import logging
import re
from urllib.parse import urljoin

EXHIBITIONS_URL = 'https://theicala.org/en/exhibitions'
VENUE = 'Institute of Contemporary Art, Los Angeles'
# Current shows: title, then "On view through February 28, 2027". Upcoming: "Opening March 27, 2027" (or
# "Opening November 07", no year), then the title.
_THROUGH_RE = re.compile(r'^On view through ([A-Z][a-z]+ \d{1,2}, \d{4})$')
_OPENING_RE = re.compile(r'^Opening ([A-Z][a-z]+ \d{1,2})(?:, (\d{4}))?$')


def _opening(month_day, year, today):
    """'November 07' with no year is the next such day within the last month or the coming year."""
    try:
        if year:
            return dt.datetime.strptime(f"{month_day} {year}", '%B %d %Y').date()
        d = dt.datetime.strptime(f"{month_day} {today.year}", '%B %d %Y').date()
        return d if d >= today - dt.timedelta(days=30) else d.replace(year=today.year + 1)
    except ValueError:
        return None


def _links(soup):
    """{link text: absolute url} for the exhibition pages linked from the listing."""
    found = {}
    for a in soup.find_all('a', href=True):
        if '/exhibitions/' in a['href']:
            # a card's link text is its title plus its dates, so use the title element alone
            title = a.select_one('.info-card--title')
            text = re.sub(r'\s+', ' ', (title or a).get_text(' ', strip=True))
            if text:
                found.setdefault(text, urljoin(EXHIBITIONS_URL, a['href']))
    return found


def scrape_ica_la(env='prod', region='la'):
    """Scrape and process the current and upcoming exhibitions at ICA LA."""
    today = region_today(region)
    soup = fetch_and_parse(EXHIBITIONS_URL)
    if soup is None:
        logging.warning("ICA LA: could not fetch the exhibitions page; existing data kept.")
        return
    links = _links(soup)
    lines = page_lines(soup)
    if 'Current Exhibitions' not in lines:
        logging.warning("ICA LA: exhibitions page has no 'Current Exhibitions' section; existing data kept.")
        return
    start_at = lines.index('Current Exhibitions')
    end_at = next((i for i, l in enumerate(lines) if i > start_at and l.startswith('Find us on')), len(lines))
    listing = Listing(env, region, VENUE, soup, EXHIBITIONS_URL)
    for i in range(start_at + 1, end_at):
        through = _THROUGH_RE.match(lines[i])
        opening = _OPENING_RE.match(lines[i])
        if through and i > start_at + 1:
            title = lines[i - 1]
            end = dt.datetime.strptime(through.group(1), '%B %d, %Y').date()
            listing.add(title, None, end, link=links.get(title), tag='gallery')
        elif opening and i + 1 < end_at:
            title = lines[i + 1]
            listing.add(title, _opening(opening.group(1), opening.group(2), today), None,
                        link=links.get(title), tag='gallery')
    if not listing.publish():
        logging.warning("ICA LA: no exhibitions found; existing data kept.")
