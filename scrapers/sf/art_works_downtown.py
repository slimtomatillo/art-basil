from utils import fetch_and_parse
from processing import process_event, derive_phase, region_today
from date_parsing import parse_date_text
import datetime as dt
from datetime import timezone
import logging
import re

VENUE = 'Art Works Downtown'
BASE_URL = 'https://www.artworksdowntown.org'

# Art Works Downtown (San Rafael) shows work in three galleries, each with its own
# page. It is a Squarespace site with no structured feed: every page has a hand-typed
# "Upcoming Exhibits" list ("<dates>: <title>", each title linking to an anchor), then
# one section per show under that anchor (a block starting with the date range and
# "Exhibition Dates", then the artists' statement, then photos).
GALLERY_PAGES = [
    ('Gallery 1337', '/current-gallery-1337'),
    ("Founders' Gallery", '/current-founders-gallery'),
    ("1325 Donors' Gallery", '/current-1325-donors-gallery'),
]
# The /past page (an archive) is not scraped: shows age into 'past' on their own once
# they have been stored and their end date passes.

# Blocks of the site footer / menu that sit between and after the show sections
_FOOTER_MARKERS = ('1325-1337 Fourth Street', 'Join Artist Membership', 'Admission is free')


def parse_exhibit_list(soup):
    """The "Upcoming Exhibits" list as [(date_text, title, anchor)]. Raises if the list
    isn't there, so a redesigned page turns the run red instead of silently emptying."""
    header = next((p for p in soup.find_all('p') if 'Upcoming Exhibits' in p.get_text()), None)
    if header is None:
        raise RuntimeError(f"{VENUE}: could not find the 'Upcoming Exhibits' list; the page layout may have changed")
    entries, buffered = [], ''
    for node in header.children:
        name = getattr(node, 'name', None)
        if name == 'br':
            continue
        if name == 'a' and node.get('href', '').startswith('#'):
            entries.append((buffered.strip().rstrip(':').strip(), node.get_text(' ', strip=True), node['href'][1:]))
            buffered = ''
        elif name == 'strong' and 'Upcoming Exhibits' in node.get_text():
            continue
        else:
            buffered += node.get_text() if hasattr(node, 'get_text') else str(node)
    return entries


def exhibit_section(soup, anchor, all_anchors):
    """(text_blocks, image_url, real_id) for the section after `anchor`, up to the next
    show's anchor. Ids are matched case-insensitively: the site links "#rina" to
    id="Rina", and real_id is the id as written. Returns ([], None, None) if the
    anchor isn't on the page."""
    wanted = {a.lower() for a in all_anchors}
    by_id = {el['id'].lower(): el for el in soup.find_all(id=True) if el['id'].lower() in wanted}
    start = by_id.get(anchor.lower())
    if start is None:
        return [], None, None
    blocks, image = [], None
    for el in start.find_all_next():
        if el is not start and el.name == 'div' and el.get('id', '').lower() in wanted:
            break
        if el.name == 'div' and 'sqs-html-content' in (el.get('class') or []):
            blocks.append(el.get_text('\n', strip=True))
        elif el.name == 'img' and image is None and el.get('data-src'):
            image = _image_url(el)
    return blocks, image, start['id']


def _image_url(img):
    """A mid-sized rendition from the image's own srcset (the full file is 2400px wide)."""
    for candidate in (img.get('srcset') or '').split(','):
        parts = candidate.split()
        if len(parts) == 2 and parts[1] == '500w':
            return parts[0]
    return img['data-src']


def find_date_block(blocks):
    """(index, date_line) of the block holding the show's dates: the line just above
    "Exhibition Dates". It is not always the first block of the section (on the Donors'
    Gallery page a title and subtitle come first). (None, None) if there isn't one."""
    for index, block in enumerate(blocks):
        lines = block.split('\n')
        for i in range(1, len(lines)):
            if lines[i].strip().lower() == 'exhibition dates':
                return index, lines[i - 1]
    return None, None


def dates_from_section(blocks, today):
    """(start, end) from the section's own date line."""
    _, date_line = find_date_block(blocks)
    return parse_date_text(date_line, today) if date_line else (None, None)


def description_from_section(blocks):
    """The first real paragraph block after the date block, skipping footer blocks."""
    date_index, _ = find_date_block(blocks)
    candidates = []
    for block in blocks[(date_index + 1 if date_index is not None else 0):]:
        if any(marker in block for marker in _FOOTER_MARKERS):
            continue
        text = ' '.join(block.split())
        if len(text) > 60:
            candidates.append(text)
    if not candidates:
        return None
    first = candidates[0] if len(candidates[0]) >= 200 else ' '.join(candidates[:2])
    return first[:1500]


def subtitle_for(soup, title):
    """The line under a show's title ("Six Artists Exploring Consciousness", "Abstract
    photography by ..."), which says what kind of show it is. The title sits in its own
    block, with the subtitle either on the next line or in the next block. None if the
    page has no such line."""
    texts = [el.get_text('\n', strip=True) for el in soup.find_all('div', class_='sqs-html-content')]
    wanted = ' '.join(title.lower().split())
    for index, text in enumerate(texts):
        lines = text.split('\n')
        if ' '.join(lines[0].lower().split()) != wanted:
            continue
        subtitle = ' '.join(lines[1:]) if len(lines) > 1 else (texts[index + 1] if index + 1 < len(texts) else '')
        subtitle = ' '.join(subtitle.split())
        if subtitle and len(subtitle) <= 120 and 'exhibition dates' not in subtitle.lower():
            return subtitle
    return None


def join_description(subtitle, paragraph):
    """Subtitle then paragraph as one text, with a full stop between them if needed."""
    if subtitle and paragraph:
        return f"{subtitle}{'' if subtitle.endswith(('.', '!', '?')) else '.'} {paragraph}"
    return subtitle or paragraph or None


def _valid(start, end):
    return bool(start and end and start <= end)


def pick_dates(list_dates, section_dates, title):
    """The section's own dates are preferred (the site's list lines go stale and the
    section can have typos, e.g. an end year before the start); falls back to the other."""
    if _valid(*section_dates):
        if _valid(*list_dates) and list_dates != section_dates:
            logging.warning(f"{VENUE}: dates for {title!r} differ (list {list_dates}, section {section_dates}); using the section's.")
        return section_dates
    if _valid(*list_dates):
        return list_dates
    return None, None


def parse_gallery_page(soup, page_url, today):
    """All shows on one gallery page as dicts (name, start, end, description, link, image)."""
    entries = parse_exhibit_list(soup)
    anchors = [anchor for _, _, anchor in entries]
    shows = []
    for date_text, title, anchor in entries:
        blocks, image, real_id = exhibit_section(soup, anchor, anchors)
        start, end = pick_dates(parse_date_text(date_text, today), dates_from_section(blocks, today), title)
        if not (start and end):
            logging.warning(f"{VENUE}: no readable dates for {title!r}; skipping")
            continue
        shows.append({
            'name': title,
            'start': start,
            'end': end,
            'description': join_description(subtitle_for(soup, title), description_from_section(blocks)),
            'link': f"{page_url}#{real_id}" if real_id else page_url,
            'image': image,
        })
    return shows


def scrape_art_works_downtown(env='prod', region='sf'):
    """Scrape current and upcoming exhibitions from Art Works Downtown (San Rafael)."""
    today = region_today(region)
    seen = set()
    for gallery, path in GALLERY_PAGES:
        url = BASE_URL + path
        soup = fetch_and_parse(url)
        if soup is None:
            # Deliberately loud: a failed run is the alert that the site changed or blocked us
            raise RuntimeError(f"{VENUE}: could not fetch {url}")
        for show in parse_gallery_page(soup, url, today):
            # A show spanning two galleries is listed on both pages; keep the first
            key = (show['name'].lower(), show['start'], show['end'])
            if key in seen:
                continue
            seen.add(key)

            phase = derive_phase(show['start'], show['end'], today) or 'current'
            event_details = {
                'name': show['name'],
                'venue': VENUE,
                'description': show['description'],
                'tags': ['exhibition', phase, 'gallery'],
                'phase': phase,
                'dates': {'start': show['start'], 'end': show['end']},
                'ongoing': False,
                'links': [{'link': show['link'], 'description': 'Event Page'}],
                'last_updated': dt.datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
            if show['image']:
                event_details['links'].append({'link': show['image'], 'description': 'Image'})

            if env == 'dev':
                logging.info(f"Event found: {show['name']} ({phase}, {show['start']} - {show['end']}) at {VENUE} [{gallery}]")
            if env == 'prod':
                process_event(event_details, region)
