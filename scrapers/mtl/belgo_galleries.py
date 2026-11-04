from utils import fetch_and_parse
from scrapers.tor._common import page_lines, publish
from scrapers.la._gallery import index_of
from date_parsing import parse_date_text
from processing import region_today
import logging
import re

LISTING_URL = 'https://belgo.art/'
# The Belgo Building (372 Sainte-Catherine W) lists every tenant's current show on one page, in French:
#   "Galerie B-312 | Local : | 403 | Centre d'artistes | Heures d'ouverture : | Mardi... | Exposition : | Title | Artist |
#    Dates : | 5 novembre au 12 décembre | 2026". A few tenants leave out the "Exposition :" / "Dates :" labels, so the
# date line is found by its shape instead. Each tenant is published as its own venue.
_DAY_RANGE_RE = re.compile(r'^\d{1,2}(?:er)? \S+ au \d{1,2}(?:er)? \S+')
_YEAR_RE = re.compile(r'^,?\s*(\d{4})$')
_SKIP = ('Exposition :', 'Dates :')
# The page misspells one tenant's name
_RENAMES = {'Éclats Art contemmporain': 'Éclats Art contemporain'}


def _name(title_lines):
    """The show's title, with its artist in front when it is a solo show ("Artist: Title")."""
    title, rest = title_lines[0], list(title_lines[1:])
    while rest and rest[0][:1].islower():  # a title that runs onto a second line
        title += ' ' + rest.pop(0)
    if len(rest) == 1 and ',' not in rest[0] and ' et ' not in rest[0] and len(rest[0]) <= 60:
        return f"{rest[0]}: {title}"
    return title


def scrape_belgo_galleries(env='prod', region='mtl'):
    """Scrape and process the exhibitions of the galleries and artist-run centres in the Belgo Building."""
    today = region_today(region)
    soup = fetch_and_parse(LISTING_URL)
    if soup is None:
        logging.warning("Belgo galleries: could not fetch belgo.art; existing data kept.")
        return
    lines = page_lines(soup)
    locals_at = [i for i, l in enumerate(lines) if l == 'Local :']
    page_end = index_of(lines, 'Le Belgo —', len(lines))
    stored = 0
    for n, i in enumerate(locals_at):
        block = lines[i - 1:(locals_at[n + 1] - 1 if n + 1 < len(locals_at) else page_end)]
        if 'Exposition :' in block and 'Dates :' in block:
            first, dated = block.index('Exposition :') + 1, block.index('Dates :') + 1
        else:
            # no labels: the title lines follow the opening hours, up to the line like "8 novembre au 11 décembre"
            first = index_of(block, 'Heures d’ouverture :', 3) + 2
            dated = next((k for k in range(first, len(block)) if _DAY_RANGE_RE.match(block[k])), None)
        if dated is None:
            continue  # artists' studios and galleries with nothing on
        text = block[dated]
        year = _YEAR_RE.match(block[dated + 1]) if dated + 1 < len(block) else None
        if year:
            text += f" {year.group(1)}"
        title_lines = [l for l in block[first:dated - ('Dates :' in block)]
                       if l not in _SKIP and not l.startswith('Commissaire')]
        venue = block[0].split(' | ')[0]
        start, end = parse_date_text(text, today)
        if title_lines and (start or end):
            stored += publish(env, region, _RENAMES.get(venue, venue), _name(title_lines), start, end,
                              LISTING_URL, tag='gallery')
    if not stored:
        logging.warning("Belgo galleries: no exhibitions found; existing data kept.")
