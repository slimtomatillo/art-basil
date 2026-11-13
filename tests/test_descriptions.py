# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# descriptions.py finds a description for events whose scraper supplied none. Nothing here touches the
# network or the real event data: pages are fake HTML, and the event files are temporary ones swapped
# into config.DB_FILES.
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import descriptions
import processing
import utils
from config import DB_FILES

TODAY = dt.date(2026, 11, 13)
NAME = 'Josiah McElheny: Island Universe'
BLURB = ("Josiah McElheny's dramatic Island Universe, installed in the Resnick Pavilion, embodies the concept "
         "of the multiverse, or multiple coexisting universes. It is a sculpture of glass and light.")


def soup(html):
    return BeautifulSoup(html, 'html.parser')


def page(head='', body=''):
    return soup(f'<html><head>{head}</head><body>{body}</body></html>')


def event(name=NAME, page_url='https://gallery.example/island', phase='current', description='', links=None, **extra):
    return {'name': name, 'venue': 'Gallery', 'phase': phase, 'description': description, 'tags': [], 'ongoing': False,
            'dates': {'start': '2026-10-01', 'end': '2026-12-01'}, 'hash': 'x',
            'links': links if links is not None else [{'link': page_url, 'description': 'Event Page'}], **extra}


class CleanAndTrimTest(unittest.TestCase):
    def test_clean_gives_plain_text(self):
        self.assertEqual(descriptions.clean('  Tom &amp; Jerry at <b>the</b>\n\n gallery​ '),
                         'Tom & Jerry at the gallery')
        self.assertEqual(descriptions.clean(None), '')

    def test_short_text_is_untouched(self):
        self.assertEqual(descriptions.trim('One sentence.'), 'One sentence.')

    def test_long_text_is_cut_at_a_sentence_end(self):
        text = ('A first sentence that is long enough to be worth keeping on its own. ' * 3
                + 'And then an unfinished sentence ' * 30)
        cut = descriptions.trim(text)
        self.assertLessEqual(len(cut), descriptions.MAX_CHARS)
        self.assertTrue(cut.endswith('.'))

    def test_a_long_run_with_no_sentence_end_is_cut_at_a_word(self):
        cut = descriptions.trim('word ' * 300)
        self.assertLessEqual(len(cut), descriptions.MAX_CHARS)
        self.assertTrue(cut.endswith('…'))
        self.assertNotIn('wor…', cut.replace('word…', ''))


class UsableTest(unittest.TestCase):
    def test_accepts_a_description_that_mentions_the_show(self):
        self.assertTrue(descriptions.usable(BLURB, NAME))

    def test_rejects_short_text_and_boilerplate(self):
        self.assertFalse(descriptions.usable('Island Universe, on now.', NAME))
        self.assertFalse(descriptions.usable('We use cookies to improve your experience on the Island Universe website, '
                                             'by continuing you agree to our terms and the privacy policy.', NAME))
        self.assertFalse(descriptions.usable('All rights reserved. Island Universe gallery website copyright notice text.', NAME))

    def test_rejects_a_site_wide_tagline_that_never_mentions_the_show(self):
        tagline = ('The Resnick Gallery is a non-profit museum dedicated to presenting modern and contemporary art '
                   'to a wide public in the heart of the city.')
        self.assertFalse(descriptions.usable(tagline, NAME))

    def test_accents_and_case_do_not_matter_when_matching_the_title(self):
        self.assertTrue(descriptions.usable(
            'Une exposition de SAKIP SABANCI présentant des œuvres récentes sur la mémoire, la lumière et la ville.',
            'Sakıp Sabancı: Mémoire'))

    def test_a_title_with_no_significant_word_cannot_be_checked(self):
        self.assertTrue(descriptions.usable(BLURB, 'Untitled'))

    def test_rejects_the_title_repeated(self):
        self.assertFalse(descriptions.usable(NAME + ' ' * 2, NAME))


class NotADescriptionTest(unittest.TestCase):
    """Real texts that looked like descriptions but were not (found reviewing a run on the live pages)."""

    def test_text_that_starts_with_dates_or_a_reception_is_not_a_description(self):
        for text in ('October 23 – November 28, 2026 Artists’ Opening Reception: Saturday, October 24, 3 – 5 pm Material Messages is a group show',
                     '15 octobre 14 novembre 2026 / Chiguer art contemporain Montréal est ravi de présenter Ma cérémonie de souvenirs',
                     '12.11.2026 Ma cérémonie de souvenirs is an exhibition of photographs recording a performance',
                     'Through March 3, 2027, Ma cérémonie de souvenirs presents photographs of a performance in the gallery',
                     'Guest Curator: Elisabetta Pisu Production: IMF Foundation Colour Matters reflects on the role of color'):
            self.assertFalse(descriptions.usable(text, 'Material Messages / Ma cérémonie de souvenirs / Colour Matters'), text)

    def test_a_sentence_that_merely_mentions_a_date_later_is_fine(self):
        self.assertTrue(descriptions.usable(
            'Ma cérémonie de souvenirs gathers photographs of a performance first given in October 2026, in a small room.',
            'Ma cérémonie de souvenirs'))

    def test_a_run_of_artists_names_is_not_a_description(self):
        names = ('Browse the artists at Regen Projects. Doug Aitken Kader Attia Matthew Barney Kevin Beasley Walead Beshty '
                 'John Bock Abraham Cruzvillegas Anish Kapoor Toba Khedoori Liz Larner')
        self.assertTrue(descriptions.looks_like_a_list(names))
        self.assertFalse(descriptions.usable(names, 'Sable Elyse Smith: SKY FENCE GROUND'))
        self.assertFalse(descriptions.looks_like_a_list(BLURB))

    def test_templates_are_not_descriptions(self):
        self.assertFalse(descriptions.usable('Visit our website to learn more about the Renzo Piano: Genius Loci exhibition '
                                             'in the Museum of Modern Art.', 'Renzo Piano: Genius Loci'))
        self.assertFalse(descriptions.usable('Browse current and past exhibitions at Regen Projects, including Sky Fence Ground '
                                             'by the artist and many others over the years.', 'Sky Fence Ground'))

    def test_a_repeated_title_heading_is_dropped_but_a_sentence_that_starts_with_the_title_is_kept(self):
        name = 'Après la pluie, la boue'
        self.assertEqual(descriptions.strip_title_heading('Après la pluie, la boue : Transforming an ancestral material', name),
                         'Transforming an ancestral material')
        self.assertEqual(descriptions.strip_title_heading('Après la pluie, la boue – une exposition', name), 'une exposition')
        sentence = 'Joey Terrill: Homeboy Beautiful is the first institutional retrospective of the artist.'
        self.assertEqual(descriptions.strip_title_heading(sentence, 'Joey Terrill: Homeboy Beautiful'), sentence)

    def test_a_paragraph_drops_its_caption_credit_and_date_lines(self):
        prose = ('My primary interest is color behavior and color perception. I use familiar views and things to explore '
                 'the experience of color across fifty years of painting.')
        s = page(body=('<main><p>Mitchell Johnson, Soup (Red Plate), 1997, 50x58 inches, oil/canvas<br>'
                       'Guest Curator: Elisabetta Pisu<br>October 23 – November 28, 2026<br>' + prose + '</p></main>'))
        self.assertEqual(descriptions.candidates(s), [('paragraph', prose)])


class MoreNotDescriptionsTest(unittest.TestCase):
    NAME = 'Paul R. Williams: An Architect Considered'

    def test_a_menu_bar_is_not_a_description(self):
        self.assertFalse(descriptions.usable('ABOUT | ARTISTS | VIRTUAL TOUR | AUDIO TOUR | TRANSLATIONS | PRESS RELEASE OBJECTS: USA is '
                                             'supported in part by an award', 'Objects: USA'))

    def test_a_photo_caption_with_dimensions_is_not_a_description(self):
        self.assertFalse(descriptions.usable('Paul R. Williams (left) standing with two men at Compton Imperial Housing Project site, '
                                             'ca. 1952. Gelatin silver print. Sheet: 8.125 × 10 in. Image: 7.375 × 9.25 in.', self.NAME))
        self.assertTrue(descriptions.DIMENSIONS.search('30 x 40 cm'))
        self.assertFalse(descriptions.DIMENSIONS.search('a 4 x 4 grid of rooms'))             # no unit, so not a caption

    def test_fragments_titles_and_year_captions_are_not_descriptions(self):
        self.assertFalse(descriptions.usable('une sélection d’oeuvre des métiers d’art autochtones des Territoires du Nord-Ouest',
                                             'Échanges: Une sélection d’oeuvres des métiers d’art autochtone'))
        self.assertFalse(descriptions.usable('F(R)ICTION - Art et jeux 8e Biennale internationale d’art numérique',
                                             'Biennale ELEKTRA: F(R)ICTION - Art et Jeux'))
        self.assertFalse(descriptions.usable('Kamrooz Aram (b. 1978, Shiraz, Iran ) Untitled (Arabesque Composition in Lapis Lazuli ), 2021',
                                             'Kamrooz Aram: Lapis Intervention'))
        # ...but a real sentence that mentions a year, or a sentence with no ending punctuation that is long, is fine
        self.assertTrue(descriptions.usable('Kamrooz Aram challenges the Eurocentric values that have shaped art history, in a gallery '
                                            'intervention first imagined in 2021 and shown here at last.', 'Kamrooz Aram: Lapis Intervention'))

    def test_a_ticketing_paragraph_does_not_hide_the_real_one_behind_it(self):
        ticket = 'Purchasing Museum admission grants full access to all exhibitions on the selected day.'
        caption = 'Kamrooz Aram (b. 1978, Shiraz, Iran ) Untitled (Arabesque Composition in Lapis Lazuli ), 2021'
        real = ('In this co-curated gallery intervention, artist Kamrooz Aram challenges the Eurocentric values that have '
                'shaped art history and museum displays.')
        s = page(body=f'<main><p>{ticket}</p><p>{caption}</p><p>{real}</p></main>')
        self.assertEqual(descriptions.candidates(s), [('paragraph', real)])


class EventInfoTest(unittest.TestCase):
    def test_event_details_run_into_the_text_are_not_a_description(self):
        for text, name in (
                ('GEOFFREY JAMES Ancient and Modern: Selected Panoramas Opening Reception: Saturday, October 31, 10am-1pm Exhibition runs', 'Geoffrey James: Ancient and Modern'),
                ('Opening Celebration: Sat. Nov. 14, 12 – 4 pm Artist Talk: Sat. Nov. 28, 2 pm Susan Freypons has an ongoing practice of marks', 'Marks and Flow: Susan Freypons'),
                ('THEY DO DREAM THINGS TRUE Stephen Schofield 12 novembre – 19 décembre 2026 McBride Contemporain présente le travail', 'Stephen Schofield: They do dream things true'),
                ('Vernissage: le 6 novembre, 17h-21h Exposition: le 8 novembre au 11 décembre « Barrel Baby » présente la vision', 'Marcus Troy: Barrel Baby'),
                ('Create a Website Account - Manage notification subscriptions, save form progress and more. The Gallery Space', 'Revived, by Susan Kuchinskas'),
                ('This page highlights the Fall 2026 exhibition "Live the moment light" at the Palo Alto Art Center.', 'Live the Moment Light')):
            self.assertFalse(descriptions.usable(text, name), text)

    def test_a_real_sentence_about_dates_is_fine(self):
        self.assertTrue(descriptions.usable(
            'The Tucker Nichols exhibition runs from March 3 to June 1 and brings together drawings, ceramics and a new mural.',
            'Tucker Nichols'))


class OpeningsAndSpacingTest(unittest.TestCase):
    def test_a_leading_ticketing_sentence_is_dropped(self):
        text = ('Purchasing Museum admission grants full access to all exhibitions on the selected day. '
                'In this co-curated intervention the artist challenges art history.')
        self.assertEqual(descriptions.strip_opening_furniture(text), 'In this co-curated intervention the artist challenges art history.')
        plain = 'The artist challenges art history. Admission is free.'
        self.assertEqual(descriptions.strip_opening_furniture(plain), plain)

    def test_a_sentence_that_opens_several_of_a_venues_descriptions_is_dropped_from_the_new_ones(self):
        opening = 'Visitors may see this show with a reservation made in advance online. '
        a = (event('A'), opening + 'Artist A makes large paintings about the sea and its weather over many years.', 'paragraph')
        b = (event('B'), opening + 'Artist B builds small sculptures from found wood and wire in a studio in Oakland.', 'paragraph')
        c = (event('C'), 'Artist C films the city at night, in a single long take that runs for two hours.', 'paragraph')
        kept = descriptions._without_shared_openings([a, b, c], [])
        self.assertEqual([t for _, t, _ in kept], [a[1][len(opening):], b[1][len(opening):], c[1]])
        # an opening already stored on another show counts too, and a text left with nothing is dropped
        short = (event('D'), opening + 'Too short.', 'paragraph')
        self.assertEqual(descriptions._without_shared_openings([short], [opening + 'Another show.']), [])

    def test_clean_keeps_quotes_and_closes_up_space_before_punctuation(self):
        self.assertEqual(descriptions.clean('“Flowing City” examines the city , its water ; and more .'),
                         '“Flowing City” examines the city, its water; and more.')

    def test_a_name_in_a_link_stays_in_its_sentence_and_only_br_splits_lines(self):
        prose = ('Presented with the Bookshelf Residency, this is a salon-style installation of papercuts created by artist '
                 '<a href="/a">Sming Sming Books</a>, based in Bay Area, and shown in the second gallery for the season.')
        s = page(body='<main><p>' + prose + '<br>October 23 – November 28, 2026</p></main>')
        (_, text), = descriptions.candidates(s)
        self.assertIn('created by artist Sming Sming Books, based in Bay Area', text)
        self.assertNotIn('October', text)


class CandidatesTest(unittest.TestCase):
    def test_order_is_json_ld_then_share_then_meta_then_paragraphs(self):
        s = page(head=(
            '<meta name="description" content="meta text">'
            '<meta property="og:description" content="og text">'
            '<meta name="twitter:description" content="twitter text">'
            '<script type="application/ld+json">{"@type": "ExhibitionEvent", "description": "ld text"}</script>'),
            body='<main><p>' + BLURB + '</p></main>')
        self.assertEqual([c[0] for c in descriptions.candidates(s)], ['jsonld', 'og', 'twitter', 'meta', 'paragraph'])

    def test_json_ld_in_a_graph_or_a_list_is_found_and_bad_json_ignored(self):
        s = page(head=('<script type="application/ld+json">{"@graph": [{"@type": "WebSite", "description": "no"},'
                       '{"@type": ["Event", "Thing"], "description": "yes"}]}</script>'
                       '<script type="application/ld+json">{not json</script>'))
        self.assertEqual(descriptions.candidates(s), [('jsonld', 'yes')])

    def test_paragraphs_skip_navigation_footer_and_short_lines(self):
        s = page(body=('<nav><p>' + BLURB.replace('Josiah', 'Nav') + '</p></nav>'
                       '<main><p>Short.</p><p>' + BLURB + '</p>'
                       '<footer><p>' + BLURB.replace('Josiah', 'Foot') + '</p></footer></main>'))
        self.assertEqual(descriptions.candidates(s), [('paragraph', BLURB)])

    def test_two_short_paragraphs_are_joined(self):
        one = 'The exhibition brings together recent paintings and drawings by the artist, made over ten years.'
        two = 'It is the first survey of this work shown in the city and runs until the end of the year.'
        s = page(body=f'<main><p>{one}</p><p>{two}</p><p>{BLURB}</p></main>')
        self.assertEqual(descriptions.candidates(s), [('paragraph', one + ' ' + two)])


class FindEventDescriptionTest(unittest.TestCase):
    def test_takes_the_first_usable_candidate(self):
        s = page(head='<meta property="og:description" content="Welcome to the Gallery website, the home of art.">'
                      '<meta name="description" content="' + BLURB + '">')
        found = descriptions.find_event_description('https://gallery.example/x', NAME, fetch=lambda url: s)
        self.assertEqual(found, (BLURB, 'meta'))

    def test_nothing_usable_gives_none(self):
        s = page(body='<main><p>Short.</p></main>')
        self.assertIsNone(descriptions.find_event_description('https://gallery.example/x', NAME, fetch=lambda url: s))

    def test_failed_fetch_and_no_page_give_none(self):
        self.assertIsNone(descriptions.find_event_description('https://gallery.example/x', NAME, fetch=lambda url: None))
        self.assertIsNone(descriptions.find_event_description(None, NAME, fetch=lambda url: self.fail('fetched')))

    def test_proxied_sites_are_not_fetched(self):
        host = next(iter(utils.PROXY_DOMAINS))
        self.assertIsNone(descriptions.find_event_description(f'https://{host}/x', NAME,
                                                              fetch=lambda url: self.fail('fetched a proxied site')))

    def test_long_text_is_trimmed(self):
        long = BLURB + ' ' + 'More about the work and the ideas behind it, in many words. ' * 30
        s = page(head='<meta name="description" content="' + long + '">')
        text, _ = descriptions.find_event_description('https://gallery.example/x', NAME, fetch=lambda url: s)
        self.assertLessEqual(len(text), descriptions.MAX_CHARS)


class NeedsDescriptionTest(unittest.TestCase):
    def test_current_and_future_events_with_a_page_and_no_description(self):
        self.assertTrue(descriptions.needs_description(event(), TODAY))
        self.assertTrue(descriptions.needs_description(event(phase='future'), TODAY))

    def test_not_past_not_described_not_manual_not_without_a_page(self):
        self.assertFalse(descriptions.needs_description(event(phase='past'), TODAY))
        self.assertFalse(descriptions.needs_description(event(description='Already here.'), TODAY))
        self.assertFalse(descriptions.needs_description(event(source='manual'), TODAY))
        self.assertFalse(descriptions.needs_description(event(source='archive'), TODAY))
        self.assertFalse(descriptions.needs_description(event(links=[]), TODAY))

    def test_a_recent_check_is_not_repeated_but_an_old_one_is(self):
        self.assertFalse(descriptions.needs_description(event(description_checked='2026-11-10'), TODAY))
        self.assertTrue(descriptions.needs_description(event(description_checked='2026-10-01'), TODAY))
        self.assertTrue(descriptions.needs_description(event(description_checked='garbage'), TODAY))


class EnrichTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, 'la_events.json')
        self.saved = DB_FILES['la']
        DB_FILES['la'] = self.path                       # the real event files are never touched

    def tearDown(self):
        DB_FILES['la'] = self.saved
        self.dir.cleanup()

    def write(self, events):
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump({'Gallery': {e['name'] + '-Gallery': e for e in events}}, f)

    def read(self):
        with open(self.path, encoding='utf-8') as f:
            return json.load(f)['Gallery']

    def test_adds_a_description_marks_its_source_and_adds_subject_tags(self):
        self.write([event(NAME, 'https://g.example/a')])
        text = 'Josiah McElheny works in glass and photography, and this survey of his photography runs all year, in the main hall.'
        report = descriptions.enrich_missing_descriptions(['la'], today=TODAY, finder=lambda url, name: (text, 'meta'))
        stored = self.read()[NAME + '-Gallery']
        self.assertEqual(stored['description'], text)
        self.assertEqual(stored['description_source'], 'page')
        self.assertEqual(stored['description_checked'], '2026-11-13')
        self.assertIn('photography', stored['tags'])
        self.assertEqual(len(report['added']), 1)

    def test_nothing_found_records_the_check_and_no_description(self):
        self.write([event(NAME, 'https://g.example/a')])
        descriptions.enrich_missing_descriptions(['la'], today=TODAY, finder=lambda url, name: None)
        stored = self.read()[NAME + '-Gallery']
        self.assertEqual(stored['description'], '')
        self.assertEqual(stored['description_checked'], '2026-11-13')
        # looked at today, so the next run leaves it alone
        calls = []
        descriptions.enrich_missing_descriptions(['la'], today=TODAY, finder=lambda url, name: calls.append(url))
        self.assertEqual(calls, [])

    def test_the_same_text_for_several_shows_is_a_tagline_and_is_dropped(self):
        same = 'The Gallery presents contemporary art, and this Show is part of the program for the whole year ahead.'
        self.write([event('Show A', 'https://g.example/a'), event('Show B', 'https://g.example/b'),
                    event('Show C', 'https://g.example/c')])
        texts = {'https://g.example/a': same, 'https://g.example/b': same.upper(),
                 'https://g.example/c': 'Show C is a new group exhibition of sculpture by five artists from the city.'}
        report = descriptions.enrich_missing_descriptions(['la'], today=TODAY, finder=lambda url, name: (texts[url], 'og'))
        stored = self.read()
        self.assertEqual(stored['Show A-Gallery']['description'], '')
        self.assertEqual(stored['Show B-Gallery']['description'], '')
        self.assertTrue(stored['Show C-Gallery']['description'].startswith('Show C is a new group'))
        self.assertEqual(len(report['dropped']), 2)

    def test_a_text_already_used_by_another_show_at_the_venue_is_dropped(self):
        used = 'A long standing description that the venue already gives to one of the shows on its program.'
        self.write([event('Old', 'https://g.example/o', description=used), event('New', 'https://g.example/n')])
        report = descriptions.enrich_missing_descriptions(['la'], today=TODAY, finder=lambda url, name: (used, 'meta'))
        self.assertEqual(self.read()['New-Gallery']['description'], '')
        self.assertEqual(len(report['dropped']), 1)

    def test_shows_that_share_one_listing_page_are_skipped(self):
        self.write([event('Show A', 'https://g.example/list'), event('Show B', 'https://g.example/list')])
        calls = []
        report = descriptions.enrich_missing_descriptions(['la'], today=TODAY, finder=lambda url, name: calls.append(url))
        self.assertEqual(calls, [])
        self.assertEqual(report['shared'], 2)

    def test_the_page_limit_is_respected(self):
        self.write([event(f'Show {i}', f'https://g.example/{i}') for i in range(5)])
        calls = []
        descriptions.enrich_missing_descriptions(['la'], today=TODAY, max_pages=2,
                                                 finder=lambda url, name: calls.append(url))
        self.assertEqual(len(calls), 2)

    def test_dry_run_writes_nothing(self):
        self.write([event(NAME, 'https://g.example/a')])
        before = open(self.path, encoding='utf-8').read()
        descriptions.enrich_missing_descriptions(['la'], today=TODAY, save=False,
                                                 finder=lambda url, name: (BLURB, 'meta'))
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(f.read(), before)


class KeepFoundDescriptionTest(unittest.TestCase):
    STORED = {'description': 'Found on the page.', 'description_source': 'page', 'description_checked': '2026-11-10',
              'links': [{'link': 'https://g.example/a', 'description': 'Event Page'}]}

    def incoming(self, **extra):
        return {'name': 'X', 'description': None, 'links': [{'link': 'https://g.example/a', 'description': 'Event Page'}], **extra}

    def test_a_scraper_that_supplies_none_keeps_the_found_description(self):
        incoming = self.incoming()
        processing.keep_found_description(incoming, self.STORED)
        self.assertEqual(incoming['description'], 'Found on the page.')
        self.assertEqual(incoming['description_source'], 'page')
        self.assertEqual(incoming['description_checked'], '2026-11-10')

    def test_a_description_the_scraper_supplies_wins(self):
        incoming = self.incoming(description='From the listing.')
        processing.keep_found_description(incoming, self.STORED)
        self.assertEqual(incoming['description'], 'From the listing.')
        self.assertNotIn('description_source', incoming)

    def test_a_scraper_description_is_not_carried_over_as_if_it_were_found(self):
        stored = {'description': 'From the listing.', 'links': self.STORED['links']}   # no description_source
        incoming = self.incoming()
        processing.keep_found_description(incoming, stored)
        self.assertIsNone(incoming['description'])

    def test_the_checked_day_is_dropped_when_the_event_page_changed(self):
        incoming = self.incoming(links=[{'link': 'https://g.example/other', 'description': 'Event Page'}])
        processing.keep_found_description(incoming, {**self.STORED, 'description': None, 'description_source': None})
        self.assertNotIn('description_checked', incoming)

    def test_no_stored_event_changes_nothing(self):
        incoming = self.incoming()
        processing.keep_found_description(incoming, None)
        self.assertIsNone(incoming['description'])


if __name__ == '__main__':
    unittest.main()
