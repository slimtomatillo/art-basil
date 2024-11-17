import json
import numpy as np
import logging
import requests
from bs4 import BeautifulSoup
from config import DB_FILES
import os

def convert_nan_to_none(data):
    if isinstance(data, dict):
        return {k: convert_nan_to_none(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_nan_to_none(i) for i in data]
    elif isinstance(data, float) and np.isnan(data):
        return None
    else:
        return data

def load_db(filepath):
    try:
        # Try to read the file first
        with open(filepath, 'r') as file:
            db = json.load(file)
            return convert_nan_to_none(db)
    except FileNotFoundError:
        # File doesn't exist - try to create it
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w') as file:
                json.dump({}, file)
            logging.info(f"Created new database file at {filepath}")
            return {}
        except (OSError, PermissionError) as e:
            logging.warning(f"Could not create database file at {filepath}: {e}")
            return {}
    except json.JSONDecodeError:
        logging.warning(f"Empty or invalid JSON file at {filepath}, returning empty dict")
        return {}

def save_db(db, region):
    # Get the correct file path from DB_FILES using the region
    db_path = DB_FILES[region]

    with open(db_path, 'w') as file:
        json.dump(db, file, indent=4, default=str)

def fetch_and_parse(url):
    try:
        response = requests.get(url, headers={'User-Agent': 'Your Bot 0.1'})
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except requests.RequestException as e:
        logging.error(f"Error fetching {url}: {e}")
        return None
    