# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# A ZenRows refusal now logs its explanation, and Kala's scraper no longer crashes (a typo in its
# error path, logging.ingo, made the whole daily run fail whenever kala.org timed out). No network.
import os
import sys
import unittest
from urllib.parse import urlparse
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import requests
import main
import utils
from scrapers.sf import kala


class FakeResponse:
    def __init__(self, status, text=''):
        self.status_code, self.text, self.content = status, text, text.encode()

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'{self.status_code} Client Error')


class ProxyErrorLoggingTest(unittest.TestCase):
    URL = 'https://www.marincounty.gov/departments/cultural-services/art-exhibits/civic-center-art-gallery'

    def fetch(self, response):
        with mock.patch.object(utils, 'ZENROWS_API_KEY', 'key'), \
                mock.patch.object(utils, 'PROXY_EXHAUSTED', False), \
                mock.patch.object(utils, '_proxy_get', return_value=response):
            with self.assertLogs(level='ERROR') as logs:
                soup = utils.fetch_and_parse(self.URL)
        return soup, '\n'.join(logs.output)

    def test_a_422_logs_zenrows_own_explanation(self):
        soup, log = self.fetch(FakeResponse(422, '{"code":"RESP001","detail":"Could not get content. Try js_render."}'))
        self.assertIsNone(soup)
        self.assertIn('ZenRows refused', log)
        self.assertIn('Could not get content', log)

    def test_out_of_credits_keeps_its_own_message_without_the_body(self):
        with mock.patch.object(utils, 'PROXY_EXHAUSTED', False):
            soup, log = self.fetch(FakeResponse(402, 'payment required'))
        self.assertIsNone(soup)
        self.assertNotIn('ZenRows refused', log)
        self.assertIn('out of credits', log)
        utils.PROXY_EXHAUSTED = False

    def test_marin_civic_center_is_fetched_with_javascript_rendering(self):
        self.assertEqual(utils.PROXY_DOMAINS['www.marincounty.gov'], {'premium_proxy': 'true', 'js_render': 'true'})

    def test_armory_is_fetched_with_javascript_rendering(self):
        self.assertEqual(utils.PROXY_DOMAINS['www.armoryarts.org'], {'premium_proxy': 'true', 'js_render': 'true'})

    def test_galerie_simon_blais_is_proxied_and_refreshed_every_four_days(self):
        from scrapers.mtl import galerie_simon_blais
        host = urlparse(galerie_simon_blais.EXHIBITIONS_URL).netloc
        self.assertEqual(utils.PROXY_DOMAINS[host], {'premium_proxy': 'true'})
        self.assertEqual(main.PROXIED_VENUES['Galerie Simon Blais'], [galerie_simon_blais.VENUE])   # else it would run daily


class KalaTest(unittest.TestCase):
    def test_an_unreachable_page_is_logged_not_raised(self):
        with mock.patch.object(kala, 'fetch_and_parse', return_value=None):
            with self.assertLogs(level='WARNING') as logs:
                kala.scrape_kala_exhibitions(env='prod')      # used to raise AttributeError: logging.ingo
        self.assertIn('Kala', logs.output[0])


if __name__ == '__main__':
    unittest.main()
