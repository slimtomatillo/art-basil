from utils import fetch_and_parse, fetch_json_via_proxy, ARTCLOUD_PROXY
from scrapers.tor._common import page_lines, publish
from scrapers.la._gallery import index_of
from date_parsing import parse_date_text
from processing import region_today
import logging
import re
from urllib.parse import urlparse

import requests

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
# Tenants whose site is on the ArtCloud platform: its show pages 403 GitHub Actions, but the JSON feed the pages are
# built from (/api/shows, called with the site's id) does not, and lists each show's id (the last part of the
# show's page address) with its picture. The id is in the page's source ("subdomain").
ARTCLOUD_SITES = {'wishboneart.com': '93234dda-ef42-40c2-a34a-f75b1565b3ee'}      # Galerie Wishbone
# The feed itself is refused on some runs (see _artcloud_pictures), so then it is fetched through ZenRows with a
# residential IP: utils.ARTCLOUD_PROXY holds the options.
_ARTCLOUD_PICTURE = 'https://cdn.artcld.com/img/w_640,h_640,c_fit/{id}.{ext}'


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


def _artcloud_pictures(host):
    """{show id: picture url} from an ArtCloud site's feed, or {} if it can't be read (the shows then have no
    picture of their own and the venue's logo is shown).

    ArtCloud's firewall refuses a GitHub Actions address with a 403 ("Ip Forbidden") on some runs and not on
    others (seen 2026-11-10 and 2026-11-12, not 11-09 or 11-11), so the feed is tried directly first, which is
    free, and through the proxy only when that request fails."""
    url = f'https://{host}/api/shows'
    query = {'limit': 100, 'offset': 0, 'sub': ARTCLOUD_SITES[host]}
    shows = None
    try:
        response = requests.get(url, params=query, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}, timeout=30)
        response.raise_for_status()
        shows = response.json().get('shows') or []
    except (requests.RequestException, ValueError, AttributeError) as e:
        if isinstance(e, requests.RequestException):       # blocked or unreachable (not "the answer was not what we expected")
            data = fetch_json_via_proxy(url, query, ARTCLOUD_PROXY)
            if isinstance(data, dict):
                shows = data.get('shows') or []
                logging.info(f"Belgo galleries: read the pictures feed of {host} through the proxy ({e}).")
        if shows is None:
            logging.warning(f"Belgo galleries: could not read the pictures feed of {host} ({e}).")
            return {}
    return {show['showId']: _ARTCLOUD_PICTURE.format(id=show['image']['id'], ext=show['image'].get('extension') or 'jpg')
            for show in shows if show.get('showId') and (show.get('image') or {}).get('id')}


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
    artcloud = {}              # host -> its feed's pictures, fetched once and only for a tenant that has a show to publish
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
            link = tenant_links.get(venue, LISTING_URL)
            host = _site(link)
            if host in ARTCLOUD_SITES and host not in artcloud:
                artcloud[host] = _artcloud_pictures(host)
            picture = artcloud.get(host, {}).get(urlparse(link).path.rstrip('/').rsplit('/', 1)[-1])
            stored += publish(env, region, _RENAMES.get(venue, venue), _name(title_lines), start, end,
                              link, tag='gallery', image=picture)
    if not stored:
        logging.warning("Belgo galleries: no exhibitions found; existing data kept.")
