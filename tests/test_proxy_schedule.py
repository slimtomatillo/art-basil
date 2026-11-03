# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# The ZenRows credit schedule (WEBSITE-83 / OPERATIONS.md): proxied venues refresh every 4 days,
# and their past-exhibition pages only on every second refresh. These tests cover the rules and
# that each scraper actually skips (or fetches) its past page. Nothing here touches the network
# or the event data files.
import datetime as dt
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import main
import utils
from scrapers.la import norton_simon
from scrapers.sf import asian_art_museum, bampfa, cantor, de_young


class PastPagesDueTest(unittest.TestCase):
    def setUp(self):
        # A key must be set for the proxied rules to apply at all
        patcher = mock.patch.object(utils, 'ZENROWS_API_KEY', 'test-key')
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(setattr, utils, 'FORCE_PAST_PAGES', False)

    def test_dev_runs_always_get_everything(self):
        for offset in range(8):
            self.assertTrue(utils.past_pages_due('dev', dt.date(2026, 11, 3) + dt.timedelta(days=offset)))

    def test_no_proxy_key_means_direct_free_fetches_get_everything(self):
        with mock.patch.object(utils, 'ZENROWS_API_KEY', None):
            for offset in range(8):
                self.assertTrue(utils.past_pages_due('prod', dt.date(2026, 11, 3) + dt.timedelta(days=offset)))

    def test_a_venue_named_on_the_command_line_gets_everything(self):
        utils.FORCE_PAST_PAGES = True
        for offset in range(8):
            self.assertTrue(utils.past_pages_due('prod', dt.date(2026, 11, 3) + dt.timedelta(days=offset)))

    def test_refreshes_four_days_apart_alternate(self):
        # The venue's refresh days are 4 days apart, so past pages come on every second one
        start = dt.date(2026, 11, 3)
        for first_offset in range(4):             # whichever day of the cycle the venue refreshes on
            results = [utils.past_pages_due('prod', start + dt.timedelta(days=first_offset + 4 * i)) for i in range(12)]
            for before, after in zip(results, results[1:]):
                self.assertNotEqual(before, after, f"refreshes didn't alternate: {results}")
            self.assertEqual(sum(results), 6)

    def test_past_pages_are_pulled_about_every_eight_days_per_venue(self):
        start = dt.date(2026, 11, 3)
        due_days = [start + dt.timedelta(days=4 * i) for i in range(12)
                    if utils.past_pages_due('prod', start + dt.timedelta(days=4 * i))]
        gaps = {(b - a).days for a, b in zip(due_days, due_days[1:])}
        self.assertEqual(gaps, {8})

    def test_the_answer_is_the_same_all_day(self):
        day = dt.date(2026, 11, 3)
        self.assertEqual(utils.past_pages_due('prod', day), utils.past_pages_due('prod', day))


class RefreshGateTest(unittest.TestCase):
    NOW = dt.datetime(2026, 11, 7, 11, 0, 0)

    def due(self, age_hours):
        stamp = (self.NOW - dt.timedelta(hours=age_hours)).strftime('%Y-%m-%d %H:%M:%S')
        db = {'BAMPFA': {'a': {'last_updated': stamp}, 'b': {'last_updated': '2020-01-01 00:00:00'}}}
        with mock.patch.object(main, 'load_db', return_value=db):
            return main.proxy_refresh_due('sf', 'BAMPFA', now=self.NOW)

    def test_refresh_interval_is_four_days_with_twelve_hours_of_slack(self):
        self.assertEqual(main.PROXY_REFRESH_MIN_AGE, dt.timedelta(hours=84))

    def test_not_due_before_three_and_a_half_days(self):
        self.assertFalse(self.due(24))
        self.assertFalse(self.due(72))     # the next daily run after 3 days: not yet
        self.assertFalse(self.due(83))

    def test_due_once_it_is_four_days_old(self):
        self.assertTrue(self.due(85))
        self.assertTrue(self.due(96))      # the daily run 4 days later
        self.assertTrue(self.due(200))

    def test_due_when_there_is_no_data(self):
        with mock.patch.object(main, 'load_db', return_value={}):
            self.assertTrue(main.proxy_refresh_due('sf', 'BAMPFA', now=self.NOW))

    def test_uses_the_newest_event_not_the_oldest(self):
        # one event was last stamped in 2020, but another is only a day old: not due
        self.assertFalse(self.due(24))


class PastPageWiringTest(unittest.TestCase):
    """Each proxied scraper that has a past page fetches it only when it is due, and its
    current/upcoming pages always. fetch_and_parse returns None, so the scraper stops right
    after fetching and nothing is written."""

    def run_scraper(self, module, function_name, due, **kwargs):
        urls = []

        def fake_fetch(url, headers=None):
            urls.append(url)
            return None

        with mock.patch.object(module, 'fetch_and_parse', side_effect=fake_fetch), \
                mock.patch.object(module, 'past_pages_due', return_value=due):
            getattr(module, function_name)(env='prod', **kwargs)
        return urls

    def check(self, module, function_name, region, current_markers, past_marker):
        skipped = self.run_scraper(module, function_name, False, region=region)
        fetched = self.run_scraper(module, function_name, True, region=region)
        for marker in current_markers:
            self.assertTrue(any(marker in u for u in skipped), f"{marker} should always be fetched: {skipped}")
        self.assertFalse(any(past_marker in u for u in skipped), f"past page fetched when not due: {skipped}")
        self.assertTrue(any(past_marker in u for u in fetched), f"past page not fetched when due: {fetched}")

    def test_bampfa(self):
        self.check(bampfa, 'scrape_bampfa_exhibitions', 'sf', ['field_event_series_type_value=1'], '/exhibitions/past')

    def test_cantor(self):
        self.check(cantor, 'scrape_cantor_exhibitions', 'sf',
                   ['/exhibitions', '/upcoming-exhibitions'], '/past-exhibitions')

    def test_de_young_and_legion_of_honor(self):
        skipped = self.run_scraper(de_young, 'scrape_de_young_and_legion_of_honor', False, region='sf')
        fetched = self.run_scraper(de_young, 'scrape_de_young_and_legion_of_honor', True, region='sf')
        self.assertEqual(len(skipped), 2, skipped)                          # one current page per site
        self.assertFalse(any('/exhibitions/past' in u for u in skipped))
        self.assertEqual(len(fetched), 4, fetched)                          # current + past for each
        self.assertEqual(sum('/exhibitions/past' in u for u in fetched), 2)

    def test_norton_simon(self):
        self.check(norton_simon, 'scrape_norton_simon_exhibitions', 'la',
                   ['/exhibitions/current'], '/exhibitions/2020-2029')

    def test_asian_art_museum_past_events(self):
        skipped = self.run_scraper(asian_art_museum, 'scrape_asian_art_museum_past_events', False, region='sf')
        fetched = self.run_scraper(asian_art_museum, 'scrape_asian_art_museum_past_events', True, region='sf')
        self.assertEqual(skipped, [])
        self.assertEqual(fetched, ['https://exhibitions.asianart.org/past/'])   # and a failed fetch no longer crashes


class NamedVenueRunTest(unittest.TestCase):
    """`--venues <name>` fetches everything, past pages included; a normal run doesn't.
    write_summary=False skips everything after the scraper loop, so no data file is touched."""

    def run_main(self, selected_venues):
        seen = {}

        def fake_scraper(env='prod', region='sf'):
            seen['force'] = utils.FORCE_PAST_PAGES

        self.addCleanup(setattr, utils, 'FORCE_PAST_PAGES', False)
        with mock.patch.object(main, 'configure_logging'), \
                mock.patch.object(main, 'get_venue_scrapers',
                                  return_value=({'BAMPFA': fake_scraper}, {'BAMPFA': 'sf'})), \
                mock.patch.object(main, 'proxy_refresh_due', return_value=True), \
                mock.patch.object(utils, 'ZENROWS_API_KEY', 'test-key'):
            main.main(env='prod', selected_venues=selected_venues, write_summary=False)
        return seen['force']

    def test_named_venue_forces_past_pages(self):
        self.assertTrue(self.run_main(['BAMPFA']))

    def test_normal_run_does_not(self):
        self.assertFalse(self.run_main(None))


if __name__ == '__main__':
    unittest.main()
