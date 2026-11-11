# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# Asian Art Museum: a failed fetch (for example a ZenRows 422, as in the 2026-11-10 scheduled run) gives
# fetch_and_parse() None. The current-events scraper used to call soup.find on it and crash, which marked
# the whole run failed. It should log, keep the existing data and return. No network.
import logging
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.sf import asian_art_museum as aam


class FailedFetchTest(unittest.TestCase):
    def test_current_events_scraper_survives_a_failed_fetch(self):
        with mock.patch.object(aam, 'fetch_and_parse', return_value=None), \
                mock.patch.object(aam, 'process_event') as process, \
                self.assertLogs(level=logging.WARNING) as logs:
            aam.scrape_asian_art_museum_current_events(env='prod')
        process.assert_not_called()
        self.assertTrue(any('could not fetch the exhibitions page' in line for line in logs.output))

    def test_past_events_scraper_survives_a_failed_fetch(self):
        with mock.patch.object(aam, 'past_pages_due', return_value=True), \
                mock.patch.object(aam, 'fetch_and_parse', return_value=None), \
                mock.patch.object(aam, 'process_event') as process, \
                self.assertLogs(level=logging.WARNING):
            aam.scrape_asian_art_museum_past_events(env='prod')
        process.assert_not_called()


if __name__ == '__main__':
    unittest.main()
