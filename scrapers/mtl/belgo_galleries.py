from utils import fetch_and_parse
from scrapers.tor._common import page_lines, publish
from scrapers.la._gallery import index_of
from date_parsing import parse_date_text
from processing import region_today
import logging
import re
from urllib.parse import urlparse

LISTING_URL = 'https://belgo.art/'
# The Belgo Building (372 Sainte-Catherine W) lists every tenant's current show on one page, in French:
#   "Galerie B-312 | Local : | 403 | Centre d'artistes | Heures d'ouverture : | Mardi... | Exposition : | Title | Artist |
#    Dates : | 5 novembre au 12 décembre | 2026". A few tenants leave out the "Exposition :" / "Dates :" labels, so the
# date line is found by its shape instead. Each tenant is published as its own venue.
_DAY_RANGE_RE = re.compile(r'^\d{1,2}(?:er)? \S+ au \d{1,2}(?:er)? \S+')
_YEAR_RE = re.compile(r'^,?\s*(\d{4})$')
_SKIP = ('Exposition :', 'Dates :')
# The page misspells one tenant's name
_SOCIAL_AND_TRANSIT = ('instagram.com', 'facebook.com', 'stm.info', 'quartierdesspectacles.com')
_RENAMES = {'Éclats Art contemmporain': 'Éclats Art contemporain'}


def _name(title_lines):
    """The show's title, with its artist in front when it is a solo show ("Artist: Title")."""
    title, rest = title_lines[0], list(title_lines[1:])
    while rest and rest[0][:1].islower():  # a title that runs onto a second line
        title += ' ' + rest.pop(0)
    if len(rest) == 1 and ',' not in rest[0] and ' et ' not in rest[0] and len(rest[0]) <= 60:
        return f"{rest[0]}: {title}"
    return title


def _site(url):
    return urlparse(url).netloc.lower().removeprefix('www.')


def _tenant_links(soup):
    """{tenant name: link} from the page: each tenant's heading is followed by its home page and, when it has
    a show on, that show's own page. belgo.art itself has no pictures, so the show's page is the best link."""
    found = {}
    for heading in soup.select('h3.TitleName'):
        links, social = [], []
        for el in heading.find_all_next():
            if el is not heading and el.name == 'h3' and 'TitleName' in (el.get('class') or []):
                break
            if el.name == 'a' and el.get('href'):
                if any(h in el['href'] for h in _SOCIAL_AND_TRANSIT):
                    social.append(el['href'])
                elif el['href'] not in links:
                    links.append(el['href'])
        # The show's page is on the tenant's own site. A link to another site is an artist the tenant shows
        # (Espace DÈS_ lists past artists' sites after its own), so the tenant's home page is used instead.
        # A tenant with only an Instagram page links to that, not to belgo.art (whose only picture is the building).
        show_page = links[1] if len(links) > 1 and _site(links[1]) == _site(links[0]) else None
        link = (show_page or links[0]) if links else (social[0] if social else None)
        if link:
            found[heading.get_text(' ', strip=True).split(' | ')[0]] = link
    return found


def scrape_belgo_galleries(env='prod', region='mtl'):
    """Scrape and process the exhibitions of the galleries and artist-run centres in the Belgo Building."""
    today = region_today(region)
    soup = fetch_and_parse(LISTING_URL)
    if soup is None:
        logging.warning("Belgo galleries: could not fetch belgo.art; existing data kept.")
        return
    tenant_links = _tenant_links(soup)
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
                              tenant_links.get(venue, LISTING_URL), tag='gallery')
    if not stored:
        logging.warning("Belgo galleries: no exhibitions found; existing data kept.")
