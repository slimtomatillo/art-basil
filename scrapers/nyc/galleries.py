"""New York's established commercial galleries (WEBSITE-121, tier 3): one reader for many gallery sites.

Most of these galleries' sites list their shows as cards on one page (what is on, what is coming, then an archive),
and a card carries the same few lines in the same order: the artist, the show's title, sometimes a place, and the run
("November 6 – December 19, 2026"). A card is read as the lines of text in it: the first line that is a date run is the
dates, the lines above it are the name (minus an address, a city and the like), and the lines below it are ignored
(a description, "Read more"). A show whose dates are over is dropped by publish(), so a page that also lists its
archive costs nothing.

Several galleries show in other cities too (Lisson, Marian Goodman, Lehmann Maupin, Fergus McCaffrey, Skarstedt...): a
card that names another city, or an address that is not the gallery's, is left out. A gallery with several New York
spaces gives each as (label, address) and a show is stored with the labels of the spaces its card names (WEBSITE-122).

A gallery is a Spec: where its listing is, how to find its cards (`cards`), and what to leave out. SPECS holds them all and
SCRAPERS the function main.py runs for each.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Optional
from urllib.parse import urljoin

from processing import region_today
from scrapers.la._gallery import join_name
from scrapers.nyc._common import card_picture, clean, parse_dates, title_case
from scrapers.tor._common import publish
from utils import fetch_and_parse

REGION = 'nyc'

# Cities and places that are not New York: a card that names one is another city's show.
OTHER_PLACES = (
    'london', 'paris', 'los angeles', 'seoul', 'shanghai', 'hong kong', 'tokyo', 'beijing', 'berlin', 'rome', 'geneva',
    'zurich', 'basel', 'palm beach', 'east hampton', 'aspen', 'miami', 'brussels', 'vancouver', 'seattle', 'milan',
    'venice', 'sao paulo', 'são paulo', 'mexico city', 'singapore', 'dubai', 'sydney', 'madrid', 'barcelona', 'lisbon',
    'vienna', 'amsterdam', 'copenhagen', 'stockholm', 'toronto', 'chicago', 'san francisco', 'washington', 'houston',
    'dallas', 'seoul, south korea', 'osaka', 'kyoto', 'taipei', 'mumbai', 'cape town', 'johannesburg', 'oslo',
    'athens', 'florence', 'naples', 'turin', 'bologna', 'cologne', 'munich', 'hamburg', 'frankfurt', 'denver', 'akron',
    'st. louis', 'cleveland', 'boston', 'philadelphia', 'atlanta', 'new orleans', 'minneapolis', 'detroit',
    'finland', 'france', 'italy', 'germany', 'spain', 'china', 'japan', 'korea', 'canada', 'brazil', 'mexico',
    'england', 'uk', 'usa',
)
_NEW_YORK = re.compile(r'\bnew york\b', re.IGNORECASE)
_ADDRESS = re.compile(r'^\d{1,4}(?:[-–&]\d+)?\s+(?:[a-z]+\.?\s+){0,2}(?:\w+\s+)?(?:street|st\.?|avenue|ave\.?|broadway|road|rd\.?|place|alley|plaza|'
                      r'walker|bowery|ludlow|eldridge|madison|fifth|tenth|eleventh|west|east)\b', re.IGNORECASE)
_NOISE = re.compile(r'^(?:read more|view more|learn more|explore|exhibition|exhibitions|current|upcoming|past|new york|'
                    r'new york, ny|new york city|on view|now open|coming soon|opening reception.*|artist.?s reception.*|reception.*|'
                    r'opening.*|curated by.*|featuring:?.*|installation view.*)$', re.IGNORECASE)
_DATE_START = re.compile(r'^(?:\d|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|on view|through|until|opens?)', re.IGNORECASE)


@dataclass
class Spec:
    venue: str
    urls: list
    cards: str = 'links'                      # 'entries' (exhibit-e sites) or 'links' (climb from the links picked by `links`)
    links: str = 'a[href*="/exhibitions/"]'
    spaces: list = field(default_factory=list)        # [(label, address, regex that finds the space in a card)] for several spaces
    tag: str = 'gallery'
    keep: Optional[Callable] = None                  # keep(lines) -> bool: a card that is not a New York show of this gallery
    require_city: bool = False                       # the gallery's cards name their city: a card must say "New York"
    drop: str = ''                                   # lines before the dates that are labels, not part of the name (a regex)
    name: Optional[Callable] = None                  # name(lines before the dates) -> str, when the generic rule is not enough
    read: Optional[Callable] = None                  # read(lines, today) -> (name, start, end) | None, for a card of another shape


# A note a gallery adds to the end of a date line after a double hyphen ("November 6 – December 19, 2026-- Thanksgiving Closure:
# 3pm, Wed, Nov 25 - Thurs, Nov 26", Luhring Augustine, WEBSITE-137). A "--" that is followed by a date ("Nov 6, 2026 -- Dec 19, 2026")
# is a range, not a note.
_NOTE_AFTER_DATES = re.compile(r'^(.*\d{4})\s*--\s*(?!(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d)[A-Za-z].*$',
                               re.IGNORECASE)


def date_line(line, today):
    """(start, end) if the line is just a run of dates (with a note after it, perhaps), else None."""
    line = clean(line)
    note = _NOTE_AFTER_DATES.match(line)
    if note:
        line = note.group(1)
    if len(line) > 70 or not _DATE_START.match(line):
        return None
    try:
        start, end = parse_dates(line, today)
    except ValueError:
        return None
    return (start, end) if (start or end) else None


def card_lines(element):
    """The text lines of a card, each once, in order."""
    lines = []
    for text in element.stripped_strings:
        text = clean(text)
        if text and text not in lines:
            lines.append(text)
    return lines


def _is_elsewhere(line):
    """Whether a line names a place that is not New York ("London", "Maison Leleu Showroom, 15 rue ..., Paris")."""
    low = clean(line).lower()
    if not low or _NEW_YORK.search(low):
        return False
    last = low.rsplit(',', 1)[-1].strip()
    return low in OTHER_PLACES or last in OTHER_PLACES


def find_cards(soup, spec, page_url, region=REGION):
    """[(link, lines, element)] for each card on a listing page."""
    today = region_today(region)
    found = []
    if spec.cards == 'entries':
        for entry in soup.select('.entry'):
            if entry.select_one('.headers') is None:
                continue
            lines = []
            for tag in entry.select('.list-detail-title, .headers h1, .headers h2, .headers h3, .headers h4'):
                text = clean(tag.get_text(' '))
                if text and text not in lines:
                    lines.append(text)
            anchor = entry.find('a', href=True)
            found.append((urljoin(page_url, anchor['href']) if anchor else page_url, lines, entry))
        return found
    anchors = soup.select(spec.links)
    picked = {id(a) for a in anchors}
    for anchor in anchors:
        card = anchor
        while card is not None and not any(date_line(l, today) for l in card_lines(card)):
            card = card.parent
        if card is None or card.name in ('body', 'html'):
            continue
        if sum(1 for a in card.select(spec.links) if id(a) in picked and a.get('href') != anchor.get('href')):
            continue                                     # climbed past the card, into the list of cards
        link = re.sub(r'/(?:installation_shots|overview|press-release|checklist)/?$', '/', urljoin(page_url, anchor['href']))
        found.append((link, card_lines(card), card))
    return found


def read_card(lines, spec, today):
    """(name, start, end) from a card's lines, or None (no dates, no name, or another city's show)."""
    if spec.read:
        return spec.read(lines, today)
    at = next((i for i, line in enumerate(lines) if date_line(line, today)), None)
    if at is None:
        return None
    start, end = date_line(lines[at], today)
    before = lines[:at]
    if any(_is_elsewhere(line) for line in before):
        return None
    if spec.require_city and not any(line.lower() in ('new york', 'new york, ny') for line in before):
        return None
    if spec.keep and not spec.keep(lines):
        return None
    if spec.name:
        name = spec.name(before)
    else:
        parts = [line for line in before if not _NOISE.match(line) and not _ADDRESS.match(line)
                 and not (spec.drop and re.match(spec.drop, line, re.IGNORECASE))]
        parts = [title_case(p) if p.isupper() and len(p) > 3 else p for p in parts]
        if len(parts) > 1 and (parts[1].count(',') > 1 or len(parts[1]) > 90
                               or (parts[1].endswith('.') and len(parts[1].split()) > 5)):
            parts = parts[:1]       # a group show's second line is the list of its artists, or a sentence about it, not a title
        name = join_name(parts[:2])
    return (name, start, end) if name else None


def spaces_of(spec, lines):
    """The labels of the gallery's spaces a card names, or None (store it for the venue as a whole)."""
    if len(spec.spaces) < 2:
        return None
    text = ' '.join(lines)
    return [label for label, _address, pattern in spec.spaces if re.search(pattern, text, re.IGNORECASE)] or None


def scrape(spec, env='prod', region=REGION):
    today = region_today(region)
    found = 0
    seen = set()
    fetched = False
    for url in spec.urls:
        soup = fetch_and_parse(url)
        if soup is None:
            logging.warning(f"{spec.venue}: could not fetch {url}; existing data kept.")
            continue
        fetched = True
        for link, lines, element in find_cards(soup, spec, url, region):
            card = read_card(lines, spec, today)
            if card is None:
                continue
            name, start, end = card
            found += publish(env, region, spec.venue, name, start, end, link, tag=spec.tag, seen=seen,
                             image=card_picture(element, url), locations=spaces_of(spec, lines))
    if fetched and not found:
        logging.warning(f"{spec.venue}: no current or upcoming exhibition found; existing data kept.")
    return found


SPECS = {}


def _add(spec):
    SPECS[spec.venue] = spec
    return spec


def _ny(label, address, pattern=None):
    return (label, address, pattern or re.escape(label))


_add(Spec('Lehmann Maupin', ['https://www.lehmannmaupin.com/exhibitions'], require_city=True,
          spaces=[_ny('501 West 24th Street', '501 W 24th St, New York, NY 10011')]))
_add(Spec('Lisson Gallery', ['https://www.lissongallery.com/exhibitions'], links='a.cover[href*="/exhibitions/"]', require_city=True,
          spaces=[_ny('504 West 24th Street', '504 W 24th St, New York, NY 10011')]))
_add(Spec('Marian Goodman Gallery', ['https://www.mariangoodman.com/exhibitions/'], require_city=True,
          spaces=[_ny('385 Broadway', '385 Broadway, New York, NY 10013')]))
_add(Spec('Paula Cooper Gallery', ['https://www.paulacoopergallery.com/exhibitions'], cards='entries',
          spaces=[_ny('534 West 21st Street', '534 W 21st St, New York, NY 10011', r'\b534\b'),
                  _ny('521 West 21st Street', '521 W 21st St, New York, NY 10011', r'\b521\b'),
                  _ny('529 West 21st Street', '529 W 21st St, New York, NY 10011', r'\b529\b')]))
_add(Spec('Sean Kelly', ['https://www.skny.com/exhibitions'], cards='entries',
          spaces=[_ny('475 Tenth Avenue', '475 10th Ave, New York, NY 10018')]))
_add(Spec('Petzel Gallery', ['https://www.petzel.com/exhibitions'], cards='entries',
          spaces=[_ny('520 West 25th Street', '520 W 25th St, New York, NY 10001')]))
_add(Spec('Andrew Kreps Gallery', ['https://www.andrewkreps.com/exhibitions'], cards='entries',
          spaces=[_ny('394 Broadway', '394 Broadway, New York, NY 10013', r'\b394 Broadway'),
                  _ny('22 Cortlandt Alley', '22 Cortlandt Alley, New York, NY 10013', r'Cortlandt')]))
_add(Spec('Luhring Augustine', ['https://www.luhringaugustine.com/exhibitions'], cards='entries',
          spaces=[_ny('531 West 24th Street', '531 W 24th St, New York, NY 10011')]))
_add(Spec('Miles McEnery Gallery', ['https://www.milesmcenery.com/exhibitions'], cards='entries',
          spaces=[_ny('511 West 22nd Street', '511 W 22nd St, New York, NY 10011', r'\b511\b'),
                  _ny('515 West 22nd Street', '515 W 22nd St, New York, NY 10011', r'\b515\b'),
                  _ny('520 West 21st Street', '520 W 21st St, New York, NY 10011', r'\b520\b'),
                  _ny('525 West 22nd Street', '525 W 22nd St, New York, NY 10011', r'\b525\b')]))
_add(Spec('Skarstedt', ['https://www.skarstedt.com/exhibitions'], cards='entries', drop=r'^(?:New York\b.*|Chelsea|East Hampton.*|Palm Beach)$',
          spaces=[_ny('Upper East Side', '20 E 79th St, New York, NY 10075', r'Upper East Side'),
                  _ny('Chelsea', '547 W 25th St, New York, NY 10001', r'Chelsea')]))
_add(Spec('Alexander Gray Associates', ['https://www.alexandergray.com/exhibitions'], links='a:-soup-contains("Read more")',
          spaces=[_ny('384 Broadway', '384 Broadway, New York, NY 10013')]))
_add(Spec('Anton Kern Gallery', ['https://www.antonkerngallery.com/exhibitions'], drop=r'^WINDOW,', links='a:-soup-contains("Read more")',
          spaces=[_ny('16 East 55th Street', '16 E 55th St, New York, NY 10022', r'^(?!.*WINDOW)'),
                  _ny('WINDOW', '91 Walker St, New York, NY 10013', r'WINDOW')]))
_add(Spec('Yossi Milo Gallery', ['https://www.yossimilo.com/exhibitions'], links='a:-soup-contains("Read more")',
          spaces=[_ny('245 Tenth Avenue', '245 10th Ave, New York, NY 10001')]))
_add(Spec('Jane Lombard Gallery', ['https://www.janelombardgallery.com/exhibitions'], drop=r'^JLG Projects$', links='a:-soup-contains("Read more")',
          spaces=[_ny('58 White Street', '58 White St, New York, NY 10013')]))
_add(Spec('ACA Galleries', ['https://www.acagalleries.com/exhibitions'], links='a:-soup-contains("Read more")',
          spaces=[_ny('173 Tenth Avenue', '173 10th Ave, New York, NY 10011')]))
_add(Spec('Miguel Abreu Gallery', ['https://www.miguelabreugallery.com/exhibitions'],
          spaces=[_ny('88 Eldridge Street', '88 Eldridge St, New York, NY 10002')]))

def _bortolami_name(before):
    """Bortolami's card is the show's title (h3), then the artist(s); a numbered series ("#35") reads "Artist: #35"."""
    lines = [line for line in before if line]
    if len(lines) > 1 and lines[0].startswith('#'):
        lines = [lines[1], lines[0]]
    return join_name(lines[:2])


def _salon_94(lines, today):
    """Salon 94's card repeats its text; deduplicated it is the dates, the title, the place, the artist. Only shows at its
    own address (3 E 89th Street) are kept: the others are in museums and at Salon 94 Paris."""
    if not lines or not date_line(lines[0], today) or not any(line == '3 E 89th Street' for line in lines):
        return None
    rest = [line for line in lines[1:] if line != '3 E 89th Street' and not date_line(line, today)]
    start, end = date_line(lines[0], today)
    return (join_name([rest[-1], rest[0]]) if len(rest) > 1 else join_name(rest[:1]), start, end) if rest else None


_add(Spec('Bortolami', ['https://www.bortolamigallery.com/exhibitions'], links='a[href^="/exhibitions/"]', name=_bortolami_name,
          keep=lambda lines: any('39 Walker' in line for line in lines),
          spaces=[_ny('39 Walker Street', '39 Walker St, New York, NY 10013')]))
_add(Spec('Salon 94', ['https://www.salon94.com/exhibitions'], links='a[href^="/exhibitions/"]', read=_salon_94,
          spaces=[_ny('3 East 89th Street', '3 E 89th St, New York, NY 10128')]))
_add(Spec('Norr Cohan', ['https://www.norrcohan.com/exhibitions'], links='a[href*="/gallery-exhibitions/"]',
          drop=r'^Gallery Exhibition at',
          spaces=[_ny('48 Walker Street', '48 Walker St, New York, NY 10013', r'\b48\b'),
                  _ny('52 Walker Street', '52 Walker St, New York, NY 10013', r'\b52\b')]))
_add(Spec('Galerie Lelong & Co.', ['https://www.galerielelong.com/exhibitions'], links='a:-soup-contains("View More")',
          keep=lambda lines: 'Galerie Lelong Exhibitions' in lines and 'GRAY New York' not in lines,
          drop=r'^(?:Galerie Lelong Exhibitions|Museum & Public Exhibitions)$',
          spaces=[_ny('528 West 26th Street', '528 W 26th St, New York, NY 10001')]))

# Tier 5 (WEBSITE-121): galleries whose listing needed a closer look
_add(Spec('303 Gallery', ['https://www.303gallery.com/gallery-exhibitions', 'https://www.303gallery.com/gallery-exhibitions/upcoming'],
          links='a[href*="/gallery-exhibitions/"]',
          spaces=[_ny('555 West 21st Street', '555 W 21st St, New York, NY 10011')]))
def _artists_space_name(before):
    """Artists Space's card is the artist, then the title; a group show lists its artists, one a line, and no title."""
    lines = [line for line in before if line]
    if len(lines) > 2 and not any(':' in line for line in lines):
        return ', '.join(lines)
    return join_name(lines[:2])


_add(Spec('Artists Space', ['https://artistsspace.org/exhibitions'], links='a[href*="/exhibitions/"]', name=_artists_space_name,
          spaces=[_ny('11 Cortlandt Alley', '11 Cortlandt Alley, New York, NY 10013')]))
_add(Spec('Matthew Marks Gallery', ['https://matthewmarks.com/exhibitions/current', 'https://matthewmarks.com/exhibitions/upcoming'],
          links='a[href^="/exhibitions/"]',
          spaces=[_ny('522 West 22nd Street', '522 W 22nd St, New York, NY 10011', r'\b522\b'),
                  _ny('523 West 24th Street', '523 W 24th St, New York, NY 10011', r'\b523\b'),
                  _ny('526 West 22nd Street', '526 W 22nd St, New York, NY 10011', r'\b526\b')]))


def addresses(venue):
    """The address entry for nyc_venues.json: a string for one space, a list of {label, address} for several."""
    spec = SPECS[venue]
    if len(spec.spaces) > 1:
        return [{'label': label, 'address': address} for label, address, _ in spec.spaces]
    return spec.spaces[0][1]


def _make(spec):
    def scraper(env='prod', region=REGION):
        """Scrape and process this gallery's New York exhibitions."""
        return scrape(spec, env=env, region=region)
    scraper.__name__ = 'scrape_' + re.sub(r'\W+', '_', spec.venue.lower()).strip('_')
    return scraper


def scrapers():
    """{venue: scrape function} for main.py."""
    return {venue: _make(spec) for venue, spec in SPECS.items()}
