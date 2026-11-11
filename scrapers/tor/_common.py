"""Shared pieces for the Toronto venue scrapers: reading a page as text lines and
publishing one exhibition, so each venue module only has to say where its titles
and date ranges sit in the page."""
import datetime as dt
import logging
import re
from datetime import timezone

from images import PageText, image_in_card
from processing import process_event, derive_phase, region_today


def page_lines(soup):
    """The page's visible text as a list of whitespace-normalised, non-empty lines."""
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    return [re.sub(r'\s+', ' ', l).strip() for l in soup.get_text('\n').split('\n') if l.strip()]


def publish(env, region, venue, name, start_date, end_date, link, tag='gallery', description=None,
            keep_past=False, seen=None, kind='exhibition', extra_tags=(), image=None, ongoing=False):
    """Build and store one exhibition (or, with kind='event', one program). Returns True if it
    was published (past entries are skipped unless keep_past, and a (name, start) pair already
    in `seen` is skipped). `image` is the show's picture URL, stored as an "Image" link. `ongoing` marks
    an open-ended show (no end date) as the site's "Ongoing"."""
    today = region_today(region)
    # A show that only says "Until <date>" has no start date; one with neither date can't be placed
    if not (name and (start_date or end_date)):
        return False
    key = (name, start_date)
    if seen is not None:
        if key in seen:
            return False
        seen.add(key)
    phase = derive_phase(start_date, end_date, today) or 'current'
    if phase == 'past' and not keep_past:
        return False
    event_details = {
        'name': name,
        'venue': venue,
        'description': description,
        'tags': [kind] + [phase] + [tag] + list(extra_tags),
        'phase': phase,
        'dates': {'start': start_date, 'end': end_date},
        'ongoing': bool(ongoing and phase == 'current'),
        'links': [{'link': link, 'description': 'Event Page'}],
        'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }
    if image:
        event_details['links'].append({'link': image, 'description': 'Image'})
    if env == 'dev':
        logging.info(f"Event found: {name} ({phase}, {start_date} - {end_date}) at {venue}")
    if env == 'prod':
        process_event(event_details, region)
    return True


class Listing:
    """Collects the shows of one listing page, then publishes them with their pictures.

    A scraper adds each show with add() as it reads the page's text; publish() then finds each
    show's picture on the page (the one in the same card as its title) and stores the shows.
    Pictures are looked up after everything is added because a card is told apart from the
    list around it by the other shows' titles. A picture that would go to more than one show
    is a banner and is left off. Shows without a picture are still published; images.py tries
    to find one later.

    `anchor` is the title as the page prints it, if the scraper builds the name from several
    lines or changes it; punctuation and line breaks don't matter."""

    def __init__(self, env, region, venue, soup, page_url, check_size=False):
        self.env, self.region, self.venue = env, region, venue
        self.soup, self.page_url, self.check_size = soup, page_url, check_size
        self.shows = []

    def add(self, name, start_date, end_date, link=None, anchor=None, **kwargs):
        self.shows.append((name, start_date, end_date, link or self.page_url, anchor or name, kwargs))

    def pictures(self):
        """{anchor: picture url} for the shows that will be stored (not the past ones)."""
        today = region_today(self.region)
        wanted = [anchor for name, start, end, link, anchor, kwargs in self.shows
                  if name and (start or end)
                  and (kwargs.get('keep_past') or derive_phase(start, end, today) != 'past')]
        if not wanted:
            return {}
        page = PageText(self.soup)
        everyone = [anchor for *_, anchor, _kwargs in self.shows]
        found = {a: image_in_card(page, a, self.page_url, everyone, self.check_size) for a in wanted}
        counts = {}
        for url in filter(None, found.values()):
            counts[url] = counts.get(url, 0) + 1
        return {a: u for a, u in found.items() if u and counts[u] == 1}

    def publish(self):
        """Store every show; returns how many were stored."""
        pictures = self.pictures()
        stored = 0
        for name, start, end, link, anchor, kwargs in self.shows:
            stored += publish(self.env, self.region, self.venue, name, start, end, link,
                              image=pictures.get(anchor), **kwargs)
        if self.shows and pictures:
            logging.info(f"{self.venue}: found pictures for {len(pictures)} of {len(self.shows)} shows")
        return stored
