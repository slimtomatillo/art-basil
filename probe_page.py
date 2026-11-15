"""Fetch one page through the paid ZenRows proxy and save what comes back, to see how a blocked site answers.

Used by the "Probe page" workflow (.github/workflows/probe-page.yml), because the proxy key only exists on GitHub:

    python probe_page.py URL [name=value ...]     e.g.  python probe_page.py https://diaart.org/exhibitions js_render=true

Each name=value is a ZenRows option (premium_proxy is always on). It spends credits (10, or 25 with js_render), prints the
status, the page's title and size and its exhibition links, and writes the HTML to probe_page.html. Nothing else is saved.
"""
import re
import sys

import requests
from bs4 import BeautifulSoup

import utils


def main(argv):
    if len(argv) < 2 or not utils.ZENROWS_API_KEY:
        print('usage: python probe_page.py URL [name=value ...]  (needs SCRAPER_PROXY_API_KEY)')
        return 2
    url = argv[1]
    params = {'premium_proxy': 'true', **dict(arg.split('=', 1) for arg in argv[2:])}
    response = requests.get(utils.ZENROWS_API_URL, params={'url': url, 'apikey': utils.ZENROWS_API_KEY, **params}, timeout=120)
    print(f'{url} with {params}: HTTP {response.status_code}, {len(response.content)} bytes')
    with open('probe_page.html', 'wb') as f:
        f.write(response.content)
    soup = BeautifulSoup(response.content, 'html.parser')
    print('title:', soup.title.get_text(' ', strip=True) if soup.title else None)
    links = []
    for a in soup.find_all('a', href=True):
        if re.search(r'exhibit|on-view|current|upcoming', a['href'], re.IGNORECASE):
            row = f"{a['href'][:100]} | {' '.join(a.get_text(' ').split())[:90]}"
            if row not in links:
                links.append(row)
    print('\n'.join(links[:40]))
    print('text:', ' '.join(soup.get_text(' ').split())[:600])
    return 0 if response.ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
