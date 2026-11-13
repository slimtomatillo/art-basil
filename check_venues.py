"""Try some venues' scrapers on their own and list what they found, without touching the real data.

    python check_venues.py nyc "Cooper Hewitt" "The Jewish Museum"
    python check_venues.py nyc "Cooper Hewitt,The Jewish Museum"        # commas work too (the CI form)

The scrapers run exactly as in a daily run (main.py), but the region's events file is swapped for a temporary one, so
nothing is written to docs/data, and no summary, health check or description/picture pass runs. What each scraper
found is printed: the shows with their phase, dates, and whether each has a description and a picture. Exit status 1
if a scraper crashed or a venue found nothing.

A venue that goes through the paid ZenRows proxy is refused (naming it would spend credits): pass --allow-proxy to run
it anyway. The "Check scrapers" workflow (.github/workflows/check-scrapers.yml) runs this on GitHub's servers, which is
how to find out whether a site that loads fine from a laptop is blocked there (ADDING_A_REGION.md, 2a).
"""
import argparse
import json
import logging
import os
import sys
import tempfile

import config


def venue_names(args):
    """The venue names from the command line: each argument may hold several, separated by commas."""
    names = []
    for arg in args:
        names += [name.strip() for name in arg.split(',') if name.strip()]
    return names


def proxied(names):
    """The named venues that go through the paid proxy (main.PROXIED_VENUES lists the venues each scraper writes)."""
    import main
    paid = {venue for venues in main.PROXIED_VENUES.values() for venue in venues}
    return [name for name in names if name in paid]


def run(region, names, quiet=False):
    """Run the named venues' scrapers against a temporary events file. Returns (failed scrapers, {venue: [events]})."""
    import main
    folder = tempfile.mkdtemp(prefix='check-venues-')
    path = os.path.join(folder, f'{region}_events.json')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('{}')
    original = config.DB_FILES[region]
    config.DB_FILES[region] = path
    try:
        failed = main.main(env='prod', selected_regions=[region], selected_venues=names, write_summary=False)
        with open(path, encoding='utf-8') as f:
            db = json.load(f)
    finally:
        config.DB_FILES[region] = original
    return failed, {venue: list(events.values()) for venue, events in db.items()}


def report(names, found):
    """Print one block per venue and return how many found nothing."""
    empty = 0
    for name in names:
        events = found.get(name, [])
        print(f"\n{name}: {len(events)} show{'' if len(events) == 1 else 's'}")
        if not events:
            empty += 1
        for e in sorted(events, key=lambda e: (e.get('phase') != 'current', str(e['dates'].get('start')), e['name'])):
            picture = any(l.get('description') == 'Image' for l in e.get('links', []))
            dates = f"{e['dates'].get('start') or '...'} to {e['dates'].get('end') or '...'}"
            print(f"  {e['phase']:7} {dates:25} desc={'yes' if e.get('description') else 'no ':3} picture={'yes' if picture else 'no'}  {e['name'][:70]}")
    return empty


def main_cli(argv=None):
    parser = argparse.ArgumentParser(description="Run some venues' scrapers and list what they found (writes nothing).")
    parser.add_argument('region', help='the region, e.g. nyc')
    parser.add_argument('venues', nargs='+', help='venue names (quote them; commas may separate several)')
    parser.add_argument('--allow-proxy', action='store_true', help='run a venue even if it goes through the paid proxy')
    args = parser.parse_args(argv)
    names = venue_names(args.venues)
    import main
    scrapers, venue_to_region = main.get_venue_scrapers()
    unknown = [n for n in names if venue_to_region.get(n) != args.region]
    if args.region not in config.DB_FILES or unknown:
        parser.error(f"unknown region or venue(s) {unknown or args.region!r} for {args.region!r}. "
                     f"Venues: {', '.join(sorted(v for v, r in venue_to_region.items() if r == args.region))}")
    paid = proxied(names)
    if paid and not args.allow_proxy:
        parser.error(f"{', '.join(paid)} go through the paid ZenRows proxy; --allow-proxy runs them anyway (it spends credits)")
    failed, found = run(args.region, names)
    empty = report(names, found)
    print()
    for _, venue, why in failed:
        print(f"CRASHED: {venue}: {why}")
    return 1 if failed or empty else 0


if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING)
    sys.exit(main_cli())
