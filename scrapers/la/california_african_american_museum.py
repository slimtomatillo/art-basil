from images import resized_image_url
from scrapers.tor._common import publish
from processing import region_today
import datetime as dt
import logging

import requests

FEED_URL = 'https://caamuseum.org/sirvy/exhibitions?service=exhibitions'
VENUE = 'California African American Museum'
# The long-running outdoor commission is listed with a 7-year run and "Ongoing" as its dates
MAX_RUN_DAYS = 3 * 365


def _date(month_day, year):
    """'October 20' + 2026 -> date(2026, 10, 20), or None."""
    try:
        return dt.datetime.strptime(f"{month_day} {int(year)}", '%B %d %Y').date()
    except (TypeError, ValueError):
        return None


def scrape_california_african_american_museum(env='prod', region='la'):
    """Scrape and process the current and upcoming exhibitions at CAAM from the museum's own JSON feed."""
    region_today(region)
    try:
        response = requests.get(FEED_URL, headers={'User-Agent': 'Your Bot 0.1'}, timeout=30)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as e:
        logging.warning(f"CAAM: could not fetch the exhibitions feed ({e}); existing data kept.")
        return
    seen = set()
    stored = 0
    for key in ('current', 'upcoming'):
        for item in data.get(key) or []:
            content = item.get('content') or {}
            start = _date(content.get('start_date'), content.get('start_year'))
            end = _date(content.get('end_date'), content.get('end_year'))
            if not (item.get('title') and start and end):
                continue
            # "Ongoing" pieces are permanent installations, not exhibitions
            if str(content.get('display_date') or '').strip().lower() == 'ongoing' or (end - start).days > MAX_RUN_DAYS:
                continue
            # "October 20, 2026 - February 27, 2027 at Art + Practice": shown at another venue
            if ' at ' in str(content.get('display_date') or ''):
                continue
            page = item.get('contentUrl') or item.get('url') or 'https://caamuseum.org/exhibitions'
            # The feed names each show's lead picture; the originals are huge PNGs, so a small copy is used
            picture = item.get('image') or (f"{page.rstrip('/')}/{content['main_image']}" if content.get('main_image') else None)
            stored += publish(env, region, VENUE, item['title'].strip(), start, end, page,
                              tag='museum', seen=seen, image=resized_image_url(picture))
    if not stored:
        logging.warning("CAAM: no exhibitions found; existing data kept.")
