# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# SFAC Galleries, Root Division and the Chinese Culture Center (WEBSITE-109). The fixtures are trimmed
# copies of the sites' markup captured on 2026-11-11. No network.
import datetime as dt
import os
import sys
import unittest
from unittest import mock
from urllib.parse import urlparse

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import utils
from scrapers.sf import chinese_culture_center, root_division, sfac_galleries
from scrapers.tor import _common

TODAY = dt.date(2026, 11, 11)


def run(module, scrape, pages):
    """Run a scraper against {url: html}; returns the events it stored."""
    stored = []

    def fetch(url, *args, **kwargs):
        html = pages.get(url)
        return BeautifulSoup(html, 'html.parser') if html else None

    with mock.patch.object(module, 'fetch_and_parse', side_effect=fetch), \
            mock.patch.object(module, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
        scrape(env='prod')
    return stored


def sfac_column(space, title, href, dates, image):
    return (f'<div class="col"><img src="{image}" alt="x"/><section><p class="font-slab">{space}</p>'
            f'<div><h3><a href="{href}">{title}</a></h3><p>{dates}</p></div></section></div>')


SFAC = ('<main>'
        + sfac_column('Main Gallery', 'Excavating Uranus, A Psalm for Nyota Uhura', '/excavating-uranus/',
                      'October 8, 2026 - January 30, 2027', 'https://media.api.sf.gov/a.jpg')
        + sfac_column('City Hall', 'Moving San Francisco: Views from the SFMTA Photo Archive 1903 - Now',
                      '/moving-san-francisco/', 'January 15 - November 25, 2026', 'https://media.api.sf.gov/b.jpg')
        + sfac_column('Cafe Valor', 'Views from the SFMTA Photo Archive', '/views/', 'August 5 - November 25, 2026',
                      'https://media.api.sf.gov/c.jpg')
        # A talk and a workshop sit under other headings; they are programs, not exhibitions
        + '<div class="col"><section><p>SFAC Main Gallery</p><div><h3><a href="/talk/">Pslam &amp; Stardust: An Artist Talk</a></h3>'
          '<p>Thursday, November 12</p></div></section></div>'
        + sfac_column('SFAC Main Gallery', 'Making Worlds: a workshop', '/workshop/', 'Saturday, December 5', 'x.jpg')
        + '</main>')


class SfacTest(unittest.TestCase):
    def test_reads_the_three_spaces_and_skips_programs(self):
        events = run(sfac_galleries, sfac_galleries.scrape_sfac_galleries, {sfac_galleries.PAGE_URL: SFAC})
        self.assertEqual([e['name'] for e in events],
                         ['Excavating Uranus, A Psalm for Nyota Uhura',
                          'Moving San Francisco: Views from the SFMTA Photo Archive 1903 - Now',
                          'Views from the SFMTA Photo Archive'])
        first = events[0]
        self.assertEqual(first['venue'], 'SFAC Galleries')
        self.assertEqual(first['dates'], {'start': dt.date(2026, 10, 8), 'end': dt.date(2027, 1, 30)})
        self.assertEqual(first['phase'], 'current')
        self.assertIn('gallery', first['tags'])
        self.assertEqual(first['links'][0]['link'], 'https://www.sf.gov/excavating-uranus/')
        self.assertEqual(first['links'][1], {'link': 'https://media.api.sf.gov/a.jpg', 'description': 'Image'})
        self.assertEqual(events[1]['dates']['start'], dt.date(2026, 1, 15))

    def test_failed_fetch_keeps_existing_data(self):
        with self.assertLogs(level='WARNING'):
            self.assertEqual(run(sfac_galleries, sfac_galleries.scrape_sfac_galleries, {}), [])

    def test_a_page_with_no_exhibitions_says_what_it_was(self):
        page = '<html><head><title>Just a moment...</title></head><body><section><p>hi</p></section></body></html>'
        with self.assertLogs(level='WARNING') as logs:
            events = run(sfac_galleries, sfac_galleries.scrape_sfac_galleries, {sfac_galleries.PAGE_URL: page})
        self.assertEqual(events, [])
        self.assertIn("page title 'Just a moment...', 1 sections", '\n'.join(logs.output))

    def test_the_page_is_fetched_through_the_proxy(self):
        # first CI run 2026-11-12: nothing found, no error; see the comment in utils.PROXY_DOMAINS
        self.assertIn(urlparse(sfac_galleries.PAGE_URL).netloc, utils.PROXY_DOMAINS)


def rd_item(title, dates, slug):
    return (f'<div class="pt-cv-content-item"><div class="pt-cv-thumb-wrapper"><a href="https://rootdivision.org/exhibition/{slug}/">'
            f'<img class="pt-cv-thumbnail" src="https://rootdivision.org/pic-{slug}.png"/></a></div>'
            f'<h2 class="pt-cv-title"><a href="https://rootdivision.org/exhibition/{slug}/">{title}</a></h2>'
            f'<div class="pt-cv-ctf-value">{dates}</div><div class="pt-cv-content">Short excerpt ...</div></div>')


RD_SHOW = ('<html><head><meta property="og:description" content="Text from a different show"></head><body><article>'
           '<h1>Root Division Presents: NEW WORKS</h1><p>New Works 2026</p>'
           '<p>Root Division is proud to present <em>New Works</em>, a biennial exhibition celebrating artists in the '
           'Studios Program.</p><p>Opening Reception</p></article></body></html>')


class RootDivisionTest(unittest.TestCase):
    def test_reads_the_listing_and_the_show_page(self):
        pages = {root_division.PAGE_URL: '<article>' + rd_item('New Works', 'November 14 – December 19, 2026', 'new-works-2') + '</article>',
                 'https://rootdivision.org/exhibition/new-works-2/': RD_SHOW}
        events = run(root_division, root_division.scrape_root_division, pages)
        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual((e['name'], e['venue'], e['phase']), ('New Works', 'Root Division', 'future'))
        self.assertEqual(e['dates'], {'start': dt.date(2026, 11, 14), 'end': dt.date(2026, 12, 19)})
        # The description is the show page's own text, not the page's (stale) og:description, and reads cleanly
        self.assertTrue(e['description'].startswith('Root Division is proud to present New Works, a biennial'))
        self.assertNotIn('different show', e['description'])
        self.assertEqual(e['links'][1]['link'], 'https://rootdivision.org/pic-new-works-2.png')

    def test_between_shows_the_page_is_empty_and_nothing_is_stored(self):
        with self.assertLogs(level='WARNING'):
            events = run(root_division, root_division.scrape_root_division,
                         {root_division.PAGE_URL: '<article><p>No posts found</p></article>'})
        self.assertEqual(events, [])


def ccc_item(title, text, category, slug):
    return (f'<div data-hook="post-list-item"><a href="https://www.cccsf.us/post/{slug}">'
            f'<div data-hook="post-list-item__title"><div data-hook="post-title"><h2>{title}</h2></div></div></a>'
            f'<div data-hook="post-description"><div>{text}</div></div>'
            f'<span data-hook="post-category-label">{category}</span></div>')


class ChineseCultureCenterTest(unittest.TestCase):
    PAGE = ('<main>' + ccc_item('Carry-On by Justin Wong', 'February 14, 2026 - Ongoing', 'EXHIBITION', 'carry-on')
            + ccc_item('Youth Unity Mural in Bayview-Hunters Point', 'August 16, 2021 - Ongoing', 'PUBLIC ART', 'mural')
            + ccc_item('A closed show', 'January 10 - March 1, 2026', 'EXHIBITION', 'closed') + '</main>')

    def test_keeps_exhibitions_marks_open_ended_ones_ongoing_and_skips_public_art(self):
        events = run(chinese_culture_center, chinese_culture_center.scrape_chinese_culture_center,
                     {chinese_culture_center.PAGE_URL: self.PAGE})
        self.assertEqual([e['name'] for e in events], ['Carry-On by Justin Wong'])
        e = events[0]
        self.assertEqual(e['venue'], 'Chinese Culture Center of San Francisco')
        self.assertEqual(e['dates'], {'start': dt.date(2026, 2, 14), 'end': None})
        self.assertTrue(e['ongoing'])
        self.assertEqual(e['phase'], 'current')
        self.assertEqual(e['links'][0]['link'], 'https://www.cccsf.us/post/carry-on')

    def test_a_dated_show_is_not_ongoing(self):
        page = '<main>' + ccc_item('Spring show', 'March 1 - May 30, 2027', 'EXHIBITION', 'spring') + '</main>'
        events = run(chinese_culture_center, chinese_culture_center.scrape_chinese_culture_center,
                     {chinese_culture_center.PAGE_URL: page})
        self.assertFalse(events[0]['ongoing'])
        self.assertEqual(events[0]['phase'], 'future')


if __name__ == '__main__':
    unittest.main()
