# Run with the project's Python: python -m unittest discover -s tests
#
# WEBSITE-122: venues with several spaces pin each show only where it is. Pace, François Ghebaly, Charlie James, Jeffrey Deitch and
# SFAC Galleries now store the labels of the spaces a show names (`locations`); these are checked against fixtures trimmed from the
# markup the sites served on 2026-11-20. Nothing touches the network.
import datetime as dt
import json
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.la import charlie_james_gallery, francois_ghebaly, jeffrey_deitch
from scrapers.nyc import pace_gallery
from scrapers.sf import sfac_galleries
from scrapers.tor import _common

TODAY = dt.date(2026, 11, 20)
DATA = os.path.join(os.path.dirname(__file__), '..', 'docs', 'data')


def venue_labels(region, venue):
    with open(os.path.join(DATA, f'{region}_venues.json'), encoding='utf-8') as handle:
        return {a['label'] for a in json.load(handle)[venue]}


def run(module, scrape, region, pages=None, json_feed=None):
    """Run a scraper over {url: html} (or a JSON feed); returns {name: stored event}."""
    stored, asked = [], []

    def fetch(url, *args, **kwargs):
        asked.append(url)
        html = (pages or {}).get(url)
        return BeautifulSoup(html, 'html.parser') if html is not None else None

    with mock.patch.object(module, 'fetch_and_parse', side_effect=fetch, create=True), \
            mock.patch.object(module, 'fetch_json', return_value=json_feed, create=True), \
            mock.patch.object(module, 'region_today', return_value=TODAY, create=True), \
            mock.patch.object(_common, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
        getattr(module, scrape)(env='prod', region=region)
    return {e['name']: e for e in stored}, asked


# --- François Ghebaly: the listing item names its street address ------------------------------------------------------

def artlogic_item(slug, title, dates, address):
    return (f'<li><a href="/exhibitions/{slug}/"><div class="content"><h2>{title}</h2><span class="date">{dates}</span>'
            f'<span class="location">{address}</span></div></a></li>')


class GhebalyTest(unittest.TestCase):
    def test_the_address_on_a_listing_item_gives_the_space(self):
        spaces = francois_ghebaly.spaces
        self.assertEqual(spaces('417 N Camden Dr, Beverly Hills'), ['Beverly Hills'])
        self.assertEqual(spaces('2245 E Washington Blvd, Los Angeles'), ['Los Angeles'])
        self.assertEqual(spaces('Beverly Hills'), ['Beverly Hills'])
        self.assertIsNone(spaces(''))
        self.assertIsNone(spaces('somewhere else'))
        self.assertIsNone(spaces(None))

    def test_each_show_is_stored_with_its_own_space(self):
        pages = {
            francois_ghebaly.URLS[0]: '<ul>' + artlogic_item('1', 'Farah Al Qasimi', 'November 4 - December 12, 2026', '417 N Camden Dr, Beverly Hills') + '</ul>',
            francois_ghebaly.URLS[1]: '<ul>' + artlogic_item('2', 'Tran Truong', 'November 21, 2026 - January 2, 2027', '2245 E Washington Blvd, Los Angeles') + '</ul>',
        }
        shows, _ = run(francois_ghebaly, 'scrape_francois_ghebaly', 'la', pages)
        self.assertEqual(shows['Farah Al Qasimi']['locations'], ['Beverly Hills'])
        self.assertEqual(shows['Tran Truong']['locations'], ['Los Angeles'])

    def test_the_labels_are_those_of_the_venues_addresses(self):
        self.assertLessEqual({label for label, _ in francois_ghebaly.SPACES}, venue_labels('la', francois_ghebaly.VENUE))


# --- Jeffrey Deitch: each show in the JSON feed says where it is -----------------------------------------------------

def deitch_show(title, location, opening='2026-10-30', closing='2027-01-30'):
    return {'template': 'exhibition', 'title': title, 'openingdate': opening, 'closingdate': closing, 'location': location, 'text': '<p>Text.</p>'}


class DeitchTest(unittest.TestCase):
    def test_the_location_gives_the_space_or_both_or_none(self):
        spaces = jeffrey_deitch.spaces
        self.assertEqual(spaces('925 N. Orange Drive, Los Angeles'), ['Orange Drive'])
        self.assertEqual(spaces('7000 Santa Monica Blvd., Los Angeles'), ['Santa Monica Boulevard'])
        self.assertEqual(spaces('925 N. Orange Drive and 7000 Santa Monica Boulevard'), ['Orange Drive', 'Santa Monica Boulevard'])
        self.assertEqual(spaces('925 N. Orange Drive & 7000 Santa Monica Boulevard, Los Angeles'), ['Orange Drive', 'Santa Monica Boulevard'])
        self.assertIsNone(spaces('1114 Horn Avenue, West Hollywood'))                # a place the venue has no address for
        self.assertIsNone(spaces(None))

    def test_each_show_is_stored_with_its_space(self):
        feed = {'/los-angeles/exhibitions/barry-mcgee': deitch_show('Barry McGee: Another Round', '7000 Santa Monica Blvd., Los Angeles'),
                '/los-angeles/exhibitions/kiki-smith': deitch_show('Kiki Smith: Untethered Journey', '925 N. Orange Drive, Los Angeles'),
                '/los-angeles/exhibitions/both': deitch_show('Urs Fischer: YES and LA DUST', '925 N. Orange Drive and 7000 Santa Monica Boulevard'),
                '/los-angeles/exhibitions/unplaced': deitch_show('A Show', '')}
        shows, _ = run(jeffrey_deitch, 'scrape_jeffrey_deitch', 'la', json_feed=feed)
        self.assertEqual(shows['Barry McGee: Another Round']['locations'], ['Santa Monica Boulevard'])
        self.assertEqual(shows['Kiki Smith: Untethered Journey']['locations'], ['Orange Drive'])
        self.assertEqual(shows['Urs Fischer: YES and LA DUST']['locations'], ['Orange Drive', 'Santa Monica Boulevard'])
        self.assertNotIn('locations', shows['A Show'])                               # pinned at every address, as before

    def test_the_labels_are_those_of_the_venues_addresses(self):
        self.assertLessEqual({label for label, _ in jeffrey_deitch.SPACES}, venue_labels('la', jeffrey_deitch.VENUE))


# --- Charlie James Gallery: only a show's own page says which gallery -----------------------------------------------

def cj_card(slug, title, artist, dates):
    return (f'<div><a href="/exhibitions/{slug}"><span>{title}</span><span>{artist}</span><span>{title}</span>'
            f'<span>{dates}</span><span>Read more →</span></a></div>')


def cj_show_page(title, address, dates):
    return (f'<html><body><p>EXHIBITIONS</p><p>{title}</p><p>Exhibition</p><p>Current</p><p>Written by</p><p>Charlie James Gallery</p>'
            f'<p>{title}</p><p>{address}</p><p>{dates}</p><p>OPENING RECEPTION: november 6, 5-8pm</p>'
            f'<p>969 Chung King Road</p><p>Gallery 1</p><p>961 Chung King Road</p><p>Gallery 2</p></body></html>')


CJ_BASE = 'https://www.cjamesgallery.com'
CJ_LIST = ('<main><p>EXHIBITIONS</p><p>UPCOMING</p>' + cj_card('vecinos', 'Vecinos', 'Rigoberto Torres', 'November 6 - December 19, 2026')
           + cj_card('atthatmoment', 'At That Moment', 'James McClung', 'November 20, 2026 - January 2, 2027')
           + '<p>PAST</p>' + cj_card('eathappy', 'Eat Happy', 'Narsiso Martinez', 'September 25 - November 7, 2026') + '</main>')


class CharlieJamesTest(unittest.TestCase):
    def test_the_address_above_the_dates_gives_the_gallery_not_the_footer(self):
        page = lambda html: BeautifulSoup(html, 'html.parser')
        self.assertEqual(charlie_james_gallery.show_space(page(cj_show_page('Vecinos', '961 Chung King Road', 'november 6 - December 19, 2026'))), 'Gallery 2')
        self.assertEqual(charlie_james_gallery.show_space(page(cj_show_page('At That Moment', '969 Chung King Road', 'november 20, 2026 - January 2, 2027'))), 'Gallery 1')
        self.assertIsNone(charlie_james_gallery.show_space(page('<html><body><p>969 Chung King Road</p><p>Gallery 1</p><p>961 Chung King Road</p><p>Gallery 2</p></body></html>')))

    def test_each_current_and_upcoming_show_is_stored_with_its_gallery_and_a_past_one_is_not_fetched(self):
        pages = {CJ_BASE + '/exhibitions': CJ_LIST,
                 CJ_BASE + '/exhibitions/vecinos': cj_show_page('Vecinos', '961 Chung King Road', 'november 6 - December 19, 2026'),
                 CJ_BASE + '/exhibitions/atthatmoment': cj_show_page('At That Moment', '969 Chung King Road', 'november 20, 2026 - January 2, 2027')}
        shows, asked = run(charlie_james_gallery, 'scrape_charlie_james_gallery', 'la', pages)
        self.assertEqual(sorted(shows), ['James McClung: At That Moment', 'Rigoberto Torres: Vecinos'])
        self.assertEqual(shows['Rigoberto Torres: Vecinos']['locations'], ['Gallery 2'])
        self.assertEqual(shows['James McClung: At That Moment']['locations'], ['Gallery 1'])
        self.assertNotIn(CJ_BASE + '/exhibitions/eathappy', asked)

    def test_a_show_whose_page_cannot_be_read_is_stored_for_the_venue_as_a_whole(self):
        shows, _ = run(charlie_james_gallery, 'scrape_charlie_james_gallery', 'la', {CJ_BASE + '/exhibitions': CJ_LIST})
        self.assertEqual(sorted(shows), ['James McClung: At That Moment', 'Rigoberto Torres: Vecinos'])
        self.assertNotIn('locations', shows['Rigoberto Torres: Vecinos'])

    def test_the_labels_are_those_of_the_venues_addresses(self):
        self.assertLessEqual(set(charlie_james_gallery.SPACES.values()), venue_labels('la', charlie_james_gallery.VENUE))


# --- Pace Gallery: a show's page names its space after a "GALLERY" line --------------------------------------------

def pace_card(href, artist, subtitle, date):
    return (f'<a class="index-grid__link" href="{href}"><div class="index-grid__text-wrapper"><h3 class="index-grid__text-title">{artist}</h3>'
            f'<p class="index-grid__text-subtitle">{subtitle}</p><p class="index-grid__text-date">{date}</p>'
            f'<p class="index-grid__text-location">New York</p></div></a>')


def pace_page(*place_lines):
    return ('<html><body><h1>Show</h1><p>Nov 6 – Dec 19, 2026</p><p>GALLERY</p>' + ''.join(f'<p>{line}</p>' for line in place_lines)
            + '<p>New York</p><p>PRESS</p><p>Show at 125 Newbury in 2025.</p></body></html>')


class PaceTest(unittest.TestCase):
    def test_the_line_after_gallery_gives_the_label(self):
        read = lambda *lines: pace_gallery.show_space(BeautifulSoup(pace_page(*lines), 'html.parser'))
        self.assertEqual(read('540 West 25th Street'), '540 West 25th Street')
        self.assertEqual(read('508 & 510 West 25th Street'), '508 & 510 West 25th Street')
        self.assertEqual(read('125 Newbury', '395 Broadway'), '125 Newbury (395 Broadway)')
        self.assertIsNone(read('Somewhere Else'))
        self.assertIsNone(pace_gallery.show_space(BeautifulSoup('<html><body><p>No gallery line, 540 West 25th Street</p></body></html>', 'html.parser')))

    def test_each_current_show_is_stored_with_its_space(self):
        base = 'https://www.pacegallery.com'
        page = ('<main>' + pace_card('/exhibitions/li-hei-di/', 'Li Hei Di', 'the year of mud', 'Nov 6 – Dec 19, 2026')
                + pace_card('/exhibitions/transition/', 'Elmgreen & Dragset', 'TRANSITION', 'Nov 6, 2026 – Jan 16, 2027')
                + pace_card('/exhibitions/rothko/', 'Gottlieb/Rothko', 'The Surrealist Years', 'Nov 13, 2026 – Jan 9, 2027')
                + pace_card('/exhibitions/old/', 'Old', 'Gone', 'Mar 6 – Apr 4, 2026') + '</main>')
        pages = {pace_gallery.PAGE_URL: page, base + '/exhibitions/li-hei-di/': pace_page('540 West 25th Street'),
                 base + '/exhibitions/transition/': pace_page('508 & 510 West 25th Street'),
                 base + '/exhibitions/rothko/': pace_page('125 Newbury', '395 Broadway')}
        shows, asked = run(pace_gallery, 'scrape_pace_gallery', 'nyc', pages)
        self.assertEqual(shows['Li Hei Di: the year of mud']['locations'], ['540 West 25th Street'])
        self.assertEqual(shows['Elmgreen & Dragset: TRANSITION']['locations'], ['508 & 510 West 25th Street'])
        self.assertEqual(shows['Gottlieb/Rothko: The Surrealist Years']['locations'], ['125 Newbury (395 Broadway)'])
        self.assertNotIn(base + '/exhibitions/old/', asked)                          # a past show is not fetched

    def test_a_show_whose_page_cannot_be_fetched_is_stored_for_the_venue_as_a_whole(self):
        page = '<main>' + pace_card('/exhibitions/li-hei-di/', 'Li Hei Di', 'the year of mud', 'Nov 6 – Dec 19, 2026') + '</main>'
        shows, _ = run(pace_gallery, 'scrape_pace_gallery', 'nyc', {pace_gallery.PAGE_URL: page})
        self.assertNotIn('locations', shows['Li Hei Di: the year of mud'])

    def test_the_labels_are_those_of_the_venues_addresses(self):
        self.assertEqual(set(pace_gallery.SPACES), venue_labels('nyc', pace_gallery.VENUE))


# --- SFAC Galleries: the section a show is listed in names its space -------------------------------------------------

def sfac_section(space, title, dates):
    return (f'<div><img src="https://www.sf.gov/x.jpg"><section><p>{space}</p><h3><a href="/event/{title.lower().replace(" ", "-")}">{title}</a></h3>'
            f'<p>{dates}</p></section></div>')


class SfacTest(unittest.TestCase):
    def test_each_show_is_stored_with_the_address_of_its_space(self):
        page = ('<main>' + sfac_section('Main Gallery', 'Excavating Uranus', 'October 8, 2026 - January 30, 2027')
                + sfac_section('City Hall', 'Moving San Francisco', 'September 1, 2026 - November 25, 2026')
                + sfac_section('Cafe Valor', 'Views from the Archive', 'October 8, 2026 - November 25, 2026') + '</main>')
        shows, _ = run(sfac_galleries, 'scrape_sfac_galleries', 'sf', {sfac_galleries.PAGE_URL: page})
        self.assertEqual(shows['Excavating Uranus']['locations'], ['Main Gallery and Cafe Valor'])
        self.assertEqual(shows['Moving San Francisco']['locations'], ['Art at City Hall'])
        self.assertEqual(shows['Views from the Archive']['locations'], ['Main Gallery and Cafe Valor'])

    def test_every_space_it_reads_has_a_label_and_the_labels_are_those_of_the_venues_addresses(self):
        self.assertEqual(set(sfac_galleries.SPACES), set(sfac_galleries.LABELS))
        self.assertEqual(set(sfac_galleries.LABELS.values()), venue_labels('sf', sfac_galleries.VENUE))


if __name__ == '__main__':
    unittest.main()
