# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# A proxied venue (WEBSITE-83 / OPERATIONS.md) needs three things to agree: its hostname in
# utils.PROXY_DOMAINS (matched exactly against the URL it fetches), a PROXIED_VENUES entry (so it
# refreshes every 4 days instead of daily), and a registered scraper. No network.
import os
import sys
import unittest
from urllib.parse import urlparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import main
import utils
from scrapers.sf import creative_growth


class ProxyRegistryTest(unittest.TestCase):
    def test_every_proxied_venue_has_a_registered_scraper(self):
        venues, _ = main.get_venue_scrapers()
        self.assertEqual([v for v in main.PROXIED_VENUES if v not in venues], [])

    def test_creative_growth_is_fetched_through_the_proxy_on_the_schedule(self):
        # WEBSITE-93: 403 from GitHub's servers, fine from a normal connection
        host = urlparse(creative_growth.EXHIBITIONS_URL).netloc
        self.assertIn(host, utils.PROXY_DOMAINS)
        self.assertEqual(main.PROXIED_VENUES['Creative Growth Art Center'], ['Creative Growth Art Center'])


if __name__ == '__main__':
    unittest.main()
