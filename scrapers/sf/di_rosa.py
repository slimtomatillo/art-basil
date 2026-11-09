"""di Rosa Center for Contemporary Art: two sites, di Rosa Napa (5200 Sonoma Hwy, paid admission) and
di Rosa SF (1150 25th St, free), published as two venues so each keeps its own address and admission.

The exhibitions page is a list of cards with only a title and a link. Each show's own page has the
dates as the line under its title ("August 29 – November 29, 2026", sometimes without the year) and
the site as the next line ("di Rosa Napa" / "di Rosa SF"). A card marked "| Ongoing" (the permanent
collection show) has no dates and is skipped. Past shows can stay on the list, so a show whose dates
have passed is not published.
"""
import logging
from urllib.parse import urljoin

from date_parsing import parse_date_text
from processing import region_today
from scrapers.tor._common import page_lines, publish
from utils import fetch_and_parse

LIST_URL = 'https://www.dirosaart.org/exhibitions/'
# site label on the show's page -> (venue name, tag): Napa charges admission, so it is a museum
# and is not assumed free; SF is free to all and is shown as a gallery
SITES = {
    'di rosa napa': ('di Rosa Napa', 'museum'),
    'di rosa sf': ('di Rosa SF', 'gallery'),
}
_MAX_DESCRIPTION = 400


def _description(lines, start):
    """The first full paragraph after the title block, cut at a word."""
    for line in lines[start:]:
        if len(line) > 80:
            return line[:_MAX_DESCRIPTION].rsplit(' ', 1)[0] if len(line) > _MAX_DESCRIPTION else line
    return None


def _read_show(url, today):
    """(title, venue, tag, start, end, description, image) from a show's page, or None."""
    soup = fetch_and_parse(url)
    if soup is None:
        logging.warning(f"di Rosa: could not fetch {url}")
        return None
    h1 = soup.find('h1')
    title = ' '.join(h1.get_text(' ').split()) if h1 else None
    image_tag = soup.find('meta', property='og:image')
    image = image_tag['content'] if image_tag and image_tag.get('content') else None
    lines = page_lines(soup)
    if not title or title not in lines:
        logging.warning(f"di Rosa: no title found on {url}")
        return None
    at = lines.index(title)
    date_line = lines[at + 1] if at + 1 < len(lines) else ''
    start_date, end_date = parse_date_text(date_line, today)
    if end_date and end_date < today:
        return None
    # The site is named within the next few lines (a projection has a "Visible nightly" line first)
    nearby = lines[at + 2:at + 5]
    site_at = next((i for i, line in enumerate(nearby) if line.strip().lower() in SITES), None)
    if not (start_date or end_date) or site_at is None:
        logging.warning(f"di Rosa: no readable dates or site for {title!r} ({date_line!r}, {nearby!r})")
        return None
    site = SITES[nearby[site_at].strip().lower()]
    return title, site[0], site[1], start_date, end_date, _description(lines, at + 3 + site_at), image


def scrape_di_rosa(env='prod', region='sf'):
    """Scrape and process the current and upcoming exhibitions of di Rosa Napa and di Rosa SF."""
    today = region_today(region)
    soup = fetch_and_parse(LIST_URL)
    if soup is None:
        logging.warning("di Rosa: could not fetch the exhibitions page; existing data kept.")
        return
    found = 0
    seen = set()
    for card in soup.select('article.elementor-post'):
        link = card.select_one('a[href]')
        title_tag = card.select_one('.elementor-post__title')
        if link is None or title_tag is None:
            continue
        if 'ongoing' in title_tag.get_text(' ').lower():
            continue
        url = urljoin(LIST_URL, link['href'])
        show = _read_show(url, today)
        if show is None:
            continue
        title, venue, tag, start_date, end_date, description, image = show
        found += publish(env, region, venue, title, start_date, end_date, url, tag=tag,
                         description=description, seen=seen, image=image)
    if not found:
        logging.warning("di Rosa: no current or upcoming exhibitions found; existing data kept.")
