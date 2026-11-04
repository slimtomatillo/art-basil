# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# images.py finds a picture for events whose scraper supplied none. Nothing here touches the
# network or the real event data: pages are fake HTML, image downloads are patched, and the
# event files are temporary ones swapped into config.DB_FILES.
import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import images
import processing
import utils
from config import DB_FILES

TODAY = dt.date(2026, 11, 3)


def event(name, page='https://gallery.example/show', phase='current', links=None, **extra):
    return {'name': name, 'venue': 'Gallery', 'phase': phase, 'description': '', 'tags': [], 'ongoing': False,
            'dates': {'start': '2026-10-01', 'end': '2026-12-01'}, 'hash': 'x',
            'links': links if links is not None else [{'link': page, 'description': 'Event Page'}], **extra}


def soup(html):
    return BeautifulSoup(html, 'html.parser')


class PlausibleImageUrlTest(unittest.TestCase):
    def test_accepts_ordinary_photos(self):
        self.assertTrue(images.plausible_image_url('https://a.example/uploads/2026/show-opening.jpg'))
        self.assertTrue(images.plausible_image_url('http://a.example/p.png?w=800'))

    def test_rejects_non_http_and_svg(self):
        for url in (None, '', 'data:image/png;base64,AAAA', '//a.example/p.jpg', 'https://a.example/mark.svg'):
            self.assertFalse(images.plausible_image_url(url), url)

    def test_rejects_logo_like_filenames_but_not_folders(self):
        for name in ('logo.png', 'site-icon.png', 'Favicon.png', 'placeholder.jpg', 'award-winner-2026.jpg',
                     'loading.gif', 'facebook.png'):
            self.assertFalse(images.plausible_image_url('https://a.example/x/' + name), name)
        # a folder that holds only such graphics is rejected, but a name that merely contains the word is fine
        self.assertFalse(images.plausible_image_url('https://a.example/images/icons/menu.png'))
        self.assertTrue(images.plausible_image_url('https://a.example/logos-and-more/show.jpg'))


class SecureImageUrlTest(unittest.TestCase):
    def test_https_and_missing_urls_pass_through(self):
        self.assertEqual(images.secure_image_url('https://a.example/p.jpg'), 'https://a.example/p.jpg')
        self.assertIsNone(images.secure_image_url(None))

    def test_http_only_pictures_go_through_an_https_proxy(self):
        url = images.secure_image_url('http://sanchezartcenter.org/images/2026/a b.jpg')
        self.assertTrue(url.startswith('https://images.weserv.nl/?url='))
        self.assertIn('sanchezartcenter.org%2Fimages%2F2026%2Fa%20b.jpg', url)
        self.assertNotIn('http://', url)

    def test_card_lookup_returns_the_https_form(self):
        html = '<div><img src="http://old.example/p.jpg"><h3>Show</h3></div>'
        found = images.image_in_card(soup(html), 'Show', 'http://old.example/', check_size=False)
        self.assertTrue(found.startswith('https://images.weserv.nl/'))


class ResizedImageUrlTest(unittest.TestCase):
    def test_gives_a_small_jpeg_copy_through_the_proxy(self):
        url = images.resized_image_url('https://caamuseum.org/content/x y/shot.png', 500)
        self.assertTrue(url.startswith('https://images.weserv.nl/?url=caamuseum.org%2Fcontent%2Fx%20y%2Fshot.png'))
        self.assertIn('w=500', url)
        self.assertIn('output=jpg', url)

    def test_missing_url_passes_through(self):
        self.assertIsNone(images.resized_image_url(None))


class CandidateImagesTest(unittest.TestCase):
    def test_share_image_comes_first_then_page_images_without_repeats(self):
        page = soup('''<html><head>
            <meta property="og:image" content="/share.jpg">
            <meta name="twitter:image" content="https://cdn.example/tw.jpg">
          </head><body><main><img src="/a.jpg"><img data-src="/b.jpg" src="/lazy-placeholder.gif"><img src="/share.jpg"></main>
          <img src="/outside.jpg"></body></html>''')
        urls = images.candidate_images(page, 'https://gallery.example/shows/1')
        self.assertEqual(urls[:2], ['https://gallery.example/share.jpg', 'https://cdn.example/tw.jpg'])
        self.assertEqual(urls.count('https://gallery.example/share.jpg'), 1)
        self.assertIn('https://gallery.example/a.jpg', urls)
        self.assertIn('https://gallery.example/b.jpg', urls)       # lazy-loaded source preferred
        self.assertNotIn('https://gallery.example/lazy-placeholder.gif', urls)

    def test_page_without_images(self):
        self.assertEqual(images.candidate_images(soup('<html><body><p>hi</p></body></html>'), 'https://a.example/'), [])


class FakeResponse:
    def __init__(self, size, content_type='image/jpeg', ok=True):
        self.ok, self.headers, self._size = ok, {'Content-Type': content_type}, size

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_content(self, chunk):
        sent = 0
        while sent < self._size:
            n = min(chunk, self._size - sent)
            sent += n
            yield b'x' * n


class BigEnoughTest(unittest.TestCase):
    def check(self, response=None, error=None):
        with mock.patch.object(images.requests, 'get', return_value=response, side_effect=error):
            return images.big_enough('https://a.example/p.jpg', minimum=1000)

    def test_large_image_passes(self):
        self.assertTrue(self.check(FakeResponse(5000)))

    def test_small_image_fails(self):
        self.assertFalse(self.check(FakeResponse(400)))

    def test_not_an_image_or_error_status_fails(self):
        self.assertFalse(self.check(FakeResponse(5000, content_type='text/html')))
        self.assertFalse(self.check(FakeResponse(5000, ok=False)))

    def test_network_error_fails(self):
        self.assertFalse(self.check(error=images.requests.ConnectionError('boom')))


class FindEventImageTest(unittest.TestCase):
    PAGE = '<html><head><meta property="og:image" content="/logo.png"></head><body><main><img src="/one.jpg"><img src="/two.jpg"></main></body></html>'

    def test_skips_proxied_sites_without_fetching(self):
        with mock.patch.object(utils, 'PROXY_DOMAINS', ['proxied.example']), \
                mock.patch.object(images, 'fetch_and_parse') as fetch:
            self.assertIsNone(images.find_event_image('https://proxied.example/show'))
            self.assertEqual(images.find_card_images('https://proxied.example/shows', ['A', 'B']), {})
        fetch.assert_not_called()

    def test_returns_first_candidate_that_is_plausible_and_big(self):
        sizes = {'https://g.example/one.jpg': False, 'https://g.example/two.jpg': True}
        with mock.patch.object(images, 'fetch_and_parse', return_value=soup(self.PAGE)), \
                mock.patch.object(images, 'big_enough', side_effect=lambda url: sizes[url]):
            # the og:image is named "logo" so it is never even downloaded; one.jpg is too small
            self.assertEqual(images.find_event_image('https://g.example/show'), 'https://g.example/two.jpg')

    def test_none_when_nothing_qualifies_or_fetch_fails(self):
        with mock.patch.object(images, 'fetch_and_parse', return_value=soup(self.PAGE)), \
                mock.patch.object(images, 'big_enough', return_value=False):
            self.assertIsNone(images.find_event_image('https://g.example/show'))
        with mock.patch.object(images, 'fetch_and_parse', return_value=None):
            self.assertIsNone(images.find_event_image('https://g.example/show'))


class ListingCardTest(unittest.TestCase):
    LISTING = '''<html><body><main>
        <img src="/banner.jpg">
        <div class="card"><img src="/a.jpg"><h3>Alpha Show</h3><p>Oct 1 to Dec 1</p></div>
        <div class="card"><div><img data-src="/b.jpg"></div><div><h3>Beta &amp; Co</h3></div></div>
        <div class="card"><h3>Gamma Show</h3></div>
      </main></body></html>'''

    def find(self, title, others=('Alpha Show', 'Beta & Co', 'Gamma Show')):
        with mock.patch.object(images, 'big_enough', return_value=True):
            return images.image_in_card(soup(self.LISTING), title, 'https://g.example/shows', others)

    def test_picture_in_the_same_card_is_used(self):
        self.assertEqual(self.find('Alpha Show'), 'https://g.example/a.jpg')

    def test_picture_a_few_levels_away_is_found(self):
        self.assertEqual(self.find('Beta & Co'), 'https://g.example/b.jpg')

    def test_never_borrows_a_neighbouring_shows_picture(self):
        # Gamma's card has no image; climbing further reaches an element that holds the other shows
        self.assertIsNone(self.find('Gamma Show'))

    def test_title_not_on_page(self):
        self.assertIsNone(self.find('Delta Show'))

    def test_find_card_images_maps_titles_to_pictures(self):
        with mock.patch.object(images, 'fetch_and_parse', return_value=soup(self.LISTING)), \
                mock.patch.object(images, 'big_enough', return_value=True):
            found = images.find_card_images('https://g.example/shows', ['Alpha Show', 'Beta & Co', 'Gamma Show'])
        self.assertEqual(found, {'Alpha Show': 'https://g.example/a.jpg', 'Beta & Co': 'https://g.example/b.jpg'})


class NeedsImageTest(unittest.TestCase):
    def test_current_and_future_events_without_an_image(self):
        self.assertTrue(images.needs_image(event('A'), TODAY))
        self.assertTrue(images.needs_image(event('A', phase='future'), TODAY))

    def test_not_past_events(self):
        self.assertFalse(images.needs_image(event('A', phase='past'), TODAY))

    def test_not_hand_entered_or_archived_events(self):
        self.assertFalse(images.needs_image(event('A', source=images.MANUAL_SOURCE), TODAY))
        self.assertFalse(images.needs_image(event('A', source=images.ARCHIVE_SOURCE), TODAY))

    def test_not_when_an_image_exists_or_there_is_no_page(self):
        with_image = event('A', links=[{'link': 'https://g.example/s', 'description': 'Event Page'},
                                       {'link': 'https://g.example/i.jpg', 'description': 'Image'}])
        self.assertFalse(images.needs_image(with_image, TODAY))
        self.assertFalse(images.needs_image(event('A', links=[]), TODAY))

    def test_recently_checked_events_wait_two_weeks(self):
        self.assertFalse(images.needs_image(event('A', image_checked='2026-10-25'), TODAY))
        self.assertTrue(images.needs_image(event('A', image_checked='2026-10-20'), TODAY))
        self.assertTrue(images.needs_image(event('A', image_checked='not a date'), TODAY))


class EnrichMissingImagesTest(unittest.TestCase):
    """Runs enrich_missing_images against a temporary event file swapped into config.DB_FILES."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, 'test_events.json')
        patcher = mock.patch.dict(DB_FILES, {'test': self.path})
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, venue_events):
        with open(self.path, 'w') as f:
            json.dump({'Gallery': {e['name'] + '-Gallery': e for e in venue_events}}, f)

    def read(self):
        with open(self.path) as f:
            return json.load(f)['Gallery']

    def run_enrich(self, finder=None, card_finder=None, **kwargs):
        return images.enrich_missing_images(['test'], today=TODAY, finder=finder or (lambda page: None),
                                            card_finder=card_finder or (lambda page, titles: {}), **kwargs)

    def test_adds_the_found_image_as_a_normal_image_link(self):
        self.write([event('A', page='https://g.example/a')])
        report = self.run_enrich(finder=lambda page: 'https://g.example/a.jpg')
        stored = self.read()['A-Gallery']
        self.assertEqual(images.image_link(stored), 'https://g.example/a.jpg')
        self.assertEqual(stored['image_checked'], '2026-11-03')
        self.assertEqual(report['checked'], 1)
        self.assertEqual([r[2] for r in report['added']], ['A'])

    def test_events_with_nothing_found_are_marked_and_not_retried_for_two_weeks(self):
        self.write([event('A', page='https://g.example/a')])
        calls = []
        self.run_enrich(finder=lambda page: calls.append(page))
        self.assertEqual(self.read()['A-Gallery']['image_checked'], '2026-11-03')
        self.run_enrich(finder=lambda page: calls.append(page))
        self.assertEqual(len(calls), 1)
        later = images.enrich_missing_images(['test'], today=TODAY + dt.timedelta(days=14),
                                             finder=lambda page: calls.append(page), card_finder=lambda p, t: {})
        self.assertEqual(len(calls), 2)
        self.assertEqual(later['added'], [])

    def test_a_picture_used_for_two_of_a_venues_shows_is_dropped(self):
        self.write([event('A', page='https://g.example/a'), event('B', page='https://g.example/b')])
        report = self.run_enrich(finder=lambda page: 'https://g.example/banner.jpg')
        stored = self.read()
        self.assertIsNone(images.image_link(stored['A-Gallery']))
        self.assertIsNone(images.image_link(stored['B-Gallery']))
        self.assertEqual(len(report['dropped']), 2)
        self.assertEqual(report['added'], [])

    def test_a_found_picture_already_used_by_another_show_is_dropped(self):
        existing = event('Old', links=[{'link': 'https://g.example/o', 'description': 'Event Page'},
                                       {'link': 'https://g.example/banner.jpg', 'description': 'Image'}])
        self.write([existing, event('New', page='https://g.example/n')])
        report = self.run_enrich(finder=lambda page: 'https://g.example/banner.jpg')
        self.assertIsNone(images.image_link(self.read()['New-Gallery']))
        self.assertEqual(len(report['dropped']), 1)

    def test_shows_sharing_a_listing_page_are_looked_up_together_by_title(self):
        listing = 'https://g.example/exhibitions'
        self.write([event('A', page=listing), event('B', page=listing), event('C', page=listing)])
        asked = []

        def card_finder(page, titles):
            asked.append((page, titles))
            return {'A': 'https://g.example/a.jpg', 'B': 'https://g.example/b.jpg'}

        report = self.run_enrich(finder=lambda page: self.fail('single-page finder used for a shared page'),
                                 card_finder=card_finder)
        stored = self.read()
        self.assertEqual(asked, [(listing, ['A', 'B', 'C'])])
        self.assertEqual(report['checked'], 1)                     # one page opened for three shows
        self.assertEqual(images.image_link(stored['A-Gallery']), 'https://g.example/a.jpg')
        self.assertEqual(images.image_link(stored['B-Gallery']), 'https://g.example/b.jpg')
        self.assertIsNone(images.image_link(stored['C-Gallery']))
        self.assertEqual(stored['C-Gallery']['image_checked'], '2026-11-03')

    def test_page_limit_stops_a_run_and_leaves_the_rest_for_later(self):
        self.write([event(n, page='https://g.example/' + n) for n in 'ABC'])
        urls = iter(f'https://g.example/{i}.jpg' for i in range(10))
        report = self.run_enrich(finder=lambda page: next(urls), max_pages=2)
        stored = self.read()
        self.assertEqual(report['checked'], 2)
        self.assertEqual(sum(1 for e in stored.values() if 'image_checked' in e), 2)

    def test_past_manual_and_archived_events_are_left_alone(self):
        self.write([event('P', phase='past'), event('M', source=images.MANUAL_SOURCE),
                    event('R', source=images.ARCHIVE_SOURCE)])
        report = self.run_enrich(finder=lambda page: self.fail('should not be asked'))
        self.assertEqual(report['checked'], 0)
        self.assertEqual(self.read()['P-Gallery'].get('image_checked'), None)

    def test_dry_run_writes_nothing(self):
        self.write([event('A', page='https://g.example/a')])
        with open(self.path) as f:
            before = f.read()
        report = self.run_enrich(finder=lambda page: 'https://g.example/a.jpg', save=False)
        with open(self.path) as f:
            self.assertEqual(f.read(), before)
        self.assertEqual(len(report['added']), 1)


class ShrinkHeavyImagesTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, 'test_events.json')
        patcher = mock.patch.dict(DB_FILES, {'test': self.path})
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, events):
        with open(self.path, 'w') as f:
            json.dump({'Gallery': {e['name'] + '-Gallery': e for e in events}}, f)

    def read(self):
        with open(self.path) as f:
            return json.load(f)['Gallery']

    def photo(self, name, url, phase='current'):
        return event(name, phase=phase, links=[{'link': 'https://g.example/' + name, 'description': 'Event Page'},
                                               {'link': url, 'description': 'Image'}])

    def run_shrink(self, sizes, proxy_ok=lambda url: True, **kwargs):
        return images.shrink_heavy_images(['test'], size_of=lambda url: sizes.get(url), proxy_ok=proxy_ok,
                                          max_bytes=1000, workers=2, **kwargs)

    def test_a_heavy_picture_is_swapped_for_a_small_copy_and_a_light_one_is_not(self):
        self.write([self.photo('Heavy', 'https://g.example/big.png'), self.photo('Light', 'https://g.example/small.jpg')])
        report = self.run_shrink({'https://g.example/big.png': 5000, 'https://g.example/small.jpg': 200})
        stored = self.read()
        self.assertTrue(images.image_link(stored['Heavy-Gallery']).startswith('https://images.weserv.nl/?url=g.example%2Fbig.png'))
        self.assertEqual(images.image_link(stored['Light-Gallery']), 'https://g.example/small.jpg')
        self.assertEqual(report['checked'], 2)
        self.assertEqual([(s[2], s[3]) for s in report['shrunk']], [('Heavy', 5000)])

    def test_not_swapped_when_the_proxy_cannot_serve_it(self):
        self.write([self.photo('Heavy', 'https://blocked.example/big.png')])
        self.run_shrink({'https://blocked.example/big.png': 5000}, proxy_ok=lambda url: False)
        self.assertEqual(images.image_link(self.read()['Heavy-Gallery']), 'https://blocked.example/big.png')

    def test_unknown_size_proxied_svg_and_past_events_are_left_alone(self):
        proxied = 'https://images.weserv.nl/?url=g.example%2Fa.jpg&w=640'
        self.write([self.photo('Unknown', 'https://g.example/u.png'), self.photo('Proxied', proxied),
                    self.photo('Vector', 'https://g.example/v.svg'),
                    self.photo('Old', 'https://g.example/old.png', phase='past')])
        sizes = {'https://g.example/u.png': None, proxied: 9000, 'https://g.example/v.svg': 9000,
                 'https://g.example/old.png': 9000}
        report = self.run_shrink(sizes)
        self.assertEqual(report['shrunk'], [])
        self.assertEqual(report['checked'], 1)                  # only the unknown-size current picture was measured
        stored = self.read()
        self.assertEqual(images.image_link(stored['Proxied-Gallery']), proxied)
        self.assertEqual(images.image_link(stored['Old-Gallery']), 'https://g.example/old.png')

    def test_dry_run_writes_nothing(self):
        self.write([self.photo('Heavy', 'https://g.example/big.png')])
        with open(self.path) as f:
            before = f.read()
        report = self.run_shrink({'https://g.example/big.png': 5000}, save=False)
        with open(self.path) as f:
            self.assertEqual(f.read(), before)
        self.assertEqual(len(report['shrunk']), 1)


class KeepFoundImageTest(unittest.TestCase):
    """A scraper that supplies no image rewrites the stored event on every run; the image
    images.py found must survive that."""

    STORED = {'links': [{'link': 'https://g.example/s', 'description': 'Event Page'},
                        {'link': 'https://g.example/found.jpg', 'description': 'Image'}], 'image_checked': '2026-11-01'}

    def test_stored_image_and_check_date_carry_over(self):
        incoming = {'links': [{'link': 'https://g.example/s', 'description': 'Event Page'}]}
        processing.keep_found_image(incoming, self.STORED)
        self.assertEqual(processing.image_link(incoming), 'https://g.example/found.jpg')
        self.assertEqual(incoming['image_checked'], '2026-11-01')

    def test_an_image_from_the_scraper_wins(self):
        incoming = {'links': [{'link': 'https://g.example/new.jpg', 'description': 'Image'}]}
        processing.keep_found_image(incoming, self.STORED)
        self.assertEqual([l['link'] for l in incoming['links']], ['https://g.example/new.jpg'])

    def test_new_event_is_untouched(self):
        incoming = {'links': []}
        processing.keep_found_image(incoming, None)
        self.assertEqual(incoming, {'links': []})

    def test_check_date_is_dropped_when_the_event_page_changes(self):
        # the venue now links a show's own page, so the page must be looked at again
        incoming = {'links': [{'link': 'https://g.example/new-page', 'description': 'Event Page'}]}
        processing.keep_found_image(incoming, self.STORED)
        self.assertNotIn('image_checked', incoming)

    def test_process_event_keeps_a_found_image_through_a_rescrape(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'test_events.json')
            with mock.patch.dict(DB_FILES, {'test': path}):
                def scraped():
                    return {'name': 'Show', 'venue': 'Gallery', 'description': 'd', 'tags': [], 'phase': 'current',
                            'dates': {'start': '2026-10-01', 'end': '2026-12-01'}, 'ongoing': False,
                            'last_updated': '2026-11-03 11:00:00',
                            'links': [{'link': 'https://g.example/s', 'description': 'Event Page'}]}

                def read():
                    with open(path) as f:
                        return json.load(f)

                processing.process_event(scraped(), 'test')
                db = read()
                key = next(iter(db['Gallery']))
                db['Gallery'][key]['links'].append({'link': 'https://g.example/found.jpg', 'description': 'Image'})
                db['Gallery'][key]['image_checked'] = '2026-11-02'
                with open(path, 'w') as f:
                    json.dump(db, f)

                again = scraped()
                again['last_updated'] = '2026-11-04 11:00:00'
                processing.process_event(again, 'test')
                stored = read()['Gallery'][key]
        self.assertEqual(processing.image_link(stored), 'https://g.example/found.jpg')
        self.assertEqual(stored['image_checked'], '2026-11-02')
        self.assertEqual(stored['last_updated'], '2026-11-04 11:00:00')


if __name__ == '__main__':
    unittest.main()
