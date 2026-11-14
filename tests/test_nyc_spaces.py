# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# New York nonprofits and alternative spaces (WEBSITE-121, tier 2). Fixtures are trimmed copies of the sites' markup
# captured on 2026-11-13. Nothing touches the network.
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.nyc import (_common as nyc_common, bric, center_for_book_arts, pioneer_works, smack_mellon, the_kitchen,
                          white_columns)
from scrapers.tor import _common

TODAY = dt.date(2026, 11, 13)


def run(module, scrape, pages):
    """Run a scraper over {url: html}; returns {name: stored event}."""
    stored = []

    def fetch(url, *args, **kwargs):
        html = pages.get(url)
        return BeautifulSoup(html, 'html.parser') if html is not None else None

    with mock.patch.object(module, 'fetch_and_parse', side_effect=fetch), \
            mock.patch.object(module, 'region_today', return_value=TODAY, create=True), \
            mock.patch.object(_common, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
        getattr(module, scrape)(env='prod', region='nyc')
    return {e['name']: e for e in stored}


def image_of(event):
    return next((l['link'] for l in event['links'] if l['description'] == 'Image'), None)


class NumericRunTest(unittest.TestCase):
    def test_a_month_day_year_run_is_read_and_a_single_date_is_not_a_run(self):
        self.assertEqual(nyc_common.numeric_run('10.08.26 - 12.12.26'), (dt.date(2026, 10, 8), dt.date(2026, 12, 12)))
        self.assertEqual(nyc_common.numeric_run('02.11.27-05.16.27'), (dt.date(2027, 2, 11), dt.date(2027, 5, 16)))
        self.assertEqual(nyc_common.numeric_run('12.10.26'), (None, None))               # one day: an event
        self.assertEqual(nyc_common.numeric_run('13.45.26 - 14.01.26'), (None, None))    # not dates
        self.assertEqual(nyc_common.numeric_run('September 12 - December 20, 2026'), (None, None))


class BricTest(unittest.TestCase):
    def page(self, title, dates):
        return (f'<html><head><meta property="og:title" content="{title}"><meta property="og:description" '
                f'content="{title} is a group show of new work by artists in the 2026 residency, shown together for the first time.">'
                f'<meta property="og:image" content="https://bric.example/a.jpg"></head><body><h1>{title}</h1><p>{dates}</p></body></html>')

    def test_shows_with_a_numeric_run_are_read_and_a_one_day_event_page_is_not(self):
        listing = ('<main><a href="/exhibition/forking-paths/">x</a><a href="/exhibition/teen-bootcamp/">x</a>'
                   '<a href="/events/exhibitions/exhibition-archive/">past</a></main>')
        shows = run(bric, 'scrape_bric', {bric.LISTINGS[0]: listing,
                                          'https://bricartsmedia.org/exhibition/forking-paths/': self.page('Johan Orellana: Remnants of Forking Paths', '10.08.26 - 12.12.26'),
                                          'https://bricartsmedia.org/exhibition/teen-bootcamp/': self.page('Teen Photography Bootcamp Exhibition', '12.10.26')})
        self.assertEqual(sorted(shows), ['Johan Orellana: Remnants of Forking Paths'])
        show = shows['Johan Orellana: Remnants of Forking Paths']
        self.assertEqual((show['dates']['start'], show['dates']['end']), (dt.date(2026, 10, 8), dt.date(2026, 12, 12)))
        self.assertEqual(show['venue'], 'BRIC')
        self.assertIn('gallery', show['tags'])
        self.assertTrue(show['description'].startswith('Johan Orellana: Remnants of Forking Paths is a group show'))
        self.assertEqual(image_of(show), 'https://bric.example/a.jpg')


class SmackMellonTest(unittest.TestCase):
    PAGE = ('<main><div class="hero-slideshow_header"><a class="article" href="https://www.smackmellon.org/exhibition/how-we-work/">'
            '<div class="post-type">— Current Exhibition</div><h3 class="entry-title">How We Work: Smack Mellon at 30</h3>'
            '<div>September 19-December 6, 2026</div></a></div>'
            '<h2>Past Exhibitions</h2>'
            '<a class="article" href="https://www.smackmellon.org/exhibition/art-ready/"><div class="post-type">— Exhibition</div>'
            '<h3>Art Ready</h3><div>May 20-24, 2026</div></a></main>')

    def test_the_current_exhibition_is_read_and_the_past_ones_are_not(self):
        shows = run(smack_mellon, 'scrape_smack_mellon', {smack_mellon.PAGE_URL: self.PAGE})
        self.assertEqual(sorted(shows), ['How We Work: Smack Mellon at 30'])
        show = shows['How We Work: Smack Mellon at 30']
        self.assertEqual(show['dates'], {'start': dt.date(2026, 9, 19), 'end': dt.date(2026, 12, 6)})
        self.assertEqual(show['links'][0]['link'], 'https://www.smackmellon.org/exhibition/how-we-work/')

    def test_an_upcoming_exhibition_is_read_too_and_an_unreachable_page_stores_nothing(self):
        page = self.PAGE.replace('— Exhibition', '— Upcoming Exhibition').replace('May 20-24, 2026', 'January 23-April 18, 2027')
        shows = run(smack_mellon, 'scrape_smack_mellon', {smack_mellon.PAGE_URL: page})
        self.assertEqual(shows['Art Ready']['phase'], 'future')
        self.assertEqual(run(smack_mellon, 'scrape_smack_mellon', {}), {})


class KitchenTest(unittest.TestCase):
    PAGE = ('<main><a href="/on-view/">ON VIEW</a>'
            '<a href="/on-view/cant/"><img src="https://kitchen.example/a.jpg"><span>Steffani Jemison</span><span>Cant</span>'
            '<span>Dec 4, 2026</span><span>- Feb 6, 2027</span></a>'
            '<a href="/on-view/the-kitchens-2027-gala/"><span>The Kitchen 2027 Spring Gala</span><span>Honoring Olivier Berggruen</span><span>May 20</span></a>'
            '<a href="/on-view/all/">All Events</a></main>')

    def test_an_exhibition_with_a_run_is_read_and_an_event_with_one_date_is_not(self):
        shows = run(the_kitchen, 'scrape_the_kitchen', {the_kitchen.PAGE_URL: self.PAGE})
        self.assertEqual(sorted(shows), ['Steffani Jemison: Cant'])
        show = shows['Steffani Jemison: Cant']
        self.assertEqual((show['dates']['start'], show['dates']['end'], show['phase']), (dt.date(2026, 12, 4), dt.date(2027, 2, 6), 'future'))
        self.assertEqual(show['links'][0]['link'], 'https://thekitchen.org/on-view/cant/')
        self.assertEqual(image_of(show), 'https://kitchen.example/a.jpg')


class BookArtsTest(unittest.TestCase):
    PAGE = ('<main><a href="https://centerforbookarts.org/exhibitions/paper-cuts"><span>Exhibitions →</span>'
            '<span>Paper Cuts: Independent Publishing in the United States, 2000-2025</span><span>Sep 10–Dec 12, 2026</span></a>'
            '<a href="/exhibitions">Exhibitions</a></main>')

    def test_the_current_exhibition_is_read_without_the_label(self):
        shows = run(center_for_book_arts, 'scrape_center_for_book_arts', {center_for_book_arts.PAGE_URL: self.PAGE})
        self.assertEqual(sorted(shows), ['Paper Cuts: Independent Publishing in the United States, 2000-2025'])
        show = shows['Paper Cuts: Independent Publishing in the United States, 2000-2025']
        self.assertEqual(show['dates'], {'start': dt.date(2026, 9, 10), 'end': dt.date(2026, 12, 12)})


def wc_card(date, lines, href, image='https://wc.example/a.jpg'):
    text = ''.join(f'<span>{line}</span>' for line in [date] + lines)
    return f'<div class="grid-item"><div class="img-wrap"><a class="photo" href="{href}"><img src="{image}"></a></div><div class="txt-wrap">{text}<a class="grid-details" href="{href}"></a></div></div>'


class WhiteColumnsTest(unittest.TestCase):
    PAGE = ('<main>'
            + wc_card('November 7–December 19, 2026', ['Marc Hundley', 'SATELLITES ARE OUT\xa0TONIGHT'], 'https://whitecolumns.org/exhibitions/marc-hundley/')
            + wc_card('November 7–December 19, 2026', ['SHOP: Artists Who Do Shirts'], 'https://whitecolumns.org/exhibitions/shop/')
            + wc_card('October 30-December 11, 2026', ['White Columns Online #38:', 'Clothes, not Fashion', 'curated by Gemma Cirignano'],
                      'https://whitecolumns.org/exhibitions/online-38/')
            + wc_card('May 10–23, 1975', ['Tina Girouard', 'Screens'], 'https://whitecolumns.org/exhibitions/tina/')
            + '<div class="grid-item"><div class="txt-wrap"><span>Exhibition</span><span>Archive</span></div></div></main>')

    def test_the_current_cards_are_read_and_the_archive_ones_are_dropped_as_past(self):
        shows = run(white_columns, 'scrape_white_columns', {white_columns.PAGE_URL: self.PAGE})
        # (the page's non-breaking space between OUT and TONIGHT becomes a plain one)
        self.assertEqual(sorted(shows), ['Marc Hundley: SATELLITES ARE OUT TONIGHT', 'SHOP: Artists Who Do Shirts',
                                         'White Columns Online #38: Clothes, not Fashion'])
        show = shows['Marc Hundley: SATELLITES ARE OUT TONIGHT']
        self.assertEqual(show['dates'], {'start': dt.date(2026, 11, 7), 'end': dt.date(2026, 12, 19)})
        self.assertEqual(image_of(show), 'https://wc.example/a.jpg')


class PioneerWorksTest(unittest.TestCase):
    LISTING = ('<main><p>Current Exhibitions</p>'
               '<a href="/exhibitions/no-me"><img src="https://pw.example/a.jpg"></a>'
               '<p>September 12 – December 20, 2026</p><a href="/exhibitions/no-me"><span>There\'s no me without you</span><span>Finnegan Shannon, with Joselia Rebekah Hughes, and Alex Salerno</span></a>'
               '<a href="/exhibitions/siphon"><img src="https://pw.example/b.jpg"></a>'
               '<p>September 12 – November 22, 2026</p><a href="/exhibitions/siphon"><span>Siphon</span><span>Tuomas A. Laitinen</span></a>'
               '<p>On View</p><p>ONGOING</p><a href="/exhibitions/ukr"><span>Molly Gochman: UKR|RUS</span></a>'
               '<p>Past Exhibitions</p><p>June 21 - Aug 9, 2026</p><a href="/exhibitions/animal"><span>ANIMAL</span><span>Ash Fure</span></a></main>')

    def test_current_shows_are_read_by_their_lines_ongoing_and_past_are_not(self):
        shows = run(pioneer_works, 'scrape_pioneer_works', {pioneer_works.PAGE_URL: self.LISTING})
        self.assertEqual(sorted(shows), ["There's no me without you", 'Tuomas A. Laitinen: Siphon'])
        group = shows["There's no me without you"]                     # several artists: named by its title
        self.assertEqual(group['dates'], {'start': dt.date(2026, 9, 12), 'end': dt.date(2026, 12, 20)})
        self.assertEqual(group['links'][0]['link'], 'https://pioneerworks.org/exhibitions/no-me')
        self.assertEqual(image_of(group), 'https://pw.example/a.jpg')
        self.assertEqual(shows['Tuomas A. Laitinen: Siphon']['dates']['end'], dt.date(2026, 11, 22))

    def test_a_page_with_no_current_section_stores_nothing(self):
        self.assertEqual(run(pioneer_works, 'scrape_pioneer_works', {pioneer_works.PAGE_URL: '<main><p>Past Exhibitions</p></main>'}), {})


class RegistryTest(unittest.TestCase):
    def test_every_space_is_registered_and_has_an_address(self):
        import json
        import main
        scrapers, _ = main.get_venue_scrapers(selected_regions=['nyc'])
        with open(os.path.join(os.path.dirname(__file__), '../docs/data/nyc_venues.json'), encoding='utf-8') as f:
            venues = json.load(f)
        for module in (pioneer_works, bric, white_columns, smack_mellon, the_kitchen, center_for_book_arts):
            self.assertIn(module.VENUE, scrapers)
            self.assertIn(module.VENUE, venues)


if __name__ == '__main__':
    unittest.main()
