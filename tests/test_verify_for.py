# Run with the project's Python: python -m unittest discover -s tests
import os
import sys
import unittest

import certifi

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import utils


class VerifyForTest(unittest.TestCase):
    def test_ordinary_hosts_use_the_default_verification(self):
        self.assertIs(utils.verify_for('https://www.moma.org/calendar'), True)
        # a look-alike domain must not get the extra bundle
        self.assertIs(utils.verify_for('https://nottheimagecentre.ca/'), True)

    def test_hosts_missing_their_intermediate_get_the_roots_plus_the_intermediates(self):
        for url in ('https://theimagecentre.ca/gallery/', 'https://www.theimagecentre.ca/exhibition/x/'):
            bundle = utils.verify_for(url)
            self.assertTrue(os.path.exists(bundle))
            text = open(bundle).read()
            self.assertIn(open(certifi.where()).read()[:200], text)
            self.assertIn('SSL.com TLS Issuing RSA CA R1', text)

    def test_the_intermediates_file_holds_one_certificate(self):
        self.assertEqual(open(utils.INTERMEDIATES_FILE).read().count('BEGIN CERTIFICATE'), 1)


if __name__ == '__main__':
    unittest.main()
