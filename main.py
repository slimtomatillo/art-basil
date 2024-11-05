import time
import logging
from config import configure_logging
from processing import update_event_phases
from utils import copy_json_file, load_db
from scrapers import de_young, sfmoma, cjm, bampfa, sf_womens_artist, asian_art_museum, omca, kala, cantor, museum_of_craft_and_design # Import other scrapers as needed

def main(env='prod', selected_venues=None, skip_venues=None, write_summary=True):
    configure_logging(env)
    logging.info("----------NEW LOG----------")
    
    if env == 'prod':
        try:
            copy_json_file('docs/events_db.json', 'docs/events_db_copy.json')
        except FileNotFoundError:
            logging.warning('Original events_db.json file not found. No copy created.')

    start_time = time.time()
    logging.info('Starting the scraping process')

    # Mapping venue names to their respective scraper functions
    venues = {
        "de Young": de_young.scrape_de_young_and_legion_of_honor,
        "SFMOMA": sfmoma.scrape_sfmoma,
        "CJM": cjm.scrape_contemporary_jewish_museum,
        "BAMPFA": bampfa.scrape_bampfa_exhibitions,
        "SF Women's Artist": sf_womens_artist.scrape_sfwomenartists,
        "Asian Art Museum": [
            asian_art_museum.scrape_asian_art_museum_current_events,
            asian_art_museum.scrape_asian_art_museum_past_events,
        ],
        "OMCA": omca.scrape_oak_museum_of_ca_exhibitions,
        "Kala": kala.scrape_kala_exhibitions,
        "Cantor": cantor.scrape_cantor_exhibitions,
        "Museum of Craft and Design": museum_of_craft_and_design.scrape_museum_of_craft_and_design_exhibitions,
        # Add other scrapers here
    }

    if selected_venues:
        logging.info(f"Only scraping {selected_venues}")
        venues = {k: v for k, v in venues.items() if k in selected_venues}

    if skip_venues:
        logging.info(f"Skipping {skip_venues}")
        venues = {k: v for k, v in venues.items() if k not in skip_venues}

    for venue, scraper in venues.items():
        logging.info(f"Starting scrape for {venue}")
        if isinstance(scraper, list):
            # If scraper is a list (e.g., multiple functions for a venue), iterate through the list
            for s in scraper:
                s(env=env)
        else:
            # Otherwise, call the single scraper function
            scraper(env=env)
        # Log the completion of scraping for each venue
        logging.info(f"Finished scrape for {venue}")

    if env == 'prod' and write_summary:
        update_event_phases()
        db = load_db()
        logging.info("Database contains {:,} venues and {:,} events".format(len(db), sum(len(v) for v in db.values())))
        execution_time_s = round(time.time() - start_time, 1)
        logging.info(f"Scraping took {execution_time_s} seconds")

    logging.info("Finished")

if __name__ == "__main__":
    main()
