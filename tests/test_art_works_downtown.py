# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.sf import art_works_downtown as awd

TODAY = dt.date(2026, 10, 27)
FOOTER = '<div class="sqs-html-content"><p>Art Works Downtown</p><p>1325-1337 Fourth Street</p><p>Admission is free</p></div>'
LONG = 'A long artists statement about the work, its materials and the people who made it, ' * 3


def block(*lines):
    return '<div class="sqs-html-content">' + ''.join(f'<p>{line}</p>' for line in lines) + '</div>'


def page(list_html, sections):
    return BeautifulSoup(f'<main><p><strong><u>Upcoming Exhibits</u></strong><br>{list_html}</p>{sections}{FOOTER}</main>', 'html.parser')


# Three shows. Numina is ordinary; "Rina" is linked as #rina but its id is "Rina", and its
# date block is not the first block of its section; the salon's own dates have a typo
# (end year before the start) so its list dates must be used.
LIST_HTML = ('October 2–November&nbsp;14, 2026: <a href="#numina"><strong>Numina</strong></a><br>'
             'August 14–September 25, 2026: <a href="#rina"><strong>In2 Liquid</strong></a><br>'
             'November 25, 2026—January 23, 2027: <a href="#salon"><strong>Members Holiday Salon</strong></a>')
IMG = '<img data-src="https://img/full.jpg" srcset="https://img/full.jpg?format=300w 300w, https://img/full.jpg?format=500w 500w, https://img/full.jpg?format=1000w 1000w">'
SECTIONS = (
    '<div id="numina"></div>' + IMG +
    block('October 2–November 14, 2026', 'Exhibition Dates', 'October 9, 5–8pm', 'Reception') +
    block('Curatorial Statement', LONG) +
    block('In2 Liquid', 'Abstract photography') +                      # the NEXT show's title block
    '<div id="Rina"></div>' +
    block('In2 Liquid', 'Abstract photography by two artists') +
    block('October 9–November 13, 2026', 'Exhibition Dates') +
    block('Short caption') + block(LONG) +
    '<div id="salon"></div>' +
    block('November 25, 2026—January 23, 2026', 'Exhibition Dates') +
    block(LONG)
)


class ParsingTest(unittest.TestCase):
    def setUp(self):
        self.soup = page(LIST_HTML, SECTIONS)

    def test_the_list_is_read_with_nbsp_and_dashes(self):
        entries = awd.parse_exhibit_list(self.soup)
        self.assertEqual([e[1] for e in entries], ['Numina', 'In2 Liquid', 'Members Holiday Salon'])
        self.assertEqual([e[2] for e in entries], ['numina', 'rina', 'salon'])
        self.assertEqual(awd.parse_date_text(entries[0][0], TODAY), (dt.date(2026, 10, 2), dt.date(2026, 11, 14)))
        self.assertEqual(awd.parse_date_text(entries[2][0], TODAY), (dt.date(2026, 11, 25), dt.date(2027, 1, 23)))

    def test_a_missing_list_raises_so_the_run_goes_red(self):
        with self.assertRaises(RuntimeError):
            awd.parse_exhibit_list(BeautifulSoup('<main><p>Something else</p></main>', 'html.parser'))

    def test_section_stops_at_the_next_anchor_and_matches_ids_case_insensitively(self):
        blocks, image, real_id = awd.exhibit_section(self.soup, 'rina', ['numina', 'rina', 'salon'])
        self.assertEqual(real_id, 'Rina')
        self.assertTrue(blocks[0].startswith('In2 Liquid'))
        self.assertNotIn('Curatorial Statement', ' '.join(blocks))
        self.assertNotIn('November 25, 2026', ' '.join(blocks))

    def test_a_missing_anchor_gives_an_empty_section(self):
        self.assertEqual(awd.exhibit_section(self.soup, 'nope', ['numina', 'nope']), ([], None, None))

    def test_the_image_is_the_500w_rendition(self):
        _, image, _ = awd.exhibit_section(self.soup, 'numina', ['numina', 'rina', 'salon'])
        self.assertEqual(image, 'https://img/full.jpg?format=500w')

    def test_the_date_block_can_be_anywhere_in_the_section(self):
        blocks, _, _ = awd.exhibit_section(self.soup, 'rina', ['numina', 'rina', 'salon'])
        index, line = awd.find_date_block(blocks)
        self.assertEqual((index, line), (1, 'October 9–November 13, 2026'))
        self.assertEqual(awd.dates_from_section(blocks, TODAY), (dt.date(2026, 10, 9), dt.date(2026, 11, 13)))

    def test_description_skips_short_blocks_and_the_footer(self):
        blocks, _, _ = awd.exhibit_section(self.soup, 'rina', ['numina', 'rina', 'salon'])
        description = awd.description_from_section(blocks + [FOOTER_TEXT])
        self.assertTrue(description.startswith('A long artists statement'))
        self.assertNotIn('Fourth Street', description)
        self.assertNotIn('Short caption', description)

    def test_subtitle_is_the_line_under_the_title_in_the_same_block_or_the_next(self):
        soup = page('', block('Numina', 'Six Artists Exploring Consciousness') + block('In2 Liquid') + block('Abstract photography by two artists') +
                    block('Solo') + block('October 9\u2013November 13, 2026', 'Exhibition Dates') + block('Salon') + block('x' * 200))
        self.assertEqual(awd.subtitle_for(soup, 'Numina'), 'Six Artists Exploring Consciousness')
        self.assertEqual(awd.subtitle_for(soup, 'In2 Liquid'), 'Abstract photography by two artists')
        self.assertIsNone(awd.subtitle_for(soup, 'Solo'), 'a following block that is the date block is not a subtitle')
        self.assertIsNone(awd.subtitle_for(soup, 'Salon'), 'a following block that is long is a paragraph, not a subtitle')
        self.assertIsNone(awd.subtitle_for(soup, 'Not on the page'))

    def test_description_is_subtitle_then_paragraph(self):
        self.assertEqual(awd.join_description('Abstract photography', 'A long text.'), 'Abstract photography. A long text.')
        self.assertEqual(awd.join_description('Six Artists?', 'Text.'), 'Six Artists? Text.')
        self.assertEqual(awd.join_description(None, 'Text.'), 'Text.')
        self.assertEqual(awd.join_description('Sub', None), 'Sub')
        self.assertIsNone(awd.join_description(None, None))

    def test_pick_dates_prefers_the_section_but_falls_back_when_it_is_invalid(self):
        sec = (dt.date(2026, 10, 9), dt.date(2026, 11, 13))
        lst = (dt.date(2026, 8, 14), dt.date(2026, 9, 25))
        with self.assertLogs(level='WARNING') as logs:
            self.assertEqual(awd.pick_dates(lst, sec, 'X'), sec)
        self.assertIn('differ', logs.output[0])
        typo = (dt.date(2026, 11, 25), dt.date(2026, 1, 23))          # ends before it starts
        self.assertEqual(awd.pick_dates((dt.date(2026, 11, 25), dt.date(2027, 1, 23)), typo, 'X'), (dt.date(2026, 11, 25), dt.date(2027, 1, 23)))
        self.assertEqual(awd.pick_dates((None, None), (None, None), 'X'), (None, None))

    def test_a_whole_page(self):
        shows = awd.parse_gallery_page(self.soup, 'https://site/g', TODAY)
        by_name = {s['name']: s for s in shows}
        self.assertEqual((by_name['Numina']['start'], by_name['Numina']['end']), (dt.date(2026, 10, 2), dt.date(2026, 11, 14)))
        self.assertEqual((by_name['In2 Liquid']['start'], by_name['In2 Liquid']['end']), (dt.date(2026, 10, 9), dt.date(2026, 11, 13)))
        self.assertEqual((by_name['Members Holiday Salon']['start'], by_name['Members Holiday Salon']['end']), (dt.date(2026, 11, 25), dt.date(2027, 1, 23)))
        self.assertEqual(by_name['In2 Liquid']['link'], 'https://site/g#Rina')


FOOTER_TEXT = 'Art Works Downtown\n1325-1337 Fourth Street\nAdmission is free'


class ScrapeTest(unittest.TestCase):
    def run_scrape(self, soups):
        calls = []
        with mock.patch.object(awd, 'fetch_and_parse', side_effect=soups), \
             mock.patch.object(awd, 'region_today', return_value=TODAY), \
             mock.patch.object(awd, 'process_event', side_effect=lambda e, r: calls.append(e)):
            awd.scrape_art_works_downtown(env='prod')
        return calls

    def test_events_have_the_expected_shape_and_a_show_on_two_galleries_is_stored_once(self):
        shared = page('November 25, 2026—January 23, 2027: <a href="#salon"><strong>Members Holiday Salon</strong></a>',
                      '<div id="salon"></div>' + block('November 25, 2026—January 23, 2027', 'Exhibition Dates') + block(LONG))
        calls = self.run_scrape([page(LIST_HTML, SECTIONS), shared, shared])
        names = [c['name'] for c in calls]
        self.assertEqual(sorted(names), ['In2 Liquid', 'Members Holiday Salon', 'Numina'])
        numina = next(c for c in calls if c['name'] == 'Numina')
        self.assertEqual(numina['venue'], 'Art Works Downtown')
        self.assertEqual(numina['tags'], ['exhibition', 'current', 'gallery'])
        self.assertEqual(numina['phase'], 'current')
        self.assertEqual([l['description'] for l in numina['links']], ['Event Page', 'Image'])
        self.assertEqual(next(c for c in calls if c['name'] == 'Members Holiday Salon')['phase'], 'future')

    def test_a_page_that_cannot_be_fetched_raises(self):
        with self.assertRaises(RuntimeError):
            self.run_scrape([None])

    def test_a_page_without_the_list_raises(self):
        with self.assertRaises(RuntimeError):
            self.run_scrape([BeautifulSoup('<main></main>', 'html.parser')])


if __name__ == '__main__':
    unittest.main()
