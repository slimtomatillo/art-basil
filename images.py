"""Find an image for events whose scraper didn't supply one.

Scrapers that can read each show's picture off the listing page store it themselves (see
scrapers/tor/_common.py Listing and image_in_card below). For the rest, main.py calls
enrich_missing_images() after the scrapers have run: for each current or upcoming event with
no image it opens the event's own page and picks the first usable picture there, best
candidate first (the page's share image, then the images on the page). Events that share one
listing page are looked up together by title, the same way a scraper does it.

"Usable" is deliberately strict, because a wrong picture is worse than none:
- not an SVG, a data URI or a file named like a logo, icon or placeholder;
- big enough to be a photo (MIN_IMAGE_BYTES), which drops logos and site icons;
- not the same picture the venue shows for several different events, which is a site-wide
  banner rather than that show's image.

An image found is stored on the event as a normal {"link", "description": "Image"} link, so the
table shows it like any other. processing.process_event keeps it when a scraper rewrites the
event later, and "image_checked" records the day an event was last looked at, so events with
nothing to find are retried only every RECHECK_AFTER, not daily.

Sites fetched through the paid proxy are skipped (an extra page would cost credits).

Dry run on the real data, writing nothing:  python images.py
"""

import concurrent.futures
import datetime as dt
import logging
import re
import sys
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import Comment

import utils
from config import DB_FILES
from manual_check import MANUAL_SOURCE
from processing import image_link
from scraper_health import ARCHIVE_SOURCE
from utils import fetch_and_parse, load_db, save_db

MIN_IMAGE_BYTES = 25_000          # real photos clear this; logos, icons and layout graphics don't
RECHECK_AFTER = dt.timedelta(days=14)
MAX_PAGES_PER_RUN = 80            # keeps a run short; a backlog is cleared over a few days
MAX_IMAGE_BYTES = 700_000          # a thumbnail heavier than this is swapped for a small copy
MAX_CANDIDATES = 12               # images tried per page
CARD_CLIMB = 7                    # parent levels searched from a show's title for its picture
IMAGE_TIMEOUT = (5, 10)
# Filenames (not whole URLs) that mark a logo, icon or placeholder
REJECT_NAME = re.compile(r'logo|icon|sitename|favicon|sprite|avatar|spacer|pixel|placeholder|'
                         r'facebook|shopping-cart|cart\b|loading|arrow|button|award|badge', re.I)
# A folder that holds only such graphics (/images/icons/menu.png)
REJECT_FOLDER = re.compile(r'/(?:icons?|logos?|sprites?|badges?|ui)/', re.I)
# Plain browser-style header: some sites' firewalls drop requests that announce themselves as a bot
IMAGE_HEADERS = {'User-Agent': 'Mozilla/5.0'}
# The phases worth spending a page fetch on (past events fill the table with old shows)
WANTED_PHASES = ('current', 'future')
SKIP_SOURCES = (MANUAL_SOURCE, ARCHIVE_SOURCE)


def secure_image_url(url):
    """Our pages are https, and a browser won't show an http-only site's pictures on them. Those
    are routed through images.weserv.nl, a free image proxy that serves them over https (and
    scaled down, since their originals are often large). https URLs pass through unchanged."""
    if url and url.lower().startswith('http://'):
        return 'https://images.weserv.nl/?url=' + quote(url[len('http://'):], safe='') + '&w=800&we'
    return url


def resized_image_url(url, width=640):
    """A small JPEG copy of a picture, served by images.weserv.nl (the same free proxy as
    secure_image_url). For a site whose pictures are huge originals (CAAM's are 5-8 MB PNGs),
    which would otherwise make the page download tens of megabytes. For photos only: a
    transparent logo would lose its transparency."""
    if not url:
        return url
    bare = re.sub(r'^https?://', '', url, flags=re.I)
    return f'https://images.weserv.nl/?url={quote(bare, safe="")}&w={width}&we&output=jpg&q=80'


def plausible_image_url(url):
    """False for anything that can't be an exhibition photo, judged from the URL alone."""
    if not url or not url.lower().startswith(('http://', 'https://')):
        return False
    path = urlparse(url).path
    if path.lower().endswith('.svg'):
        return False
    return not (REJECT_NAME.search(path.rsplit('/', 1)[-1]) or REJECT_FOLDER.search(path))


def big_enough(url, minimum=MIN_IMAGE_BYTES):
    """True if the image is at least `minimum` bytes. Reads just far enough to know: the size a
    server reports for a HEAD request can't be trusted (Squarespace says 1 byte)."""
    try:
        with requests.get(url, headers=IMAGE_HEADERS, timeout=IMAGE_TIMEOUT, stream=True) as response:
            if not response.ok or 'image' not in response.headers.get('Content-Type', ''):
                return False
            received = 0
            for chunk in response.iter_content(8192):
                received += len(chunk)
                if received >= minimum:
                    return True
            return False
    except requests.RequestException:
        return False


def candidate_images(soup, page_url):
    """Image URLs on an event page, best first, without repeats."""
    found = []

    def add(src):
        if src:
            url = urljoin(page_url, src.strip())
            if url not in found:
                found.append(url)

    for selector in ('meta[property="og:image"]', 'meta[property="og:image:url"]', 'meta[name="twitter:image"]'):
        tag = soup.select_one(selector)
        if tag:
            add(tag.get('content'))
    link = soup.select_one('link[rel="image_src"]')
    if link:
        add(link.get('href'))
    # Then the page's own pictures, the main content's first
    for scope in ('main', 'article', '[role="main"]', 'body'):
        container = soup.select_one(scope)
        if container:
            for img in container.find_all('img'):
                add(img.get('data-src') or img.get('data-lazy-src') or img.get('src'))
    return found


def find_event_image(page_url):
    """The best usable image on an event's page, or None."""
    if not page_url or urlparse(page_url).netloc in utils.PROXY_DOMAINS:
        return None
    soup = fetch_and_parse(page_url)
    if soup is None:
        return None
    for url in candidate_images(soup, page_url)[:MAX_CANDIDATES]:
        if plausible_image_url(url) and big_enough(url):
            return secure_image_url(url)
    return None


def _key(text):
    """A title reduced to lowercase letters and digits, so "Kamiphony | Cybèle Young",
    "Kamiphony: Cybèle Young" and a title split over several tags all compare equal."""
    return re.sub(r'\W+', '', text.lower())


class PageText:
    """A page's text nodes with title-friendly keys, so many titles can be located quickly."""

    def __init__(self, soup):
        self.strings = [s for s in soup.find_all(string=True)
                        if not isinstance(s, Comment) and s.parent.name not in ('script', 'style', 'noscript')]
        self.keys = [_key(str(s)) for s in self.strings]
        self.joined = ''.join(self.keys)
        self.starts = []                      # where each node's text begins within `joined`
        offset = 0
        for piece in self.keys:
            self.starts.append(offset)
            offset += len(piece)

    def element_for(self, title):
        """The smallest element whose text holds `title` (None if the page doesn't show it). Works
        when a title is broken up by <em>, <br> or separate spans, which a plain string search misses."""
        key = _key(title)
        where = self.joined.find(key) if key else -1
        if where < 0:
            return None
        end = where + len(key)
        covering = [i for i, piece in enumerate(self.keys)
                    if piece and self.starts[i] < end and self.starts[i] + len(piece) > where]
        if not covering:
            return None
        first, last = self.strings[covering[0]], self.strings[covering[-1]]
        if first is last:
            return first.parent
        above_last = {id(p) for p in last.parents}
        return next(p for p in first.parents if id(p) in above_last)


def _image_sources(img):
    """Candidate URLs for an <img>, best first. Lazy-loaded pictures keep the real address in a
    data- attribute (src is a placeholder), and some sites list sizes in a dict-like string."""
    sources = []
    responsive = img.get('data-responsive-src')
    if responsive:
        urls = re.findall(r"https?://[^'\"\s,}]+", responsive)
        medium = re.search(r"['\"]750['\"]:\s*['\"]([^'\"]+)", responsive)
        sources += [medium.group(1)] if medium else urls[:1]
    sources += [img.get('data-src'), img.get('data-lazy-src'), img.get('src')]
    srcset = img.get('data-srcset') or img.get('srcset')
    if srcset:
        sources.append(srcset.split(',')[0].split()[0])
    return [s for s in sources if s]


_BACKGROUND_URL = re.compile(r'background(?:-image)?\s*:[^;]*?url\(\s*[\'"]?([^\'")]+?)[\'"]?\s*\)', re.I)


def _pictures_in(element):
    """Candidate picture URLs inside an element, in page order: <img> tags, and elements that
    show their picture as a CSS background (some themes do this for exhibition cards)."""
    sources = []
    for tag in element.find_all(True):
        if tag.name == 'img':
            sources += _image_sources(tag)
        elif tag.get('style'):
            sources += _BACKGROUND_URL.findall(tag['style'])
    return sources


def image_in_card(page, title, page_url, other_titles=(), check_size=True):
    """The picture shown with `title` on a listing page: climbs from the title up through its
    parents until one contains an image, giving up if it reaches an element that also holds
    another show's title (then the pictures are shared, not this show's).

    check_size=False skips downloading the picture to see how big it is, for scrapers that have
    looked at the page and know its pictures are the shows' own (a small thumbnail is fine).
    `page` is the page's soup, or a PageText built from it when looking up many titles."""
    if not isinstance(page, PageText):
        page = PageText(page)
    key = _key(title)
    others = [k for k in (_key(t) for t in other_titles) if k and k != key and k not in key]
    element = page.element_for(title)
    for _ in range(CARD_CLIMB):
        if element is None or element.name in ('body', 'html'):
            return None
        if any(other in _key(element.get_text(' ')) for other in others):
            return None
        for src in _pictures_in(element):
            url = urljoin(page_url, src.strip())
            if plausible_image_url(url) and (not check_size or big_enough(url)):
                return secure_image_url(url)
        element = element.parent
    return None


def card_images(soup, page_url, titles, check_size=True):
    """{title: picture url} for the shows listed on one page, each taken from the card that holds
    its title. A picture that turns up for more than one show is dropped as a banner."""
    found = {}
    page = PageText(soup)
    for title in titles:
        url = image_in_card(page, title, page_url, titles, check_size)
        if url:
            found[title] = url
    counts = {}
    for url in found.values():
        counts[url] = counts.get(url, 0) + 1
    return {title: url for title, url in found.items() if counts[url] == 1}


def find_card_images(page_url, titles):
    """{title: image url} for the shows of a listing page that several events point to."""
    if not page_url or urlparse(page_url).netloc in utils.PROXY_DOMAINS:
        return {}
    soup = fetch_and_parse(page_url)
    if soup is None:
        return {}
    return card_images(soup, page_url, titles)


def event_page(event):
    return next((l['link'] for l in event.get('links', [])
                 if l.get('description') == 'Event Page' and l.get('link')), None)


def needs_image(event, today):
    if event.get('phase') not in WANTED_PHASES or event.get('source') in SKIP_SOURCES:
        return False
    if image_link(event) or not event_page(event):
        return False
    checked = event.get('image_checked')
    if checked:
        try:
            if today - dt.date.fromisoformat(checked) < RECHECK_AFTER:
                return False
        except ValueError:
            pass
    return True


def enrich_missing_images(regions=None, today=None, finder=find_event_image, card_finder=find_card_images,
                          max_pages=MAX_PAGES_PER_RUN, save=True):
    """Give image-less current and upcoming events an image from their own page.

    An event with a page of its own is looked up with `finder(page_url)`. Several events that
    share one listing page are looked up together with `card_finder(page_url, titles)`, which
    returns each show's own picture from that page.

    Returns {'checked': pages opened, 'added': [(region, venue, event name, url)], 'dropped': [...]}.
    `dropped` lists pictures rejected because the venue uses the same one for several shows.
    """
    today = today or dt.date.today()
    report = {'checked': 0, 'added': [], 'dropped': []}
    for region in (regions or DB_FILES):
        db = load_db(DB_FILES[region])
        changed = False
        for venue, events in db.items():
            if report['checked'] >= max_pages:
                break
            by_page = {}
            for event in events.values():
                if needs_image(event, today):
                    by_page.setdefault(event_page(event), []).append(event)
            found = []                                  # (event, image url)
            for page, group in by_page.items():
                if report['checked'] >= max_pages:
                    break
                report['checked'] += 1
                if len(group) == 1:
                    url = finder(page)
                    found.extend([(group[0], url)] if url else [])
                else:
                    by_title = card_finder(page, [e['name'] for e in group])
                    found.extend((e, by_title[e['name']]) for e in group if e['name'] in by_title)
                for event in group:
                    event['image_checked'] = today.isoformat()
                changed = True
            # The same picture for several of a venue's shows is its banner, not their images
            in_use = [image_link(e) for e in events.values()]
            for event, url in found:
                shared = sum(1 for _, u in found if u == url) + sum(1 for u in in_use if u == url)
                if shared >= 2:
                    report['dropped'].append((region, venue, event['name'], url))
                    continue
                event.setdefault('links', []).append({'link': url, 'description': 'Image'})
                report['added'].append((region, venue, event['name'], url))
        if changed and save:
            save_db(db, region)
    return report


PROXY_HOST = 'https://images.weserv.nl/'


def image_size(url):
    """The size in bytes a server reports for a picture (read from the response headers; the body
    is not downloaded), or None if it can't be told."""
    try:
        with requests.get(url, headers=IMAGE_HEADERS, timeout=IMAGE_TIMEOUT, stream=True) as response:
            if not response.ok or 'image' not in response.headers.get('Content-Type', ''):
                return None
            return int(response.headers.get('Content-Length') or 0) or None
    except (requests.RequestException, ValueError):
        return None


def proxy_serves(url):
    """True if the image proxy returns a picture for `url` (it can't reach every site: one that
    blocks it would leave a broken thumbnail, so a swap is made only after this check)."""
    try:
        with requests.get(url, headers=IMAGE_HEADERS, timeout=IMAGE_TIMEOUT, stream=True) as response:
            return response.ok and 'image' in response.headers.get('Content-Type', '')
    except requests.RequestException:
        return False


def shrink_heavy_images(regions=None, today=None, size_of=image_size, proxy_ok=proxy_serves,
                        max_bytes=MAX_IMAGE_BYTES, save=True, workers=16):
    """Swap a current or upcoming event's picture for a small JPEG copy when the original is
    heavy. Some venues serve full-size originals (several MB each), and a page of them is slow
    to load. The copy comes from images.weserv.nl (resized_image_url) and is used only when the
    proxy really serves it. Pictures already on the proxy are left alone.

    A scraper rewrites the event with the original link on its next run, so this runs after
    every scrape. Returns {'checked': pictures measured, 'shrunk': [(region, venue, event name, bytes)]}.
    """
    today = today or dt.date.today()
    todo = []                                        # (region, db, venue, event, link dict)
    dbs = {}
    for region in (regions or DB_FILES):
        dbs[region] = load_db(DB_FILES[region])
        for venue, events in dbs[region].items():
            for event in events.values():
                if event.get('phase') not in WANTED_PHASES:
                    continue
                for link in event.get('links', []):
                    url = link.get('link') or ''
                    if (link.get('description') == 'Image' and url.lower().startswith(('http://', 'https://'))
                            and not url.startswith(PROXY_HOST) and not url.lower().split('?')[0].endswith('.svg')):
                        todo.append((region, venue, event, link))
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        sizes = list(pool.map(lambda item: size_of(item[3]['link']), todo))
    report = {'checked': len(todo), 'shrunk': []}
    changed = set()
    for (region, venue, event, link), size in zip(todo, sizes):
        if size and size > max_bytes:
            small = resized_image_url(link['link'])
            if proxy_ok(small):
                link['link'] = small
                changed.add(region)
                report['shrunk'].append((region, venue, event['name'], size))
    if save:
        for region in changed:
            save_db(dbs[region], region)
    return report


if __name__ == '__main__':
    # Dry run: shows what would be added to the real data, writes nothing.
    logging.basicConfig(level=logging.WARNING)
    regions = sys.argv[1:] or None
    result = enrich_missing_images(regions, save=False)
    print(f"Opened {result['checked']} event pages")
    for region, venue, name, url in result['added']:
        print(f"  + [{region}] {venue}: {name[:48]}\n      {url}")
    for region, venue, name, url in result['dropped']:
        print(f"  - dropped (same picture on several shows) [{region}] {venue}: {name[:40]}\n      {url}")
