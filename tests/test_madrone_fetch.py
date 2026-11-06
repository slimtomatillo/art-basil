# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# Madrone Art Bar's feed: a 200 response that is not the post list (a bot-check page, an error object)
# must give no posts, not crash the whole run. No network, no data.
import os
import sys
import unittest
from unittest import mock

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.sf import madrone_art_bar as madrone


class FakeResponse:
    status_code = 200

    def __init__(self, text, data=None, bad_json=False):
        self.text, self.data, self.bad_json = text, data, bad_json

    def raise_for_status(self):
        pass

    def json(self):
        if self.bad_json:
            raise requests.exceptions.JSONDecodeError('Expecting value', self.text, 0)
        return self.data


def fetch(response):
    with mock.patch.object(madrone.requests, 'get', return_value=response):
        return madrone.fetch_exhibition_posts()


class FetchTest(unittest.TestCase):
    def test_a_list_of_posts_is_returned(self):
        posts = [{'id': 1}]
        self.assertEqual(fetch(FakeResponse('[...]', data=posts)), posts)

    def test_a_page_that_is_not_json_gives_no_posts(self):
        with self.assertLogs(level='ERROR') as logs:
            self.assertEqual(fetch(FakeResponse('<html>Checking your browser</html>', bad_json=True)), [])
        self.assertIn('Checking your browser', logs.output[0])

    def test_an_error_object_gives_no_posts(self):
        self.assertEqual(fetch(FakeResponse('{"code":"rest_forbidden"}', data={'code': 'rest_forbidden'})), [])

    def test_a_network_error_gives_no_posts(self):
        with mock.patch.object(madrone.requests, 'get', side_effect=requests.ConnectionError('down')):
            self.assertEqual(madrone.fetch_exhibition_posts(), [])


if __name__ == '__main__':
    unittest.main()
