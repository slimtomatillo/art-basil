import json
import numpy as np
import logging
import requests
from bs4 import BeautifulSoup
from config import DB_FILES
import os
import time
from urllib.parse import urlparse

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

# (connect, read) seconds. Without a timeout a server that accepts the connection
# but never responds hangs the scraper forever, which stalls every scraper after
# it and the CI job's commit step.
REQUEST_TIMEOUT = (10, 30)

# Proxied requests run a real browser on ZenRows' side (js_render), which takes
# 5-20s normally and occasionally much longer; at the plain 30s limit CI runs
# kept losing a page to a read timeout (Cantor, then Huntington). Give them more
# room, and retry once on a timeout or a transient ZenRows error (429 = over its
# concurrency limit, 5xx = their side) since the pages are only fetched daily.
PROXY_TIMEOUT = (10, 90)
PROXY_ATTEMPTS = 2
PROXY_RETRY_DELAY = 5

# Domains whose own protection blocks GitHub Actions' datacenter IPs outright
# (confirmed by direct testing - see WEBSITE-53), routed through the ZenRows
# proxy instead of a direct request. Each domain maps to only the ZenRows
# params it actually needs, kept as cheap as possible since a "protected"
# (js_render + premium_proxy) request costs 25x a plain one:
#   - bampfa.org (Fastly WAF) blocks on IP/UA reputation alone - no JS
#     challenge - so a premium (residential) proxy IP is enough.
#   - everything else below needs js_render too, confirmed by a live test
#     against the real ZenRows API rather than assumed from how the block
#     merely *looks* from a browser - several of these (Norton Simon,
#     famsf.org, Stanford) initially looked like plain IP/UA blocks and
#     weren't; premium_proxy alone got back "RESP001: could not get
#     content, try enabling javascript rendering" from ZenRows itself.
# A domain not listed here is fetched directly, exactly as before - this is
# deliberately an allowlist, not a blanket "proxy everything", both for cost
# and because most venues' sites have no issue with CI's IP at all.
PROXY_DOMAINS = {
    'bampfa.org': {'premium_proxy': 'true'},
    'www.nortonsimon.org': {'premium_proxy': 'true', 'js_render': 'true'},
    'www.huntington.org': {'premium_proxy': 'true', 'js_render': 'true'},
    'ago.ca': {'premium_proxy': 'true', 'js_render': 'true'},
    # Cantor Arts Center
    'museum.stanford.edu': {'premium_proxy': 'true', 'js_render': 'true'},
    # de Young, Legion of Honor (WEBSITE-68)
    'www.famsf.org': {'premium_proxy': 'true', 'js_render': 'true'},
    # Southern Exposure (WEBSITE-71): 403s GitHub Actions' IPs, fine from a
    # normal connection; a premium proxy IP alone gets through (live-tested).
    'soex.org': {'premium_proxy': 'true'},
}
ZENROWS_API_URL = 'https://api.zenrows.com/v1/'
ZENROWS_API_KEY = os.environ.get('SCRAPER_PROXY_API_KEY')

# Set once ZenRows answers 402 (account out of credits). Every later proxied
# request in the run would fail the same way, so fetch_and_parse stops sending
# them and main.py skips the remaining proxied scrapers.
PROXY_EXHAUSTED = False

def _proxy_get(url, proxy_params):
    """GET through ZenRows, retrying once on a timeout or transient error."""
    for attempt in range(1, PROXY_ATTEMPTS + 1):
        try:
            response = requests.get(
                ZENROWS_API_URL,
                params={'url': url, 'apikey': ZENROWS_API_KEY, **proxy_params},
                timeout=PROXY_TIMEOUT,
            )
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt == PROXY_ATTEMPTS:
                raise
            logging.warning(f"Proxy request for {url} failed ({type(e).__name__}); retrying.")
        else:
            if response.status_code != 429 and response.status_code < 500 or attempt == PROXY_ATTEMPTS:
                return response
            logging.warning(f"Proxy request for {url} returned {response.status_code}; retrying.")
        time.sleep(PROXY_RETRY_DELAY)

def fetch_and_parse(url, headers=None):
    global PROXY_EXHAUSTED
    request_headers = {'User-Agent': 'Your Bot 0.1'}
    if headers:
        request_headers.update(headers)

    proxy_params = PROXY_DOMAINS.get(urlparse(url).netloc)

    try:
        if proxy_params and ZENROWS_API_KEY:
            if PROXY_EXHAUSTED:
                logging.info(f"Not fetching {url}: the ZenRows account is out of credits.")
                return None
            # Routed through ZenRows. It manages its own User-Agent and
            # browser fingerprinting for the anti-bot path, so our usual
            # headers (e.g. a scraper's custom browser UA) don't apply here -
            # only our own URL and the domain's minimum required params go.
            response = _proxy_get(url, proxy_params)
            if response.status_code == 402:
                PROXY_EXHAUSTED = True
                logging.error("ZenRows reports the account is out of credits (402); "
                              "skipping all remaining proxied fetches this run.")
        else:
            if proxy_params:
                logging.warning(
                    f"{urlparse(url).netloc} needs the proxy to work from CI but "
                    f"SCRAPER_PROXY_API_KEY isn't set; fetching directly (likely to fail)."
                )
            response = requests.get(url, headers=request_headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except requests.RequestException as e:
        logging.error(f"Error fetching {url}: {e}")
        return None
