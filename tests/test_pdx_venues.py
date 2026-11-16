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
from scrapers.pdx import (adams_and_ollman, chefas_projects, galleries, lewis_clark_hoffman_gallery, nationale, oregon_contemporary,
                          psu_littman_white, reed_cooley_gallery)
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


class AdamsAndOllmanTest(unittest.TestCase):
    MENU = '<projectcontent><h2><a href="Current-Exhibitions">Exhibitions</a></h2></projectcontent>'

    def page(self, *lines):
        return '<html><body>' + self.MENU + '<projectcontent><h2>Current</h2><h2>Upcoming</h2><h2>Past</h2>' + ''.join(f'<i>{l}</i><br/>' for l in lines) + '</projectcontent></body></html>'

    def test_a_title_may_be_on_two_lines_and_ends_at_its_run(self):
        shows = adams_and_ollman.read_shows(soup(self.page('Peter Gallo', 'February 13–March 27, 2027', 'Conny Purtill:', 'The Ground',
                                                           'May 8–June 5, 2027')), TODAY)
        self.assertEqual(shows, [('Peter Gallo', dt.date(2027, 2, 13), dt.date(2027, 3, 27)),
                                 ('Conny Purtill: The Ground', dt.date(2027, 5, 8), dt.date(2027, 6, 5))])

    def test_a_page_with_no_show_gives_nothing_and_the_scraper_publishes_each_listed_show(self):
        self.assertEqual(adams_and_ollman.read_shows(soup(self.page()), TODAY), [])
        pages = {adams_and_ollman.PAGES[0]: self.page(), adams_and_ollman.PAGES[1]: self.page('Bethann Parker', 'April 3–May 1, 2027')}
        shows = run(adams_and_ollman, adams_and_ollman.scrape_adams_and_ollman, pages)
        self.assertEqual(sorted(shows), ['Bethann Parker'])
        self.assertEqual(shows['Bethann Parker']['phase'], 'future')


class LittmanAndWhiteTest(unittest.TestCase):
    PAGE = ('<main><p>Ongoing</p><p>10.26.26 - 01.22.27</p><p>Littman Gallery</p><h3>Always Almost • Mae Al-Jiboori</h3>'
            '<p>The experience of living in perpetual nearness.</p><a href="/littman">Learn More</a>'
            '<p>11.03.26 - 01.xx.27</p><p>White Gallery</p><h3>Ofrenda</h3><p>A collaborative exhibition.</p><a href="/white">Learn More</a>'
            '<p>10.27.26 - 12.08.27</p><p>Microgalleries</p><h3>Micro-Manifesto</h3><p>A manifesto is a declaration.</p>'
            '<a href="/microgalleries">Learn More</a><p>mailing list sign up</p></main>')

    def test_runs_are_read_with_a_month_only_end_and_a_mistyped_year(self):
        self.assertEqual(psu_littman_white.parse_run('10.26.26 - 01.22.27'), (dt.date(2026, 10, 26), dt.date(2027, 1, 22)))
        self.assertEqual(psu_littman_white.parse_run('11.03.26 - 01.xx.27'), (dt.date(2026, 11, 3), dt.date(2027, 1, 31)))
        self.assertEqual(psu_littman_white.parse_run('10.27.26 - 12.08.27'), (dt.date(2026, 10, 27), dt.date(2026, 12, 8)))
        self.assertEqual(psu_littman_white.parse_run('Ongoing'), (None, None))

    def test_each_show_has_its_title_artist_description_and_link(self):
        shows = {s['name']: s for s in psu_littman_white.read_shows(soup(self.PAGE), psu_littman_white.PAGE_URL)}
        self.assertEqual(sorted(shows), ['Always Almost', 'Micro-Manifesto', 'Ofrenda'])
        self.assertEqual(shows['Always Almost']['artist'], 'Mae Al-Jiboori')
        self.assertEqual(shows['Ofrenda']['link'], 'https://www.littmanandwhite.com/white')
        self.assertEqual(shows['Ofrenda']['description'], 'A collaborative exhibition.')

    def test_the_scraper_publishes_them_under_one_venue(self):
        shows = run(psu_littman_white, psu_littman_white.scrape_psu_littman_white, {psu_littman_white.PAGE_URL: self.PAGE})
        self.assertEqual(sorted(shows), ['Always Almost • Mae Al-Jiboori', 'Micro-Manifesto', 'Ofrenda'])
        self.assertEqual({s['venue'] for s in shows.values()}, {'Littman and White Galleries'})


class HoffmanGalleryTest(unittest.TestCase):
    HOME = ('<html><body><div><h3>Current Exhibition</h3><section><a href="/live/news/58521-converge-45">'
            '<img src="/x.jpg"></a><h4><a href="/live/news/58521-converge-45">Converge 45</a></h4></section></div></body></html>')
    SHOW = ('<html><head><title>Converge 45: Phool • Hoffman</title><meta property="og:title" content="Converge 45: Phool and Pony Express">'
            '</head><body><h1>Converge 45</h1><p>This fall, the Hoffman Gallery hosts a featured exhibition for the 2026 Converge 45 triennial '
            'with an immersive tarot-themed installation alongside a cinematic inquiry into historical reconstruction.</p>'
            '<p>The exhibition opens on Sunday, August 30, 2026 and continues through to December 10th. Gallery hours are 11am-4pm daily.</p>'
            '</body></html>')

    def test_the_run_is_read_from_the_sentence_that_gives_it(self):
        today = dt.date(2026, 11, 16)
        text = 'The exhibition opens on Sunday, August 30, 2026 and continues through to December 10th. Gallery hours are 11am-4pm daily.'
        self.assertEqual(lewis_clark_hoffman_gallery.parse_sentence(text, today), (dt.date(2026, 8, 30), dt.date(2026, 12, 10)))
        self.assertEqual(lewis_clark_hoffman_gallery.parse_sentence('Open daily 11am-4pm.', today), (None, None))

    def test_the_current_exhibition_is_found_on_the_home_page_and_published(self):
        url = 'https://www.lclark.edu/live/news/58521-converge-45'
        self.assertEqual(lewis_clark_hoffman_gallery.read_current(soup(self.HOME), lewis_clark_hoffman_gallery.PAGE_URL), url)
        shows = run(lewis_clark_hoffman_gallery, lewis_clark_hoffman_gallery.scrape_hoffman_gallery,
                    {lewis_clark_hoffman_gallery.PAGE_URL: self.HOME, url: self.SHOW})
        self.assertEqual(sorted(shows), ['Converge 45: Phool and Pony Express'])
        show = shows['Converge 45: Phool and Pony Express']
        self.assertEqual(show['dates'], {'start': dt.date(2026, 8, 30), 'end': dt.date(2026, 12, 10)})
        self.assertEqual(show['venue'], 'Hoffman Gallery')


class NationaleTest(unittest.TestCase):
    MENU = '<a href="/two-shows">CURRENT</a><a href="/upcoming">UPCOMING</a><a href="/project-room">PROJECT ROOM</a><a href="/past">PAST</a>'

    def page(self, *lines):
        return '<html><body>' + self.MENU + ''.join(f'<p>{line}</p>' for line in lines) + '</body></html>'

    def test_the_menu_gives_the_current_upcoming_and_project_room_pages(self):
        self.assertEqual(nationale.menu_links(soup(self.page()), nationale.HOME_URL),
                         ['https://www.nationale.us/two-shows', 'https://www.nationale.us/upcoming', 'https://www.nationale.us/project-room'])

    def test_artist_title_and_run_are_read_from_the_on_view_line(self):
        page = self.page('F R O N T G A L L E R Y', 'GABI VILLASEÑOR //', '“We found a freshwater spring while you were sleeping”',
                         'On view in the Front Space October 17–November 21, 2026', 'Opening reception Saturday, October 17 (2–4pm)')
        self.assertEqual(nationale.read_shows(soup(page), TODAY),
                         [('Gabi Villaseñor: We found a freshwater spring while you were sleeping', dt.date(2026, 10, 17), dt.date(2026, 11, 21))])

    def test_a_show_that_only_gives_its_opening_reception_is_held_back(self):
        page = self.page('UPCOMING //', 'WILLIAM MATHESON / Painting', 'Opening reception November 28, 2026 (2-4pm)')
        self.assertEqual(nationale.read_shows(soup(page), TODAY), [])

    def test_the_scraper_reads_every_menu_page_under_one_venue(self):
        pages = {nationale.HOME_URL: self.page(),
                 'https://www.nationale.us/two-shows': self.page('GABI VILLASEÑOR //', 'Spring', 'On view in the Front Space October 17–November 21, 2026'),
                 'https://www.nationale.us/upcoming': self.page('WILLIAM MATHESON / Painting', 'Opening reception November 28, 2026 (2-4pm)'),
                 'https://www.nationale.us/project-room': self.page('PURL SAMOHEYL //', 'It Feels like a Tuesday',
                                                                    'On view in the Project Room November 14–December 12, 2026')}
        shows = run(nationale, nationale.scrape_nationale, pages)
        self.assertEqual(sorted(shows), ['Gabi Villaseñor: Spring', 'Purl Samoheyl: It Feels like a Tuesday'])
        self.assertEqual({s['venue'] for s in shows.values()}, {'Nationale'})


class ChefasProjectsTest(unittest.TestCase):
    CURRENT = ('<html><head><meta property="og:title" content="KRISTEN DIEDERICH | OUTSIDE NATURE - CHEFAS PROJECTS"></head><body>'
               '<p>EXHIBITS</p><h1>KRISTEN DIEDERICH</h1><p>OUTSIDE NATURE</p><p>OCTOBER 23 - NOVEMBER 21, 2026</p><p>OPENING RECEPTION</p>'
               '<p>FRIDAY, OCTOBER 23, 2026</p></body></html>')

    def upcoming(self, *lines):
        return '<html><body><p>UPCOMING EXHIBITS</p>' + ''.join(f'<p>{line}</p>' for line in lines) + \
            '<p>134 SE TAYLOR STREET, SUITE 203, PORTLAND, OR 97214</p></body></html>'

    def test_the_current_show_is_named_from_its_title_and_dated_from_its_run(self):
        page = soup(self.CURRENT)
        self.assertEqual(chefas_projects.current_name(page), 'Kristen Diederich: Outside Nature')
        self.assertEqual(chefas_projects.current_run(page, TODAY), (dt.date(2026, 10, 23), dt.date(2026, 11, 21)))

    def test_upcoming_shows_that_only_say_when_they_open_are_held_back(self):
        page = soup(self.upcoming('HOLLY OSBORNE', 'OPENS DECEMBER 4, 2026', 'REQUEST COLLECTOR PREVIEW', 'NATE ORTON', 'OPENS DECEMBER 4, 2026'))
        self.assertEqual(chefas_projects.upcoming_shows(page, TODAY), [])

    def test_an_upcoming_show_with_a_full_run_is_published(self):
        page = soup(self.upcoming('HOLLY OSBORNE', 'DECEMBER 4 - JANUARY 9, 2027', 'NATE ORTON', 'OPENS JANUARY 15, 2027'))
        self.assertEqual(chefas_projects.upcoming_shows(page, TODAY), [('Holly Osborne', dt.date(2026, 12, 4), dt.date(2027, 1, 9))])
        shows = run(chefas_projects, chefas_projects.scrape_chefas_projects,
                    {chefas_projects.CURRENT_URL: self.CURRENT, chefas_projects.UPCOMING_URL: self.upcoming('HOLLY OSBORNE', 'DECEMBER 4 - JANUARY 9, 2027')})
        self.assertEqual(sorted(shows), ['Holly Osborne', 'Kristen Diederich: Outside Nature'])
        self.assertEqual(shows['Holly Osborne']['phase'], 'future')


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
