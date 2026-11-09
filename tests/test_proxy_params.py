# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# The ZenRows options a proxied host is fetched with (utils.PROXY_DOMAINS) reach the request as query
# parameters. WEBSITE-106: Marin Civic Center is fetched with a US exit IP. No network.
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import utils

MARIN_URL = 'https://www.marincounty.gov/departments/cultural-services/art-exhibits/civic-center-art-gallery'


class ProxyParamsTest(unittest.TestCase):
    def test_marin_civic_center_asks_for_a_us_exit_ip(self):
        self.assertEqual(utils.PROXY_DOMAINS['www.marincounty.gov'],
                         {'premium_proxy': 'true', 'js_render': 'true', 'proxy_country': 'us'})

    def test_the_options_are_sent_as_query_parameters(self):
        response = mock.Mock(status_code=200)
        with mock.patch.object(utils, 'ZENROWS_API_KEY', 'test-key'), \
                mock.patch.object(utils.requests, 'get', return_value=response) as get:
            utils._proxy_get(MARIN_URL, utils.PROXY_DOMAINS['www.marincounty.gov'])
        params = get.call_args.kwargs['params']
        self.assertEqual(params['url'], MARIN_URL)
        self.assertEqual(params['proxy_country'], 'us')
        self.assertEqual(params['js_render'], 'true')
        self.assertEqual(params['premium_proxy'], 'true')


if __name__ == '__main__':
    unittest.main()
