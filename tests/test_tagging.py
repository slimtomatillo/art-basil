# Run with: python3 -m unittest discover -s tests
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import tagging


class FreeGalleryTest(unittest.TestCase):
    def tagged(self, tags):
        event = {'name': 'A show', 'description': '', 'venue': 'Somewhere', 'tags': list(tags)}
        tagging.add_content_tags(event)
        return event['tags']

    def test_gallery_is_free(self):
        self.assertIn('free', self.tagged(['exhibition', 'current', 'gallery']))

    def test_museum_is_not_assumed_free(self):
        self.assertNotIn('free', self.tagged(['exhibition', 'current', 'museum']))

    def test_gallery_that_is_also_a_museum_is_not_assumed_free(self):
        self.assertNotIn('free', self.tagged(['exhibition', 'gallery', 'museum']))

    def test_other_venues_are_not_assumed_free(self):
        self.assertNotIn('free', self.tagged(['exhibition', 'current']))

    def test_free_is_added_once_and_existing_free_is_kept(self):
        tags = self.tagged(['gallery', 'free'])
        self.assertEqual(tags.count('free'), 1)


if __name__ == '__main__':
    unittest.main()
