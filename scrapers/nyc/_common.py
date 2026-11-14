"""Small helpers shared by the New York scrapers (WEBSITE-120)."""
import datetime as dt
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


_SMALL_WORDS = {'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'in', 'nor', 'of', 'on', 'or', 'the', 'to', 'vs'}


def title_case(text):
    """A title set in capitals ("FREDERIC CHURCH IN JAMAICA") in title case, with the small words lower ("Frederic Church
    in Jamaica") and apostrophes left alone."""
    words = [w[:1].upper() + w[1:].lower() for w in clean(text).split(' ')]
    return ' '.join(w.lower() if i and w.lower() in _SMALL_WORDS else w for i, w in enumerate(words))


def card_picture(element, page_url):
    """The first plausible exhibition picture inside a listing card (an <img>, a lazy-loaded data-src or a CSS
    background), made absolute and https; None if the card has none."""
    for source in images._pictures_in(element):
        url = urljoin(page_url, source.strip())
        if images.plausible_image_url(url):
            return images.secure_image_url(url)
    return None


_NUMERIC_RUN = re.compile(r'^(\d{1,2})\.(\d{1,2})\.(\d{2,4})\s*[-–—]\s*(\d{1,2})\.(\d{1,2})\.(\d{2,4})$')


def numeric_run(text):
    """(start, end) from a run written month.day.year to month.day.year ("10.08.26 - 12.12.26", "02.11.27-05.16.27"), or
    (None, None). A single numeric date ("12.10.26") is an event's day, not a run, and gives (None, None)."""
    match = _NUMERIC_RUN.match(clean(text))
    if not match:
        return None, None
    m1, d1, y1, m2, d2, y2 = (int(g) for g in match.groups())
    year = lambda y: y + 2000 if y < 100 else y
    try:
        return dt.date(year(y1), m1, d1), dt.date(year(y2), m2, d2)
    except ValueError:
        return None, None


_MONTHS = ('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec')
_DAY_FIRST = re.compile(r'^(\d{1,2})\s+([A-Za-z]{3,9})\.?(?:\s+(\d{4}))?\s*[-–—]\s*(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{4})$')
_DAY_FIRST_ONE_MONTH = re.compile(r'^(\d{1,2})\s*[-–—]\s*(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{4})$')
_DOTTED = re.compile(r'^(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?\s*[-–—]\s*(\d{1,2})\.(\d{1,2})\.(\d{4})$')


def _month(word):
    word = word.lower()[:3]
    return _MONTHS.index(word) + 1 if word in _MONTHS else None


def alternate_run(text):
    """(start, end) from the runs `parse_date_text` does not read: day first ("30 Oct - 19 Dec 2026", "11 November 2026 -
    16 January 2027", "5 NOVEMBER 2026 - 9 JANUARY 2027", "5-30 Nov 2026") and dotted month.day ("11.05-12.19.2026",
    "11.05.2026-07.04.2027"). (None, None) when the text is none of these or not a real date."""
    text = clean(text)
    try:
        match = _DAY_FIRST.match(text)
        if match:
            d1, m1, y1, d2, m2, y2 = match.groups()[0], _month(match.group(2)), match.group(3), match.group(4), _month(match.group(5)), match.group(6)
            if m1 and m2:
                end = dt.date(int(y2), m2, int(d2))
                start_year = int(y1) if y1 else (int(y2) - (1 if m1 > m2 else 0))
                return dt.date(start_year, m1, int(d1)), end
        match = _DAY_FIRST_ONE_MONTH.match(text)
        if match and _month(match.group(3)):
            month, year = _month(match.group(3)), int(match.group(4))
            return dt.date(year, month, int(match.group(1))), dt.date(year, month, int(match.group(2)))
        match = _DOTTED.match(text)
        if match:
            m1, d1, y1, m2, d2, y2 = match.groups()
            end = dt.date(int(y2), int(m2), int(d2))
            start_year = int(y1) if y1 else (end.year - (1 if int(m1) > int(m2) else 0))
            return dt.date(start_year, int(m1), int(d1)), end
    except ValueError:
        pass
    return None, None


def parse_dates(text, today):
    """(start, end) from a listing's date text, or (None, None). Reads "Through May 10, 2027" (an end only),
    "Opens Nov 21" (a start only), "Nov 6 – Dec 19, 2026", "October 15, 2026 to January 18, 2027" and an
    open-ended "Oct 29, 2025–" (a start only). Text with no day ("Through Spring 2027", "2026") gives (None, None)."""
    text = clean(text)
    text = re.sub(r'^(?:now open|coming soon|on view|opens?)\s*:?\s*', 'Opens ' if text.lower().startswith('opens') else '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+to\s+', ' - ', text)
    text = text.rstrip(' –—-')
    start, end = parse_date_text(text, today)
    if not (start or end):
        start, end = alternate_run(text)
    return start, end
