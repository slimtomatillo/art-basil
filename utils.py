import datetime as dt
import json
import numpy as np
import logging
import re
import requests
from bs4 import BeautifulSoup
from config import DB_FILES
import os
import tempfile
import time
from urllib.parse import urlparse

import certifi

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
    # Marin Civic Center (WEBSITE-81): Cloudflare 403s scripted requests from any connection (a browser
    # is fine). premium_proxy alone was tried first and ZenRows answered 422 in CI (2026-11-05), so this
    # adds js_render (25 credits per request, about 190 a month). Not live-tested with it yet.
    'www.marincounty.gov': {'premium_proxy': 'true', 'js_render': 'true'},
    # Asian Art Museum: began 403ing GitHub Actions' IPs on 2026-10-21 (Cloudflare);
    # still fine from a normal connection. A static WordPress site, so a premium
    # proxy IP without JS rendering should be enough - not live-tested yet, the
    # ZenRows account was out of credits when this was added.
    'exhibitions.asianart.org': {'premium_proxy': 'true'},
    # Art Museum at the University of Toronto (WEBSITE-87): 403s scripted requests from
    # any connection (a browser is fine). A server-rendered WordPress site, so premium
    # proxy alone is tried first - not live-tested; if CI still gets a 403, add js_render.
    'artmuseum.utoronto.ca': {'premium_proxy': 'true'},
    # Armory Center for the Arts (WEBSITE-90): fine from a normal connection, 403s
    # GitHub Actions' IPs (seen 2026-11-04). Premium proxy alone worked on the first refresh, then
    # ZenRows answered 422 ("try enabling javascript rendering") in CI on 2026-11-08, so js_render
    # is added (25 credits a request, about 190 a month). Not live-tested with it yet.
    'www.armoryarts.org': {'premium_proxy': 'true', 'js_render': 'true'},
    # Galerie Simon Blais (Montreal): 403s GitHub Actions' IPs on every run since 2026-11-06 (fine from
    # a normal connection). A server-rendered page, so premium proxy alone is tried first (10 credits,
    # about 76 a month) - not live-tested (no proxy key locally); if ZenRows answers 422 or CI still
    # gets a 403, add js_render as for Marin Civic Center.
    'galeriesimonblais.com': {'premium_proxy': 'true'},
}
# Sites whose server doesn't send its intermediate certificate: browsers fetch it themselves, Python
# fails with "unable to get local issuer certificate". The intermediates (public CA certificates) are
# kept in certs/intermediates.pem and added to the standard roots for these hosts only; verification
# stays on. (A site with an expired certificate or a broken TLS setup is not fixable this way.)
EXTRA_CA_HOSTS = ('theimagecentre.ca',)
INTERMEDIATES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'certs', 'intermediates.pem')
_ca_bundle = None


def verify_for(url):
    """The `verify` argument for requests.get(url): True, or for a host in EXTRA_CA_HOSTS a CA bundle of
    the standard roots plus certs/intermediates.pem."""
    global _ca_bundle
    host = urlparse(url).netloc.lower()
    if not any(host == h or host.endswith('.' + h) for h in EXTRA_CA_HOSTS):
        return True
    if _ca_bundle is None:
        with open(certifi.where()) as roots, open(INTERMEDIATES_FILE) as extra:
            bundle = tempfile.NamedTemporaryFile('w', suffix='.pem', delete=False)
            bundle.write(roots.read() + '\n' + extra.read())
            bundle.close()
        _ca_bundle = bundle.name
    return _ca_bundle

ZENROWS_API_URL = 'https://api.zenrows.com/v1/'
ZENROWS_API_KEY = os.environ.get('SCRAPER_PROXY_API_KEY')

# Set once ZenRows answers 402 (account out of credits). Every later proxied
# request in the run would fail the same way, so fetch_and_parse stops sending
# them and main.py skips the remaining proxied scrapers.
PROXY_EXHAUSTED = False

# Proxied venues are refreshed about every PROXY_REFRESH_DAYS days (main.py). Their
# "past exhibitions" pages change rarely but cost as much as any other page, so they
# are pulled on every second refresh only, about every 8 days. Which refreshes those
# are comes from the calendar (no stored state): a venue's refreshes fall 4 days
# apart, so they alternate between even and odd 4-day blocks.
PROXY_REFRESH_DAYS = 4

# main.py sets this while it runs a venue that was named on the command line
# (--venues), which always fetches everything.
FORCE_PAST_PAGES = False

def past_pages_due(env='prod', today=None):
    """True if a proxied scraper should fetch its past-exhibition pages in this run."""
    if env != 'prod' or FORCE_PAST_PAGES or not ZENROWS_API_KEY:
        return True    # dev runs, named venues and direct (free) fetches always get everything
    today = today or dt.date.today()
    return (today.toordinal() // PROXY_REFRESH_DAYS) % 2 == 0

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

# Some sites answer a runner they distrust with a "200 OK" bot-check page instead of an error, so the scraper
# finds no shows and reports only "no exhibitions found". Say what the page really was.
BLOCK_PAGE_TITLE_RE = re.compile(
    r'just a moment|attention required|access denied|are you (?:a )?(?:human|robot)|verify you are (?:a )?human|'
    r'security check|captcha|request blocked|forbidden|too many requests', re.IGNORECASE)


def _warn_if_block_page(url, soup):
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    if BLOCK_PAGE_TITLE_RE.search(title):
        logging.warning(f"{url} answered with what looks like a bot-check or block page (title {title[:80]!r}); "
                        "the site may be blocking this connection.")


def fetch_json(url, query=None, headers=None):
    """GET `url` (or, with `query`, POST it as a GraphQL query) and return the parsed JSON, or None
    if the request fails or the answer isn't JSON. For sites that load their shows from a public
    JSON endpoint instead of putting them in the page (these are not routed through the proxy)."""
    request_headers = {'User-Agent': 'Mozilla/5.0', **(headers or {})}
    try:
        if query is not None:
            response = requests.post(url, json={'query': query}, headers=request_headers,
                                     timeout=REQUEST_TIMEOUT, verify=verify_for(url))
        else:
            response = requests.get(url, headers=request_headers, timeout=REQUEST_TIMEOUT, verify=verify_for(url))
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as e:
        logging.error(f"Error fetching {url}: {e}")
        return None


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
            if response.status_code >= 400 and response.status_code != 402:
                # ZenRows explains a refusal in the body (e.g. a 422 for a site its basic options can't
                # get past); without it the log only says "Unprocessable Entity"
                logging.error(f"ZenRows refused {url} ({response.status_code}): {response.text[:300]}")
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
            response = requests.get(url, headers=request_headers, timeout=REQUEST_TIMEOUT, verify=verify_for(url))
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        _warn_if_block_page(url, soup)
        return soup
    except requests.RequestException as e:
        logging.error(f"Error fetching {url}: {e}")
        return None
