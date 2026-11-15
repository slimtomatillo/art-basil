# Run with the project's Python: python -m unittest discover -s tests
#
# Portland's first venues (WEBSITE-124). The fixtures are trimmed copies of the sites' text captured on 2026-11-15. No network.
import datetime as dt
import json
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.nyc import galleries as base
from scrapers.pdx import galleries, oregon_contemporary, reed_cooley_gallery
from scrapers.tor import _common

TODAY = dt.date(2026, 11, 15)
DATA = os.path.join(os.path.dirname(__file__), '..', 'docs', 'data')


def soup(html):
    return BeautifulSoup(html, 'html.parser')


def card(href, *lines):
    return f'<div class="card"><a href="{href}">{"".join(f"<p>{line}</p>" for line in lines)}</a></div>'


def run(module, scrape, pages, patch_on=None):
    """Run a scraper over {url: html}; returns {name: stored event}."""
    stored = []
    fetch = lambda url, *a, **k: soup(pages[url]) if url in pages else None
    targets = [module] + ([patch_on] if patch_on else [])
    patches = [mock.patch.object(t, 'fetch_and_parse', side_effect=fetch, create=True) for t in targets]
    patches += [mock.patch.object(module, 'region_today', return_value=TODAY, create=True),
                mock.patch.object(base, 'region_today', return_value=TODAY),
                mock.patch.object(_common, 'region_today', return_value=TODAY),
                mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d))]
    for p in patches:
        p.start()
    try:
        scrape(env='prod', region='pdx')
    finally:
        for p in patches:
            p.stop()
    return {e['name']: e for e in stored}


class GalleryCardsTest(unittest.TestCase):
    def scrape(self, venue, pages):
        return run(base, galleries.scrapers()[venue], pages)

    def test_a_card_is_artist_title_and_run_and_past_shows_are_dropped(self):
        url = galleries.SPECS['Froelick Gallery'].urls[0]
        page = '<main>' + card('/exhibitions/151-laurie-danial/', 'Laurie Danial', 'Beauty and the Long Walk Home', 'October 14 – November 28, 2026') \
            + card('/exhibitions/148-kris-hargis/', 'Kris Hargis', 'Alone, Together', 'July 21 – August 29, 2026') + '</main>'
        shows = self.scrape('Froelick Gallery', {url: page})
        self.assertEqual(sorted(shows), ['Laurie Danial: Beauty and the Long Walk Home'])
        show = shows['Laurie Danial: Beauty and the Long Walk Home']
        self.assertEqual(show['dates'], {'start': dt.date(2026, 10, 14), 'end': dt.date(2026, 11, 28)})
        self.assertEqual(show['venue'], 'Froelick Gallery')
        self.assertIn('gallery', show['tags'])

    def test_a_sentence_about_the_show_under_the_title_is_not_part_of_the_name(self):
        url = galleries.SPECS['Froelick Gallery'].urls[0]
        page = '<main>' + card('/exhibitions/153-confidants/', 'Confidants: Rick Bartow and Seiichi Hiroshima',
                               'Two close friends whose collaboration spanned decades.', 'December 2, 2026 – January 30, 2027') + '</main>'
        self.assertEqual(sorted(self.scrape('Froelick Gallery', {url: page})), ['Confidants: Rick Bartow and Seiichi Hiroshima'])

    def test_blue_sky_reads_both_its_current_and_upcoming_pages(self):
        current, upcoming = galleries.SPECS['Blue Sky Gallery'].urls
        shows = self.scrape('Blue Sky Gallery', {
            current: '<main>' + card('/gallery-exhibitions/2026/ashley-pena', 'Ashley Peña', 'Nov 5 - 28, 2026', 'Read more →') + '</main>',
            upcoming: '<main>' + card('/gallery-exhibitions/2026/someone', 'Someone Else', 'Dec 3 - 26, 2026', 'Read more →') + '</main>'})
        self.assertEqual(sorted(shows), ['Ashley Peña', 'Someone Else'])
        self.assertEqual(shows['Someone Else']['phase'], 'future')

    def test_the_museum_names_the_building_each_show_is_in(self):
        url = galleries.SPECS['Portland Art Museum'].urls[0]
        page = '<main>' + card('/event/rothko/', 'Exhibitions', 'The Art of Mark Rothko', 'A major survey of the painter across his career.',
                               '1219 SW Park Ave', 'Nov 20, 2025 – May 30, 2027') \
            + card('/event/mark/', 'Exhibitions', 'A Mark Building Show', 'About a show in the second building.',
                   '934 SW Salmon St', 'Oct 1, 2026 – Jan 31, 2027') + '</main>'
        shows = self.scrape('Portland Art Museum', {url: page})
        self.assertEqual(sorted(shows), ['A Mark Building Show', 'The Art of Mark Rothko'])
        self.assertEqual(shows['The Art of Mark Rothko']['locations'], ['Park Avenue'])
        self.assertEqual(shows['A Mark Building Show']['locations'], ['Mark Building'])
        self.assertIn('museum', shows['The Art of Mark Rothko']['tags'])


class OregonContemporaryTest(unittest.TestCase):
    LINES = ['On View and Upcoming', 'On view and upcoming at Ox', 'Gons: The Pictures, Mechanisms, and Camera Works of Doug Wing',
             'November 4th - December 19th', 'Curated by Kristan Kennedy + Organized by North Pole Studio',
             'Thought Forms: Open Studio', 'November 7th - February 6th', 'Curated by Jamison Edgar, CIR 12',
             'Andy Warhol:', 'Camouflage', '(1986)', 'This piece is part of our Special Art on Loan program & on view Fall 2026.']

    def test_titles_are_the_lines_above_a_run_and_the_year_is_worked_out(self):
        shows = oregon_contemporary.read_oregon_contemporary(self.LINES, TODAY)
        self.assertEqual([s[0] for s in shows], ['Gons: The Pictures, Mechanisms, and Camera Works of Doug Wing', 'Thought Forms: Open Studio'])
        self.assertEqual(shows[0][1:], (dt.date(2026, 11, 4), dt.date(2026, 12, 19)))
        self.assertEqual(shows[1][1:], (dt.date(2026, 11, 7), dt.date(2027, 2, 6)))

    def test_carnation_names_the_current_show_after_its_label(self):
        lines = ['Exhibitions', 'Artists', 'CURRENT:', 'Drip Slip Lapse', 'Russell Borne & Drew Laughery', 'November 7-29, 2026', 'ARCHIVE:']
        self.assertEqual(oregon_contemporary.read_carnation(lines, TODAY), [('Drip Slip Lapse', dt.date(2026, 11, 7), dt.date(2026, 11, 29))])

    def test_a_page_with_no_heading_or_label_gives_nothing(self):
        self.assertEqual(oregon_contemporary.read_oregon_contemporary(['Home', 'About'], TODAY), [])
        self.assertEqual(oregon_contemporary.read_carnation(['Home', 'About'], TODAY), [])

    def test_the_scrapers_publish_through_the_shared_helper(self):
        page = '<main>' + ''.join(f'<p>{line}</p>' for line in self.LINES) + '</main>'
        shows = run(oregon_contemporary, oregon_contemporary.scrape_oregon_contemporary, {oregon_contemporary.OC_URL: page})
        self.assertEqual(sorted(shows), ['Gons: The Pictures, Mechanisms, and Camera Works of Doug Wing', 'Thought Forms: Open Studio'])
        self.assertEqual(shows['Thought Forms: Open Studio']['venue'], 'Oregon Contemporary')


class CooleyTest(unittest.TestCase):
    def test_the_gallery_name_is_cut_from_the_title_and_ended_shows_are_dropped(self):
        listing = '<main><a href="/cooley/exhibitions/rose-salane.html">x</a><a href="/cooley/exhibitions/if.html">x</a></main>'

        def show(title, dates):
            return f'<html><head><title>{title} - Cooley Gallery - Reed College</title></head><body><main><h1>{title}</h1><p>{dates}</p></main></body></html>'
        pages = {reed_cooley_gallery.LISTINGS[0]: listing,
                 'https://www.reed.edu/cooley/exhibitions/rose-salane.html': show('Rose Salane: Afterlife in Public', 'August 29 – December 10, 2026'),
                 'https://www.reed.edu/cooley/exhibitions/if.html': show('IF', 'February 21 – May 17, 2026')}
        shows = run(reed_cooley_gallery, reed_cooley_gallery.scrape_cooley_gallery, pages, patch_on=None)
        self.assertEqual(sorted(shows), ['Rose Salane: Afterlife in Public'])


class RegionWiringTest(unittest.TestCase):
    def test_the_registry_and_the_venue_list_agree(self):
        import main
        scrapers, _ = main.get_venue_scrapers(selected_regions=['pdx'])
        with open(os.path.join(DATA, 'pdx_venues.json'), encoding='utf-8') as f:
            venues = json.load(f)
        self.assertEqual(sorted(scrapers), sorted(venues))

    def test_every_museum_has_an_admission_record_and_the_region_has_its_settings(self):
        with open(os.path.join(DATA, 'venue_admission.json'), encoding='utf-8') as f:
            admission = json.load(f)['pdx']
        self.assertIn('Portland Art Museum', admission)
        self.assertIn('Oregon Jewish Museum and Center for Holocaust Education', admission)
        for name, key in (('regions.json', 'pdx'), ('region_bounds.json', 'pdx')):
            with open(os.path.join(DATA, name), encoding='utf-8') as f:
                self.assertIn(key, json.load(f))


if __name__ == '__main__':
    unittest.main()
