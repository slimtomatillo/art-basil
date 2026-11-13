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
import unittest.mock

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


class ProgramsCreditsAndTaglinesTest(unittest.TestCase):
    """Real texts found on listing-card pages (WEBSITE-117) that were not descriptions of the show."""

    def test_a_program_announcement_is_not_the_exhibitions_description(self):
        self.assertFalse(descriptions.usable(
            'IN PERSON RSVP Exhibition co-curator Amy Landau and Paul Connor, director of video experience for Mountain Spirits, '
            'will lead a gallery walk-through of this exhibition and discuss the research.', 'Mountain Spirits: Rice and Indigeneity'))
        self.assertFalse(descriptions.usable(
            'ONLINE RSVP Guest curators Tangimoe Clay and Gina Tawhai Matchitt will discuss the historic kaitaka in the Fowler '
            'collection and Ancestral Gifts.', 'Uhengaparaoa, Taonga Tuku Iho: Ancestral Gifts'))

    def test_a_talk_about_the_show_is_not_the_shows_description(self):
        self.assertFalse(descriptions.usable(
            'This behind-the-scenes conversation explores the digital production of Mountain Spirits: Rice and Indigeneity, an exhibition at the Fowler.',
            'Mountain Spirits: Rice and Indigeneity in the Northern Luzon Highlands'))
        self.assertTrue(descriptions.usable(
            'This exhibition explores rice and Indigeneity in the Northern Luzon Highlands through objects, video and landscape, in Mountain Spirits.',
            'Mountain Spirits: Rice and Indigeneity in the Northern Luzon Highlands'))

    def test_an_invitation_or_a_program_is_not_the_shows_description(self):
        self.assertFalse(descriptions.usable(
            'Join us on November 26th to celebrate the opening reception of Terry’s Pipe, solo exhibition of new work by Ken Nicol.', 'Ken Nicol: Terry’s Pipe'))
        self.assertFalse(descriptions.usable(
            'IN CONVERSATION: Meaghan Hyckie & Luke Painter Location: Olga Korper Gallery Join us for an engaging conversation between artists', 'Meaghan Hyckie: Haunts'))
        self.assertTrue(descriptions.usable(
            'Haunts is an installation of new sculpture by Meaghan Hyckie, made over two years in her studio in Toronto.', 'Meaghan Hyckie: Haunts'))

    def test_a_title_dates_and_location_run_together_is_not_a_description(self):
        for text, name in (
                ('Yellow Marquee July 1, 2026 – July 1, 2029 18th Street Arts Center A small yellow awning appears to have slipped from the wall',
                 'Hilla Toony Navok: Yellow Marquee'),
                ('Rhizome’s Solar Server November 15, 2025 – ongoing 18th Street Arts Center is excited to partner with Rhizome on the launch',
                 'Rhizome’s Solar Server'),
                ('Ghost Agency: Smooth Criminal March 1, 2027 – March 31, 2028 Hearth Gallery -18th Street Arts Center Smooth Criminal reimagines public sculpture',
                 'Ghost Agency: Smooth Criminal')):
            self.assertFalse(descriptions.usable(text, name), text)

    def test_a_photo_credit_sentence_is_cut_from_the_front(self):
        text = ('Francis and Anthony Almendárez, Production still from Navigating the Archives Within, 2026. Courtesy of the artists. '
                'In their ongoing film and performance work, the brothers revisit family archives.')
        self.assertEqual(descriptions.strip_opening_furniture(text),
                         'In their ongoing film and performance work, the brothers revisit family archives.')

    def test_a_gallery_describing_itself_is_not_a_description_of_the_show(self):
        tagline = ('Roberts Projects is Los Angeles-based contemporary art gallery representing artists across multiple generations of '
                   'internationally recognized, established artists as well as emerging artists including Wendy Red Star and Betye Saar')
        self.assertFalse(descriptions.usable(tagline, 'Wendy Red Star: False Stars'))
        self.assertFalse(descriptions.usable('The Hammer is a public museum of contemporary art and Michelle Stuart is among the artists shown there.',
                                             'Michelle Stuart: The Memory of Paper'))
        # a show that is described, even at a gallery, is fine
        self.assertTrue(descriptions.usable('Roberts Projects is pleased to present Wherever You Are, Remember Me, an exhibition of new works by Collins Obijiaku.',
                                            'Collins Obijiaku: Wherever You Are, Remember Me'))
        self.assertTrue(descriptions.usable('Haunts is an installation of new sculpture by Meaghan Hyckie, shown in the main gallery space.',
                                            'Meaghan Hyckie: Haunts'))


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


class WiderParagraphSearchTest(unittest.TestCase):
    """The Image Centre's pages: an <article> that is not where the text is, and the exhibition text inside a <header>."""
    PROSE = ('For nearly half a century, celebrated American photographer Richard Avedon confronted one of portraiture\'s '
             'enduring taboos: aging. He revealed the marks of time on his subjects\' faces with unsparing clarity.')

    def test_text_in_a_header_block_outside_the_article_is_found_when_the_article_has_none(self):
        s = page(body=('<header><div><p>September 9–December 5, 2026 South Gallery & North Gallery Curator: Paul Roth</p>'
                       f'<p>{self.PROSE}</p></div></header><article><p>Short.</p></article>'))
        self.assertEqual(descriptions.candidates(s), [('paragraph', self.PROSE)])

    def test_a_site_header_with_a_menu_is_still_left_out(self):
        site = BLURB.replace('Josiah', 'Gallery')
        s = page(body=f'<header><nav><a href="/">Home</a></nav><p>{site}</p></header><article><p>Short.</p></article>')
        self.assertEqual(descriptions.candidates(s), [])

    def test_the_strict_pass_still_comes_first(self):
        s = page(body=f'<header><p>{self.PROSE}</p></header><main><p>{BLURB}</p></main>')
        self.assertEqual(descriptions.candidates(s), [('paragraph', BLURB)])


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


class FeedDescriptionTest(unittest.TestCase):
    """Text a venue's own feed or API supplies (CAAM's markdown, Daniel Faria's HTML): WEBSITE-119."""
    FIRST = ('*How to Fly* is a site-specific photomural by visual artist Sadie Barnette installed in CAAM\u2019s atrium. Born and '
             'raised in Oakland, California, Barnette incorporates photographs she has taken of the places around her.')

    def test_markdown_becomes_plain_prose_and_a_bold_header_line_is_left_out(self):
        text = descriptions.feed_description(self.FIRST + '\n\n**Presented at Art + Practice**')
        self.assertTrue(text.startswith('How to Fly is a site-specific photomural by visual artist Sadie Barnette'))
        self.assertNotIn('*', text)
        self.assertNotIn('Art + Practice', text)

    def test_stray_tags_in_markdown_text_do_not_make_it_html(self):
        # CAAM's text has a leftover </iframe> (an embedded video) and <A HREF> links, which once made it read as HTML
        text = descriptions.feed_description(
            self.FIRST + ' See <A HREF="https://example.org/work">the artist\u2019s site</A> for more.</iframe>\n\nA second paragraph about the work.')
        self.assertTrue(text.startswith('How to Fly is a site-specific photomural'))
        self.assertNotIn('<', text)
        self.assertIn('the artist\u2019s site', text)

    def test_markdown_links_keep_their_label_and_br_makes_a_new_paragraph(self):
        text = descriptions.feed_description('See [the exhibition guide](https://example.org/guide) for the show Nocturne by the artist, '
                                             'a series of drawings made in the dark over a year.<br>Opening reception: Friday, October 30')
        self.assertTrue(text.startswith('See the exhibition guide for the show Nocturne'))
        self.assertNotIn('Opening reception', text)

    def test_html_text_takes_its_first_paragraphs_and_cuts_to_a_length(self):
        html = ('<div>\n<div>\n<p><span class="font-avenir">Daniel Faria Gallery is pleased to present <em>I is Another</em>, '
                'Chris Curreri\u2019s sixth solo exhibition with the gallery.</span></p>\n'
                '<p><span>First presented at the Counterpublic Triennial in St. Louis, the work brings together sculpture and video.</span></p>'
                '<p>' + 'A third paragraph that goes on about the work and the ideas behind it, in many words. ' * 12 + '</p></div></div>')
        text = descriptions.feed_description(html)
        self.assertTrue(text.startswith('Daniel Faria Gallery is pleased to present I is Another, Chris Curreri'))
        self.assertIn('Counterpublic Triennial', text)
        self.assertNotIn('A third paragraph', text)                    # two paragraphs are enough
        self.assertNotIn('<', text)
        self.assertLessEqual(len(text), descriptions.MAX_CHARS)

    def test_nothing_usable_gives_none(self):
        for text in (None, '', '   ', 42, '<p>Opening reception November 12.</p>', 'Short.', '**Presented at Art + Practice**'):
            self.assertIsNone(descriptions.feed_description(text), text)


class SiteExtractorAndCaptionTest(unittest.TestCase):
    """AGO's text is in none of the usual places; the Cantor puts a caption paragraph before the text."""
    AGO_TEXT = ('Spotlighting the power of Black style, Sunday Best traces the histories of migration, activism and joy '
                'through fashion, photography and film, from the church pew to the runway, over many decades.')

    def ago_page(self, body_text=None, heading='About the Exhibition'):
        return page(body=(
            '<div class="node__content"><div class="field--name-body"></div></div>'
            '<div class="postcard-desc"><div class="field field--name-body">Enjoy early access to select exhibitions*, special '
            'events, exclusive perks, and more. Find the Membership level that is right for you and enjoy benefits as a '
            'valued supporter of the AGO.</div></div>'
            f'<div class="node__content"><div class="field field--name-body"><h2>{heading}</h2>{body_text or self.AGO_TEXT}</div></div>'
            '<div class="node__content"><div class="field--name-body">Bloomberg Connects Discover behind-the-scenes stories of the exhibition.</div></div>'))

    def test_the_ago_exhibition_block_is_found_and_the_membership_promo_and_heading_are_left_out(self):
        got = descriptions.candidates(self.ago_page(), 'https://ago.ca/exhibitions/sunday-best-power-glory-black-style')
        self.assertEqual(got, [('site', self.AGO_TEXT)])

    def test_only_ago_pages_use_that_rule(self):
        self.assertEqual([c for c in descriptions.candidates(self.ago_page(), 'https://gallery.example/x') if c[0] == 'site'], [])
        self.assertEqual([c for c in descriptions.candidates(self.ago_page()) if c[0] == 'site'], [])

    def test_the_ago_text_is_used_when_it_is_about_the_show(self):
        fetch = lambda url: self.ago_page()
        found = descriptions.find_event_description('https://ago.ca/exhibitions/sunday-best', 'Sunday Best: The Power & The Glory of Black Style',
                                                    fetch=fetch, allow_proxy=True)
        self.assertEqual(found, (self.AGO_TEXT, 'site'))

    def test_a_paragraph_in_a_caption_container_is_skipped(self):
        caption = ('Ruth Asawa with life masks on the exterior wall of her house. Photography by Terry Schmitt. Untitled, '
                   'c. 1966 to 2000, collection of the museum and shown here for the first time in the galleries.')
        real = ('The Cantor Arts Center at Stanford University acquired this work in 2020. These 233 masks, which originally hung '
                'on the exterior wall of the artist\'s home, are shown together here.')
        s = page(body=(f'<main><div class="image__field-caption"><p>{caption}</p></div>'
                       f'<div class="text-section__field-body"><p>{real}</p></div></main>'))
        self.assertEqual(descriptions.candidates(s), [('paragraph', real)])


class ProxiedPagesTest(unittest.TestCase):
    """Paid-proxy pages (WEBSITE-118): a few a run, cheapest first, last, and never past the credits."""
    CHEAP, DEAR = 'https://cheap.example/', 'https://dear.example/'

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, 'la_events.json')
        self.saved = DB_FILES['la']
        DB_FILES['la'] = self.path
        patcher = unittest.mock.patch.dict(utils.PROXY_DOMAINS, {'cheap.example': {'premium_proxy': 'true'},
                                                                'dear.example': {'premium_proxy': 'true', 'js_render': 'true'}})
        patcher.start()
        self.addCleanup(patcher.stop)
        flag = unittest.mock.patch.object(utils, 'PROXY_EXHAUSTED', False)
        flag.start()
        self.addCleanup(flag.stop)

    def tearDown(self):
        DB_FILES['la'] = self.saved
        self.dir.cleanup()

    def write(self, events, venue='Gallery'):
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump({venue: {e['name'] + '-' + venue: e for e in events}}, f)

    def read(self, venue='Gallery'):
        with open(self.path, encoding='utf-8') as f:
            return json.load(f)[venue]

    def test_credits_follow_the_domains_settings(self):
        self.assertEqual(descriptions.proxy_credits(self.CHEAP + 'x'), 10)
        self.assertEqual(descriptions.proxy_credits(self.DEAR + 'x'), 25)
        self.assertEqual(descriptions.proxy_credits('https://not-proxied.example/x'), 10)

    def test_a_proxied_page_is_not_fetched_unless_asked(self):
        self.assertIsNone(descriptions.find_event_description(self.DEAR + 'x', NAME, fetch=lambda url: self.fail('fetched')))
        s = page(head='<meta name="description" content="' + BLURB + '">')
        self.assertEqual(descriptions.find_event_description(self.DEAR + 'x', NAME, fetch=lambda url: s, allow_proxy=True), (BLURB, 'meta'))

    def test_the_ordinary_finder_never_sees_a_proxied_event(self):
        self.write([event(NAME, self.DEAR + 'a')])
        report = descriptions.enrich_missing_descriptions(['la'], today=TODAY, proxy_pages=0,
                                                          finder=lambda url, name: self.fail('the ordinary finder was used'),
                                                          proxy_finder=lambda url, name: self.fail('proxy pages are switched off'))
        self.assertEqual((report['proxied'], report['credits']), (0, 0))
        self.assertNotIn('description_proxy_checked', self.read()[NAME + '-Gallery'])

    def test_only_a_few_pages_a_run_cheapest_first_and_the_rest_wait_for_the_next_run(self):
        names = [f'Show {i}' for i in range(5)]
        events = [event(n, (self.DEAR if i < 3 else self.CHEAP) + str(i)) for i, n in enumerate(names)]     # 0-2 dear, 3-4 cheap
        self.write(events)
        order = []

        def proxy_finder(url, name):
            order.append(url)
            return (f'{name} is a show of paintings and drawings made over many years by one artist, shown in the main gallery.', 'og')

        report = descriptions.enrich_missing_descriptions(['la'], today=TODAY, proxy_pages=3, finder=lambda u, n: self.fail('x'),
                                                          proxy_finder=proxy_finder)
        self.assertEqual(order, [self.CHEAP + '3', self.CHEAP + '4', self.DEAR + '0'])                    # cheap first, then dear, by name
        self.assertEqual((report['proxied'], report['credits']), (3, 10 + 10 + 25))
        stored = self.read()
        self.assertEqual([stored[n + '-Gallery']['description'] != '' for n in names], [True, False, False, True, True])
        self.assertNotIn('description_proxy_checked', stored['Show 1-Gallery'])                          # not asked yet: next run
        self.assertEqual(stored['Show 0-Gallery']['description_proxy_checked'], '2026-11-13')

    def test_nothing_found_is_remembered_so_it_is_not_paid_for_again_for_a_while(self):
        self.write([event(NAME, self.DEAR + 'a')])
        descriptions.enrich_missing_descriptions(['la'], today=TODAY, proxy_finder=lambda url, name: None)
        self.assertEqual(self.read()[NAME + '-Gallery']['description_proxy_checked'], '2026-11-13')
        calls = []
        descriptions.enrich_missing_descriptions(['la'], today=TODAY, proxy_finder=lambda url, name: calls.append(url))
        self.assertEqual(calls, [])

    def test_when_the_account_runs_out_of_credits_it_stops_and_asks_again_next_run(self):
        self.write([event('Show A', self.DEAR + 'a'), event('Show B', self.DEAR + 'b')])
        calls = []

        def proxy_finder(url, name):
            calls.append(url)
            utils.PROXY_EXHAUSTED = True                     # what utils.fetch_and_parse does on the first 402
            return None

        report = descriptions.enrich_missing_descriptions(['la'], today=TODAY, proxy_pages=4, proxy_finder=proxy_finder)
        self.assertEqual(len(calls), 1)                      # the second page was never asked for
        self.assertEqual(report['proxied'], 1)
        stored = self.read()
        self.assertNotIn('description_proxy_checked', stored['Show A-Gallery'])      # out of credits is not "nothing there"
        self.assertNotIn('description_proxy_checked', stored['Show B-Gallery'])

    def test_a_page_that_could_not_be_fetched_is_not_stamped_and_two_in_a_row_stop_the_pass(self):
        self.write([event(f'Show {i}', self.CHEAP + str(i)) for i in range(4)])
        asked = []

        def proxy_finder(url, name):
            asked.append(url)
            return descriptions.FETCH_FAILED

        report = descriptions.enrich_missing_descriptions(['la'], today=TODAY, proxy_pages=4, proxy_finder=proxy_finder)
        self.assertEqual(len(asked), 2)                                         # stopped after two in a row
        self.assertEqual((report['proxied'], report['failed'], report['credits']), (2, 2, 20))
        self.assertTrue(all('description_proxy_checked' not in e for e in self.read().values()))   # all asked for again next run

    def test_one_failure_among_successes_does_not_stop_the_pass(self):
        self.write([event(f'Show {i}', self.CHEAP + str(i)) for i in range(3)])
        answers = iter([descriptions.FETCH_FAILED, None, None])
        report = descriptions.enrich_missing_descriptions(['la'], today=TODAY, proxy_pages=4, proxy_finder=lambda u, n: next(answers))
        self.assertEqual((report['proxied'], report['failed']), (3, 1))
        stamped = sorted(n for n, e in self.read().items() if e.get('description_proxy_checked'))
        self.assertEqual(stamped, ['Show 1-Gallery', 'Show 2-Gallery'])         # the failed one (Show 0) is not stamped

    def test_find_proxied_description_tells_a_failed_fetch_from_a_page_with_nothing(self):
        with unittest.mock.patch.object(descriptions, 'fetch_and_parse', return_value=None):
            self.assertIs(descriptions.find_proxied_description(self.DEAR + 'a', NAME), descriptions.FETCH_FAILED)
        with unittest.mock.patch.object(descriptions, 'fetch_and_parse', return_value=page(body='<main><p>Short.</p></main>')):
            self.assertIsNone(descriptions.find_proxied_description(self.DEAR + 'a', NAME))
        good = page(head='<meta name="description" content="' + BLURB + '">')
        with unittest.mock.patch.object(descriptions, 'fetch_and_parse', return_value=good):
            self.assertEqual(descriptions.find_proxied_description(self.DEAR + 'a', NAME), (BLURB, 'meta'))

    def test_a_stamp_left_by_the_old_pass_does_not_hide_a_proxied_event(self):
        # before WEBSITE-118 the pass stamped proxied events "checked" without fetching anything
        self.write([event(NAME, self.DEAR + 'a', description_checked='2026-11-13')])
        asked = []
        descriptions.enrich_missing_descriptions(['la'], today=TODAY, proxy_finder=lambda url, name: asked.append(url))
        self.assertEqual(asked, [self.DEAR + 'a'])
        # ...while the same stamp on an ordinary page still counts
        self.assertFalse(descriptions.needs_description(event(NAME, 'https://g.example/a', description_checked='2026-11-13'), TODAY))
        self.assertEqual((descriptions.stamp_key(self.DEAR + 'a'), descriptions.stamp_key('https://g.example/a')),
                         ('description_proxy_checked', 'description_checked'))

    def test_a_host_with_no_text_in_its_pages_is_never_paid_for(self):
        with unittest.mock.patch.dict(utils.PROXY_DOMAINS, {'galeriesimonblais.com': {'premium_proxy': 'true'}}):
            self.write([event(NAME, 'https://galeriesimonblais.com/en/expos/x')])
            report = descriptions.enrich_missing_descriptions(['la'], today=TODAY, proxy_finder=lambda u, n: self.fail('paid for it'))
        self.assertEqual((report['proxied'], report['credits']), (0, 0))

    def test_proxied_events_on_a_listing_that_several_shows_share_are_not_looked_up(self):
        self.write([event('Show A', self.DEAR + 'list'), event('Show B', self.DEAR + 'list')])
        report = descriptions.enrich_missing_descriptions(['la'], today=TODAY, proxy_finder=lambda u, n: self.fail('x'),
                                                          card_finder=lambda page, titles: ({}, 0))
        self.assertEqual(report['proxied'], 0)

    def test_what_a_proxied_page_gives_goes_through_the_same_checks_as_any_other(self):
        same = 'The Gallery presents contemporary art and this show is part of the program for the whole year ahead of us.'
        self.write([event('Show A', self.DEAR + 'a'), event('Show B', self.DEAR + 'b')])
        report = descriptions.enrich_missing_descriptions(['la'], today=TODAY, proxy_finder=lambda url, name: (same, 'og'))
        self.assertEqual(len(report['dropped']), 2)                            # one tagline for two shows is dropped
        self.assertEqual([e['description'] for e in self.read().values()], ['', ''])

    def test_the_command_line_dry_run_does_not_touch_the_proxy_unless_asked(self):
        # enrich_missing_descriptions is replaced, so this reads no event file and opens no page
        empty = {'checked': 0, 'added': [], 'dropped': [], 'shared': 0, 'proxied': 0, 'credits': 0, 'failed': 0}
        with unittest.mock.patch.object(descriptions, 'enrich_missing_descriptions', return_value=empty) as enrich:
            descriptions.main(['la'])
            self.assertEqual(enrich.call_args.kwargs['proxy_pages'], 0)
            self.assertEqual(enrich.call_args.args[0], ['la'])
            self.assertFalse(enrich.call_args.kwargs['save'])
            descriptions.main(['--proxy', 'la'])
            self.assertEqual(enrich.call_args.kwargs['proxy_pages'], descriptions.PROXY_PAGES_PER_RUN)
            self.assertEqual(enrich.call_args.args[0], ['la'])


class FindCardDescriptionsTest(unittest.TestCase):
    LISTING = 'https://gallery.example/exhibitions/'
    TITLES = ['Island Universe', 'Mobile Images', 'Other Show']

    def pages(self):
        listing = page(body=('<div><a href="/exhibitions/island-universe/"><h3>Island Universe</h3></a></div>'
                             '<div><a href="/exhibitions/mobile-images/"><h3>Mobile Images</h3></a></div>'
                             '<div><h3>Other Show</h3></div>'))
        return {
            self.LISTING: listing,
            'https://gallery.example/exhibitions/island-universe/':
                page(head='<meta name="description" content="' + BLURB + '">'),
            'https://gallery.example/exhibitions/mobile-images/':
                page(head='<meta name="description" content="Welcome to the Gallery website, the home of art.">'),
        }

    def test_each_shows_own_page_is_found_from_its_card_and_read(self):
        pages = self.pages()
        opened = []

        def fetch(url):
            opened.append(url)
            return pages.get(url)

        found, count = descriptions.find_card_descriptions(self.LISTING, self.TITLES, fetch=fetch)
        self.assertEqual(found, {'Island Universe': (BLURB, 'meta')})        # the other page had only a site tagline
        self.assertEqual(count, 3)                                           # the listing and the two show pages it linked to
        self.assertEqual(opened[0], self.LISTING)

    def test_a_listing_that_cannot_be_fetched_or_is_proxied_gives_nothing(self):
        self.assertEqual(descriptions.find_card_descriptions(self.LISTING, self.TITLES, fetch=lambda url: None), ({}, 1))
        host = next(iter(utils.PROXY_DOMAINS))
        self.assertEqual(descriptions.find_card_descriptions(f'https://{host}/x', self.TITLES,
                                                             fetch=lambda url: self.fail('fetched')), ({}, 0))
        self.assertEqual(descriptions.find_card_descriptions(None, self.TITLES, fetch=lambda url: self.fail('fetched')), ({}, 0))


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

    def test_shows_on_a_shared_listing_page_are_looked_up_together_through_their_cards(self):
        past = event('Old Show', 'https://g.example/list', phase='past')
        self.write([event('Show A', 'https://g.example/list'), event('Show B', 'https://g.example/list'), past])
        seen = []

        def card_finder(page, titles):
            seen.append((page, sorted(titles)))
            return {'Show A': (BLURB.replace('Josiah', 'Show A'), 'meta')}, 3

        calls = []
        report = descriptions.enrich_missing_descriptions(['la'], today=TODAY, card_finder=card_finder,
                                                          finder=lambda url, name: calls.append(url))
        self.assertEqual(seen, [('https://g.example/list', ['Old Show', 'Show A', 'Show B'])])   # every show on the page, past too
        self.assertEqual(calls, [])                                                              # not looked up one by one
        stored = self.read()
        self.assertTrue(stored['Show A-Gallery']['description'].startswith('Show A'))
        self.assertEqual(stored['Show A-Gallery']['description_source'], 'page')
        self.assertEqual(stored['Show B-Gallery']['description'], '')                            # its card gave nothing
        self.assertEqual(stored['Show B-Gallery']['description_checked'], '2026-11-13')          # and is not asked again today
        self.assertNotIn('description_checked', stored['Old Show-Gallery'])                      # a past show is left alone
        self.assertEqual(report['shared'], 2)
        self.assertEqual(report['checked'], 3)                                                   # the listing and two show pages
        # the stored Event Page link is untouched: only the description came from the show's own page
        self.assertEqual(stored['Show A-Gallery']['links'], [{'link': 'https://g.example/list', 'description': 'Event Page'}])

    def test_a_shared_listing_with_nothing_to_look_up_is_not_opened(self):
        self.write([event('Show A', 'https://g.example/list', description='Has one already.'),
                    event('Show B', 'https://g.example/list', description='So has this one.')])
        descriptions.enrich_missing_descriptions(['la'], today=TODAY, finder=lambda url, name: self.fail('opened a page'),
                                                 card_finder=lambda page, titles: self.fail('opened a listing'))

    def test_the_same_text_found_for_two_shows_of_a_listing_is_dropped(self):
        same = 'This gallery presents contemporary art and this Show is part of the program for the year.'
        self.write([event('Show A', 'https://g.example/list'), event('Show B', 'https://g.example/list')])
        report = descriptions.enrich_missing_descriptions(
            ['la'], today=TODAY, card_finder=lambda page, titles: ({'Show A': (same, 'og'), 'Show B': (same, 'og')}, 3))
        self.assertEqual([e['description'] for e in self.read().values()], ['', ''])
        self.assertEqual(len(report['dropped']), 2)

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

    def test_the_proxy_stamp_is_carried_over_like_the_other_one(self):
        stored = {**self.STORED, 'description': None, 'description_source': None, 'description_proxy_checked': '2026-11-12'}
        incoming = self.incoming()
        processing.keep_found_description(incoming, stored)
        self.assertEqual(incoming['description_proxy_checked'], '2026-11-12')
        other = self.incoming(links=[{'link': 'https://g.example/other', 'description': 'Event Page'}])
        processing.keep_found_description(other, stored)
        self.assertNotIn('description_proxy_checked', other)

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
