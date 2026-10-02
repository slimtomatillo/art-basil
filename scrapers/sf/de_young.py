from utils import fetch_and_parse
from processing import process_event
from config import MONTH_TO_NUM_DICT
import datetime as dt
from datetime import timezone
import logging

def convert_date_to_dt(date_string):
    """Takes a date in string form and converts it to a dt object"""

    date_parts = date_string.split()
    month_num = int(MONTH_TO_NUM_DICT[date_parts[0]])
    day = int(date_parts[1])
    year = int(date_parts[2])
    if month_num and day and year:
        date_dt = dt.date(year, month_num, day)
    return date_dt

def scrape_de_young_and_legion_of_honor(env='prod', region='sf'):
    """Scrape and process exhibitions from the de Young and Legion of Honor."""

    # Not /calendar?type=exhibition&location=... - that filter isn't actually
    # applied server- or client-side (confirmed in a real browser: it returns
    # every event type - tours, talks, parties - unfiltered), so the scraper
    # was never reading exhibition data from it. /exhibitions is the real
    # exhibitions listing, with a genuine `where=` location filter. famsf.org
    # has no "Virtual" location here (it's an event type on /calendar, not a
    # real exhibition venue - WEBSITE-68's "Virtual" venue never had any
    # stored events), so it's dropped.
    locations = [
        {'venue': 'de Young', 'slug': 'de-young'},
        {'venue': 'Legion of Honor', 'slug': 'legion-of-honor'},
    ]

    today = dt.date.today()

    def process_card(card, venue):
        title_link = card.find('h3').find('a')
        name = title_link.get_text(strip=True)
        link = title_link.get('href')

        date_text = card.find('p').get_text(' ', strip=True).lower().replace(',', '')
        ongoing = date_text == 'ongoing'

        if ongoing:
            # A bare "Ongoing" label (permanent installations) has no date
            # range to parse.
            phase = 'current'
            start_date = None
            end_date = None
        elif date_text.startswith('through'):
            phase = 'current'
            start_date = None
            end_date = convert_date_to_dt(date_text.replace('through ', ''))
        else:
            dates = date_text.split(' – ')
            # If no year on the start date, borrow the end date's year
            if len(dates[0].split()) == 2:
                dates[0] = dates[0] + ' ' + dates[1].split()[-1]
            start_date = convert_date_to_dt(dates[0])
            end_date = convert_date_to_dt(dates[1])
            phase = 'future' if start_date > today else 'past'

        img = card.select_one('picture img')
        image_link = img.get('src') if img else None

        event_details = {
            'name': name,
            'venue': venue,
            'tags': ['exhibition', phase, 'museum'],
            'phase': phase,
            'dates': {'start': start_date, 'end': end_date},
            'ongoing': ongoing,
            'links': [{'link': link, 'description': 'Event Page'}],
            'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        if image_link:
            event_details['links'].append({'link': image_link, 'description': 'Image'})

        if env == 'dev':
            logging.info(f"Event found: {event_details['name']} at {event_details['venue']}")
        if env == 'prod':
            process_event(event_details, region)

    for loc in locations:
        venue = loc['venue']
        # Current+upcoming exhibitions live on one page; a separate page
        # holds past exhibitions (257+ deep per location) - only its first
        # page (most recent ~21) is pulled, matching this scraper's
        # historical scope rather than paging through the full archive.
        for url in [
            f"https://www.famsf.org/exhibitions?where={loc['slug']}",
            f"https://www.famsf.org/exhibitions/past?where={loc['slug']}",
        ]:
            soup = fetch_and_parse(url)
            if soup is None:
                # famsf.org is behind a Cloudflare WAF that returns 403 to
                # datacenter IPs (e.g. GitHub Actions runners) unless routed
                # through the proxy - see WEBSITE-53. Skip this page and
                # leave existing data untouched rather than erroring out.
                logging.warning(
                    f"Skipping {venue} ({url}): could not fetch "
                    f"(likely the CDN 403 block on CI IPs); existing data kept."
                )
                continue

            # The site reuses this same data-behavior marker on non-exhibition
            # cards too (e.g. "visit us" venue-hours promos), which have no
            # /exhibitions/ link - filter to real exhibition cards only.
            cards = soup.find_all(attrs={'data-behavior': 'BlockLink'})
            cards = [
                c for c in cards
                if c.find('h3') and c.find('h3').find('a')
                and '/exhibitions/' in (c.find('h3').find('a').get('href') or '')
            ]

            for card in cards:
                try:
                    process_card(card, venue)
                except Exception as e:
                    logging.error(f"Error processing exhibition card for {venue}: {e}", exc_info=True)
