# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# images.link_in_card / card_links (WEBSITE-117): the link to a show's own page, found in the card that holds its
# title on a listing page. A wrong link would be shown to visitors as the show's "Event Page", so these tests are
# mostly about what must NOT be returned. Pages are fake HTML; nothing touches the network.
import os
import sys
import unittest

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import images

LISTING = 'https://gallery.example/exhibitions/'
TITLES = ['Sable Elyse Smith: Sky Fence Ground', 'Mavis Pusey: Mobile Images', 'Carl Cheng']


def soup(body):
    return BeautifulSoup(f'<html><body>{body}</body></html>', 'html.parser')


def link(html, title=TITLES[0], titles=TITLES, listing=LISTING):
    return images.link_in_card(images.PageText(soup(html)), title, listing, titles)


class PlausiblePageLinkTest(unittest.TestCase):
    def test_accepts_another_page_on_the_same_site(self):
        self.assertTrue(images.plausible_page_link('https://gallery.example/exhibitions/sable-smith/', LISTING))
        self.assertTrue(images.plausible_page_link('https://www.gallery.example/exhibitions/x', LISTING))       # www. is not another site
        self.assertTrue(images.plausible_page_link('https://gallery.example/exhibitions/?show=12', LISTING))    # only the query differs

    def test_rejects_the_listing_itself_other_sites_files_and_non_web_links(self):
        for url in ('https://gallery.example/exhibitions', LISTING, 'https://gallery.example/exhibitions/#top',
                    'https://instagram.com/gallery', 'https://other.example/exhibitions/x',
                    'https://gallery.example/files/press.pdf', 'https://gallery.example/img/a.JPG?w=2',
                    'mailto:hi@gallery.example', 'javascript:void(0)'):
            self.assertFalse(images.plausible_page_link(url.split('#')[0] if url.startswith('http') else url, LISTING), url)


class LinkInCardTest(unittest.TestCase):
    def test_a_link_around_the_title_is_the_shows_page(self):
        html = ('<div class="card"><a href="/exhibitions/sable-smith/"><h3>Sable Elyse Smith: Sky Fence Ground</h3></a></div>'
                '<div class="card"><a href="/exhibitions/pusey/"><h3>Mavis Pusey: Mobile Images</h3></a></div>')
        self.assertEqual(link(html), 'https://gallery.example/exhibitions/sable-smith/')
        self.assertEqual(link(html, TITLES[1]), 'https://gallery.example/exhibitions/pusey/')

    def test_a_card_whose_link_text_or_address_uses_a_word_of_the_title(self):
        html = ('<div class="card"><h3>Sable Elyse Smith: Sky Fence Ground</h3><a href="/about/">About us</a>'
                '<a href="/exhibitions/sable-elyse-smith-sky-fence-ground/">Read more</a></div>'
                '<div class="card"><h3>Mavis Pusey: Mobile Images</h3><a href="/exhibitions/mp/">View Mobile Images</a></div>')
        self.assertEqual(link(html), 'https://gallery.example/exhibitions/sable-elyse-smith-sky-fence-ground/')
        self.assertEqual(link(html, TITLES[1]), 'https://gallery.example/exhibitions/mp/')

    def test_the_only_link_in_a_card_is_taken_but_two_different_unrelated_ones_are_not(self):
        one = '<div><h3>Carl Cheng</h3><a href="/e/4821">More</a></div><div><h3>Mavis Pusey: Mobile Images</h3></div>'
        self.assertEqual(link(one, 'Carl Cheng'), 'https://gallery.example/e/4821')
        two = ('<div><h3>Carl Cheng</h3><a href="/e/4821">More</a><a href="/press/">Press</a></div>'
               '<div><h3>Mavis Pusey: Mobile Images</h3></div>')
        self.assertIsNone(link(two, 'Carl Cheng'))

    def test_the_listing_other_sites_and_social_links_are_never_the_shows_page(self):
        html = ('<div><h3>Carl Cheng</h3><a href="/exhibitions/">All exhibitions</a>'
                '<a href="https://instagram.com/carl">Instagram</a><a href="/files/carl.pdf">Press release</a></div>'
                '<div><h3>Mavis Pusey: Mobile Images</h3></div>')
        self.assertIsNone(link(html, 'Carl Cheng'))

    def test_it_does_not_climb_into_the_next_shows_card(self):
        # the first show has no link of its own; the link belongs to the second show
        html = ('<section><h3>Carl Cheng</h3><h3>Mavis Pusey: Mobile Images</h3>'
                '<a href="/exhibitions/pusey/">Mobile Images</a></section>')
        self.assertIsNone(link(html, 'Carl Cheng'))

    def test_a_title_the_page_does_not_show_has_no_link(self):
        self.assertIsNone(link('<div><h3>Something else</h3><a href="/x/">x</a></div>'))

    def test_a_title_split_over_tags_is_found(self):
        html = ('<div><a href="/exhibitions/sable/"><h3>Sable Elyse Smith:<br><em>Sky Fence Ground</em></h3></a></div>'
                '<div><h3>Carl Cheng</h3></div>')
        self.assertEqual(link(html), 'https://gallery.example/exhibitions/sable/')

    def test_relative_links_and_fragments_are_made_absolute_and_tidy(self):
        html = '<div><a href="sable/#top"><h3>Sable Elyse Smith: Sky Fence Ground</h3></a></div><div><h3>Carl Cheng</h3></div>'
        self.assertEqual(link(html), 'https://gallery.example/exhibitions/sable/')


class CardLinksTest(unittest.TestCase):
    def test_returns_each_shows_own_link(self):
        html = ('<div><a href="/s/sable/"><h3>Sable Elyse Smith: Sky Fence Ground</h3></a></div>'
                '<div><a href="/s/pusey/"><h3>Mavis Pusey: Mobile Images</h3></a></div><div><h3>Carl Cheng</h3></div>')
        self.assertEqual(images.card_links(soup(html), LISTING, TITLES),
                         {TITLES[0]: 'https://gallery.example/s/sable/', TITLES[1]: 'https://gallery.example/s/pusey/'})

    def test_a_link_that_turns_up_for_two_shows_is_dropped(self):
        html = ('<div><a href="/shared/"><h3>Sable Elyse Smith: Sky Fence Ground</h3></a></div>'
                '<div><a href="/shared/"><h3>Mavis Pusey: Mobile Images</h3></a></div>'
                '<div><a href="/s/carl/"><h3>Carl Cheng</h3></a></div>')
        self.assertEqual(images.card_links(soup(html), LISTING, TITLES), {'Carl Cheng': 'https://gallery.example/s/carl/'})


class SplitTitleCardTest(unittest.TestCase):
    """A listing that shows a show's title and its artist in separate elements (Commonwealth and Council), so no
    card holds the whole "Artist: Title" name that the scraper stored."""
    CARDS = ('<ul>'
             '<li><a href="/exhibitions/folding-boy-and-blue"><img src="/a.jpg"><h2>FOLDING BOY AND BLUE</h2><h1>Michelle Lopez</h1></a></li>'
             '<li><a href="/exhibitions/shimmering-menace"><img src="/b.jpg"><h2>Shimmering Menace</h2><h1>Jemima Wyman</h1></a></li>'
             '<li><a href="/exhibitions/another-show"><img src="/c.jpg"><h2>Another Show</h2><h1>Michelle Lopez</h1></a></li>'
             '</ul>')
    TITLES = ['Michelle Lopez: FOLDING BOY AND BLUE', 'Jemima Wyman: Shimmering Menace', 'Michelle Lopez: Another Show']

    def test_the_card_is_found_by_the_title_part_when_the_whole_name_is_not_on_the_page(self):
        page = images.PageText(soup(self.CARDS))
        self.assertEqual(images.link_in_card(page, self.TITLES[0], LISTING, self.TITLES),
                         'https://gallery.example/exhibitions/folding-boy-and-blue')
        self.assertEqual(images.link_in_card(page, self.TITLES[1], LISTING, self.TITLES),
                         'https://gallery.example/exhibitions/shimmering-menace')

    def test_an_artist_with_two_shows_is_never_used_to_find_a_card(self):
        # "Michelle Lopez" is on two cards, so only the title part can find a card: a show whose title is not
        # on the page has no link, rather than the first Michelle Lopez card's
        page = images.PageText(soup(self.CARDS))
        self.assertIsNone(images.link_in_card(page, 'Michelle Lopez: A Show That Is Not Listed', LISTING, self.TITLES))

    def test_the_card_does_not_climb_into_the_next_shows_card(self):
        # no link around or in the card itself: the search must stop at the next show's card, not take the page's first link
        html = ('<div><div><h2>FOLDING BOY AND BLUE</h2><h1>Michelle Lopez</h1></div>'
                '<div><h2>Shimmering Menace</h2><h1>Jemima Wyman</h1><a href="/exhibitions/shimmering-menace">View</a></div></div>')
        page = images.PageText(soup(html))
        titles = self.TITLES[:2]
        self.assertIsNone(images.link_in_card(page, titles[0], LISTING, titles))
        self.assertEqual(images.link_in_card(page, titles[1], LISTING, titles),
                         'https://gallery.example/exhibitions/shimmering-menace')

    def test_card_links_returns_the_split_cards_links(self):
        found = images.card_links(soup(self.CARDS), LISTING, self.TITLES)
        self.assertEqual(found[self.TITLES[0]], 'https://gallery.example/exhibitions/folding-boy-and-blue')
        self.assertEqual(found[self.TITLES[1]], 'https://gallery.example/exhibitions/shimmering-menace')
        self.assertEqual(found[self.TITLES[2]], 'https://gallery.example/exhibitions/another-show')


if __name__ == '__main__':
    unittest.main()
