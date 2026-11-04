import datetime as dt
import re

from config import MONTH_TO_NUM_DICT

_MONTHS = '|'.join(sorted(MONTH_TO_NUM_DICT, key=len, reverse=True))
_DATE_RE = re.compile(rf'(?:({_MONTHS})\.?\s+)?(\d{{1,2}})(?:\s+(\d{{4}}))?')
_MONTH_YEAR_RE = re.compile(rf'({_MONTHS})\.?\s+(\d{{4}})')

# How far in the past a yearless date can be before it is assumed to mean next year
_YEARLESS_LOOKBACK_DAYS = 60


_FRENCH_MONTHS = {
    'janvier': 'january', 'février': 'february', 'fevrier': 'february', 'mars': 'march', 'avril': 'april',
    'mai': 'may', 'juin': 'june', 'juillet': 'july', 'août': 'august', 'aout': 'august',
    'septembre': 'september', 'octobre': 'october', 'novembre': 'november', 'décembre': 'december',
    'decembre': 'december',
    # abbreviations ("2 oct au 28 nov", "12 sept. au 4 déc.")
    'janv': 'january', 'févr': 'february', 'fevr': 'february', 'avr': 'april', 'juil': 'july',
    'sept': 'september', 'déc': 'december',
    # Turkish ("12 Eylül - 20 Aralık 2026", day first like French); the capitals İ/I make no month's first letter
    'ocak': 'january', 'şubat': 'february', 'subat': 'february', 'mart': 'march', 'nisan': 'april', 'mayıs': 'may', 'mayis': 'may',
    'haziran': 'june', 'temmuz': 'july', 'ağustos': 'august', 'agustos': 'august', 'eylül': 'september',
    'eylul': 'september', 'ekim': 'october', 'kasım': 'november', 'kasim': 'november', 'aralık': 'december',
    'aralik': 'december',
}
_FRENCH_MONTH_RE = re.compile(rf"\b({'|'.join(sorted(_FRENCH_MONTHS, key=len, reverse=True))})\b\.?")
# Any month word, English or French-turned-English, for the day-first swap
_ANY_MONTH = '|'.join(sorted(set(_FRENCH_MONTHS.values()) | set(MONTH_TO_NUM_DICT), key=len, reverse=True))
_DAY_FIRST_RE = re.compile(rf"\b(\d{{1,2}})(?:er)?\s+({_ANY_MONTH})\b\.?")


def _from_french(text):
    """'du 24 octobre au 28 novembre 2026' -> 'october 24 - november 28 2026' (Turkish month names
    are read the same way). Text with neither a French/Turkish month name nor a French 'au'
    ("2 oct au 28 nov") is returned as it is, so English dates are never touched."""
    text = text.lower()
    if not (_FRENCH_MONTH_RE.search(text) or re.search(r'\d\s+(?:\S+\s+)?au\s+\d', text)):
        return text
    text = _FRENCH_MONTH_RE.sub(lambda m: _FRENCH_MONTHS[m.group(1)], text)
    text = _DAY_FIRST_RE.sub(r'\2 \1', text)
    text = re.sub(r"^\s*jusqu['’]au\s+", 'through ', text)
    text = re.sub(r'^\s*du\s+', '', text)
    return re.sub(r'\s+au\s+', ' - ', text)


def _normalize(text):
    text = _from_french(text).replace('–', '-').replace('—', '-')
    text = re.sub(r'(\d)(st|nd|rd|th)\b', r'\1', text)
    text = re.sub(r'\s+to\s+', '-', text)
    text = text.replace(',', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def _parse_side(side):
    """Returns (month, day, year); any may be None."""
    m = _DATE_RE.search(side)
    if not m:
        return None, None, None
    month, day, year = m.groups()
    return (MONTH_TO_NUM_DICT[month] if month else None), int(day), int(year) if year else None


def _yearless(month, day, today):
    """Year for a date written without one: the nearest occurrence that isn't
    long past (e.g. 'Through January 3' read in October means next January)."""
    candidate = dt.date(today.year, month, day)
    if candidate < today - dt.timedelta(days=_YEARLESS_LOOKBACK_DAYS):
        candidate = dt.date(today.year + 1, month, day)
    return candidate


def parse_date_text(text, today):
    """Parse an exhibition date label into (start, end) dates.

    Handles 'Oct 3-Dec 19, 2026', 'Oct 3rd, 2026-Feb 27, 2027', 'Oct 3-24, 2026',
    'September 12 - November 22, 2026', 'Through January 3' (no year: inferred
    from `today`), and a lone 'October 10, 2026' (treated as a start date).
    Returns (None, None) if no date can be read. `today` is only used to place
    dates written without a year.
    """
    t = _normalize(text)
    if not t:
        return None, None

    through = re.match(r'(?:through|until|thru|closes?)\s+(.*)', t)
    if through:
        month, day, year = _parse_side(through.group(1))
        if month is None:
            return None, None
        end = dt.date(year, month, day) if year else _yearless(month, day, today)
        return None, end

    if '-' not in t:
        month, day, year = _parse_side(t)
        if month is None:
            return None, None
        start = dt.date(year, month, day) if year else _yearless(month, day, today)
        return start, None

    left, right = t.split('-', 1)
    s_month, s_day, s_year = _parse_side(left)
    e_month, e_day, e_year = _parse_side(right)
    if s_day is None or e_day is None:
        return None, None
    # 'Oct 3-24, 2026': the end borrows the start's month
    e_month = e_month or s_month
    s_month = s_month or e_month
    if s_month is None:
        return None, None

    if e_year:
        end = dt.date(e_year, e_month, e_day)
    elif s_year:
        end = dt.date(s_year, e_month, e_day)
        if end < dt.date(s_year, s_month, s_day):
            end = dt.date(s_year + 1, e_month, e_day)
    else:
        end = _yearless(e_month, e_day, today)

    start_year = s_year or end.year
    start = dt.date(start_year, s_month, s_day)
    if not s_year and start > end:
        start = dt.date(start_year - 1, s_month, s_day)
    return start, end


def parse_month_year_range(text):
    """'October 2024-October 2025' / 'Nov 2023-Aug 2024' -> (start, end), both
    on the 1st. Returns (None, None) when the text isn't in this form."""
    t = _normalize(text)
    found = _MONTH_YEAR_RE.findall(t)
    if len(found) == 2:
        (m1, y1), (m2, y2) = found
        return dt.date(int(y1), MONTH_TO_NUM_DICT[m1], 1), dt.date(int(y2), MONTH_TO_NUM_DICT[m2], 1)
    return None, None
