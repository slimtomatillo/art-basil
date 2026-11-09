# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# Scrapers that read a listing page pick up each show's own picture from the card that holds
# its title (images.image_in_card, scrapers.tor._common.Listing). These tests use small fake
# pages shaped like the real ones; nothing touches the network or the event data.
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import images
from scrapers.sf import creative_growth, sanchez_art_center, shooting_gallery
from scrapers.la import california_african_american_museum as caam, ica_la, molaa
from scrapers.tor import _common, art_museum_uoft, paul_petro_contemporary_art

PAGE = 'https://g.example/shows/'
TODAY = dt.date(2026, 11, 3)


def soup(html):
    return BeautifulSoup(html, 'html.parser')


def card(html, title, others=()):
    return images.image_in_card(soup(html), title, PAGE, others or [title], check_size=False)


class CardLookupTest(unittest.TestCase):
    def test_title_split_by_markup_or_punctuation_still_matches(self):
        html = '<div><img src="/a.jpg"><h2>Torkwase Dyson: <em>The Distance Inside Us</em></h2></div>'
        self.assertEqual(card(html, 'Torkwase Dyson: The Distance Inside Us'), 'https://g.example/a.jpg')
        html = '<div><img src="/k.jpg"><h1><a>Kamiphony | Cybèle Young</a></h1></div>'
        self.assertEqual(card(html, 'Kamiphony: Cybèle Young'), 'https://g.example/k.jpg')

    def test_name_built_from_two_lines_matches_text_across_elements(self):
        html = '<div><img src="/m.jpg"><span>Ben Reeves</span><span>Parklife</span></div>'
        self.assertEqual(card(html, 'Ben Reeves: Parklife'), 'https://g.example/m.jpg')

    def test_picture_set_as_a_css_background(self):
        html = ('<div><a><div style="background-image: url(https://g.example/wp/haunts-1024x768.jpg ) !important;"></div></a>'
                '<h3>Meaghan Hyckie</h3><h3>Haunts</h3></div>')
        self.assertEqual(card(html, 'Meaghan Hyckie: Haunts'), 'https://g.example/wp/haunts-1024x768.jpg')

    def test_lazy_loaded_and_responsive_sources(self):
        html = '<div><img src="data:image/gif;base64,R0lGOD" data-src="/lazy.jpg"><h3>Lazy Show</h3></div>'
        self.assertEqual(card(html, 'Lazy Show'), 'https://g.example/lazy.jpg')
        html = ('<div><img src="/pixel.gif" data-responsive-src="{\'345\': \'https://cdn.example/w_345/a.jpg\', '
                '\'750\': \'https://cdn.example/w_750/a.jpg\'}"><h3>Responsive Show</h3></div>')
        self.assertEqual(card(html, 'Responsive Show'), 'https://cdn.example/w_750/a.jpg')

    def test_logos_and_placeholders_are_never_used(self):
        html = '<div><img src="/site-logo.png"><img src="/icons/menu.png"><h3>Only Logos</h3></div>'
        self.assertIsNone(card(html, 'Only Logos'))

    def test_a_card_without_a_picture_never_borrows_a_neighbours(self):
        html = '<ul><li><img src="/a.jpg"><h3>Alpha</h3></li><li><h3>Beta</h3></li></ul>'
        self.assertEqual(card(html, 'Alpha', ['Alpha', 'Beta']), 'https://g.example/a.jpg')
        self.assertIsNone(card(html, 'Beta', ['Alpha', 'Beta']))

    def test_title_missing_from_page(self):
        self.assertIsNone(card('<div><img src="/a.jpg"><h3>Alpha</h3></div>', 'Zeta'))

    def test_card_images_drops_a_picture_shared_by_several_shows(self):
        html = ('<ul><li><img src="/banner.jpg"><h3>Alpha</h3></li><li><img src="/banner.jpg"><h3>Beta</h3></li>'
                '<li><img src="/c.jpg"><h3>Gamma</h3></li></ul>')
        found = images.card_images(soup(html), PAGE, ['Alpha', 'Beta', 'Gamma'], check_size=False)
        self.assertEqual(found, {'Gamma': 'https://g.example/c.jpg'})


class ListingTest(unittest.TestCase):
    HTML = ('<main><div class="card"><img src="/now.jpg"><h2>Now Showing</h2></div>'
            '<div class="card"><img src="/soon.jpg"><h2>Coming Soon</h2></div>'
            '<div class="card"><img src="/old.jpg"><h2>Long Gone</h2></div>'
            '<div class="card"><h2>No Picture Show</h2></div></main>')

    def publish(self, shows, region='tor'):
        stored = []
        with mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)), \
                mock.patch.object(_common, 'region_today', return_value=TODAY):
            listing = _common.Listing('prod', region, 'Gallery', soup(self.HTML), PAGE)
            for name, start, end in shows:
                listing.add(name, start, end, tag='gallery')
            count = listing.publish()
        return count, {d['name']: d for d in stored}

    def test_each_published_show_gets_its_own_picture_as_an_image_link(self):
        count, stored = self.publish([('Now Showing', dt.date(2026, 10, 1), dt.date(2026, 12, 1)),
                                      ('Coming Soon', dt.date(2026, 12, 5), dt.date(2027, 2, 1)),
                                      ('No Picture Show', dt.date(2026, 10, 1), dt.date(2026, 12, 1))])
        self.assertEqual(count, 3)
        self.assertEqual(stored['Now Showing']['links'],
                         [{'link': PAGE, 'description': 'Event Page'},
                          {'link': 'https://g.example/now.jpg', 'description': 'Image'}])
        self.assertIn({'link': 'https://g.example/soon.jpg', 'description': 'Image'}, stored['Coming Soon']['links'])
        self.assertEqual(len(stored['No Picture Show']['links']), 1)          # still published, just no picture

    def test_past_shows_are_not_published(self):
        count, stored = self.publish([('Now Showing', dt.date(2026, 10, 1), dt.date(2026, 12, 1)),
                                      ('Long Gone', dt.date(2025, 1, 1), dt.date(2025, 2, 1))])
        self.assertEqual(count, 1)
        self.assertNotIn('Long Gone', stored)

    def test_a_shows_own_link_is_kept(self):
        stored = []
        with mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)), \
                mock.patch.object(_common, 'region_today', return_value=TODAY):
            listing = _common.Listing('prod', 'tor', 'Gallery', soup(self.HTML), PAGE)
            listing.add('Now Showing', dt.date(2026, 10, 1), dt.date(2026, 12, 1), link='https://g.example/now-showing/')
            listing.publish()
        self.assertEqual(stored[0]['links'][0], {'link': 'https://g.example/now-showing/', 'description': 'Event Page'})

    def test_dev_runs_store_nothing(self):
        with mock.patch.object(_common, 'process_event') as process:
            listing = _common.Listing('dev', 'tor', 'Gallery', soup(self.HTML), PAGE)
            listing.add('Now Showing', dt.date(2026, 10, 1), dt.date(2026, 12, 1))
            self.assertEqual(listing.publish(), 1)
        process.assert_not_called()


class ScraperRunner:
    def run_scraper(self, module, function, html, **kwargs):
        stored = []
        with mock.patch.object(module, 'fetch_and_parse', return_value=soup(html)), \
                mock.patch.object(module, 'region_today', return_value=TODAY), \
                mock.patch.object(_common, 'region_today', return_value=TODAY), \
                mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)), \
                mock.patch.object(module, 'process_event', side_effect=lambda d, r: stored.append(d), create=True):
            getattr(module, function)(env='prod', **kwargs)
        return stored


class ScraperWiringTest(ScraperRunner, unittest.TestCase):
    def test_art_museum_uoft_uses_each_items_thumbnail(self):
        html = ('<div id="current"><div class="exhibition item current"><a href="https://artmuseum.utoronto.ca/exhibition/tfa/">'
                '<div class="exhibition-thumb"><img src="https://artmuseum.utoronto.ca/wp-content/uploads/2026/09/2026_TFA_i.png" '
                'srcset="x 738w"></div><h3 class="item-title">Things Fall Apart</h3>'
                '<p class="date">September 26, 2026–December 20, 2026</p></a></div></div>'
                '<div id="current"><div class="program item current"><a href="https://artmuseum.utoronto.ca/program/p/">'
                '<img src="/wp-content/uploads/2026/10/2026_logo.png"><h3 class="item-title">Seed Workshop</h3>'
                '<p class="date">November 7, 2026–November 21, 2026</p></a></div></div>')
        stored = self.run_scraper(art_museum_uoft, 'scrape_art_museum_uoft', html)
        by_name = {d['name']: d for d in stored}
        self.assertIn({'link': 'https://artmuseum.utoronto.ca/wp-content/uploads/2026/09/2026_TFA_i.png',
                       'description': 'Image'}, by_name['Things Fall Apart']['links'])
        # a logo-like file name is not used as a show's picture
        self.assertNotIn('Image', [l['description'] for l in by_name['Seed Workshop']['links']])

    def test_paul_petro_links_each_show_to_its_own_page(self):
        html = ('<div id="content"><h1><a href="/exhibitions/688-mythical-threads"><em>Mythical Threads</em></a></h1>'
                '<h2><a>Barbara Klunder</a></h2><h3>Embroidered Fables<br>October 9 - November 7, 2026<br>Opening</h3>'
                '<h1><a href="/exhibitions/704-regional"><em>Current Regional Programming</em></a></h1><h2></h2>'
                '<h3>October 23, 2026 - January 31, 2027</h3></div>')
        stored = self.run_scraper(paul_petro_contemporary_art, 'scrape_paul_petro_contemporary_art', html)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]['links'][0],
                         {'link': 'https://www.paulpetro.com/exhibitions/688-mythical-threads', 'description': 'Event Page'})

    def test_shooting_gallery_shows_take_their_own_thumbnail(self):
        html = ('<div class="show_list"><div class="event"><div class="ev_img"><img src="../media/events/gallery/a_t.jpg"></div>'
                '<div><em>November 1st - November 29th, 2026</em><h2>Show A</h2>Artist A</div></div>'
                '<div class="event"><div><em>December 1st - December 20th, 2026</em><h2>Show B</h2>Artist B</div></div></div>')
        stored = self.run_scraper(shooting_gallery, 'scrape_shooting_gallery', html)
        by_name = {d['name']: [l['link'] for l in d['links'] if l['description'] == 'Image'] for d in stored}
        self.assertEqual(by_name['Show A - Artist A'], ['https://shootinggallerysf.com/media/events/gallery/a_t.jpg'])
        self.assertEqual(by_name['Show B - Artist B'], [])          # no picture: never borrows Show A's


class CreativeGrowthTest(ScraperRunner, unittest.TestCase):
    # The page is rendered by JavaScript from a JSON blob; only the logo is an <img>
    PAGE = (
        '<span data-heading="h1">CURRENT EXHIBITION</span>'
        '<span data-heading="h1">Stereo Dynamic</span><span data-heading="h2">Oct 10 - Dec 12, 2026</span>'
        '<script>ReactDOM.hydrate(x, {"blocks":[[{"config":{"block":{"image":{"extension":"png","height":9,'
        '"id":"logologologologologol","width":9},"url":"https://www.creativegrowth.org/"}},"type":{"value":"Image_v2"}},'
        '{"config":{"block":{"image":{"extension":"jpg","height":2385,"id":"1c4g2dt8va86bi6tewu2","width":3601},'
        '"borderRadius":{"unit":"px","value":"15"},"animation":"0","newWindow":true,"altText":"",'
        '"url":"https://www.creativegrowth.org/post/19799-stereo-dynamic"}},"type":{"value":"Image_v2"}}]]})</script>')

    def test_picture_and_show_page_come_from_the_page_data(self):
        stored = self.run_scraper(creative_growth, 'scrape_creative_growth', self.PAGE)
        links = {l['description']: l['link'] for l in stored[0]['links']}
        self.assertEqual(links['Event Page'], 'https://www.creativegrowth.org/post/19799-stereo-dynamic')
        self.assertEqual(links['Image'], 'https://cdn.artcld.com/img/w_640,h_640,c_fit/1c4g2dt8va86bi6tewu2.jpg')

    def test_no_matching_image_block_keeps_the_listing_link(self):
        page = self.PAGE.replace('19799-stereo-dynamic', '1-something-else')
        stored = self.run_scraper(creative_growth, 'scrape_creative_growth', page)
        self.assertEqual(stored[0]['links'], [{'link': creative_growth.EXHIBITIONS_URL, 'description': 'Event Page'}])


class SanchezTest(unittest.TestCase):
    CALENDAR = (
        '<table><tr><td valign="top" width="22"></td><td>Oct 23 \u2013 Nov 22</td><td></td>'
        '<td>68th Annual Art Guild of Pacifica Members Show<br>Chris Darst</td></tr>'
        '<tr><td></td><td>Dec 12 \u2014 13</td><td></td><td><a href="2026WinterArtFaire.html">AGP Winter Art Faire</a>, 11am</td></tr>'
        '<tr><td></td><td>Nov 6 \u2014 Nov 16</td><td></td><td>Arbor Day Popup<br>Details</td></tr></table>')
    EXHIBITIONS = ('<img src="images/SanchezArtCenter_new.jpg"><img src="images/2026/Exhibit_1026_1.gif">'
                   '<img src="images/2026/Exhibit_1026_2.jpg"><p>The 68th Annual Members Show opens Oct 23.</p>')
    FAIRE = '<img src="_borders/MuralTree_small.jpg"><img src="images/2026/2026WinterArtFaire.gif">'

    def run_sanchez(self, exhibitions=EXHIBITIONS):
        pages = {sanchez_art_center.CALENDAR_URL: self.CALENDAR, sanchez_art_center.EXHIBITIONS_URL: exhibitions,
                 'http://sanchezartcenter.org/2026WinterArtFaire.html': self.FAIRE}
        stored = []
        with mock.patch.object(sanchez_art_center, 'fetch_and_parse', side_effect=lambda u: soup(pages[u]) if u in pages else None), \
                mock.patch.object(sanchez_art_center, 'region_today', return_value=TODAY), \
                mock.patch.object(sanchez_art_center, 'process_event', side_effect=lambda d, r: stored.append(d)):
            sanchez_art_center.scrape_sanchez_art_center(env='prod')
        return {d['name'].split(',')[0]: [l['link'] for l in d['links'] if l['description'] == 'Image'] for d in stored}

    def test_members_show_gets_the_photo_from_the_exhibitions_page_not_the_banner_gif(self):
        got = self.run_sanchez()
        self.assertEqual(len(got['68th Annual Art Guild of Pacifica Members Show']), 1)
        self.assertIn('Exhibit_1026_2.jpg', got['68th Annual Art Guild of Pacifica Members Show'][0])
        self.assertTrue(got['68th Annual Art Guild of Pacifica Members Show'][0].startswith('https://images.weserv.nl/'))

    def test_a_show_with_its_own_page_gets_that_pages_poster_not_the_site_mural(self):
        got = self.run_sanchez()
        self.assertEqual(len(got['AGP Winter Art Faire']), 1)
        self.assertIn('2026WinterArtFaire.gif', got['AGP Winter Art Faire'][0])

    def test_shows_with_nothing_of_their_own_get_no_picture(self):
        self.assertEqual(self.run_sanchez()['Arbor Day Popup'], [])

    def test_exhibitions_page_about_another_show_is_not_used(self):
        stale = self.EXHIBITIONS.replace('68th Annual', '67th Annual')
        self.assertEqual(self.run_sanchez(stale)['68th Annual Art Guild of Pacifica Members Show'], [])


class LosAngelesPicturesTest(ScraperRunner, unittest.TestCase):
    def test_caam_uses_a_small_copy_of_the_feeds_lead_picture(self):
        item = {'title': 'Sadie Barnette: How to Fly', 'contentUrl': 'https://caamuseum.org/content/x/10-sadie',
                'image': 'https://caamuseum.org/content/x/10-sadie/caam-pr_3.jpg',
                'content': {'start_date': 'October 1', 'start_year': 2026, 'end_date': 'December 1', 'end_year': 2026,
                            'display_date': '', 'main_image': 'caam-pr_3.jpg'}}
        response = mock.Mock(json=lambda: {'current': [item], 'upcoming': []})
        stored = []
        with mock.patch.object(caam.requests, 'get', return_value=response), \
                mock.patch.object(caam, 'region_today', return_value=TODAY), \
                mock.patch.object(_common, 'region_today', return_value=TODAY), \
                mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
            caam.scrape_california_african_american_museum(env='prod')
        image = [l['link'] for l in stored[0]['links'] if l['description'] == 'Image'][0]
        self.assertTrue(image.startswith('https://images.weserv.nl/?url=caamuseum.org%2Fcontent%2Fx%2F10-sadie%2Fcaam-pr_3.jpg'))

    def test_ica_la_links_each_show_to_its_own_page(self):
        html = ('<div>Current Exhibitions</div>'
                '<a class="info-card--wrapper" href="/en/exhibitions/765-carl-cheng"><div class="info-card"><div class="info-card--title">Carl Cheng: Nature</div>'
                '<div class="info-card--sub-title">On view through February 28, 2027</div></div></a>'
                '<div>Find us on</div>')
        stored = self.run_scraper(ica_la, 'scrape_ica_la', html)
        self.assertEqual(stored[0]['links'][0]['link'], 'https://theicala.org/en/exhibitions/765-carl-cheng')

    def test_molaa_falls_back_to_the_shows_title_card(self):
        listing = '<a class="image-slide-anchor" href="/2026-sigils"></a>'
        show = ('<img src="//cdn/header.jpg"><h1>SIGILS</h1><p>Starting October 4, 2026 - February 21, 2027</p>'
                '<img data-src="https://cdn.example/TitularSigils_Logo.jpg"><img data-src="https://cdn.example/30th-logo.jpg">')
        pages = {molaa.EXHIBITIONS_URL: listing, 'https://molaa.org/2026-sigils': show}
        stored = []
        with mock.patch.object(molaa, 'fetch_and_parse', side_effect=lambda u: soup(pages[u])), \
                mock.patch.object(molaa, 'region_today', return_value=TODAY), \
                mock.patch.object(_common, 'region_today', return_value=TODAY), \
                mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
            molaa.scrape_molaa(env='prod')
        images_ = [l['link'] for l in stored[0]['links'] if l['description'] == 'Image']
        self.assertEqual(images_, ['https://cdn.example/TitularSigils_Logo.jpg'])


if __name__ == '__main__':
    unittest.main()
