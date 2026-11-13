# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# Palo Alto Art Center (WEBSITE-117): each show's description is read off its page, leaving out the date line and
# the picture captions. The pages are trimmed copies of the real markup (2026-11-13); nothing touches the network.
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.sf import palo_alto_art_center as pa

TODAY = dt.date(2026, 11, 13)

CURRENT = '''<main id="main-content"><h1>Live the Moment Light</h1>
<p>September 19-December 13, 2026</p>
<p>Live the moment light brings together the work of Soleé Darrell, Terri Friedman, Corita Kent, and Angelica Trimble-Yanu, exploring the enduring influence of Corita Kent's approach to making.</p>
<p>Corita Kent, live the moment light, 1977, serigraph, 16 x 11-1/2 in., Courtesy of Corita Art Center, Los Angeles, corita.org</p>
<p>The exhibition takes its title from Corita Kent's 1977 serigraph. Created during a period of reflection and renewal in the artist's late career.</p>
<h2>Live the moment light Associated Programs</h2><p>Join us for a family day with workshops for all ages.</p></main>'''

UPCOMING = '''<main id="main-content"><h1>Upcoming Exhibitions</h1>
<p>This year the Palo Alto Art Center presents our Year of Legacy, highlighting our 55th anniversary and its role as a community resource.</p>
<h2>Big Feelings: Figures and Faces in Nathan Oliveira, Lynn Hershman Leeson, Gregory Rick, and Koak</h2>
<h3>January 23-April 11, 2027</h3>
<p>Left image: Nathan Oliveira, Profile, 2010, oil on canvas, 66 x 50 in., Courtesy of Oliveira Art LLC</p>
<p>36 x 28 inches, Courtesy of Oliveira Art LLC</p>
<p>Nathan Oliveira, one of the central figures of the Bay Area Figurative movement and an integral member of the Palo Alto artistic community, is best known for his abstracted figures placed in ambiguous voids.</p>
<p>Big Feelings explores the intentionality and impact of Oliveira's use of figuration as an expression of his state of mind.</p>
<h2>Another Show</h2><h3>June 1-August 30, 2027</h3><p>A second show's own text that is long enough to be a description of it.</p></main>'''


def run(pages):
    stored = []

    def fetch(url, *args, **kwargs):
        for key, html in pages.items():
            if url.endswith('/' + key):
                return BeautifulSoup(html, 'html.parser')
        return None

    with mock.patch.object(pa, 'fetch_and_parse', side_effect=fetch), \
            mock.patch.object(pa, 'region_today', return_value=TODAY), \
            mock.patch.object(pa, 'process_event', side_effect=lambda d, r: stored.append(d)):
        pa.scrape_palo_alto_art_center(env='prod')
    return {e['name']: e for e in stored}


class DescriptionTest(unittest.TestCase):
    def test_the_current_shows_description_skips_the_date_line_and_the_caption(self):
        shows = run({'Current-Exhibition': CURRENT})
        text = shows['Live the Moment Light']['description']
        self.assertTrue(text.startswith('Live the moment light brings together the work of Soleé Darrell'))
        self.assertNotIn('September 19', text)
        self.assertNotIn('Courtesy of', text)
        self.assertNotIn('Associated Programs', text)
        self.assertNotIn('family day', text)                    # that is the next section's

    def test_an_upcoming_shows_description_skips_captions_and_the_pages_banner_and_stops_at_the_next_show(self):
        shows = run({'Upcoming': UPCOMING})
        big = shows['Big Feelings: Figures and Faces in Nathan Oliveira, Lynn Hershman Leeson, Gregory Rick, and Koak']
        self.assertTrue(big['description'].startswith('Nathan Oliveira, one of the central figures'))
        self.assertNotIn('Year of Legacy', big['description'])
        self.assertNotIn('Courtesy of', big['description'])
        self.assertNotIn('second show', big['description'])
        self.assertTrue(shows['Another Show']['description'].startswith("A second show's own text"))

    def test_a_show_with_no_text_has_no_description_and_a_long_text_is_cut_at_a_sentence(self):
        page = '<main id="main-content"><h1>Plain Show</h1><p>September 19-December 13, 2026</p></main>'
        self.assertIsNone(run({'Current-Exhibition': page})['Plain Show']['description'])
        sentences = ' '.join(f'This is sentence number {i} of a very long description of the show.' for i in range(30))
        long_page = f'<main id="main-content"><h1>Long Show</h1><p>September 19-December 13, 2026</p><p>{sentences}</p></main>'
        text = run({'Current-Exhibition': long_page})['Long Show']['description']
        self.assertLessEqual(len(text), 500)
        self.assertTrue(text.endswith('show.'))


if __name__ == '__main__':
    unittest.main()
