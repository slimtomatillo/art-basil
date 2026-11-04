from scrapers.ist._artlogic_listing import scrape_artlogic_listing

EXHIBITIONS_URL = 'https://www.galerist.com.tr/exhibitions/'
VENUE = 'Galerist'


def scrape_galerist(env='prod', region='ist'):
    """Scrape and process the exhibitions at Galerist."""
    scrape_artlogic_listing(env, region, VENUE, EXHIBITIONS_URL)
