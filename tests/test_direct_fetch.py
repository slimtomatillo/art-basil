# Run with the project's Python: python -m unittest discover -s tests
#
# WEBSITE-123: a direct fetch is tried twice when it times out, cannot connect, or gets a 429/5xx, and once more when the page
# comes back empty; every fetch is noted so the log can say what a page was when a scraper then stores nothing. No network.
import os
import sys
import unittest
from unittest import mock

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import utils


def response(status=200, body='<html><head><title>Exhibitions</title></head><body>' + 'x ' * 80 + '</body></html>'):
    r = requests.Response()
    r.status_code = status
    r._content = body.encode()
    r.headers['Server'] = 'nginx'
    r.url = 'https://gallery.example/x'
    return r


class DirectFetchTest(unittest.TestCase):
    def setUp(self):
        utils.reset_fetch_log()
        patches = [mock.patch.object(utils.time, 'sleep'), mock.patch.object(utils, 'verify_for', return_value=True)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def fetch(self, *answers):
        with mock.patch.object(utils.requests, 'get', side_effect=list(answers)) as get:
            soup = utils.fetch_and_parse('https://gallery.example/x')
        return soup, get.call_count

    def test_a_timeout_is_tried_once_more(self):
        soup, calls = self.fetch(requests.Timeout('slow'), response())
        self.assertEqual(calls, 2)
        self.assertEqual(soup.title.get_text(), 'Exhibitions')

    def test_two_timeouts_in_a_row_give_none(self):
        soup, calls = self.fetch(requests.Timeout('slow'), requests.Timeout('slow'))
        self.assertIsNone(soup)
        self.assertEqual(calls, 2)
        self.assertEqual(utils.FETCH_LOG[-1]['status'], 'failed')

    def test_a_server_error_or_429_is_tried_once_more_but_a_403_is_not(self):
        for status in (500, 503, 429):
            self.assertEqual(self.fetch(response(status), response())[1], 2, status)
        soup, calls = self.fetch(response(403))
        self.assertIsNone(soup)
        self.assertEqual(calls, 1)

    def test_an_empty_page_is_tried_once_more(self):
        soup, calls = self.fetch(response(body='<html><head></head><body></body></html>'), response())
        self.assertEqual(calls, 2)
        self.assertEqual(soup.title.get_text(), 'Exhibitions')

    def test_a_page_that_stays_empty_is_returned_after_one_more_try(self):
        empty = '<html><head></head><body></body></html>'
        soup, calls = self.fetch(response(body=empty), response(body=empty))
        self.assertEqual(calls, 2)
        self.assertIsNotNone(soup)

    def test_a_normal_page_is_fetched_once(self):
        self.assertEqual(self.fetch(response())[1], 1)

    def test_the_summary_says_what_each_page_was(self):
        self.fetch(response(body='<html><head></head><body>' + 'x ' * 60 + '</body></html>'))
        text = utils.fetch_summary()
        self.assertIn('https://gallery.example/x (200,', text)
        self.assertIn('nginx', text)
        utils.reset_fetch_log()
        self.assertEqual(utils.fetch_summary(), 'no page was fetched')

    def test_the_log_is_capped(self):
        for _ in range(utils.FETCH_LOG_MAX + 5):
            self.fetch(response())
        self.assertEqual(len(utils.FETCH_LOG), utils.FETCH_LOG_MAX)
        self.assertIn('more', utils.fetch_summary())


if __name__ == '__main__':
    unittest.main()
