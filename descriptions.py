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

Shows that are listed together on one page (their "Event Page" is that listing, as at most galleries) are looked
up through their cards (WEBSITE-117): images.card_links finds each show's own page from the card that holds its
title, strictly (a link around the title, or one whose text or address uses a word of the title, or the card's
only link, on the venue's own site), and that page is read like any event page. The event's stored "Event Page"
link is left as the scraper wrote it; only the description is taken from the show's own page.

Dry run on the real data, writing nothing:  python descriptions.py [--proxy] [region ...]
(paid-proxy pages, which cost credits, are only fetched with --proxy, and then at most PROXY_PAGES_PER_RUN)
"""

import datetime as dt
import html
import json
import logging
import re
import sys
from urllib.parse import urlparse

from bs4 import BeautifulSoup

import utils
from config import DB_FILES
from textmatch import fold, title_words
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
# Paid-proxy sites (utils.PROXY_DOMAINS) cost ZenRows credits, so only this many of their pages are fetched in a run
# (WEBSITE-118): at most about 100 credits a run, and the cheapest pages first. A backlog of 70 pages clears in about
# two and a half weeks; after that only newly listed shows are fetched. Set it to 0 to switch proxied pages off.
PROXY_PAGES_PER_RUN = 4
# A text that never uses a word of the show's title is only accepted if it is at least this long and does not name the
# venue near its start (WEBSITE-119): a show's blurb often shares no word with a title like "Spotlight" or "Neighbours",
# while a site-wide tagline almost always opens with the venue's name.
NO_TITLE_MIN_CHARS = 150
VENUE_HEAD_CHARS = 160
# Paid-proxy hosts whose event pages have no description in the HTML the proxy returns (checked 2026-11-13): fetching them
# would spend credits for nothing. Galerie Simon Blais builds its pages from blocks with no text we can tell apart.
PROXIED_WITHOUT_TEXT = {'galeriesimonblais.com'}
# The proxy cannot be tried from outside CI, so a failure is treated as a possible systematic fault (a refused setting, a
# block): after this many failed fetches in a row the proxied pass stops for the run, and the failed pages are not stamped
# as looked at, so they are asked for again next run. That caps the loss at a couple of pages a day.
PROXY_FAILURES_BEFORE_STOP = 2
FETCH_FAILED = object()                   # what find_proxied_description returns when the page could not be fetched
WANTED_PHASES = ('current', 'future')
SKIP_SOURCES = (MANUAL_SOURCE, ARCHIVE_SOURCE)
SOURCE = 'page'                   # the value of "description_source" for a description found here

# Text that is the site's furniture, not a show's description
BOILERPLATE = re.compile(
    r'cookie|javascript|enable js|all rights reserved|privacy policy|terms (?:of|and) (?:use|service|conditions)'
    r'|page not found|\b404\b|skip to (?:main )?content|subscribe to our|sign up for (?:our|the)|log ?in to'
    r'|lorem ipsum|click here|read more\s*$|^home\b|^menu\b'
    r'|visit our website|^(?:visit|browse|learn more|find out more|more information|see more)\b'
    r'|create a (?:website )?account|manage notification|^this page (?:highlights|features|describes)'
    r'|^(?:(?:in[- ]person|online|virtual|hybrid)\s+)?rsvp\b'                  # a program announcement, not the show
    r'|^this\s+(?:[\w-]+\s+){0,3}(?:conversation|talk|panel|lecture|workshop|tour|screening|walk-?through)\b'
    r'|^(?:join us|in conversation|artist talk|panel discussion)\b'                   # an invitation to an event, not the show
    # a gallery describing itself ("Roberts Projects is Los Angeles-based contemporary art gallery representing artists...")
    r'|\brepresent(?:ing|s)\s+(?:artists|a\s+(?:roster|group))'
    r'|\bis\s+(?:an?|the)\b(?:\s+[\w,-]+){0,6}\s+(?:gallery|museum|cent(?:er|re)|institution|foundation|space for)\b'
    r'|\bcarousel\b|^find out about\b', re.IGNORECASE)
# Event information set in the text ("Opening Reception: Saturday, October 31", "12 novembre – 19 décembre 2026")
EVENT_INFO = re.compile(r'\b(?:opening|closing|artists?\W?s?)\s+(?:reception|celebration|night)\s*:', re.IGNORECASE)
# A line that starts with a date ("October 23 - November 28, 2026", "15 octobre", "12.11.2026", "Through March 3")
_MONTHS = (r'jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?'
           r'|nov(?:ember)?|dec(?:ember)?|janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre'
           r'|ocak|subat|nisan|mayis|haziran|temmuz|agustos|eylul|ekim|kasim|aralik')
DATE_RANGE = re.compile(
    rf'\b(?:{_MONTHS})\b\.?\s+\d{{1,2}},?\s+\d{{4}}\s*[–—-]\s*(?:(?:{_MONTHS})\b\.?\s+\d{{1,2}},?\s+\d{{4}}|ongoing|present)'   # March 1, 2027 – March 31, 2028
    rf'|\b\d{{1,2}}(?:er)?\s+(?:{_MONTHS})\b\.?\s*[–—-]\s*\d{{1,2}}(?:er)?\s+(?:{_MONTHS})\b'
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
FURNITURE_SENTENCE = re.compile(
    r'\b(?:purchasing|admission grants|buy tickets|book (?:your )?tickets|free with (?:museum )?admission'
    r'|courtesy of|production still|still from|installation view|photo(?:graph)? (?:by|credit)|image credit)\b', re.IGNORECASE)


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


def names_the_venue(text, venue):
    """Whether the start of a text names the venue: the whole name, or one of its significant words ("Mercer Union is a
    non-profit...", "Fonderie Darling in Montreal is a space..."). A show's blurb rarely opens that way, a tagline always."""
    if not venue:
        return False
    head = fold(text[:VENUE_HEAD_CHARS])
    return fold(venue).strip() in head or bool(title_words(venue) & set(re.findall(r'[a-z0-9]{4,}', head)))


def usable(text, name, venue=None):
    """Whether a candidate is long enough, not boilerplate, and about this show."""
    if len(text) < MIN_CHARS or len(text.split()) < MIN_WORDS:
        return False
    if BOILERPLATE.search(text) or looks_like_a_list(text) or DIMENSIONS.search(text):
        return False
    # (the raw text too: folding a text drops its en dashes, and French months only match once the accents are gone)
    if EVENT_INFO.search(text) or DATE_RANGE.search(text[:120]) or DATE_RANGE.search(fold(text[:120])):   # event details run into the text
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
    if mentions_show(text, name):
        return True
    # It never uses a word of the title. Without the venue we cannot tell it from a tagline; with it, a long text that
    # does not open by naming the venue is the show's own.
    return bool(venue) and len(text) >= NO_TITLE_MIN_CHARS and not names_the_venue(text, venue)


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


def _in_site_chrome(p, strict):
    """Whether a paragraph sits in navigation, a footer, a form, a caption... With `strict` any <header> counts too;
    otherwise only a site header (one that holds a navigation menu), since some pages put the exhibition's own text
    in a <header> block."""
    if p.find_parent(['nav', 'footer', 'aside', 'form', 'script', 'style', 'noscript', 'figcaption']):
        return True
    # a photo caption or credit, by the class of its container or of the paragraph itself (the Cantor's pages
    # put a caption paragraph before the text)
    caption = re.compile(r'caption|credit', re.IGNORECASE)
    if p.find_parent(class_=caption) is not None or any(caption.search(c) for c in (p.get('class') or [])):
        return True
    header = p.find_parent('header')
    return bool(header is not None and (strict or header.find('nav')))


def _prose_paragraphs(root, strict):
    """The first substantial paragraphs under `root`: up to two, until there are 200 characters."""
    parts = []
    for p in root.find_all('p'):
        if _in_site_chrome(p, strict):
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


def _paragraphs(soup):
    """The page's first substantial paragraphs, from its main content. If that has none (a page whose <article> is
    not where the exhibition text is, or whose text sits in a <header> block, as at the Image Centre), the whole
    page is tried, still leaving out navigation, footers and site headers."""
    root = soup.find('main') or soup.find('article') or soup.body or soup
    found = _prose_paragraphs(root, strict=True)
    if not found and root is not (soup.body or soup):
        found = _prose_paragraphs(soup.body or soup, strict=False)
    elif not found:
        found = _prose_paragraphs(root, strict=False)
    return found


def _ago_body(soup):
    """AGO's exhibition text. Its pages have no description meta tag, structured data or paragraphs: the text is the first
    long `field--name-body` block inside `.node__content` (the membership promo is in `.postcard-desc`, which is not),
    often headed "Exhibition Overview" or "About the Exhibition"."""
    found = []
    for div in soup.find_all('div'):
        if not any('field--name-body' in c for c in (div.get('class') or [])):
            continue
        if 'node__content' not in ((div.parent.get('class') or []) if div.parent is not None else []):
            continue
        text = clean(div.get_text(' '))
        text = re.sub(r'^(?:exhibition overview|about (?:the|this) exhibition|overview)\s+', '', text, flags=re.IGNORECASE)
        if len(text) >= 150:
            found.append(text)
    return found[:1]


# Sites whose text is in none of the usual places: host -> function(soup) giving the texts to try, best first
SITE_EXTRACTORS = {'ago.ca': _ago_body}


def feed_description(text):
    """A description from text that a venue's own feed or API supplies for a show, as HTML or as markdown-ish text
    (WEBSITE-119: the California African American Museum's feed and Daniel Faria's API carry the whole show text, so
    the scrapers can store it and nothing needs fetching): its first one or two prose paragraphs, plain, at most
    MAX_CHARS, or None. The venue wrote it for this show, so the rules for what is not prose apply (dates, credits,
    captions, boilerplate), but not the ones that guard against a scraped page's site-wide text."""
    if not isinstance(text, str) or not text.strip():
        return None
    if not re.search(r'<p[\s>]', text, re.IGNORECASE):
        # markdown-ish text. It can still hold a stray tag (CAAM's has a leftover </iframe> and <A HREF> links), so it is
        # judged by having no paragraph tags, not by having no "<" at all
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)                      # [label](address) -> label
        text = re.sub(r'^#+\s*', '', text.replace('*', ''), flags=re.MULTILINE)       # emphasis and heading marks
        text = ''.join(f'<p>{html.escape(par.strip())}</p>' for par in re.split(r'\n\s*\n', text) if par.strip())
    found = _prose_paragraphs(BeautifulSoup(text, 'html.parser'), strict=False)
    return trim(found[0]) if found else None


def candidates(soup, page_url=None):
    """[(source, text)] in the order they are tried."""
    found = [('jsonld', t) for t in _json_ld_descriptions(soup)]
    found += [('og', _meta(soup, property='og:description')),
              ('twitter', _meta(soup, name='twitter:description')),
              ('meta', _meta(soup, name='description'))]
    extractor = SITE_EXTRACTORS.get(urlparse(page_url).netloc) if page_url else None
    if extractor:
        found += [('site', t) for t in extractor(soup)]
    found += [('paragraph', t) for t in _paragraphs(soup)]
    return [(source, clean(text)) for source, text in found if text]


def find_event_description(page_url, name, fetch=fetch_and_parse, allow_proxy=False, venue=None):
    """(text, source) for the best usable description on an event's page, or None.

    A page on a paid-proxy site is only fetched with `allow_proxy` (it costs credits: see proxy_credits)."""
    if not page_url:
        return None
    if urlparse(page_url).netloc in utils.PROXY_DOMAINS and not allow_proxy:
        return None
    soup = fetch(page_url)
    if soup is None:
        return None
    found = [(source, strip_opening_furniture(strip_title_heading(text, name))) for source, text in candidates(soup, page_url)]
    for source, text in found:                              # the strict rule first, over every candidate, as it always was
        if usable(text, name):
            return trim(text), source
    # Nothing named the show. A long text that does not open by naming the venue is accepted instead, but only on a page that
    # is itself about the show: on a listing of several shows the first paragraph can belong to another one (Sprüth Magers'
    # /exhibitions page gave a paragraph about a different artist).
    if venue and page_is_about(soup, page_url, name):
        for source, text in found:
            if usable(text, name, venue):
                return trim(text), source
    return None


def page_is_about(soup, page_url, name):
    """Whether the page itself is about the show: a significant word of its title is in the page's address, its <title>,
    its first heading or its share title (substring, so "spotlight" matches /spotlights/)."""
    words = title_words(name)
    if not words:
        return True
    heading = soup.find('h1')
    share = _meta(soup, property='og:title')
    haystack = fold(' '.join([urlparse(page_url or '').path, soup.title.get_text(' ') if soup.title else '',
                              heading.get_text(' ') if heading else '', share or '']))
    return any(word in haystack for word in words)


def find_proxied_description(page_url, name, venue=None):
    """find_event_description for a page on a paid-proxy site, fetched through the proxy. Returns FETCH_FAILED when the
    page could not be fetched at all (as opposed to None: fetched, but nothing usable on it)."""
    failed = []

    def fetch(url):
        soup = fetch_and_parse(url)
        if soup is None:
            failed.append(url)
        return soup

    result = find_event_description(page_url, name, fetch=fetch, allow_proxy=True, venue=venue)
    return FETCH_FAILED if result is None and failed else result


def proxy_credits(page_url):
    """The ZenRows credits one fetch of this page costs: 25 with JavaScript rendering, 10 without (OPERATIONS.md)."""
    params = utils.PROXY_DOMAINS.get(urlparse(page_url or '').netloc) or {}
    return 25 if params.get('js_render') else 10


def find_card_descriptions(page_url, titles, fetch=fetch_and_parse, venue=None):
    """({title: (text, source)}, pages opened) for the shows of a listing page that several events point to.

    Each show's own page is found from its card on the listing, then read like an event page. `titles` are all the
    shows listed on that page (a card is told apart from the others by their titles)."""
    import images                                           # images.py is the home of the card-finding; it imports nothing from here
    if not page_url or urlparse(page_url).netloc in utils.PROXY_DOMAINS:
        return {}, 0
    soup = fetch(page_url)
    if soup is None:
        return {}, 1
    links = images.card_links(soup, page_url, titles)
    found = {}
    for title, url in links.items():
        result = find_event_description(url, title, fetch=fetch, venue=venue)
        if result:
            found[title] = result
    return found, 1 + len(links)


def event_page(event):
    return next((l['link'] for l in event.get('links', [])
                 if l.get('description') == 'Event Page' and l.get('link')), None)


def stamp_key(page_url):
    """Which field records the day a page was last looked at. A paid-proxy page has its own, "description_proxy_checked":
    before WEBSITE-118 the pass stamped proxied events "checked" without fetching anything, and those stamps must not hide
    them now."""
    return 'description_proxy_checked' if urlparse(page_url or '').netloc in utils.PROXY_DOMAINS else 'description_checked'


def needs_description(event, today):
    if event.get('phase') not in WANTED_PHASES or event.get('source') in SKIP_SOURCES:
        return False
    if event.get('description') or not event_page(event):
        return False
    checked = event.get(stamp_key(event_page(event)))
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


def _accept(report, region, venue, events, found):
    """Store the descriptions found for a venue's events, after the checks that look at the venue as a whole:
    a first sentence that opens several of its descriptions is the site's, not the show's (cut), and the same text
    for several shows is its tagline (dropped). found: [(event, text, source)]."""
    found = _without_shared_openings(found, [e['description'] for e in events.values() if e.get('description')])
    in_use = [e['description'] for e in events.values() if e.get('description')]
    for event, text, source in found:
        shared = sum(1 for _, t, _ in found if _same(t, text)) + sum(1 for t in in_use if _same(t, text))
        if shared >= 2:
            report['dropped'].append((region, venue, event['name'], text))
            continue
        event['description'] = text
        event['description_source'] = SOURCE
        add_content_tags(event)                         # subject tags (photography, ceramics...) from the new text
        report['added'].append((region, venue, event['name'], source, text))


def enrich_missing_descriptions(regions=None, today=None, finder=find_event_description,
                                card_finder=find_card_descriptions, proxy_finder=find_proxied_description,
                                max_pages=MAX_PAGES_PER_RUN, proxy_pages=PROXY_PAGES_PER_RUN, save=True):
    """Give description-less current and upcoming events a description from their own page.

    An event with a page of its own is looked up with `finder(page_url, name, venue=venue)`. Several events that share one
    listing page are looked up together with `card_finder(page_url, titles, venue=venue)`, which returns
    ({title: (text, source)}, pages opened): each show's own page found from its card on the listing.

    An event on a paid-proxy site costs credits, so those are left to the end and only `proxy_pages` of them are
    fetched in a run, the cheapest first (`proxy_finder(page_url, name, venue=venue)`); the regular scrape has had its credits by
    then, and the pass stops at the first "out of credits" answer (utils.PROXY_EXHAUSTED). Proxied events on a
    listing that several shows share are not looked up.

    Returns {'checked': pages opened, 'added': [(region, venue, event name, source, text)],
             'dropped': [(region, venue, event name, text)], 'shared': events looked up on shared listing pages,
             'proxied': proxied pages fetched, 'credits': the credits those cost (an estimate), 'failed': proxied
             pages that could not be fetched}.
    The page limit is checked before each page or listing, so a listing's own show pages can go a little over it."""
    today = today or dt.date.today()
    report = {'checked': 0, 'added': [], 'dropped': [], 'shared': 0, 'proxied': 0, 'credits': 0, 'failed': 0}
    dbs, changed, queue = {}, set(), []
    for region in (regions or DB_FILES):
        dbs[region] = load_db(DB_FILES[region])
        for venue, events in dbs[region].items():
            groups = {}                                     # event page -> every event of the venue that points at it
            for event in events.values():
                groups.setdefault(event_page(event), []).append(event)
            found = []                                      # (event, text, source)
            for page, group in groups.items():
                needing = [e for e in group if needs_description(e, today)]
                if not needing:
                    continue
                if len(group) == 1 and urlparse(page).netloc in utils.PROXY_DOMAINS:
                    if urlparse(page).netloc not in PROXIED_WITHOUT_TEXT:
                        queue.append((region, venue, needing[0], page))
                    continue
                if report['checked'] >= max_pages:
                    continue
                if len(group) == 1:
                    event = needing[0]
                    report['checked'] += 1
                    result = finder(page, event['name'], venue=venue)
                    if result:
                        found.append((event, *result))
                else:
                    by_title, opened = card_finder(page, [e['name'] for e in group], venue=venue)
                    report['checked'] += max(opened, 1)
                    report['shared'] += len(needing)
                    found.extend((e, *by_title[e['name']]) for e in needing if e['name'] in by_title)
                for event in needing:
                    event['description_checked'] = today.isoformat()
                changed.add(region)
            _accept(report, region, venue, events, found)

    # Paid-proxy pages, last: cheapest first, a few a run, and none once the account is out of credits
    queue.sort(key=lambda item: (proxy_credits(item[3]), item[0], item[1], item[2]['name']))
    proxied, failures = {}, 0
    for region, venue, event, page in queue[:max(proxy_pages, 0)]:
        if utils.PROXY_EXHAUSTED:
            break
        report['proxied'] += 1
        report['credits'] += proxy_credits(page)
        result = proxy_finder(page, event['name'], venue=venue)
        if utils.PROXY_EXHAUSTED and not result:
            break                                           # out of credits, not "nothing there": ask again next run
        if result is FETCH_FAILED:                          # not stamped: asked for again next run
            report['failed'] += 1
            failures += 1
            if failures >= PROXY_FAILURES_BEFORE_STOP:
                break
            continue
        failures = 0
        event['description_proxy_checked'] = today.isoformat()
        changed.add(region)
        if result:
            proxied.setdefault((region, venue), []).append((event, *result))
    for (region, venue), found in proxied.items():
        _accept(report, region, venue, dbs[region][venue], found)

    if save:
        for region in changed:
            save_db(dbs[region], region)
    return report


def main(argv):
    logging.basicConfig(level=logging.WARNING, format='%(levelname)s - %(message)s')
    use_proxy = '--proxy' in argv
    regions = [a for a in argv if a != '--proxy'] or None
    report = enrich_missing_descriptions(regions, save=False, max_pages=10_000,
                                         proxy_pages=PROXY_PAGES_PER_RUN if use_proxy else 0)
    for region, venue, name, source, text in report['added']:
        print(f"[{region}] {venue}: {name}\n    ({source}) {text}\n")
    for region, venue, name, text in report['dropped']:
        print(f"[{region}] DROPPED (shared by several shows) {venue}: {name}\n    {text[:120]}\n")
    print(f"opened {report['checked']} pages, found {len(report['added'])}, dropped {len(report['dropped'])}, "
          f"looked up {report['shared']} events on shared listing pages through their cards; "
          f"{report['proxied']} proxied pages (about {report['credits']} credits, {report['failed']} failed)")


if __name__ == '__main__':
    main(sys.argv[1:])
