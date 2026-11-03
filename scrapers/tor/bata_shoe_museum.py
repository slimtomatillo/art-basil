from utils import fetch_and_parse
from date_parsing import parse_date_text
from scrapers.tor._common import page_lines, publish
from processing import region_today
import calendar
import datetime as dt
import logging
import re

EXHIBITIONS_URL = 'https://batashoemuseum.ca/exhibitions/'
_SHOW_URL_RE = re.compile(r'^https://batashoemuseum\.ca/exhibitions/[^/]+/$')
# Each show's page says "On view October 22, 2026, until April 2028", "On view May 7, 2026 until
# September 2027" or just "Until April 4, 2027"; the end is sometimes only a month and year.
_ON_VIEW_RE = re.compile(r'^On view (.+?),? until (.+)$', re.I)
_UNTIL_RE = re.compile(r'^Until (.+)$', re.I)
_MONTH_YEAR_RE = re.compile(r'^([A-Za-z]+) (\d{4})$')


def _parse_end(text, today):
    """'April 4, 2027' -> that date; 'April 2028' -> the last day of that month."""
    m = _MONTH_YEAR_RE.match(text.strip())
    if m:
        first, _ = parse_date_text(f'{m.group(1)} 1, {m.group(2)}', today)
        if first:
            return dt.date(first.year, first.month, calendar.monthrange(first.year, first.month)[1])
        return None
    _, end = parse_date_text(f'Until {text}', today)
    return end


def scrape_bata_shoe_museum(env='prod', region='tor'):
    """Scrape and process the current exhibitions of the Bata Shoe Museum."""
    today = region_today(region)
    listing = fetch_and_parse(EXHIBITIONS_URL)
    if listing is None:
        logging.warning("Bata Shoe Museum: could not fetch the exhibitions page; existing data kept.")
        return
    urls = []
    for a in listing.find_all('a', href=True):
        if _SHOW_URL_RE.match(a['href']) and a['href'] not in urls:
            urls.append(a['href'])

    found = 0
    for url in urls:
        soup = fetch_and_parse(url)
        if soup is None:
            continue
        og = soup.find('meta', property='og:title')
        name = og['content'].strip() if og and og.get('content') else None
        start_date = end_date = None
        for line in page_lines(soup):
            m = _ON_VIEW_RE.match(line)
            if m:
                start_date, _ = parse_date_text(m.group(1), today)
                end_date = _parse_end(m.group(2), today)
                break
            m = _UNTIL_RE.match(line)
            if m:
                end_date = _parse_end(m.group(1), today)
                break
        if not (name and end_date):
            logging.warning(f"Bata Shoe Museum: no readable dates on {url}")
            continue
        found += publish(env, region, 'Bata Shoe Museum', name, start_date, end_date, url, tag='museum')
    if not found:
        logging.warning("Bata Shoe Museum: no exhibitions found; existing data kept.")
