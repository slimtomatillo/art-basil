"""Find a description for events whose scraper didn't supply one (WEBSITE-115).

The site's search reads each event's description (WEBSITE-39) and tagging reads it for subject tags, so an
event with none can only be found by its title, venue and tags. Scrapers that can read a blurb off the
listing should store it themselves (ADDING_A_REGION.md, 2b-ii). For the rest, main.py calls
enrich_missing_descriptions() after the scrapers have run: for each current or upcoming event with no
description it opens the event's own page and takes the best text there, in this order: the page's
structured data (JSON-LD), its share description (og:description, twitter:description), its meta
description, then its first real paragraphs.

A wrong blurb is worse than none, so a candidate must pass these checks:
- long enough to be a description (MIN_CHARS, MIN_WORDS), and not boilerplate (cookie banners, "all rights
  reserved", an error page);
- it mentions the show: one of the title's significant words appears in it, which a site-wide tagline
  ("The Gallery is a non-profit museum...") does not;
- it does not start with dates or a credit line ("October 23 - November 28", "Guest curator:", "Opening
  reception"), is not a run of names (a site-wide list of the gallery's artists), and is not a template
  ("Visit our website to learn more...");
- it is not the text the venue gives several different shows, which is its tagline and not their blurb
  (the same rule images.py applies to pictures).
Text is plain (entities decoded, whitespace collapsed) and cut to MAX_CHARS at a sentence boundary.

A description found is stored on the event with "description_source": "page", and
processing.keep_found_description keeps it when a scraper rewrites the event without one. "description_checked"
records the day an event was last looked at, so events with nothing to find are retried only every
RECHECK_AFTER, not daily. Sites fetched through the paid proxy are skipped (an extra page would cost credits).

Dry run on the real data, writing nothing:  python descriptions.py [region ...]
"""

import datetime as dt
import html
import json
import logging
import re
import sys
import unicodedata
from urllib.parse import urlparse

import utils
from config import DB_FILES
from manual_check import MANUAL_SOURCE
from scraper_health import ARCHIVE_SOURCE
from tagging import add_content_tags
from utils import fetch_and_parse, load_db, save_db

MIN_CHARS = 60
MIN_WORDS = 9
MAX_CHARS = 500
FIRST_SENTENCE_MIN = 120          # a cut at a sentence end is only taken past this length
RECHECK_AFTER = dt.timedelta(days=14)
MAX_PAGES_PER_RUN = 100           # keeps a run short; a backlog is cleared over a few days
WANTED_PHASES = ('current', 'future')
SKIP_SOURCES = (MANUAL_SOURCE, ARCHIVE_SOURCE)
SOURCE = 'page'                   # the value of "description_source" for a description found here

# Text that is the site's furniture, not a show's description
BOILERPLATE = re.compile(
    r'cookie|javascript|enable js|all rights reserved|privacy policy|terms (?:of|and) (?:use|service|conditions)'
    r'|page not found|\b404\b|skip to (?:main )?content|subscribe to our|sign up for (?:our|the)|log ?in to'
    r'|lorem ipsum|click here|read more\s*$|^home\b|^menu\b'
    r'|visit our website|^(?:visit|browse|learn more|find out more|more information|see more)\b'
    r'|create a (?:website )?account|manage notification|^this page (?:highlights|features|describes)', re.IGNORECASE)
# Event information set in the text ("Opening Reception: Saturday, October 31", "12 novembre – 19 décembre 2026")
EVENT_INFO = re.compile(r'\b(?:opening|closing|artists?\W?s?)\s+(?:reception|celebration|night)\s*:', re.IGNORECASE)
# A line that starts with a date ("October 23 - November 28, 2026", "15 octobre", "12.11.2026", "Through March 3")
_MONTHS = (r'jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?'
           r'|nov(?:ember)?|dec(?:ember)?|janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre'
           r'|ocak|subat|nisan|mayis|haziran|temmuz|agustos|eylul|ekim|kasim|aralik')
DATE_RANGE = re.compile(
    rf'\b\d{{1,2}}(?:er)?\s+(?:{_MONTHS})\b\.?\s*[–—-]\s*\d{{1,2}}(?:er)?\s+(?:{_MONTHS})\b'
    rf'|\b(?:{_MONTHS})\b\.?\s*\d{{1,2}}\s*[–—-]\s*(?:(?:{_MONTHS})\b\.?\s*)?\d{{1,2}}', re.IGNORECASE)
DATE_START = re.compile(
    rf'^(?:(?:through|until|on view|opens?|opened|from|du|au|jusqu\W?au)\s+)?(?:\d{{1,2}}(?:st|nd|rd|th|er)?\s+)?(?:{_MONTHS})\b'
    r'|^\d{1,2}[./-]\d{1,2}[./-]\d{2,4}', re.IGNORECASE)
# Credits, visitor information and the like that sit among a page's paragraphs
CREDIT_LINE = re.compile(
    r'^(?:guest\s+)?(?:curators?|curated by|organi[sz]ed by|production|produced by|vernissage|sponsors?|sponsored by|photo(?:graph)?s? by'
    r'|image(?: credit)?|courtesy|(?:artists?\W?s?\s+|opening\s+|closing\s+)?reception|hours|admission|free admission|tickets)\b',
    re.IGNORECASE)
# Dimensions with a unit ("8.125 × 10 in.", "50x58 inches", "30 x 40 cm"): a caption, never a description
DIMENSIONS = re.compile(r'\b\d+(?:[.,]\d+)?\s*[x×]\s*\d+(?:[.,]\d+)?(?:\s*[x×]\s*\d+(?:[.,]\d+)?)?\s*(?:inches|inch|in|cm|mm)\b', re.IGNORECASE)
# A short line that ends with a year ("..., 2021"): an artwork's caption
ENDS_WITH_YEAR = re.compile(r'\b(?:1[89]|20)\d\d\W*$')
# An artwork's caption: its size or medium and support ("50x58 inches, oil/canvas", "oil on linen")
CAPTION = re.compile(
    r'\b\d+(?:[.,]\d+)?\s*[x×]\s*\d+(?:[.,]\d+)?(?:\s*[x×]\s*\d+(?:[.,]\d+)?)?\s*(?:inches|inch|in\.|cm|mm)\b'
    r'|\b(?:oil|acrylic|gouache|ink|watercolou?r|graphite|charcoal|pigment print|gelatin silver)\b[^.]{0,40}\b(?:on|/)\s*(?:canvas|paper|linen|panel|wood|board)\b',
    re.IGNORECASE)
# Words in a title too common to show that a text is about this show
TITLE_STOPWORDS = {
    'exhibition', 'exhibitions', 'gallery', 'galleries', 'museum', 'present', 'presents', 'opening', 'closing',
    'solo', 'group', 'show', 'shows', 'works', 'art', 'arts', 'contemporary', 'new', 'with', 'from', 'this',
    'that', 'the', 'and', 'for', 'into', 'about', 'untitled',
}
_NOT_IN_BODY = ['nav', 'header', 'footer', 'aside', 'form', 'script', 'style', 'noscript', 'figcaption']


def fold(text):
    """Lower case without accents."""
    return unicodedata.normalize('NFKD', text or '').encode('ascii', 'ignore').decode().lower()


def clean(text):
    """Plain text: entities decoded, odd spaces and zero-width characters dropped, whitespace collapsed."""
    if not isinstance(text, str):
        return ''
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub('[\u200b\u200c\u200d\ufeff]', '', text).replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return re.sub(r'\s+([,.;:!?])', r'\1', text)          # "Books , LONG" (a link's text set in its own spaces)


def trim(text, limit=MAX_CHARS):
    """At most `limit` characters, cut at a sentence end when there is one past FIRST_SENTENCE_MIN, else at a word."""
    if len(text) <= limit:
        return text
    head = text[:limit]
    ends = [m.end() for m in re.finditer(r'[.!?][)"”’\']?(?=\s)', head) if m.end() >= FIRST_SENTENCE_MIN]
    if ends:
        return head[:ends[-1]].strip()
    return head[:head.rfind(' ')].rstrip(' ,;:-–—') + '…'


def title_words(name):
    """The words of a title that would show a text is about it: 4+ letters, not a stop word."""
    return {w for w in re.findall(r'[a-z0-9]{4,}', fold(name)) if w not in TITLE_STOPWORDS}


def mentions_show(text, name):
    """Whether the text uses a significant word of the title (a title with none, like "Untitled", can't be checked)."""
    words = title_words(name)
    if not words:
        return True
    body = set(re.findall(r'[a-z0-9]+', fold(text)))
    return bool(words & body)


def strip_title_heading(text, name):
    """Drop the show's title when it only heads the text ("Après la pluie : Transforming..."), not when the
    sentence runs on from it ("Joey Terrill: Homeboy Beautiful is the first retrospective...")."""
    match = re.match(r'(.{3,200}?)\s*[:–—|]\s+', text)
    if match and fold(match.group(1)).strip() == fold(name).strip():
        return text[match.end():]
    return text


def looks_like_a_list(text):
    """A run of capitalised names (a site-wide list of the gallery's artists), not a description."""
    words = re.findall(r'[^\W\d_]+', text)
    return len(words) >= 12 and sum(1 for w in words if w[0].isupper()) / len(words) > 0.6


# A sentence of ticketing or visitor information that opens a page's text ("Purchasing Museum admission grants full
# access to all exhibitions on the selected day.")
FURNITURE_SENTENCE = re.compile(r'\b(?:purchasing|admission grants|buy tickets|book (?:your )?tickets|free with (?:museum )?admission)\b', re.IGNORECASE)


def first_sentence(text):
    match = re.match(r'(.+?[.!?])(?:\s|$)', text)
    return match.group(1) if match else text


def strip_opening_furniture(text):
    """Drop leading sentences that are ticketing information."""
    while True:
        first = first_sentence(text)
        if text and FURNITURE_SENTENCE.search(first):         # a paragraph that is only that sentence becomes empty
            text = text[len(first):].lstrip()
        else:
            return text


def furniture_line(line):
    """A line that is a date, a credit or visitor information, or an artwork's caption, not description."""
    folded = fold(line).strip()
    return (len(folded) < 25 or bool(DATE_START.match(folded) or CREDIT_LINE.match(folded) or CAPTION.search(line))
            or (len(line) < 200 and bool(ENDS_WITH_YEAR.search(line))))


def usable(text, name):
    """Whether a candidate is long enough, not boilerplate, and about this show."""
    if len(text) < MIN_CHARS or len(text.split()) < MIN_WORDS:
        return False
    if BOILERPLATE.search(text) or looks_like_a_list(text) or DIMENSIONS.search(text):
        return False
    if EVENT_INFO.search(text) or DATE_RANGE.search(fold(text[:120])):     # event details run into the text
        return False
    if text.count(' | ') >= 2:                                   # a menu bar: "ABOUT | ARTISTS | VIRTUAL TOUR"
        return False
    if text[0].islower():                                         # a fragment (a subtitle, the rest of a sentence)
        return False
    if len(text) < 120 and not re.search(r'[.!?]', text):         # a title or a tagline, not a sentence
        return False
    if len(text) < 200 and ENDS_WITH_YEAR.search(text):           # a caption
        return False
    folded = fold(text).strip()
    if DATE_START.match(folded) or CREDIT_LINE.match(folded):
        return False
    if folded.strip(' .') == fold(name).strip(' .'):
        return False
    return mentions_show(text, name)


def _json_ld_descriptions(soup):
    """Descriptions of Event / Exhibition items in the page's JSON-LD, if any."""
    found = []

    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            kind = node.get('@type')
            kinds = kind if isinstance(kind, list) else [kind]
            if any(isinstance(k, str) and ('Event' in k or 'Exhibition' in k) for k in kinds):
                if isinstance(node.get('description'), str):
                    found.append(node['description'])
            for value in node.values():
                if isinstance(value, (list, dict)):
                    walk(value)

    for tag in soup.find_all('script', type='application/ld+json'):
        try:
            walk(json.loads(tag.string or tag.get_text() or ''))
        except ValueError:
            continue
    return found


def _meta(soup, **attrs):
    tag = soup.find('meta', attrs=attrs)
    return tag.get('content') if tag and tag.get('content') else None


def _paragraphs(soup):
    """The page's first substantial paragraphs, from its main content: up to two, until there are 200 characters."""
    root = soup.find('main') or soup.find('article') or soup.body or soup
    parts = []
    for p in root.find_all('p'):
        if p.find_parent(_NOT_IN_BODY):
            continue
        # a paragraph can hold a caption or credit lines set apart by line breaks (<br>, not other tags: a name in a
        # link is part of its sentence): keep only the prose
        for br in p.find_all('br'):
            br.replace_with('\n')
        lines = [clean(line) for line in p.get_text(' ').split('\n')]
        text = strip_opening_furniture(' '.join(line for line in lines if line and not furniture_line(line)))
        if len(text) < 60 or len(text.split()) < 9 or BOILERPLATE.search(text):
            continue
        parts.append(text)
        if len(' '.join(parts)) >= 200 or len(parts) == 2:
            break
    return [' '.join(parts)] if parts else []


def candidates(soup):
    """[(source, text)] in the order they are tried."""
    found = [('jsonld', t) for t in _json_ld_descriptions(soup)]
    found += [('og', _meta(soup, property='og:description')),
              ('twitter', _meta(soup, name='twitter:description')),
              ('meta', _meta(soup, name='description'))]
    found += [('paragraph', t) for t in _paragraphs(soup)]
    return [(source, clean(text)) for source, text in found if text]


def find_event_description(page_url, name, fetch=fetch_and_parse):
    """(text, source) for the best usable description on an event's page, or None."""
    if not page_url or urlparse(page_url).netloc in utils.PROXY_DOMAINS:
        return None
    soup = fetch(page_url)
    if soup is None:
        return None
    for source, text in candidates(soup):
        text = strip_opening_furniture(strip_title_heading(text, name))
        if usable(text, name):
            return trim(text), source
    return None


def event_page(event):
    return next((l['link'] for l in event.get('links', [])
                 if l.get('description') == 'Event Page' and l.get('link')), None)


def needs_description(event, today):
    if event.get('phase') not in WANTED_PHASES or event.get('source') in SKIP_SOURCES:
        return False
    if event.get('description') or not event_page(event):
        return False
    checked = event.get('description_checked')
    if checked:
        try:
            if today - dt.date.fromisoformat(checked) < RECHECK_AFTER:
                return False
        except ValueError:
            pass
    return True


def _same(a, b):
    return re.sub(r'\W+', ' ', fold(a)).strip() == re.sub(r'\W+', ' ', fold(b)).strip()


def _without_shared_openings(found, stored):
    """found: [(event, text, source)]. A first sentence that opens two or more of the venue's descriptions (found
    now or already stored) is removed from the found ones; a text left too short to be a description is dropped."""
    norm = lambda text: re.sub(r'\W+', ' ', fold(first_sentence(text))).strip()
    counts = {}
    for text in [t for _, t, _ in found] + list(stored):
        counts[norm(text)] = counts.get(norm(text), 0) + 1
    kept = []
    for event, text, source in found:
        first = first_sentence(text)
        if first != text and counts[norm(text)] >= 2:
            text = text[len(first):].lstrip()
            if len(text) < MIN_CHARS or len(text.split()) < MIN_WORDS:
                continue
        kept.append((event, text, source))
    return kept


def enrich_missing_descriptions(regions=None, today=None, finder=find_event_description,
                                max_pages=MAX_PAGES_PER_RUN, save=True):
    """Give description-less current and upcoming events a description from their own page.

    Returns {'checked': pages opened, 'added': [(region, venue, event name, source, text)],
             'dropped': [(region, venue, event name, text)], 'shared': pages several shows point at}.
    `dropped` lists texts rejected because the venue gives the same one to several shows (a tagline).
    `shared` counts events skipped because their "Event Page" is a listing page that other shows also use:
    its text can't be told apart per show."""
    today = today or dt.date.today()
    report = {'checked': 0, 'added': [], 'dropped': [], 'shared': 0}
    for region in (regions or DB_FILES):
        db = load_db(DB_FILES[region])
        changed = False
        for venue, events in db.items():
            if report['checked'] >= max_pages:
                break
            uses = {}
            for event in events.values():
                uses[event_page(event)] = uses.get(event_page(event), 0) + 1
            found = []                                      # (event, text, source)
            for event in events.values():
                if not needs_description(event, today):
                    continue
                if uses[event_page(event)] > 1:
                    report['shared'] += 1
                    continue
                if report['checked'] >= max_pages:
                    break
                report['checked'] += 1
                result = finder(event_page(event), event['name'])
                event['description_checked'] = today.isoformat()
                changed = True
                if result:
                    found.append((event, *result))
            # A sentence that opens several of a venue's descriptions is the site's, not the show's: drop it
            found = _without_shared_openings(found, [e['description'] for e in events.values() if e.get('description')])
            # The same text for several of a venue's shows is its tagline, not their descriptions
            in_use = [e['description'] for e in events.values() if e.get('description')]
            for event, text, source in found:
                shared = sum(1 for _, t, _ in found if _same(t, text)) + sum(1 for t in in_use if _same(t, text))
                if shared >= 2:
                    report['dropped'].append((region, venue, event['name'], text))
                    continue
                event['description'] = text
                event['description_source'] = SOURCE
                add_content_tags(event)                     # subject tags (photography, ceramics...) from the new text
                report['added'].append((region, venue, event['name'], source, text))
        if changed and save:
            save_db(db, region)
    return report


def main(argv):
    logging.basicConfig(level=logging.WARNING, format='%(levelname)s - %(message)s')
    regions = argv or None
    report = enrich_missing_descriptions(regions, save=False, max_pages=10_000)
    for region, venue, name, source, text in report['added']:
        print(f"[{region}] {venue}: {name}\n    ({source}) {text}\n")
    for region, venue, name, text in report['dropped']:
        print(f"[{region}] DROPPED (shared by several shows) {venue}: {name}\n    {text[:120]}\n")
    print(f"opened {report['checked']} pages, found {len(report['added'])}, dropped {len(report['dropped'])}, "
          f"skipped {report['shared']} events on shared listing pages")


if __name__ == '__main__':
    main(sys.argv[1:])
