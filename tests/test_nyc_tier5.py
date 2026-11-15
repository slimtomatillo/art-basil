# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# New York tier 5 (WEBSITE-121): venues whose listing needed a closer look. Fixtures are trimmed copies of the markup
# and data the sites served on 2026-11-15. Nothing touches the network.
import datetime as dt
import json
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.nyc import galleries, gladstone_gallery, moma_ps1, new_museum
from scrapers.tor import _common

TODAY = dt.date(2026, 11, 15)
DOCS = os.path.join(os.path.dirname(__file__), '../docs/data')


def run(module, scrape, pages=None, data=None):
    stored = []

    def fetch(url, *args, **kwargs):
        html = (pages or {}).get(url)
        return BeautifulSoup(html, 'html.parser') if html is not None else None

    with mock.patch.object(module, 'fetch_and_parse', side_effect=fetch, create=True), \
            mock.patch.object(module, 'fetch_json', return_value=data, create=True), \
            mock.patch.object(module, 'region_today', return_value=TODAY, create=True), \
            mock.patch.object(_common, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
        getattr(module, scrape)(env='prod', region='nyc')
    return {e['name']: e for e in stored}


def image_of(event):
    return next((link['link'] for link in event['links'] if link['description'] == 'Image'), None)


def new_museum_page(*exhibitions):
    data = {'props': {'pageProps': {'__TEMPLATE_QUERY_DATA__': {'page': {'blocks': [{'name': 'x'}, {'exhibitions': list(exhibitions)}]}}}}}
    return f'<html><body><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></body></html>'


def new_museum_item(title, start, end, slug):
    return {'title': title, 'startDate': f'{start}T00:00:00.000Z', 'endDate': f'{end}T00:00:00.000Z' if end else None,
            'link': f'https://www.newmuseum.org/exhibition/{slug}/',
            'featuredImage': {'node': {'sourceUrl': f'https://admin.newmuseum.org/wp-content/uploads/{slug}.jpeg'}}}


class NewMuseumTest(unittest.TestCase):
    def test_reads_the_data_and_leaves_out_the_ongoing_commissions(self):
        page = new_museum_page(
            new_museum_item('Arthur Jafa: I Am Tony', '2026-09-25', '2027-01-04', 'arthur-jafa'),
            new_museum_item('Sixth New Museum Triennial: The Outside Expands', '2027-02-05', '2027-05-16', 'triennial'),
            new_museum_item('Plaza: Sarah Lucas', '2026-05-12', '2028-05-12', 'plaza'),
            new_museum_item('Atrium Stair: Shelter', '2026-03-21', None, 'atrium'),
            new_museum_item('New Humans', '2026-03-20', '2026-08-30', 'new-humans'))
        shows = run(new_museum, 'scrape_new_museum', {new_museum.PAGE_URL: page})
        self.assertEqual(sorted(shows), ['Arthur Jafa: I Am Tony', 'Sixth New Museum Triennial: The Outside Expands'])
        jafa = shows['Arthur Jafa: I Am Tony']
        self.assertEqual((jafa['dates']['start'], jafa['dates']['end']), (dt.date(2026, 9, 25), dt.date(2027, 1, 4)))
        self.assertEqual(jafa['links'][0]['link'], 'https://www.newmuseum.org/exhibition/arthur-jafa/')
        self.assertEqual(image_of(jafa), 'https://admin.newmuseum.org/wp-content/uploads/arthur-jafa.jpeg')

    def test_a_page_with_no_data_keeps_existing_data(self):
        self.assertEqual(run(new_museum, 'scrape_new_museum', {new_museum.PAGE_URL: '<html>Just a moment</html>'}), {})


def gladstone_node(slug, artists, title, start, end, location, region='New York'):
    return {'slug': slug, 'artists': [{'name': a} for a in artists], 'title': title, 'startDate': start, 'endDate': end,
            'location': location, 'region': region,
            'tileImage': {'image': {'gatsbyImageData': {'images': {'fallback': {
                'src': f'https://images.ctfassets.net/cmz556ev1x99/abc/{slug}.jpg?w=300&h=211&q=100&fm=jpg'}}}}}}


class GladstoneTest(unittest.TestCase):
    def test_keeps_new_york_shows_with_their_spaces_and_joins_a_show_at_two(self):
        data = {'result': {'data': {'allContentfulExhibition': {'nodes': [
            gladstone_node('je-pense', ['Sarah Lucas', 'Cerith Wyn Evans'], 'Je Pense', '2026-11-12', '2027-01-16', 'New York: 21st Street'),
            gladstone_node('kounellis-2', ['Jannis Kounellis'], ' ', '2026-11-06', '2026-12-19', '229 Lenox Avenue,  New York'),
            gladstone_node('kounellis', ['Jannis Kounellis'], ' ', '2026-11-06', '2026-12-19', 'New York: 64th Street'),
            gladstone_node('cairo', ['Robert H. Colescott'], 'Cairo', '2026-11-05', '2026-12-19', 'New York: 24th Street'),
            gladstone_node('rose-garden', ['T. J. Wilcox'], 'The Rose Garden', '2026-11-12', '2026-12-19', 'Brussels', 'Brussels'),
            gladstone_node('old', ['Someone'], 'Old', '2025-01-01', '2025-02-01', 'New York: 24th Street'),
        ]}}}}
        shows = run(gladstone_gallery, 'scrape_gladstone_gallery', data=data)
        self.assertEqual(sorted(shows), ['Jannis Kounellis', 'Robert H. Colescott: Cairo', 'Sarah Lucas, Cerith Wyn Evans: Je Pense'])
        self.assertEqual(shows['Sarah Lucas, Cerith Wyn Evans: Je Pense']['locations'], ['21st Street'])
        self.assertEqual(sorted(shows['Jannis Kounellis']['locations']), ['64th Street', 'Lenox Avenue'])
        cairo = shows['Robert H. Colescott: Cairo']
        self.assertEqual(cairo['locations'], ['24th Street'])
        self.assertEqual(cairo['links'][0]['link'], 'https://gladstonegallery.com/exhibitions/cairo/')
        self.assertTrue(image_of(cairo).startswith('https://images.ctfassets.net/cmz556ev1x99/abc/cairo.jpg'))

    def test_missing_data_keeps_existing_data(self):
        self.assertEqual(run(gladstone_gallery, 'scrape_gladstone_gallery', data=None), {})


def ps1_row(slug, title, date, *badges):
    badge_html = ''.join(f'<li>{b}</li>' for b in badges)
    return (f'<a class="program-row" href="/en/programs/{slug}"><div><div class="primary-heading__title"><div><p>{title}</p></div></div>'
            f'<div class="primary-heading__date"><span><p>{date}</p></span></div><ul class="badge-list">{badge_html}</ul>'
            f'<img src="https://www.momaps1.org/pictures/{slug}.jpg"></div></a>')


class MomaPs1Test(unittest.TestCase):
    def test_keeps_exhibitions_with_a_run_and_leaves_out_events_and_standing_displays(self):
        current = ('<main>' + ps1_row('744-hard-art', 'HARD ART', 'Ends Mar 15, 2027', 'On View')
                   + ps1_row('799-masao-gozu', 'Masao Gozu: Windows and Bars', 'Ends Mar 15, 2027', 'On View', 'Exhibition')
                   + ps1_row('838-homeroom', 'Homeroom: Artists Against the Bomb', 'Now On View', 'On View', 'Exhibition')
                   + ps1_row('4-homeroom', 'Homeroom', 'Ongoing', 'Exhibition')
                   + ps1_row('900-concert', 'Warm Up', 'Nov 20, 2026', 'Event') + '</main>')
        upcoming = '<main>' + ps1_row('950-next', 'Next Show', 'Mar 20–Aug 8, 2027', 'Exhibition') + '</main>'
        shows = run(moma_ps1, 'scrape_moma_ps1', {moma_ps1.PAGES[0]: current, moma_ps1.PAGES[1]: upcoming})
        self.assertEqual(sorted(shows), ['Hard Art', 'Masao Gozu: Windows and Bars', 'Next Show'])
        hard = shows['Hard Art']
        self.assertEqual((hard['dates']['start'], hard['dates']['end']), (None, dt.date(2027, 3, 15)))
        self.assertEqual(hard['links'][0]['link'], 'https://www.momaps1.org/en/programs/744-hard-art')
        self.assertTrue(image_of(hard).endswith('744-hard-art.jpg'))
        nxt = shows['Next Show']
        self.assertEqual((nxt['dates']['start'], nxt['dates']['end']), (dt.date(2027, 3, 20), dt.date(2027, 8, 8)))


GALLERY = ('<html><body>{}</body></html>')


class GalleryPagesTest(unittest.TestCase):
    def test_303_gallery_reads_the_artist_title_and_run(self):
        spec = galleries.SPECS['303 Gallery']
        page = GALLERY.format('<div><a href="/gallery-exhibitions/doug-aitken14"><div><img src="https://static-assets.artlogic.net/w_2160/x.jpeg"></div>'
                              '<div><h1>Doug Aitken</h1><h2>HOWL</h2><h3>November 13 – December 19, 2026</h3></div></a></div>'
                              '<a href="/gallery-exhibitions/upcoming">UPCOMING</a><a href="/gallery-exhibitions/past">PAST</a>')
        shows = self._run(spec, {spec.urls[0]: page})
        self.assertEqual(list(shows), ['Doug Aitken: Howl'])
        show = shows['Doug Aitken: Howl']
        self.assertEqual((show['dates']['start'], show['dates']['end']), (dt.date(2026, 11, 13), dt.date(2026, 12, 19)))
        self.assertEqual(show['links'][0]['link'], 'https://www.303gallery.com/gallery-exhibitions/doug-aitken14')

    def test_matthew_marks_keeps_the_space_each_show_is_at_and_skips_other_museums(self):
        spec = galleries.SPECS['Matthew Marks Gallery']
        card = ('<a href="{}"><div>{}</div><div>{}</div><div>through January 23, 2027</div><div>{}</div><div>New York</div></a>')
        page = GALLERY.format(card.format('/exhibitions/wade-guyton-sculpture-10-26', 'WADE GUYTON', 'Sculpture', '522 West 22nd Street')
                              + card.format('/exhibitions/101-drawings-11-2026', '101 DRAWINGS', '', '523 West 24th Street')
                              + '<a href="https://whitney.org/exhibitions/da-corte"><div>Alex Da Corte</div><div>Whitney Museum of American Art</div>'
                                '<div>New York, NY</div><div>October 11, 2026–May 10, 2027</div></a>')
        shows = self._run(spec, {spec.urls[0]: page})
        self.assertEqual(sorted(shows), ['101 Drawings', 'Wade Guyton: Sculpture'])
        self.assertEqual(shows['Wade Guyton: Sculpture']['locations'], ['522 West 22nd Street'])
        self.assertEqual(shows['101 Drawings']['locations'], ['523 West 24th Street'])

    def test_artists_space_names_a_group_show_by_its_artists(self):
        spec = galleries.SPECS['Artists Space']
        card = '<a href="https://artistsspace.org/exhibitions/{}"><div>{}</div><div>{}</div><div>{}</div><div>{}</div></a>'
        page = GALLERY.format(card.format('cha', 'Theresa Hak Kyung Cha: Multiple Offerings', 'September 11 – November 21, 2026', '', '')
                              + card.format('group', 'Fiona Connor', 'Eli Coplan', 'Joseph Kusendila', 'December 11, 2026 – February 27, 2027'))
        shows = self._run(spec, {spec.urls[0]: page})
        self.assertIn('Theresa Hak Kyung Cha: Multiple Offerings', shows)
        self.assertIn('Fiona Connor, Eli Coplan, Joseph Kusendila', shows)

    def _run(self, spec, pages):
        stored = []

        def fetch(url, *args, **kwargs):
            html = pages.get(url)
            return BeautifulSoup(html, 'html.parser') if html is not None else None

        with mock.patch.object(galleries, 'fetch_and_parse', side_effect=fetch), \
                mock.patch.object(galleries, 'region_today', return_value=TODAY), \
                mock.patch.object(_common, 'region_today', return_value=TODAY), \
                mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
            galleries.scrape(spec, env='prod', region='nyc')
        return {e['name']: e for e in stored}


class RegistryTest(unittest.TestCase):
    VENUES = ['New Museum', 'Gladstone Gallery', 'MoMA PS1', '303 Gallery', 'Artists Space', 'Matthew Marks Gallery']

    def test_each_venue_is_registered_and_has_its_data(self):
        import main
        scrapers, _ = main.get_venue_scrapers(selected_regions=['nyc'])
        with open(os.path.join(DOCS, 'nyc_venues.json'), encoding='utf-8') as f:
            venues = json.load(f)
        with open(os.path.join(DOCS, 'venue_coordinates.json'), encoding='utf-8') as f:
            coordinates = json.load(f)['nyc']
        with open(os.path.join(DOCS, 'venue_admission.json'), encoding='utf-8') as f:
            admission = json.load(f)['nyc']
        self.assertEqual(sorted(scrapers), sorted(venues))
        for venue in self.VENUES:
            self.assertIn(venue, scrapers)
            addresses = venues[venue] if isinstance(venues[venue], list) else [venues[venue]]
            self.assertEqual(len(coordinates[venue]), len(addresses), f'{venue} needs coordinates for each address')
        for venue in ('New Museum', 'MoMA PS1'):
            self.assertIn(venue, admission, f'{venue} needs an admission record')

    def test_gladstone_spaces_are_the_labels_in_the_venue_data(self):
        with open(os.path.join(DOCS, 'nyc_venues.json'), encoding='utf-8') as f:
            venues = json.load(f)
        self.assertEqual(sorted(label for label, _pattern in gladstone_gallery.SPACES),
                         sorted(space['label'] for space in venues['Gladstone Gallery']))


if __name__ == '__main__':
    unittest.main()
