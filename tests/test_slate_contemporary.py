# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# SLATE contemporary's shows list is a public JSON feed on the ArtCloud platform, whose firewall refused GitHub
# Actions' address on 2026-11-12 (403 "Ip Forbidden"). It is read directly first and through the proxy only if
# that fails. No network.
import datetime as dt
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import requests
from scrapers.sf import slate_contemporary

TODAY = dt.date(2026, 11, 12)
SHOWS = {'shows': [
    {'showId': 'now', 'title': 'Current Show', 'date': 'Oct 3-Dec 19, 2026'},
    {'showId': 'soon', 'title': 'Coming Show', 'date': 'Jan 8-Feb 20, 2027'},
    {'showId': 'old', 'title': 'Old Show', 'date': 'Jan 8-Feb 20, 2025'},
    {'showId': 'away', 'title': '225 WEST SANTA CLARA: Off-site', 'date': 'Oct 3-Dec 19, 2026'},
]}


class Feed:
    def __init__(self, data=None, error=None):
        self.data, self.error = data, error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        if isinstance(self.error, ValueError):
            raise self.error
        return self.data


def run_scraper(direct, proxied=None):
    stored = []
    with mock.patch.object(slate_contemporary.requests, 'get', return_value=direct) as get, \
            mock.patch.object(slate_contemporary, 'fetch_json_via_proxy', return_value=proxied) as proxy, \
            mock.patch.object(slate_contemporary, 'region_today', lambda region: TODAY), \
            mock.patch.object(slate_contemporary, 'process_event', lambda details, region: stored.append(details)):
        slate_contemporary.scrape_slate_contemporary(env='prod')
    return {e['name']: e for e in stored}, get, proxy


class SlateTest(unittest.TestCase):
    def test_current_and_upcoming_gallery_shows_are_stored_and_the_proxy_is_left_alone(self):
        events, get, proxy = run_scraper(Feed(SHOWS))
        self.assertEqual(sorted(events), ['Coming Show', 'Current Show'])        # not the past show, not the off-site one
        self.assertEqual((events['Current Show']['phase'], events['Coming Show']['phase']), ('current', 'future'))
        proxy.assert_not_called()

    def test_a_blocked_feed_is_read_through_the_proxy_instead(self):
        blocked = Feed(error=requests.HTTPError('403 Client Error: Ip Forbidden'))
        events, _, proxy = run_scraper(blocked, SHOWS)
        self.assertEqual(sorted(events), ['Coming Show', 'Current Show'])
        self.assertEqual(proxy.call_args.args[0], 'https://slatecontemporary.com/api/shows')
        self.assertEqual(proxy.call_args.args[1], {'sub': 'slateart', 'limit': 100})
        self.assertEqual(proxy.call_args.args[2], slate_contemporary.ARTCLOUD_PROXY)

    def test_a_blocked_feed_the_proxy_cannot_read_either_keeps_the_existing_data_and_says_so(self):
        blocked = Feed(error=requests.HTTPError('403 Client Error: Ip Forbidden'))
        with self.assertLogs(level='WARNING') as logs:
            events, _, _ = run_scraper(blocked, None)
        self.assertEqual(events, {})
        self.assertIn('existing data kept', '\n'.join(logs.output))

    def test_an_answer_that_is_not_json_does_not_cost_proxy_credits(self):
        with self.assertLogs(level='WARNING'):
            events, _, proxy = run_scraper(Feed(error=ValueError('not json')), SHOWS)
        self.assertEqual(events, {})
        proxy.assert_not_called()

    def test_an_empty_list_keeps_the_existing_data(self):
        with self.assertLogs(level='WARNING') as logs:
            events, _, proxy = run_scraper(Feed({'shows': []}))
        self.assertEqual(events, {})
        proxy.assert_not_called()
        self.assertIn('empty', '\n'.join(logs.output))


if __name__ == '__main__':
    unittest.main()
