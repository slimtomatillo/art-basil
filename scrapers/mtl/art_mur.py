from utils import fetch_and_parse
from scrapers.tor._common import publish
from scrapers.la._gallery import date_label
from processing import region_today
import logging
import re

LIST_URLS = ['https://artmur.com/en/current-exhibitions/', 'https://artmur.com/en/upcoming-exhibitions/']
VENUE = 'Art Mur'
# Each show is a div.one_half of <br>-separated lines, with its picture in the div.one_half.last beside it:
#   November 14–December 19, 2026
#   Opening reception: Saturday, November 14, from 3:00 p.m. to 5:00 p.m.
#   Karine Giboulo: <em>Retrospective and New Works</em>
#   (then artists, curator, partner)
# Between shows the "current" page just says "Installation in progress".


def _picture(img, most=1200):
    """The biggest version in an <img>'s srcset that is at most `most` px wide (else its src);
    the originals are 2048px and several MB."""
    best, width = img.get('src'), 0
    for part in (img.get('srcset') or '').split(','):
        bits = part.split()
        if len(bits) == 2 and bits[1].endswith('w') and bits[1][:-1].isdigit():
            w = int(bits[1][:-1])
            if width < w <= most:
                best, width = bits[0], w
    return best


def read_shows(soup, today):
    """Yield (name, start, end, picture url) for each show on a list page."""
    content = soup.select_one('div.entry-content')
    if content is None:
        return
    for block in content.find_all('div', class_='one_half', recursive=False):
        if 'last' in block.get('class', []):
            continue
        for br in block.find_all('br'):
            br.replace_with('\n')
        # Lines are split at <br> only: a title is partly in <em>
        lines = [' '.join(l.split()) for l in block.get_text().split('\n')]
        lines = [l for l in lines if l]
        label = date_label(lines[0], today) if lines else None
        rest = [l for l in lines[1:] if not l.lower().startswith('opening')]
        if not (label and rest):
            continue
        name = re.sub(r'\s*:\s*', ': ', rest[0]).strip()
        name = re.sub(r':\s*$', '', name)
        picture = block.find_next_sibling('div')
        img = picture.find('img') if picture is not None and 'last' in picture.get('class', []) else None
        yield name, label[0], label[1], _picture(img) if img else None


def scrape_art_mur(env='prod', region='mtl'):
    """Scrape and process the current and upcoming exhibitions at Art Mur."""
    today = region_today(region)
    seen = set()
    fetched = stored = 0
    for list_url in LIST_URLS:
        soup = fetch_and_parse(list_url)
        if soup is None:
            continue
        fetched += 1
        for name, start, end, image in read_shows(soup, today):
            stored += publish(env, region, VENUE, name, start, end, list_url, tag='gallery', seen=seen, image=image)
    if not fetched:
        logging.warning("Art Mur: could not fetch the exhibition lists; existing data kept.")
    elif not stored:
        logging.warning("Art Mur: no exhibitions found; existing data kept.")
