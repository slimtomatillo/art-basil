"""Small helpers shared by the New York scrapers (WEBSITE-120)."""
import re
from urllib.parse import urljoin

import images
from date_parsing import parse_date_text


def clean(text):
    """Plain text on one line (tags are gone already; this collapses whitespace and odd spaces)."""
    return ' '.join(str(text or '').replace('\xa0', ' ').split())


def strip_tags(html):
    """The text of a snippet of HTML (a description with <em> in it), on one line."""
    return clean(re.sub(r'<[^>]+>', ' ', str(html or '')))


def card_picture(element, page_url):
    """The first plausible exhibition picture inside a listing card (an <img>, a lazy-loaded data-src or a CSS
    background), made absolute and https; None if the card has none."""
    for source in images._pictures_in(element):
        url = urljoin(page_url, source.strip())
        if images.plausible_image_url(url):
            return images.secure_image_url(url)
    return None


def parse_dates(text, today):
    """(start, end) from a listing's date text, or (None, None). Reads "Through May 10, 2027" (an end only),
    "Opens Nov 21" (a start only), "Nov 6 – Dec 19, 2026", "October 15, 2026 to January 18, 2027" and an
    open-ended "Oct 29, 2025–" (a start only). Text with no day ("Through Spring 2027", "2026") gives (None, None)."""
    text = clean(text)
    text = re.sub(r'^(?:now open|coming soon|on view|opens?)\s*:?\s*', 'Opens ' if text.lower().startswith('opens') else '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+to\s+', ' - ', text)
    text = text.rstrip(' –—-')
    return parse_date_text(text, today)
