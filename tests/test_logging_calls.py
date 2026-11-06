# Run with the project's Python: python -m unittest discover -s tests
import glob
import logging
import os
import re
import unittest

ROOT = os.path.join(os.path.dirname(__file__), '..')


class LoggingCallsTest(unittest.TestCase):
    def test_every_logging_call_names_a_real_function(self):
        """A mistyped call such as logging.ingo(...) only fails when its line runs, which for a
        scraper's "could not fetch" branch means the day a site is down: the scraper then crashes
        and the whole daily run is marked failed (Kala, November 2026)."""
        files = glob.glob(os.path.join(ROOT, '*.py')) + glob.glob(os.path.join(ROOT, 'scrapers', '**', '*.py'), recursive=True)
        bad = []
        for path in files:
            for number, line in enumerate(open(path, encoding='utf-8'), start=1):
                for name in re.findall(r'\blogging\.([A-Za-z_]+)\(', line):
                    if not callable(getattr(logging, name, None)):
                        bad.append(f'{os.path.relpath(path, ROOT)}:{number}: logging.{name}(')
        self.assertEqual(bad, [])


if __name__ == '__main__':
    unittest.main()
