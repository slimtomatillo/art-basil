"""MACLA (Movimiento de Arte y Cultura Latino Americana), 510 S 1st St, San Jose: the Exhibitions of
its calendar page.

The page is the site's events calendar (the Modern Events Calendar plugin): an <article> per event
under "Current Visual Arts Exhibition", "Upcoming Workshops" and "Past Exhibitions", each with a
title, a category link, and the dates as day-and-month labels with no year ("04 September" and
" - 08 November"); the year is in a class on the article ("mec-toggle-202609" = starts September
2026). The event's text usually opens with the exhibition's own dates ("September 4 – November 15,
2026"), which carry the year and can differ from the calendar's, so those are read first. Only
events in the Exhibitions category are kept (workshops and performances are not), and past ones
are dropped by publish(). Between shows the "current" list is empty, which is normal.
"""
import datetime as dt
import logging
import re

from date_parsing import parse_date_text
from processing import region_today
from scrapers.tor._common import publish
from utils import fetch_and_parse

PAGE_URL = 'https://maclaarte.org/programs/visual-arts/'
VENUE = 'MACLA'
_MAX_DESCRIPTION = 400
_DAY_MONTH = re.compile(r'(\d{1,2})(?:\s+([A-Za-z]+))?')


def _day_month(label):
    """(day, month number or None) from '04 September', '03' or '- 05 October'."""
    m = _DAY_MONTH.search(label or '')
    if not m:
        return None, None
    month = None
    if m.group(2):
        for fmt in ('%B', '%b'):
            try:
                month = dt.datetime.strptime(m.group(2), fmt).month
                break
            except ValueError:
                continue
    return int(m.group(1)), month


def _calendar_dates(article, today):
    """(start, end) from the article's day-and-month labels, the year taken from its class."""
    start_tag = article.select_one('.mec-start-date-label')
    end_tag = article.select_one('.mec-end-date-label')
    start_text = start_tag.get_text(' ') if start_tag else ''
    end_text = end_tag.get_text(' ') if end_tag else ''
    # A short run can sit all in the first label ("03 - 05 October")
    if '-' in start_text and not end_text.strip():
        start_text, end_text = start_text.split('-', 1)
    s_day, s_month = _day_month(start_text)
    e_day, e_month = _day_month(end_text)
    s_month = s_month or e_month
    e_month = e_month or s_month
    e_day = e_day or s_day
    if not (s_day and s_month):
        return None, None
    year = today.year
    for cls in article.get('class', []):
        m = re.match(r'mec-toggle-(\d{4})(\d{2})', cls)
        if m:
            year = int(m.group(1))
    try:
        start = dt.date(year, s_month, s_day)
        end = dt.date(year + (1 if e_month < s_month else 0), e_month, e_day)
    except ValueError:
        return None, None
    return start, end


def _text_dates(description, today):
    """(start, end) from a date range at the start of the event text, or (None, None)."""
    head = re.match(r'[A-Z][a-z]+ \d{1,2}(?:, \d{4})? ?[–-] ?(?:[A-Z][a-z]+ )?\d{1,2}, \d{4}', description or '')
    if not head:
        return None, None
    start, end = parse_date_text(head.group(0), today)
    return (start, end) if start and end else (None, None)


def scrape_macla(env='prod', region='sf'):
    """Scrape and process the current and upcoming exhibitions of MACLA."""
    today = region_today(region)
    soup = fetch_and_parse(PAGE_URL)
    if soup is None:
        logging.warning("MACLA: could not fetch the visual arts page; existing data kept.")
        return
    seen = set()
    for article in soup.select('article.mec-event-article'):
        category = article.select_one('.mec-events-event-categories')
        title_tag = article.select_one('.mec-toggle-title')
        if title_tag is None or category is None or 'exhibition' not in category.get_text().lower():
            continue
        name = ' '.join(title_tag.get_text(' ').split())
        description_tag = article.select_one('.mec-single-event-description')
        text = ' '.join(description_tag.get_text(' ').split()) if description_tag else ''
        start_date, end_date = _text_dates(text, today)
        if not (start_date and end_date):
            start_date, end_date = _calendar_dates(article, today)
        if not (start_date and end_date):
            logging.warning(f"MACLA: no readable dates for {name!r}")
            continue
        body = re.sub(r'^[A-Z][a-z]+ \d{1,2}(?:, \d{4})? ?[–-] ?(?:[A-Z][a-z]+ )?\d{1,2}, \d{4}\s*', '', text)
        description = body[:_MAX_DESCRIPTION].rsplit(' ', 1)[0] if len(body) > _MAX_DESCRIPTION else (body or None)
        image_tag = article.find('img')
        image = image_tag.get('src') if image_tag else None
        publish(env, region, VENUE, name, start_date, end_date, PAGE_URL, tag='gallery',
                description=description, seen=seen, image=image)
