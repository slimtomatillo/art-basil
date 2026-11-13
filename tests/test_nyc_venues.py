# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# The New York venues (WEBSITE-120). Each fixture is a trimmed copy of the site's listing markup captured on
# 2026-11-13. Nothing touches the network.
import datetime as dt
import json
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.la import night_gallery
from scrapers.nyc import (david_zwirner, frick_collection, guggenheim, night_gallery_new_york, pace_gallery,
                          studio_museum_in_harlem, whitney)
from scrapers.tor import _common

TODAY = dt.date(2026, 11, 13)


def soup(html):
    return BeautifulSoup(html, 'html.parser')


def run(module, scrape, pages, region='nyc', extra=()):
    """Run a scraper over {url: html}; returns {name: stored event}."""
    stored = []

    def fetch(url, *args, **kwargs):
        html = pages.get(url)
        return soup(html) if html is not None else None

    patches = [mock.patch.object(module, 'fetch_and_parse', side_effect=fetch),
               mock.patch.object(module, 'region_today', return_value=TODAY, create=True),
               mock.patch.object(_common, 'region_today', return_value=TODAY),
               mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d))]
    for target, name in extra:
        patches.append(mock.patch.object(target, name, side_effect=fetch, create=True))
    for p in patches:
        p.start()
    try:
        getattr(module, scrape)(env='prod', region=region)
    finally:
        for p in patches:
            p.stop()
    return {e['name']: e for e in stored}


def image_of(event):
    return next((l['link'] for l in event['links'] if l['description'] == 'Image'), None)


class WhitneyTest(unittest.TestCase):
    PAGE = ('<main>'
            '<a href="/exhibitions/lichtenstein"><img src="https://whitneymedia.org/a.jpg"><div class="list-item__text">'
            '<h3 class="list-item__title"> Roy Lichtenstein: Like New </h3><p class="list-item__subtitle"> Through May 10, 2027 </p></div></a>'
            '<a href="/exhibitions/artport-25"><img src="https://whitneymedia.org/b.jpg"><div class="list-item__text">'
            '<h3 class="list-item__title">artport: A History of Internet Art</h3><p class="list-item__subtitle">Opens Nov 21</p></div></a>'
            '<a href="/exhibitions/frank-wang"><div class="list-item__text"><h3 class="list-item__title">Frank WANG Yefeng: The Levitating Perils #2</h3>'
            '<p class="list-item__subtitle">Oct 29, 2025–</p></div></a>'
            '<a href="/exhibitions/charles-burchfield"><div class="list-item__text"><h3 class="list-item__title">Charles Burchfield: Elemental</h3>'
            '<p class="list-item__subtitle">Through Spring 2027</p></div></a>'
            '<a href="/exhibitions/untitled-america"><div class="list-item__text"><h3 class="list-item__title">“Untitled” (America)</h3></div></a>'
            '<a href="/exhibitions/performance">Performance Upcoming and past</a>'
            '</main>')

    def test_shows_with_a_day_are_read_and_the_rest_left_out(self):
        shows = run(whitney, 'scrape_whitney', {whitney.PAGE_URL: self.PAGE})
        self.assertEqual(sorted(shows), ['Frank WANG Yefeng: The Levitating Perils #2', 'Roy Lichtenstein: Like New',
                                         'artport: A History of Internet Art'])
        run_ = shows['Roy Lichtenstein: Like New']
        self.assertEqual((run_['dates']['start'], run_['dates']['end'], run_['phase']), (None, dt.date(2027, 5, 10), 'current'))
        self.assertEqual(run_['venue'], 'Whitney Museum of American Art')
        self.assertIn('museum', run_['tags'])
        self.assertEqual(run_['links'][0], {'link': 'https://whitney.org/exhibitions/lichtenstein', 'description': 'Event Page'})
        self.assertEqual(image_of(run_), 'https://whitneymedia.org/a.jpg')

    def test_an_opening_and_an_open_ended_run(self):
        shows = run(whitney, 'scrape_whitney', {whitney.PAGE_URL: self.PAGE})
        soon = shows['artport: A History of Internet Art']
        self.assertEqual((soon['dates']['start'], soon['dates']['end'], soon['phase']), (dt.date(2026, 11, 21), None, 'future'))
        open_ended = shows['Frank WANG Yefeng: The Levitating Perils #2']
        self.assertEqual((open_ended['dates']['start'], open_ended['dates']['end']), (dt.date(2025, 10, 29), None))

    def test_an_unreachable_page_stores_nothing(self):
        self.assertEqual(run(whitney, 'scrape_whitney', {}), {})


def guggenheim_page(on_view, upcoming):
    data = {'initial': {'main': {'posts': {'featuredExhibitions': {
        'on_view': {'items': on_view}, 'upcoming': {'items': upcoming}, 'past': {'items': [{'title': 'Old', 'slug': 'old'}]}}}}}}
    return f'<html><body><script>const appConfig = {{"x":1}};</script><script>const bootstrap = {json.dumps(data)};</script></body></html>'


def gug_item(title, slug, start, end, label='', excerpt='An exhibition.', image='/wp-content/uploads/a.jpg'):
    def part(d):
        return {'day': str(d.day), 'month': d.strftime('%B'), 'year': str(d.year)}
    return {'title': title, 'slug': slug, 'dates': {'start': part(start), 'end': part(end), 'label': label},
            'excerpt': excerpt, 'featuredImage': {'sourceUrl': image}}


class GuggenheimTest(unittest.TestCase):
    PAGE = guggenheim_page(
        [gug_item('TARYN SIMON<br>FATHER COUNTRY<br>I DO LOVE YOU', 'taryn-simon', dt.date(2026, 9, 18), dt.date(2027, 3, 14),
                  excerpt='Experience an <em>interactive</em> installation.'),
         gug_item('Collection in Focus | Modern European Currents', 'cif', dt.date(2025, 7, 15), dt.date(2027, 1, 10)),
         gug_item('Thannhauser Collection', 'thannhauser', dt.date(2015, 9, 18), dt.date(2025, 9, 9), label='Ongoing')],
        [gug_item('I dream in another language | Do Ho Suh', 'do-ho-suh', dt.date(2027, 2, 19), dt.date(2027, 8, 1))])

    def test_the_embedded_exhibitions_are_read_with_description_picture_and_page(self):
        shows = run(guggenheim, 'scrape_guggenheim', {guggenheim.PAGE_URL: self.PAGE})
        self.assertEqual(sorted(shows), ['Collection in Focus: Modern European Currents', 'I dream in another language: Do Ho Suh',
                                         'Taryn Simon: Father Country: I Do Love You'])
        taryn = shows['Taryn Simon: Father Country: I Do Love You']
        self.assertEqual(taryn['dates'], {'start': dt.date(2026, 9, 18), 'end': dt.date(2027, 3, 14)})
        self.assertEqual(taryn['description'], 'Experience an interactive installation.')      # no HTML
        self.assertEqual(taryn['links'][0]['link'], 'https://www.guggenheim.org/exhibition/taryn-simon')
        self.assertEqual(image_of(taryn), 'https://www.guggenheim.org/wp-content/uploads/a.jpg')
        self.assertEqual(shows['I dream in another language: Do Ho Suh']['phase'], 'future')

    def test_an_ongoing_permanent_display_and_the_past_list_are_left_out(self):
        shows = run(guggenheim, 'scrape_guggenheim', {guggenheim.PAGE_URL: self.PAGE})
        self.assertNotIn('Thannhauser Collection', shows)
        self.assertNotIn('Old', shows)

    def test_a_page_without_the_data_or_unreachable_stores_nothing(self):
        self.assertEqual(run(guggenheim, 'scrape_guggenheim', {guggenheim.PAGE_URL: '<html><body>Exhibitions</body></html>'}), {})
        self.assertEqual(run(guggenheim, 'scrape_guggenheim', {}), {})


def studio_card(href, title, text, image='https://studiomuseum.imgix.net/a.jpg'):
    return (f'<a class="ActivityCard_main" href="{href}"><div><img src="{image}"></div>'
            f'<div><h3>{title}</h3><span>{title}</span><p>{text}</p></div></a>')


class StudioMuseumTest(unittest.TestCase):
    PAGE = ('<main>' + studio_card('/exhibitions/tone', 'Tone', 'Through January 3, 2027')
            + studio_card('/exhibitions/woody', 'Woody De Othello: coming forth by day', '02.11.27-05.16.27')
            + studio_card('/exhibitions/archives', 'To Be A Place', 'Ongoing')
            + studio_card('/exhibitions/artist-installations', 'Artist Installations', 'On Long-term View') + '</main>')

    def test_a_through_date_and_a_month_day_year_run_are_read_and_permanent_installations_are_not(self):
        shows = run(studio_museum_in_harlem, 'scrape_studio_museum_in_harlem', {studio_museum_in_harlem.PAGE_URL: self.PAGE})
        self.assertEqual(sorted(shows), ['Tone', 'Woody De Othello: coming forth by day'])
        self.assertEqual((shows['Tone']['dates']['start'], shows['Tone']['dates']['end']), (None, dt.date(2027, 1, 3)))
        woody = shows['Woody De Othello: coming forth by day']
        self.assertEqual((woody['dates']['start'], woody['dates']['end'], woody['phase']),
                         (dt.date(2027, 2, 11), dt.date(2027, 5, 16), 'future'))
        self.assertEqual(woody['links'][0]['link'], 'https://www.studiomuseum.org/exhibitions/woody')
        self.assertEqual(image_of(woody), 'https://studiomuseum.imgix.net/a.jpg')


def frick_card(title, run_text, text, slug, image='/sites/default/files/a.jpg'):
    return (f'<div class="paragraph paragraph-card"><img src="{image}"><div class="paragraph-card__content-text">'
            f'<div class="paragraph-card__body-text"><p><em><strong>{title}</strong></em><br/>{run_text}</p><p>{text}</p>'
            f'<p><a href="/exhibitions/{slug}">Read More<span>about the {slug} exhibition</span></a></p></div></div></div>')


class FrickTest(unittest.TestCase):
    PAGE = ('<main><nav><a>Current</a><a>Upcoming</a><a>Past</a></nav><h2>Current</h2>'
            + frick_card('Siena: The Art of Bronze, 1450–1500', 'October 15, 2026 to January 18, 2027',
                         'The first exhibition to focus on Siena as a center of excellence in bronze sculpture.', 'siena')
            + '<h2>Upcoming</h2>'
            + frick_card('Kent Monkman: Officer and Laughing Girl', 'November 12, 2026 to February 22, 2027', 'New paintings by Kent Monkman.', 'monkman')
            + '<h2>Past</h2>'
            + frick_card('Ruffles &amp; Ribbons', 'April 1, 2026 to August 3, 2026', 'Fashion plates.', 'ruffles') + '</main>')

    def test_current_and_upcoming_shows_are_read_with_their_description_and_picture_and_past_ones_are_not(self):
        shows = run(frick_collection, 'scrape_frick_collection', {frick_collection.PAGE_URL: self.PAGE})
        self.assertEqual(sorted(shows), ['Kent Monkman: Officer and Laughing Girl', 'Siena: The Art of Bronze, 1450–1500'])
        siena = shows['Siena: The Art of Bronze, 1450–1500']
        self.assertEqual(siena['dates'], {'start': dt.date(2026, 10, 15), 'end': dt.date(2027, 1, 18)})
        self.assertTrue(siena['description'].startswith('The first exhibition to focus on Siena'))
        self.assertEqual(siena['links'][0]['link'], 'https://www.frick.org/exhibitions/siena')
        self.assertEqual(image_of(siena), 'https://www.frick.org/sites/default/files/a.jpg')
        self.assertEqual(shows['Kent Monkman: Officer and Laughing Girl']['phase'], 'current')


def pace_card(href, artist, subtitle, date, city, status='On View'):
    return (f'<a class="index-grid__link" href="{href}"><div class="index-grid__image-wrapper"><img src="https://www.pacegallery.com/media/{href.strip("/").split("/")[-1]}.png"></div>'
            f'<div class="index-grid__text-wrapper"><h3 class="index-grid__text-title">{artist}</h3><p class="index-grid__text-status">{status}</p>'
            f'<p class="index-grid__text-subtitle">{subtitle}</p><p class="index-grid__text-date">{date}</p><p class="index-grid__text-location">{city}</p></div></a>')


class PaceTest(unittest.TestCase):
    PAGE = ('<main>' + pace_card('/exhibitions/li-hei-di/', 'Li Hei Di', 'the year of mud', 'Nov 6 – Dec 19, 2026', 'New York')
            + pace_card('/exhibitions/david-lynch-la/', 'David Lynch', 'LA', 'Sep 19 – Dec 22, 2026', 'Los Angeles')
            + pace_card('/exhibitions/brancusi/', 'Constantin Brancusi', 'Matrix Muse', 'Nov 25, 2026 – Jan 30, 2027', 'London', 'Upcoming')
            + pace_card('/exhibitions/david-byrne/', 'David Byrne', '', 'Apr 10, 2025 – Dec 31, 2026', 'New York') + '</main>')

    def test_only_new_york_shows_are_kept_named_artist_and_title(self):
        shows = run(pace_gallery, 'scrape_pace_gallery', {pace_gallery.PAGE_URL: self.PAGE})
        self.assertEqual(sorted(shows), ['David Byrne', 'Li Hei Di: the year of mud'])
        show = shows['Li Hei Di: the year of mud']
        self.assertEqual(show['dates'], {'start': dt.date(2026, 11, 6), 'end': dt.date(2026, 12, 19)})
        self.assertIn('gallery', show['tags'])
        self.assertEqual(show['links'][0]['link'], 'https://www.pacegallery.com/exhibitions/li-hei-di/')
        self.assertTrue(image_of(show).endswith('li-hei-di.png'))


def zwirner_card(href, lines):
    text = ''.join(f'<span>{line}</span>' for line in lines)
    return f'<div class="group relative"><img src="https://cdn.example/{href.split("/")[-1]}.jpg"><a class="absolute inset-0" href="{href}"><span class="sr-only">{lines[0]}</span></a>{text}</div>'


class ZwirnerTest(unittest.TestCase):
    PAGE = ('<main>'
            + zwirner_card('/exhibitions/2026/jem-perucchini', ['Jem Perucchini', 'Jem Perucchini', 'Sospiro', 'New York: Tribeca',
                                                               'Now Open: November 6—December 19, 2026', 'Learn More'])
            + zwirner_card('/exhibitions/2026/yoshitomo-nara', ['Yoshitomo Nara', 'Yoshitomo Nara', 'New York: 19th Street, New York: 20th Street',
                                                               'Now Open: November 5—December 12, 2026', 'Learn More'])
            + zwirner_card('/exhibitions/2026/yoshitomo-nara', ['Yoshitomo Nara', 'Yoshitomo Nara', 'New York: 19th Street, New York: 20th Street',
                                                               'Now Open: November 5—December 12, 2026', 'Learn More'])
            + zwirner_card('/exhibitions/2026/thomas-ruff', ['Thomas Ruff', 'In Series, 1979–2024', 'Los Angeles',
                                                            'Now Open: November 13, 2026—February 6, 2027', 'Learn More'])
            + zwirner_card('/exhibitions/2026/frank-walter', ['Frank Walter', 'London', 'Coming Soon: November 25—December 5, 2026', 'Learn More'])
            + '</main>')

    def test_new_york_shows_are_kept_once_named_artist_and_title(self):
        shows = run(david_zwirner, 'scrape_david_zwirner', {david_zwirner.PAGE_URL: self.PAGE})
        self.assertEqual(sorted(shows), ['Jem Perucchini: Sospiro', 'Yoshitomo Nara'])
        nara = shows['Yoshitomo Nara']
        self.assertEqual(nara['dates'], {'start': dt.date(2026, 11, 5), 'end': dt.date(2026, 12, 12)})
        self.assertEqual(nara['links'][0]['link'], 'https://www.davidzwirner.com/exhibitions/2026/yoshitomo-nara')
        self.assertEqual(image_of(shows['Jem Perucchini: Sospiro']), 'https://cdn.example/jem-perucchini.jpg')


NG_LISTING = ('<main><p>Current</p><p>Upcoming</p><p>Past</p>'
              '<div><a href="/exhibitions/hasani-sahlehe2"><p>HASANI SAHLEHE</p><p>Monoprints</p><p>November 13 – December 18, 2026</p></a></div>'
              '<div><a href="/exhibitions/tidawhitney-lek"><p>TIDAWHITNEY LEK</p><p>Something Familiar</p><p>November 21 – January 30, 2027</p></a></div></main>')
NG_NY = '<head><meta property="og:description" content="HASANI SAHLEHE Monoprints November 13-December 18, 2026 61 Lispenard St, 2nd Floor New York, NY Night gallery is pleased to present new monoprints in our Tribeca, New York viewing room."></head>'
NG_LA = '<head><meta property="og:description" content="TIDAWHITNEY LEK Something Familiar November 21-January 30, 2027 2050 Imperial St Los Angeles, CA 90021 Night gallery is pleased to present new work."></head>'
NG_PAGES = {night_gallery.EXHIBITIONS_URL: NG_LISTING,
            'https://www.nightgallery.ca/exhibitions/hasani-sahlehe2': NG_NY,
            'https://www.nightgallery.ca/exhibitions/tidawhitney-lek': NG_LA}


class NightGalleryTest(unittest.TestCase):
    def test_a_show_is_placed_by_the_address_on_its_own_page(self):
        pages = {'ny': NG_NY, 'la': NG_LA, 'blank': '<head></head><body>Nothing here</body>',
                 'mention': '<head><meta name="description" content="Los Angeles, CA. The artist lives in New York, NY."></head>'}
        with mock.patch.object(night_gallery, 'fetch_and_parse', side_effect=lambda url: soup(pages[url]) if url in pages else None):
            self.assertEqual(night_gallery.show_city('ny'), 'nyc')
            self.assertEqual(night_gallery.show_city('la'), 'la')
            self.assertEqual(night_gallery.show_city('blank'), 'la')            # no city named: Los Angeles, as before
            self.assertEqual(night_gallery.show_city('mention'), 'la')          # an address in Los Angeles wins
            self.assertEqual(night_gallery.show_city('missing'), 'la')          # an unreadable page: Los Angeles
            self.assertEqual(night_gallery.show_city(None), 'la')

    def test_los_angeles_keeps_its_shows_and_leaves_the_new_york_one(self):
        shows = run(night_gallery, 'scrape_night_gallery', NG_PAGES, region='la')
        self.assertEqual(sorted(shows), ['Tidawhitney Lek: Something Familiar'])
        self.assertEqual(shows['Tidawhitney Lek: Something Familiar']['venue'], 'Night Gallery')
        self.assertEqual(shows['Tidawhitney Lek: Something Familiar']['links'][0]['link'],
                         'https://www.nightgallery.ca/exhibitions/tidawhitney-lek')

    def test_new_york_takes_the_new_york_show(self):
        shows = run(night_gallery_new_york, 'scrape_night_gallery_new_york', NG_PAGES,
                    extra=[(night_gallery, 'fetch_and_parse')])
        self.assertEqual(sorted(shows), ['Hasani Sahlehe: Monoprints'])
        show = shows['Hasani Sahlehe: Monoprints']
        self.assertEqual(show['venue'], 'Night Gallery New York')
        self.assertEqual(show['dates'], {'start': dt.date(2026, 11, 13), 'end': dt.date(2026, 12, 18)})
        self.assertEqual(show['links'][0]['link'], 'https://www.nightgallery.ca/exhibitions/hasani-sahlehe2')


class RegionWiringTest(unittest.TestCase):
    def test_the_registry_and_the_venue_list_agree(self):
        import main
        scrapers, _ = main.get_venue_scrapers(selected_regions=['nyc'])
        with open(os.path.join(os.path.dirname(__file__), '../docs/data/nyc_venues.json'), encoding='utf-8') as f:
            venues = json.load(f)
        self.assertEqual(sorted(scrapers), sorted(venues))
        for module in (whitney, guggenheim, studio_museum_in_harlem, frick_collection, david_zwirner, pace_gallery, night_gallery_new_york):
            self.assertIn(module.VENUE, venues)


if __name__ == '__main__':
    unittest.main()
