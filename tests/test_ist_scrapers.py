# Run with the project's Python (needs its dependencies): python -m unittest discover -s tests
import datetime as dt
import os
import sys
import unittest
from unittest import mock

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scrapers.ist import _artlogic_listing, anna_laudel, depo_istanbul, elgiz_museum, pi_artworks, rahmi_koc_museum
from scrapers.tor import _common

TODAY = dt.date(2026, 11, 4)


def run(module, func, html):
    """Run one scraper over a page; returns {name: stored event}."""
    stored = []
    with mock.patch.object(module, 'fetch_and_parse', lambda url, headers=None: BeautifulSoup(f'<main>{html}</main>', 'html.parser')), \
            mock.patch.object(module, 'region_today', lambda region: TODAY, create=True), \
            mock.patch.object(_common, 'region_today', lambda region: TODAY), \
            mock.patch.object(_common, 'process_event', lambda details, region: stored.append(details)):
        getattr(module, func)(env='prod')
    return {e['name']: e for e in stored}


def blocks(*lines):
    return ''.join(f'<p>{line}</p>' for line in lines)


class ElgizTest(unittest.TestCase):
    def test_numeric_ranges(self):
        self.assertEqual(elgiz_museum.parse_numeric_range('28.08 - 28.11.2026'), (dt.date(2026, 8, 28), dt.date(2026, 11, 28)))
        self.assertEqual(elgiz_museum.parse_numeric_range('14.05.2025 - 31.05.2025'), (dt.date(2025, 5, 14), dt.date(2025, 5, 31)))
        self.assertEqual(elgiz_museum.parse_numeric_range('20.12 - 10.02.2027'), (dt.date(2026, 12, 20), dt.date(2027, 2, 10)))
        self.assertEqual(elgiz_museum.parse_numeric_range('Nisan-Kasım 2025'), (None, None))

    def test_only_shows_not_marked_past_are_kept(self):
        page = blocks('Süreli Sergiler', 'Buluşma', 'Devamını Oku', 'Güncel', '28.08 - 28.11.2026',
                      'Süreli Sergiler', 'Serap Mevsimi', 'Devamını Oku', 'Geçmiş', '14.05.2025 - 31.05.2025')
        events = run(elgiz_museum, 'scrape_elgiz_museum', page)
        self.assertEqual(list(events), ['Buluşma'])
        self.assertEqual(events['Buluşma']['dates'], {'start': dt.date(2026, 8, 28), 'end': dt.date(2026, 11, 28)})


class DepoTest(unittest.TestCase):
    def test_turkish_ranges_are_read_and_other_languages_and_lone_dates_are_not(self):
        page = blocks('Sergiler', 'Akımlar: Tarabya Kültür Akademisi 15 Yaşında', '5-22 Kasım 2026',
                      'Dîlan Cûdî Saruhan – Îhtîmaleke Asîman', '22 Îlon – 21 Mijdar 2026',
                      'Dilan Cudi Saruhan – Bir İhtimal Gökyüzü', '22 Eylül – 21 Kasım 2026',
                      'Eski Performans', '7 Mart 2010')
        events = run(depo_istanbul, 'scrape_depo_istanbul', page)
        self.assertEqual(sorted(events), ['Akımlar: Tarabya Kültür Akademisi 15 Yaşında', 'Dilan Cudi Saruhan – Bir İhtimal Gökyüzü'])
        self.assertEqual(events['Akımlar: Tarabya Kültür Akademisi 15 Yaşında']['dates'],
                         {'start': dt.date(2026, 11, 5), 'end': dt.date(2026, 11, 22)})


class AnnaLaudelTest(unittest.TestCase):
    def test_only_istanbul_shows_are_kept_each_once_with_readable_names(self):
        show = ('BİLAL HAKAN KARAKAYA', 'LUGGAGE OF THE UNSEEN', 'NOVEMBER 14, 2026 – JANUARY 3, 2027', 'ISTANBUL')
        page = blocks('Upcoming', *show, *show, 'TUĞÇE DİRİ', 'LITTLE PIECES OF INFINITY', 'NOVEMBER 27, 2026 – JANUARY 23, 2027', 'ANKARA',
                      'SERKAN KÜÇÜKÖZCÜ', 'PROLOGUE', 'OCTOBER 30, 2026 – JANUARY 6, 2027', 'DUSSELDORF')
        events = run(anna_laudel, 'scrape_anna_laudel', page)
        self.assertEqual(list(events), ['Bilal Hakan Karakaya: Luggage Of The Unseen'])
        self.assertEqual(events['Bilal Hakan Karakaya: Luggage Of The Unseen']['dates'],
                         {'start': dt.date(2026, 11, 14), 'end': dt.date(2027, 1, 3)})


class RahmiKocTest(unittest.TestCase):
    def test_the_on_view_exhibition_is_read(self):
        page = blocks('Devam Eden Sergiler', 'Geçmiş Sergiler', '09 Ekim 2026 - 07 Şubat 2027', 'Yerli Sanayi, Uluslararası İtibar',
                      'Sergi, Koç Topluluğu’nun bir asırlık üretim yolculuğunu anlatıyor.', 'ÇALIŞMA SAATLERİMİZ', 'Haftaiçi')
        events = run(rahmi_koc_museum, 'scrape_rahmi_koc_museum', page)
        self.assertEqual(list(events), ['Yerli Sanayi, Uluslararası İtibar'])
        self.assertEqual(events['Yerli Sanayi, Uluslararası İtibar']['dates'], {'start': dt.date(2026, 10, 9), 'end': dt.date(2027, 2, 7)})


class ArtlogicListingTest(unittest.TestCase):
    @staticmethod
    def item(name, dates, city):
        return (f'<li><a href="/exhibitions/1/"><div class="content"><h2>{name}</h2><span class="date">{dates}</span>'
                f'<span class="location">{city}</span></div></a></li>')

    def test_only_istanbul_shows_and_a_range_without_a_start_month_are_read(self):
        page = '<ul>' + self.item('Albano Hernández', '5 Nov - 31 Dec 2026', 'Istanbul') \
            + self.item('Elina Yumasheva', '13 - 28 Nov 2026', 'London') \
            + self.item('Rû Bi Rû', '13 - 28 Nov 2026', 'İstanbul, Dialogues') + '</ul>'
        stored = []
        with mock.patch.object(_artlogic_listing, 'fetch_and_parse', lambda url: BeautifulSoup(page, 'html.parser')), \
                mock.patch.object(_artlogic_listing, 'region_today', lambda region: TODAY), \
                mock.patch.object(_common, 'region_today', lambda region: TODAY), \
                mock.patch.object(_common, 'process_event', lambda details, region: stored.append(details)):
            pi_artworks.scrape_pi_artworks(env='prod')
        events = {e['name']: e for e in stored}
        self.assertEqual(sorted(events), ['Albano Hernández', 'Rû Bi Rû'])
        self.assertEqual(events['Rû Bi Rû']['dates'], {'start': dt.date(2026, 11, 13), 'end': dt.date(2026, 11, 28)})


if __name__ == '__main__':
    unittest.main()
