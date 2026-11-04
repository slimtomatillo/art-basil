from scrapers.ist._artlogic_listing import scrape_artlogic_listing

EXHIBITIONS_URL = 'https://www.piartworks.com/exhibitions/'
VENUE = 'Pi Artworks Istanbul'


def scrape_pi_artworks(env='prod', region='ist'):
    """Scrape and process the exhibitions at Pi Artworks' Istanbul gallery (its London shows are left out)."""
    scrape_artlogic_listing(env, region, VENUE, EXHIBITIONS_URL, city_marker='stanbul')
