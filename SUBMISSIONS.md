# Handling submitted events

People submit events by emailing `info.artbasil@gmail.com` with the fields
listed on `docs/add_event.html`:

| Form field | Maps to |
|---|---|
| Region | `region` (`sf`, `la`, `mtl`, `tor`, `ist`) |
| Event Title | `name` |
| Venue | `venue` |
| Event Type | folded into `tags` (e.g. `exhibition`, `workshop`, `talk`) |
| Start/End Dates | `start_date` / `end_date` (`YYYY-MM-DD`) |
| Start/End Time | not stored — the DB has no time field, only dates |
| Tags | `tags` — canonical list is `docs/tags.html` |
| Price | `free` tag if free; otherwise not currently tracked |
| Link to event page | a `links` entry with `"description": "Event Page"` |
| Any other relevant links | additional `links` entries (RSVP, Instagram, artist site, ...) |
| Comments/notes | folded into `description`, trimmed to a sentence or two |

`submissions.py` does the mechanical part — writing to the right
`<region>_events.json` / `<region>_venues.json` with the correct schema, hash,
and `last_updated`, and refusing to add something that looks like a duplicate.
It does **not** replace judgment: read the submission and the linked event
page yourself first.

## Judgment calls the script can't make

- **Verify against the source.** Don't trust the submission text alone —
  open the linked event page and confirm dates, venue name/address, and
  pull an image if one's available (add it as a `links` entry with
  `"description": "Image"`).
- **New venue?** If `venue` isn't already in `<region>_venues.json`, you need
  its address (`venue_address`). Check the linked event page or search for it.
- **Multi-event submissions.** A submission can imply more than one event
  (e.g. an exhibition + a separately-timed opening reception). Decide
  whether that's one entry (reception folded into tags/description) or two —
  there's no fixed rule; use judgment based on how distinct they are.
- **Duplicates.** The script fuzzy-matches the new title against existing
  event names at the same venue and refuses to write if something looks
  close (ratio ≥ 0.6). If it's a false positive, re-run with `force=True`
  (or `--force` on the CLI).

## Running it

As a script, from a JSON file matching the submission:
```bash
python submissions.py --json path/to/submission.json
```

JSON shape:
```json
{
  "region": "sf",
  "name": "Event Title",
  "venue": "Venue Name",
  "venue_address": "Street, City, ST",
  "start_date": "2026-10-01",
  "end_date": "2026-11-12",
  "description": "One or two sentences.",
  "tags": ["exhibition", "opening", "free"],
  "links": [
    {"link": "https://example.com/event", "description": "Event Page"},
    {"link": "https://example.com/image.jpg", "description": "Image"}
  ]
}
```
`venue_address` is only required the first time a venue is submitted.
`start_date`/`end_date`/`description`/`tags`/`links` are all optional.

Or import it directly and call `add_submission(...)` with the same fields
(this is the more convenient path when going straight from a pasted email —
build the call from the email's fields rather than writing a JSON file first).

## After adding

Reply to the submitter using the template kept in the top-level project
folder (`SUBMISSION_RESPONSE_TEMPLATE.md`, outside this repo) — link to the
matching region page, e.g. `https://artbasil.info/sf/index.html`.
