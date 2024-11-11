import time
import logging
import pandas as pd
import os
from config import configure_logging
from processing import update_event_phases
from utils import copy_json_file, load_db
from scrapers import de_young, sfmoma, cjm, bampfa, sf_women_artists, asian_art_museum, omca, kala, cantor, museum_of_craft_and_design, sj_museum_of_art # Import other scrapers as needed

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
        "de Young Museum": de_young.scrape_de_young_and_legion_of_honor,
        "SFMOMA": sfmoma.scrape_sfmoma,
        "Contemporary Jewish Museum": cjm.scrape_contemporary_jewish_museum,
        "BAMPFA": bampfa.scrape_bampfa_exhibitions,
        "SF Women Artists": sf_women_artists.scrape_sfwomenartists,
        "Asian Art Museum": [
            asian_art_museum.scrape_asian_art_museum_current_events,
            asian_art_museum.scrape_asian_art_museum_past_events,
        ],
        "Oakland Museum of California": omca.scrape_oak_museum_of_ca_exhibitions,
        "Kala Art Institute": kala.scrape_kala_exhibitions,
        "Cantor Arts Center": cantor.scrape_cantor_exhibitions,
        "Museum of Craft and Design": museum_of_craft_and_design.scrape_museum_of_craft_and_design_exhibitions,
        "San Jose Museum of Art": sj_museum_of_art.scrape_sj_museum_of_art_exhibitions,
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
        # Correct misaligment between phase and end date
        update_event_phases()

        # Load db and count the venues and events
        db = load_db()
        event_count = sum(len(v) for v in db.values())
        logging.info("Database contains {:,} venues and {:,} events".format(len(db), event_count))
        # Capture the execution time and convert to minutes and seconds
        execution_time_s = round(time.time() - start_time, 1)
        minutes = int(execution_time_s // 60)
        seconds = int(execution_time_s % 60)
        logging.info(f"Scraping took {minutes} minutes and {seconds} seconds")
        # Record the number of venues and events in the db
        file_path = 'docs/db_size.csv'
        df = pd.DataFrame([{
            "timestamp": pd.Timestamp.now(),
            "num_venues": len(db),
            "num_events": event_count,
            "scrape_time_s": execution_time_s
        }])
        # Check if the file exists
        if os.path.exists(file_path):
            # File exists, append without writing the header
            df.to_csv(file_path, mode='a', header=False, index=False)
        else:
            # File does not exist, write with the header
            df.to_csv(file_path, mode='w', header=True, index=False)
        logging.info("Database size recorded")

    logging.info("Finished")

if __name__ == "__main__":
    main()
