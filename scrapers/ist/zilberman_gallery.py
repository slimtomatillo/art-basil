from scrapers.ist._artlogic_listing import scrape_artlogic_listing

EXHIBITIONS_URL = 'https://www.zilbermangallery.com/exhibitions/'
VENUE = 'Zilberman Istanbul'


def scrape_zilberman_gallery(env='prod', region='ist'):
    """Scrape and process the exhibitions at Zilberman's Istanbul gallery (its Berlin shows are left out)."""
    scrape_artlogic_listing(env, region, VENUE, EXHIBITIONS_URL, city_marker='stanbul')
