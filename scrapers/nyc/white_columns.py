"""White Columns, 91 Horatio St, West Village: the exhibitions on its home page.

whitecolumns.org/exhibitions/ is an archive of every show since the 1970s with no current/upcoming section, so the
current shows are read from the home page: cards (.grid-item) with a link to the show and, in .txt-wrap, the run
("November 7–December 19, 2026") then the artist and the title ("Marc Hundley", "SATELLITES ARE OUT TONIGHT"), and for
the online series "White Columns Online #38:" and its title. The archive teasers lower on the page (dated 1971 to 2017)
have the same shape and are dropped as past. "Coming up" events (screenings, talks) are not cards and are not read.
"""
import logging

from processing import region_today
from scrapers.la._gallery import join_name
from scrapers.nyc._common import card_picture, clean, parse_dates
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://whitecolumns.org/'
VENUE = 'White Columns'


def _name(lines):
    """The title lines of a card, without the "curated by ..." line or an installation-view caption."""
    lines = [line for line in lines if not line.lower().startswith(('curated by', 'installation view'))]
    names = []
    for line in lines:
        if line not in names:
            names.append(line)
    # "White Columns Online #38:" + "Clothes, not Fashion" is one title; "Marc Hundley" + "SATELLITES..." is artist and title
    return join_name(names[:2])


def scrape_white_columns(env='prod', region='nyc'):
    """Scrape and process White Columns' current and upcoming exhibitions."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("White Columns: could not fetch the home page; existing data kept.")
        return
    found = 0
    seen = set()
    for card in soup.select('.grid-item'):
        text = card.select_one('.txt-wrap')
        link = card.select_one('a[href*="/exhibitions/"]')
        if text is None or link is None:
            continue
        lines = [clean(t) for t in text.stripped_strings]
        lines = [line for line in lines if line]
        if len(lines) < 2:
            continue
        start_date, end_date = parse_dates(lines[0], today)
        name = _name(lines[1:])
        if not (name and (start_date or end_date)):
            continue
        found += publish(env, region, VENUE, name, start_date, end_date, link['href'], tag='gallery', seen=seen,
                         image=card_picture(card, PAGE_URL))
    if not found:
        logging.warning("White Columns: no current or upcoming exhibition found; existing data kept.")
