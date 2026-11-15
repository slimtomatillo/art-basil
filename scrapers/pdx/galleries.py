"""Portland's commercial galleries (WEBSITE-124): the same card reader as New York's (scrapers/nyc/galleries.py).

These galleries list their shows as cards on one page (what is on, what is coming, then an archive), and a card carries the
artist, the title and the run. See that module for how a card is read; a show whose dates are over is dropped by publish(),
so a listing that also holds its archive costs nothing. Each Spec here is one gallery, and all are Portland-only, so no
other-city filter is needed. SPECS holds them and scrapers() gives main.py the function for each.
"""
import re

from scrapers.nyc import galleries as base
from scrapers.nyc.galleries import Spec

REGION = 'pdx'
SPECS = {}


def _add(venue, urls, address, **kwargs):
    SPECS[venue] = Spec(venue, urls, spaces=[('', address, '')], **kwargs)


_add('Elizabeth Leach Gallery', ['https://elizabethleach.com/exhibitions/'], '417 NW 9th Ave, Portland, OR 97209')
_add('Russo Lee Gallery', ['https://www.russoleegallery.com/exhibitions'], '805 NW 21st Ave, Portland, OR 97209')
_add('Froelick Gallery', ['https://froelickgallery.com/exhibitions/'], '714 NW Davis St, Portland, OR 97209')
_add('Augen Gallery', ['https://www.augengallery.com/exhibitions/'], '716 NW Davis St, Portland, OR 97209')
_add('PDX Contemporary Art', ['https://www.pdxcontemporaryart.com/exhibitions'], '1881 NW Vaughn St, Portland, OR 97209',
     links='.views-row a[href]')


_add('Blue Sky Gallery', ['https://www.blueskygallery.org/currently-showing', 'https://www.blueskygallery.org/upcoming-exhibitions'],
     '122 NW 8th Ave, Portland, OR 97209', links='a[href*="/gallery-exhibitions/"]')
_add('Oregon Jewish Museum and Center for Holocaust Education',
     ['https://www.ojmche.org/exhibit-type/exhibitions/', 'https://www.ojmche.org/exhibit-type/upcoming-exhibitions/'],
     '724 NW Davis St, Portland, OR 97209', links='a[href*="/events/"]', tag='museum')


def _first_line(before):
    """The Portland Art Museum's card is the title, then a sentence about the show, then its address and run."""
    return next((line for line in before if line.lower() not in ('exhibitions', 'exhibition')), '')


# The museum shows in two buildings; a card names its address ("1219 SW Park Ave")
SPECS['Portland Art Museum'] = Spec(
    'Portland Art Museum', ['https://portlandartmuseum.org/exhibitions/', 'https://portlandartmuseum.org/upcoming-exhibitions/'],
    links='a[href*="/event/"]', tag='museum', name=_first_line,
    spaces=[('Park Avenue', '1219 SW Park Ave, Portland, OR 97205', r'\b1219\b'),
            ('Mark Building', '934 SW Salmon St, Portland, OR 97205', r'\b934\b|Mark Building')])


def addresses(venue):
    """The address entry for pdx_venues.json: a string for one space, a list of {label, address} for several."""
    spaces = SPECS[venue].spaces
    if len(spaces) > 1:
        return [{'label': label, 'address': address} for label, address, _ in spaces]
    return spaces[0][1]


def _make(spec):
    def scraper(env='prod', region=REGION):
        """Scrape and process this gallery's exhibitions."""
        return base.scrape(spec, env=env, region=region)
    scraper.__name__ = 'scrape_' + re.sub(r'\W+', '_', spec.venue.lower()).strip('_')
    return scraper


def scrapers():
    """{venue: scrape function} for main.py."""
    return {venue: _make(spec) for venue, spec in SPECS.items()}
