# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# di Rosa and MACLA (WEBSITE-72). The fixtures are trimmed copies of the sites' markup captured on
# 2026-11-09. No network.
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.sf import di_rosa, macla
from scrapers.tor import _common

TODAY = dt.date(2026, 11, 9)


def soup(html):
    return BeautifulSoup(html, 'html.parser')


def run(module, scrape, pages):
    """Run a scraper against {url: html}; returns the events it stored."""
    stored = []

    def fetch(url, *args, **kwargs):
        html = pages.get(url)
        return soup(html) if html else None

    with mock.patch.object(module, 'fetch_and_parse', side_effect=fetch), \
            mock.patch.object(module, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
        scrape(env='prod')
    return stored


LONG = 'This exhibition brings together work from the collection in a way that has not been seen before. ' * 2


def card(path, title):
    return (f'<article class="elementor-post"><a href="https://www.dirosaart.org/{path}/"></a>'
            f'<h3 class="elementor-post__title"><a href="https://www.dirosaart.org/{path}/">{title}</a></h3></article>')


def show_page(title, dates, site, image='https://www.dirosaart.org/pic.jpg'):
    return (f'<html><head><meta property="og:image" content="{image}"><title>{title} | di Rosa</title></head><body>'
            f'<a>Skip to content</a><h1>{title}</h1><div>{dates}</div><div>{site}</div><p>{LONG}</p></body></html>')


class DiRosaTest(unittest.TestCase):
    LIST = ('<main>' + card('2023/01/incorrect', 'The Incorrect Museum | Ongoing')
            + card('2026/07/pred', 'Michele Pred: Projecting Democracy')
            + card('2026/08/making-strange', 'Making Strange')
            + card('2026/10/invaders', 'Invaders: Vallejo, Food and the Making of California')
            + card('2026/12/later', 'A Later Show') + '</main>')
    PAGES = {
        di_rosa.LIST_URL: LIST,
        'https://www.dirosaart.org/2026/07/pred/': show_page('Michele Pred: Projecting Democracy', 'June 20-September 20', 'Visible nightly'),
        'https://www.dirosaart.org/2026/08/making-strange/': show_page('Making Strange', 'August 29 – November 29, 2026', 'di Rosa Napa'),
        'https://www.dirosaart.org/2026/10/invaders/': show_page('Invaders: Vallejo, Food and the Making of California', 'November 7, 2026-February 6, 2027', 'di Rosa SF'),
        'https://www.dirosaart.org/2026/12/later/': show_page('A Later Show', 'December 12-March 1', 'di Rosa Napa'),
    }

    def events(self, pages=None):
        return {e['name']: e for e in run(di_rosa, di_rosa.scrape_di_rosa, pages or self.PAGES)}

    def test_current_and_upcoming_shows_are_published_at_their_own_site(self):
        events = self.events()
        self.assertEqual(set(events), {'Making Strange', 'Invaders: Vallejo, Food and the Making of California', 'A Later Show'})
        self.assertEqual(events['Making Strange']['venue'], 'di Rosa Napa')
        self.assertEqual(events['Invaders: Vallejo, Food and the Making of California']['venue'], 'di Rosa SF')

    def test_ongoing_and_past_shows_are_left_out(self):
        events = self.events()
        self.assertNotIn('The Incorrect Museum | Ongoing', events)
        self.assertNotIn('Michele Pred: Projecting Democracy', events)

    def test_dates_phases_and_the_year_when_the_page_omits_it(self):
        events = self.events()
        self.assertEqual(events['Making Strange']['dates'], {'start': dt.date(2026, 8, 29), 'end': dt.date(2026, 11, 29)})
        self.assertEqual(events['Making Strange']['phase'], 'current')
        later = events['A Later Show']
        self.assertEqual((later['dates']['start'], later['dates']['end']), (dt.date(2026, 12, 12), dt.date(2027, 3, 1)))
        self.assertEqual(later['phase'], 'future')

    def test_napa_is_a_museum_and_sf_a_gallery(self):
        events = self.events()
        self.assertIn('museum', events['Making Strange']['tags'])
        self.assertIn('gallery', events['Invaders: Vallejo, Food and the Making of California']['tags'])

    def test_picture_link_and_description(self):
        event = self.events()['Making Strange']
        self.assertIn({'link': 'https://www.dirosaart.org/pic.jpg', 'description': 'Image'}, event['links'])
        self.assertTrue(event['description'].startswith('This exhibition brings together'))

    def test_unreadable_list_page_keeps_existing_data(self):
        self.assertEqual(run(di_rosa, di_rosa.scrape_di_rosa, {}), [])

    def test_a_show_page_that_cannot_be_read_does_not_stop_the_others(self):
        pages = dict(self.PAGES)
        del pages['https://www.dirosaart.org/2026/08/making-strange/']
        self.assertEqual(set(self.events(pages)), {'Invaders: Vallejo, Food and the Making of California', 'A Later Show'})


def article(title, start, end, year_month, description, category='Exhibitions', past=False):
    end_label = f'<span class="mec-end-date-label"> {end}</span>' if end else ''
    return (f'<article class="{"mec-past-event " if past else ""}mec-event-article mec-toggle-{year_month}-mec3">'
            f'<div class="mec-event-month"><span class="mec-start-date-label">{start}</span>{end_label}</div>'
            f'<h3 class="mec-toggle-title">{title}</h3><img src="https://maclaarte.org/wp-content/{title[:3]}.png">'
            f'<div class="mec-single-event-description">{description}</div>'
            f'<div class="mec-events-event-categories"><a>{category}</a></div></article>')


class MaclaTest(unittest.TestCase):
    def events(self, *articles):
        html = '<main>' + ''.join(articles) + '</main>'
        return {e['name']: e for e in run(macla, macla.scrape_macla, {macla.PAGE_URL: html})}

    def test_the_text_dates_win_over_the_calendar_labels(self):
        # The calendar says it ended Nov 8; the exhibition's own text says Nov 15
        events = self.events(article('Poetic Utterances', '04 September', '- 08 November', '202609',
                                     'September 4 – November 15, 2026 Supported by MACLA, a solo show.', past=True))
        event = events['Poetic Utterances']
        self.assertEqual(event['dates'], {'start': dt.date(2026, 9, 4), 'end': dt.date(2026, 11, 15)})
        self.assertEqual(event['phase'], 'current')
        self.assertEqual(event['description'], 'Supported by MACLA, a solo show.')

    def test_calendar_labels_are_used_when_the_text_has_no_dates(self):
        events = self.events(article('Winter Show', '05 December', '- 08 March', '202612', 'A show about winter.'))
        self.assertEqual(events['Winter Show']['dates'], {'start': dt.date(2026, 12, 5), 'end': dt.date(2027, 3, 8)})
        self.assertEqual(events['Winter Show']['phase'], 'future')

    def test_a_short_run_inside_one_label(self):
        events = self.events(article('Weekend Show', '07 - 15 November', None, '202611', 'A weekend show.'))
        self.assertEqual(events['Weekend Show']['dates'], {'start': dt.date(2026, 11, 7), 'end': dt.date(2026, 11, 15)})

    def test_past_shows_and_other_categories_are_left_out(self):
        events = self.events(
            article('Old Show', '06 June', '- 10 August', '202606', 'An old show.', past=True),
            article('Clay Workshop', '10 November', '- 12 November', '202611', 'Learn clay.', category='Workshops'))
        self.assertEqual(events, {})

    def test_free_gallery_tag_and_venue(self):
        event = self.events(article('Open Now', '01 November', '- 20 December', '202611', 'On view.'))['Open Now']
        self.assertEqual(event['venue'], 'MACLA')
        self.assertIn('gallery', event['tags'])

    def test_no_events_is_not_an_error(self):
        self.assertEqual(self.events(), {})


if __name__ == '__main__':
    unittest.main()
