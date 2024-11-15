import time
import logging
import pandas as pd
import os
from config import configure_logging, DB_FILES
from processing import update_event_phases
from utils import load_db
from scrapers import de_young, sfmoma, cjm, bampfa, sf_women_artists, asian_art_museum, omca, \
    kala, cantor, museum_of_craft_and_design, sj_museum_of_art # Import other scrapers as needed

def get_venue_scrapers(selected_regions=None, selected_venues=None, skip_venues=None):
    """Return dictionary of venue:scraper pairs and venue-to-region mapping"""
    all_scrapers = {
        'sf': {
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
        },
        # 'la': {
        #     "LACMA": lacma.scrape_lacma_exhibitions,
        # }
    }
    
    # Create venue to region mapping
    venue_to_region = {}
    for region, scrapers in all_scrapers.items():
        for venue in scrapers:
            venue_to_region[venue] = region
    
    # Filter and flatten scrapers as before
    if selected_regions:
        all_scrapers = {k: v for k, v in all_scrapers.items() if k in selected_regions}
    
    venues = {}
    for region_scrapers in all_scrapers.values():
        venues.update(region_scrapers)
    
    if selected_venues:
        venues = {k: v for k, v in venues.items() if k in selected_venues}
    
    if skip_venues:
        venues = {k: v for k, v in venues.items() if k not in skip_venues}
    
    return venues, venue_to_region

def main(env='prod', selected_regions=None, selected_venues=None, skip_venues=None, write_summary=True):
    configure_logging(env)
    logging.info("----------NEW LOG----------")

    start_time = time.time()
    logging.info('Starting the scraping process')

    # Log selection criteria if specified
    if selected_regions:
        logging.info(f"Selected regions: {selected_regions}")
    if selected_venues:
        logging.info(f"Selected venues: {selected_venues}")
    if skip_venues:
        logging.info(f"Skipping venues: {skip_venues}")

    # Get both the scrapers and the mapping
    venues, venue_to_region = get_venue_scrapers(selected_regions, selected_venues, skip_venues)

    for venue, scraper in venues.items():
        region = venue_to_region[venue]
        logging.info(f"[{region}] Starting scrape for {venue}")
        if isinstance(scraper, list):
            for s in scraper:
                s(env=env, region=region)
        else:
            scraper(env=env, region=region)
        logging.info(f"[{region}] Finished scrape for {venue}")

    if env == 'prod' and write_summary:
        # Load dbs and regions
        # dbs = {region: load_db(db_file) for region, db_file in DB_FILES.items()}
        # For now, only update the sf db
        dbs = {region: load_db(db_file) for region, db_file in DB_FILES.items() if region == 'sf'}
        
        # Update the event phases for each db
        for region, db in dbs.items():
            update_event_phases(db, region)
        
        # Count the venues and events
        event_count = sum(len(events) for db in dbs.values() for events in db.values())
        venue_count = sum(len(db) for db in dbs.values())
        logging.info("Database contains {:,} venues and {:,} events".format(venue_count, event_count))
        
        # Capture the execution time and convert to minutes and seconds
        execution_time_s = round(time.time() - start_time, 1)
        minutes = int(execution_time_s // 60)
        seconds = int(execution_time_s % 60)
        logging.info(f"Scraping took {minutes} min, {seconds} sec")
        
        # Record the number of venues and events in the db
        file_path = 'docs/data/db_size.csv'
        df = pd.DataFrame([{
            "timestamp": pd.Timestamp.now(),
            "num_venues": venue_count,
            "num_events": event_count,
            "scrape_time_s": execution_time_s,
            "regions": ','.join(selected_regions) if selected_regions else ','.join(dbs.keys())
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
