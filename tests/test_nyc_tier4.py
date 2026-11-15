# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
#
# New York tier 4 (WEBSITE-121): the five big venues fetched through the paid proxy (the Met, MoMA, the Brooklyn Museum,
# Gagosian, Hauser & Wirth). Fixtures are trimmed copies of the markup the sites served a browser on 2026-11-14.
# Nothing touches the network.
import datetime as dt
import json
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.nyc import brooklyn_museum, gagosian, hauser_and_wirth, metropolitan_museum_of_art, museum_of_modern_art
from scrapers.tor import _common

TODAY = dt.date(2026, 11, 14)
DOCS = os.path.join(os.path.dirname(__file__), '../docs/data')


def run(module, scrape, pages):
    """Run a scraper over {url: html}; returns {name: stored event}."""
    stored = []

    def fetch(url, *args, **kwargs):
        html = pages.get(url)
        return BeautifulSoup(html, 'html.parser') if html is not None else None

    with mock.patch.object(module, 'fetch_and_parse', side_effect=fetch), \
            mock.patch.object(module, 'region_today', return_value=TODAY, create=True), \
            mock.patch.object(_common, 'region_today', return_value=TODAY), \
            mock.patch.object(_common, 'process_event', side_effect=lambda d, r: stored.append(d)):
        getattr(module, scrape)(env='prod', region='nyc')
    return {e['name']: e for e in stored}


def image_of(event):
    return next((link['link'] for link in event['links'] if link['description'] == 'Image'), None)


def met_card(slug, title, dates):
    return (f'<article class="Tm8WZW_exhibitionCard"><figure class="Tm8WZW_figure"><a class="redundantlink" href="/exhibitions/{slug}"></a>'
            f'<img src="https://cdn.sanity.io/images/cctd4ker/production/abc-5120x2880.jpg?w=3840&amp;q=75&amp;fit=clip&amp;auto=format"></figure>'
            f'<div><div class="Tm8WZW_title" role="heading" aria-level="2"><a href="/exhibitions/{slug}"><span>{title}</span></a></div>'
            f'<div class="Tm8WZW_meta"><div><div>{dates}</div></div></div></div></article>')


class MetTest(unittest.TestCase):
    def test_reads_current_and_upcoming_and_leaves_out_permanent_galleries(self):
        html = '<main><h2>Current Exhibitions</h2>' + ''.join([
            met_card('costume-art', 'Costume Art', 'Through January 10, 2027'),
            met_card('face-of-life', 'The Face of Life: Modern Portraits at The Met', 'Ongoing'),
            met_card('decorative-arts', 'Decorative Arts in China, 1000 to the Present', 'July 25, 2026–Ongoing'),
            met_card('costume-art', 'Costume Art', 'Through January 10, 2027'),
            met_card('baseball', 'Baseball Cards', 'Reopens–Spring 2027'),
        ]) + '<h2>Upcoming Exhibitions</h2>' + ''.join([
            met_card('across-wine-dark-seas', 'Across Wine-Dark Seas: Art and Identity beyond Ancient Greece',
                     'December 20, 2026–April 11, 2027'),
            met_card('radiant-world', 'Radiant World: Jahangir and Mughal India', 'April 25–August 15, 2027'),
        ]) + '</main>'
        shows = run(metropolitan_museum_of_art, 'scrape_metropolitan_museum_of_art',
                    {metropolitan_museum_of_art.PAGE_URL: html})
        self.assertEqual(sorted(shows), ['Across Wine-Dark Seas: Art and Identity beyond Ancient Greece', 'Costume Art',
                                         'Radiant World: Jahangir and Mughal India'])
        costume = shows['Costume Art']
        self.assertEqual((costume['dates']['start'], costume['dates']['end']), (None, dt.date(2027, 1, 10)))
        self.assertEqual(costume['links'][0]['link'], 'https://www.metmuseum.org/exhibitions/costume-art')
        self.assertIn('w=1200', image_of(costume))
        radiant = shows['Radiant World: Jahangir and Mughal India']
        self.assertEqual((radiant['dates']['start'], radiant['dates']['end']), (dt.date(2027, 4, 25), dt.date(2027, 8, 15)))

    def test_a_failed_fetch_keeps_existing_data(self):
        self.assertEqual(run(metropolitan_museum_of_art, 'scrape_metropolitan_museum_of_art', {}), {})


def moma_card(number, title, dates, extra=''):
    return (f'<a class="wrapper" href="/calendar/exhibitions/{number}"><div><div><h3><div class="block"><p class="balance-text">{title}</p></div>'
            f'<div class="none"><p>Artist</p><p>Subtitle</p></div></h3><div class="margin"><p>{extra}</p><p>{dates}</p></div></div></div>'
            f'<div><picture><img src="/d/assets/abc/pic.jpg?sha=1"></picture></div></a>')


class MomaTest(unittest.TestCase):
    def test_reads_every_section_and_leaves_out_ongoing_displays(self):
        html = ('<main><h2>Current exhibitions</h2>'
                + moma_card(5912, 'Pierre Huyghe: UUmwelt', 'Through Nov&nbsp;29', 'Last chance')
                + moma_card(5906, 'Architects of Liberation: Modernism in Western Africa', 'Through Jan 2, 2027')
                + '<h2>Upcoming exhibitions</h2>'
                + moma_card(5916, 'Mondrian Boogie Woogie', 'Mar 21–Jul 31, 2027', 'Member Previews, Mar 18–20')
                + '<h2>Installations and projects</h2>'
                + moma_card(5942, 'Art Lab: Imagination', 'Ongoing')
                + moma_card(5797, 'The Sumptuous Discovery of Gotham a Go-Go', 'Mar 8, 2025–ongoing')
                + '<a href="/calendar/exhibitions/history"><span>Exhibition history</span></a></main>')
        shows = run(museum_of_modern_art, 'scrape_museum_of_modern_art', {museum_of_modern_art.PAGE_URL: html})
        self.assertEqual(sorted(shows), ['Architects of Liberation: Modernism in Western Africa', 'Mondrian Boogie Woogie',
                                         'Pierre Huyghe: UUmwelt'])
        huyghe = shows['Pierre Huyghe: UUmwelt']
        self.assertEqual((huyghe['dates']['start'], huyghe['dates']['end']), (None, dt.date(2026, 11, 29)))
        self.assertEqual(huyghe['links'][0]['link'], 'https://www.moma.org/calendar/exhibitions/5912')
        self.assertEqual(image_of(huyghe), 'https://www.moma.org/d/assets/abc/pic.jpg?sha=1')
        mondrian = shows['Mondrian Boogie Woogie']
        self.assertEqual((mondrian['dates']['start'], mondrian['dates']['end']), (dt.date(2027, 3, 21), dt.date(2027, 7, 31)))


def brooklyn_card(slug, title, dates):
    return (f'<li><a href="/exhibitions/{slug}"><span><span><div><div><h3><span><span>{title}</span></span></h3>'
            f'<span><span>{dates}</span></span></div><div><div><div><img alt="" loading="lazy" '
            f'srcset="https://cms-images.brooklynmuseum.org/abc-4267x2400.jpg?w=384&amp;q=75&amp;auto=format 384w, '
            f'https://cms-images.brooklynmuseum.org/abc-4267x2400.jpg?w=640&amp;q=75&amp;auto=format 640w" '
            f'src="https://cms-images.brooklynmuseum.org/abc-4267x2400.jpg?w=3840&amp;q=75&amp;auto=format"></div></div></div></div></span></span></a></li>')


class BrooklynMuseumTest(unittest.TestCase):
    def test_reads_shows_and_leaves_out_permanent_galleries_and_old_spotlights(self):
        html = ('<main><ul>' + brooklyn_card('manga', 'Art of Manga', 'October 3, 2026–January 31, 2027')
                + brooklyn_card('iris-van-herpen', 'Iris van Herpen: Sculpting the Senses', 'May 16, 2026–January 3, 2027')
                + brooklyn_card('american-art', 'American Art', 'Ongoing')
                + brooklyn_card('giovanni_della_robbia', 'The Brooklyn Della Robbia', 'Opened June 16, 2018')
                + '</ul><a href="/exhibitions/upcoming">Upcoming exhibitions</a></main>')
        shows = run(brooklyn_museum, 'scrape_brooklyn_museum', {brooklyn_museum.PAGE_URL: html})
        self.assertEqual(sorted(shows), ['Art of Manga', 'Iris van Herpen: Sculpting the Senses'])
        manga = shows['Art of Manga']
        self.assertEqual((manga['dates']['start'], manga['dates']['end']), (dt.date(2026, 10, 3), dt.date(2027, 1, 31)))
        self.assertEqual(manga['links'][0]['link'], 'https://www.brooklynmuseum.org/exhibitions/manga')
        self.assertTrue(image_of(manga).startswith('https://cms-images.brooklynmuseum.org/abc-4267x2400.jpg'))


def gagosian_card(slug, artist, title, dates, place, curated=''):
    return (f'<div><a class="group" href="/exhibitions/2026/{slug}/"><div><img src="https://gagosian.com/media/images/exhibitions/2026/{slug}/pic_300x300.jpg" '
            f'alt="x"></div><div class="pt-5"><h4><b>{artist}</b>{"<br>" + title if title else ""}</h4><div>'
            f'{"<p>" + curated + "</p>" if curated else ""}<p><span>{dates[0]}</span><span>{dates[1]}</span></p><p>{place}</p></div></div></a></div>')


class GagosianTest(unittest.TestCase):
    def test_keeps_only_new_york_shows_and_the_space_each_is_at(self):
        html = ('<main>'
                + gagosian_card('friends-and-legends', 'Friends and Legends', 'The Collection of Michael Chow',
                                ('November 14–', 'December 22, 2026'), '980 Madison at 76th Street, New&nbsp;York')
                + gagosian_card('bea-scaccia-groomed', 'Bea Scaccia', 'Groomed', ('September 22–', 'December 23, 2026'),
                                'Park &amp; 75, New&nbsp;York', curated='Curated by Francesco&nbsp;Bonami')
                + gagosian_card('georg-baselitz', 'Georg Baselitz', 'Meine Schule', ('November 12, 2026–', 'January 23, 2027'),
                                '555 West 24th Street, New&nbsp;York')
                + gagosian_card('brice-marden', 'Brice Marden', 'I Am Plane Image', ('September 15–', 'December 12, 2026'),
                                'West 21st Street, New&nbsp;York')
                + gagosian_card('cady-noland', 'Cady Noland', '', ('October 12–', 'December 19, 2026'), 'Davies Street, London')
                + gagosian_card('richard-avedon', 'Richard Avedon', 'Hollywood', ('November 4–', 'December 19, 2026'), 'Beverly Hills')
                + '</main>')
        upcoming = '<main>' + gagosian_card('theaster-gates', 'Theaster Gates', 'Surrogate', ('November 19, 2026–', 'February 27, 2027'),
                                            'Hong Kong') + '</main>'
        shows = run(gagosian, 'scrape_gagosian', {gagosian.PAGES[0]: html, gagosian.PAGES[1]: upcoming})
        self.assertEqual(sorted(shows), ['Bea Scaccia: Groomed', 'Brice Marden: I Am Plane Image', 'Friends and Legends: The Collection of Michael Chow',
                                         'Georg Baselitz: Meine Schule'])
        chow = shows['Friends and Legends: The Collection of Michael Chow']
        self.assertEqual((chow['dates']['start'], chow['dates']['end']), (dt.date(2026, 11, 14), dt.date(2026, 12, 22)))
        self.assertEqual(chow['locations'], ['980 Madison'])
        self.assertEqual(shows['Bea Scaccia: Groomed']['locations'], ['Park & 75'])
        self.assertEqual(shows['Georg Baselitz: Meine Schule']['locations'], ['555 West 24th'])
        self.assertEqual(shows['Brice Marden: I Am Plane Image']['locations'], ['West 21st Street'])
        self.assertEqual(chow['links'][0]['link'], 'https://gagosian.com/exhibitions/2026/friends-and-legends/')
        self.assertTrue(image_of(chow).endswith('pic_300x300.jpg'))

    def test_a_page_that_fails_leaves_the_other_read(self):
        html = '<main>' + gagosian_card('julie-curtiss', 'Julie Curtiss', 'UNREAL', ('November 10–', 'December 19, 2026'),
                                        '541 West 24th Street, New&nbsp;York') + '</main>'
        shows = run(gagosian, 'scrape_gagosian', {gagosian.PAGES[0]: html})
        self.assertEqual(list(shows), ['Julie Curtiss: UNREAL'])


def hauser_page(items):
    data = {'props': {'pageProps': {'initialExhibitionsData': {'galleryExhibitionCollection': {'items': items}}}}}
    return f'<html><body><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></body></html>'


def hauser_item(slug, title, start, end, *places):
    return {'title': title, 'slug': slug, 'startDate': f'{start}T00:00:00.000Z', 'endDate': f'{end}T00:00:00.000Z',
            'relatedLocationsCollection': {'items': [{'name': p, 'slug': 'x'} for p in places]},
            'listingPageImage': [{'src': f'https://media.hauserwirth.com/asset/{slug}/thumbnail/web', 'type': 'image'}]}


class HauserWirthTest(unittest.TestCase):
    def test_keeps_only_new_york_shows_with_their_space(self):
        page = hauser_page([
            hauser_item('mike-kelley-jerry-meandering', 'Mike Kelley. Jerry Meandering', '2026-11-12', '2027-01-16', 'New York, 18th Street'),
            hauser_item('zeng-fanzhi-new-york', 'Zeng Fanzhi', '2026-11-05', '2027-01-23', 'New York, 22nd Street'),
            hauser_item('rashid-johnson-birthday-boys', 'Rashid Johnson. Birthday Boys', '2026-11-03', '2027-01-16', 'New York, Wooster Street '),
            hauser_item('emma-kunz', 'Emma Kunz ', '2026-11-07', '2027-04-04', 'Somerset'),
            hauser_item('glenn-ligon', 'Glenn Ligon. Sit So Your Back', '2026-09-30', '2027-01-17', 'Downtown Los Angeles'),
        ])
        shows = run(hauser_and_wirth, 'scrape_hauser_and_wirth', {hauser_and_wirth.PAGE_URL: page})
        self.assertEqual(sorted(shows), ['Mike Kelley: Jerry Meandering', 'Rashid Johnson: Birthday Boys', 'Zeng Fanzhi'])
        kelley = shows['Mike Kelley: Jerry Meandering']
        self.assertEqual((kelley['dates']['start'], kelley['dates']['end']), (dt.date(2026, 11, 12), dt.date(2027, 1, 16)))
        self.assertEqual(kelley['locations'], ['18th Street'])
        self.assertEqual(shows['Zeng Fanzhi']['locations'], ['22nd Street'])
        self.assertEqual(shows['Rashid Johnson: Birthday Boys']['locations'], ['Wooster Street'])
        self.assertEqual(kelley['links'][0]['link'], 'https://www.hauserwirth.com/hauser-wirth-exhibitions/mike-kelley-jerry-meandering/')
        self.assertEqual(image_of(kelley), 'https://media.hauserwirth.com/asset/mike-kelley-jerry-meandering/thumbnail/web')

    def test_a_page_with_no_data_keeps_existing_data(self):
        self.assertEqual(run(hauser_and_wirth, 'scrape_hauser_and_wirth', {hauser_and_wirth.PAGE_URL: '<html><body>Just a moment</body></html>'}), {})


class RegistryTest(unittest.TestCase):
    VENUES = {'The Metropolitan Museum of Art': ('www.metmuseum.org', 'metropolitan_museum_of_art'),
              'Museum of Modern Art': ('www.moma.org', 'museum_of_modern_art'),
              'Brooklyn Museum': ('www.brooklynmuseum.org', 'brooklyn_museum'),
              'Gagosian': ('gagosian.com', 'gagosian'),
              'Hauser & Wirth': ('www.hauserwirth.com', 'hauser_and_wirth')}

    def test_each_venue_is_registered_proxied_scheduled_and_has_its_data(self):
        import main
        import utils
        scrapers, _ = main.get_venue_scrapers(selected_regions=['nyc'])
        with open(os.path.join(DOCS, 'nyc_venues.json'), encoding='utf-8') as f:
            venues = json.load(f)
        with open(os.path.join(DOCS, 'venue_coordinates.json'), encoding='utf-8') as f:
            coordinates = json.load(f)['nyc']
        with open(os.path.join(DOCS, 'venue_admission.json'), encoding='utf-8') as f:
            admission = json.load(f)['nyc']
        self.assertEqual(sorted(scrapers), sorted(venues))
        for venue, (host, _module) in self.VENUES.items():
            self.assertIn(venue, scrapers)
            self.assertIn(host, utils.PROXY_DOMAINS)
            self.assertEqual(main.PROXIED_VENUES[venue], [venue])
            addresses = venues[venue] if isinstance(venues[venue], list) else [venues[venue]]
            self.assertEqual(len(coordinates[venue]), len(addresses), f'{venue} needs coordinates for each address')
        for venue in ('The Metropolitan Museum of Art', 'Museum of Modern Art', 'Brooklyn Museum'):
            self.assertIn(venue, admission, f'{venue} needs an admission record')

    def test_the_spaces_the_scrapers_name_are_the_labels_in_the_venue_data(self):
        with open(os.path.join(DOCS, 'nyc_venues.json'), encoding='utf-8') as f:
            venues = json.load(f)
        labels = lambda venue: [space['label'] for space in venues[venue]]
        self.assertEqual(sorted(label for label, _pattern in gagosian.SPACES), sorted(labels('Gagosian')))
        self.assertEqual(sorted(hauser_and_wirth.SPACES.values()), sorted(labels('Hauser & Wirth')))


if __name__ == '__main__':
    unittest.main()
