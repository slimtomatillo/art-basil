import json
import numpy as np
import logging
import requests
from bs4 import BeautifulSoup
from config import DB_FILE

def copy_json_file(source_file_path, destination_file_path):
    with open(source_file_path, 'r') as json_file:
        data = json.load(json_file)
    with open(destination_file_path, 'w') as destination_json_file:
        json.dump(data, destination_json_file, indent=4)
    logging.info(f"Copied {source_file_path} to {destination_file_path}")

def convert_nan_to_none(data):
    if isinstance(data, dict):
        return {k: convert_nan_to_none(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_nan_to_none(i) for i in data]
    elif isinstance(data, float) and np.isnan(data):
        return None
    else:
        return data

def load_db():
    try:
        with open(DB_FILE, 'r') as file:
            db = json.load(file)
            return convert_nan_to_none(db)
    except FileNotFoundError:
        logging.warning(f"Database file {DB_FILE} not found.")
        return {}

def save_db(db):
    with open(DB_FILE, 'w') as file:
        json.dump(db, file, indent=4, default=str)

def fetch_and_parse(url):
    try:
        response = requests.get(url, headers={'User-Agent': 'Your Bot 0.1'})
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except requests.RequestException as e:
        logging.error(f"Error fetching {url}: {e}")
        return None
    