# Run with the project's Python: python -m unittest discover -s tests
#
# WEBSITE-138: a page on a host in utils.PROXY_JS_RETRY_HOSTS (MoMA) that ZenRows refuses with a 422 RESP001 is fetched once more
# with js_render, and only then. No network.
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import requests
import utils

MOMA = 'https://www.moma.org/calendar/exhibitions/5964'
REFUSED = '{"code":"RESP001","instance":"/v1","status":422,"title":"Could not get content. try enabling javascript rendering (RESP001)"}'
PAGE = '<html><head><title>Ana Mendieta | MoMA</title></head><body><p>A retrospective.</p></body></html>'


class FakeResponse:
    def __init__(self, status, text=''):
        self.status_code, self.text, self.content = status, text, text.encode()
        self.headers = {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'{self.status_code} Client Error')


class JsRetryTest(unittest.TestCase):
    def setUp(self):
        for patcher in (mock.patch.object(utils, 'ZENROWS_API_KEY', 'key'), mock.patch.object(utils, 'PROXY_EXHAUSTED', False),
                        mock.patch.object(utils, 'PROXY_JS_RETRIES', 0)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def fetch(self, url, *responses):
        """fetch_and_parse over the responses a proxied GET gives in turn; returns (soup, the options each GET was made with)."""
        with mock.patch.object(utils, '_proxy_get', side_effect=list(responses)) as get:
            soup = utils.fetch_and_parse(url)
        return soup, [call.args[1] for call in get.call_args_list]

    def test_a_422_resp001_is_fetched_again_with_js_render_and_counted(self):
        soup, options = self.fetch(MOMA, FakeResponse(422, REFUSED), FakeResponse(200, PAGE))
        self.assertEqual(soup.title.get_text(), 'Ana Mendieta | MoMA')
        self.assertEqual(options, [{'premium_proxy': 'true'}, {'premium_proxy': 'true', 'js_render': 'true'}])
        self.assertEqual(utils.PROXY_JS_RETRIES, 1)

    def test_a_second_refusal_is_not_retried_again(self):
        soup, options = self.fetch(MOMA, FakeResponse(422, REFUSED), FakeResponse(422, REFUSED))
        self.assertIsNone(soup)
        self.assertEqual(len(options), 2)
        self.assertEqual(utils.PROXY_JS_RETRIES, 1)

    def test_a_page_that_comes_back_the_first_time_is_not_fetched_again(self):
        soup, options = self.fetch(MOMA, FakeResponse(200, PAGE))
        self.assertIsNotNone(soup)
        self.assertEqual(len(options), 1)
        self.assertEqual(utils.PROXY_JS_RETRIES, 0)

    def test_other_answers_are_not_retried(self):
        for response in (FakeResponse(403, 'Forbidden'), FakeResponse(404, 'Not found'), FakeResponse(422, '{"code":"REQS004"}')):
            utils.PROXY_JS_RETRIES = 0
            soup, options = self.fetch(MOMA, response)
            self.assertIsNone(soup)
            self.assertEqual(len(options), 1, response.status_code)
            self.assertEqual(utils.PROXY_JS_RETRIES, 0)

    def test_out_of_credits_is_not_retried_and_stops_the_proxied_fetches(self):
        soup, options = self.fetch(MOMA, FakeResponse(402, 'out of credits'))
        self.assertIsNone(soup)
        self.assertEqual(len(options), 1)
        self.assertTrue(utils.PROXY_EXHAUSTED)

    def test_a_host_that_is_not_listed_is_not_retried(self):
        url = 'https://www.marincounty.gov/departments/cultural-services/art-exhibits/civic-center-art-gallery'
        soup, options = self.fetch(url, FakeResponse(422, REFUSED))
        self.assertIsNone(soup)
        self.assertEqual(len(options), 1)

    def test_a_host_that_already_renders_is_not_asked_for_it_twice(self):
        with mock.patch.object(utils, 'PROXY_JS_RETRY_HOSTS', frozenset({'gagosian.com'})):
            soup, options = self.fetch('https://gagosian.com/exhibitions/', FakeResponse(422, REFUSED))
        self.assertIsNone(soup)
        self.assertEqual(len(options), 1)                                           # gagosian.com is on js_render already

    def test_moma_is_listed_and_its_plain_options_do_not_already_render(self):
        self.assertIn('www.moma.org', utils.PROXY_JS_RETRY_HOSTS)
        self.assertEqual(utils.PROXY_DOMAINS['www.moma.org'], {'premium_proxy': 'true'})
        self.assertLessEqual(utils.PROXY_JS_RETRY_HOSTS, set(utils.PROXY_DOMAINS))   # a retry host is a proxied host


if __name__ == '__main__':
    unittest.main()
