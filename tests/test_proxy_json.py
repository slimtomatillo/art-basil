# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# utils.fetch_json_via_proxy: a public JSON feed fetched through ZenRows, for a feed that refuses GitHub
# Actions' address on some runs. It costs credits, so it does nothing without a key or once the account is
# out of credits. No network.
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import requests
import utils

FEED = 'https://wishboneart.com/api/shows'
QUERY = {'limit': 100, 'offset': 0, 'sub': 'abc'}


class FakeResponse:
    def __init__(self, status, data=None, text='', json_error=False):
        self.status_code, self._data, self.text, self._json_error = status, data, text, json_error

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'{self.status_code} Client Error')

    def json(self):
        if self._json_error:
            raise ValueError('not json')
        return self._data


class FetchJsonViaProxyTest(unittest.TestCase):
    def fetch(self, response=None, key='key', exhausted=False, **kwargs):
        with mock.patch.object(utils, 'ZENROWS_API_KEY', key), \
                mock.patch.object(utils, 'PROXY_EXHAUSTED', exhausted), \
                mock.patch.object(utils, '_proxy_get', return_value=response) as get:
            result = utils.fetch_json_via_proxy(FEED, QUERY, **kwargs)
            return result, get, utils.PROXY_EXHAUSTED

    def test_it_returns_the_feeds_json_and_sends_the_query_in_the_url(self):
        result, get, _ = self.fetch(FakeResponse(200, {'shows': [1]}))
        self.assertEqual(result, {'shows': [1]})
        self.assertEqual(get.call_args.args[0], f'{FEED}?limit=100&offset=0&sub=abc')
        self.assertEqual(get.call_args.args[1], {'premium_proxy': 'true'})          # the default options

    def test_the_callers_proxy_options_are_used(self):
        _, get, _ = self.fetch(FakeResponse(200, {}), proxy_params={'premium_proxy': 'true', 'proxy_country': 'ca'})
        self.assertEqual(get.call_args.args[1], {'premium_proxy': 'true', 'proxy_country': 'ca'})

    def test_without_a_key_nothing_is_requested(self):
        result, get, _ = self.fetch(FakeResponse(200, {'shows': []}), key=None)
        self.assertIsNone(result)
        get.assert_not_called()

    def test_once_the_account_is_out_of_credits_nothing_is_requested(self):
        result, get, _ = self.fetch(FakeResponse(200, {'shows': []}), exhausted=True)
        self.assertIsNone(result)
        get.assert_not_called()

    def test_a_402_marks_the_account_out_of_credits(self):
        with self.assertLogs(level='ERROR') as logs:
            result, _, exhausted = self.fetch(FakeResponse(402))
        self.assertIsNone(result)
        self.assertTrue(exhausted)
        self.assertIn('out of credits', '\n'.join(logs.output))

    def test_a_refusal_logs_zenrows_own_explanation(self):
        with self.assertLogs(level='ERROR') as logs:
            result, _, exhausted = self.fetch(FakeResponse(422, text='{"code":"RESP001","detail":"Try js_render."}'))
        self.assertIsNone(result)
        self.assertFalse(exhausted)
        self.assertIn('RESP001', '\n'.join(logs.output))

    def test_a_timeout_or_an_answer_that_is_not_json_gives_none(self):
        with self.assertLogs(level='ERROR'):
            self.assertIsNone(self.fetch(FakeResponse(200, json_error=True))[0])
        with mock.patch.object(utils, 'ZENROWS_API_KEY', 'key'), \
                mock.patch.object(utils, 'PROXY_EXHAUSTED', False), \
                mock.patch.object(utils, '_proxy_get', side_effect=requests.Timeout('slow')), \
                self.assertLogs(level='ERROR'):
            self.assertIsNone(utils.fetch_json_via_proxy(FEED, QUERY))


if __name__ == '__main__':
    unittest.main()
