# JavaScript Refactoring Documentation

## Overview
The JavaScript code has been refactored from a single monolithic `scroll.js` file into multiple focused modules for better maintainability, testability, and code organization.

## New File Structure

### 1. `dataManager.js`
**Purpose**: Handles data fetching and region detection
**Functions**:
- `getRegion()` - Detects current region (SF/LA/MTL/TOR/IST) from URL
- `fetchVenues()` - Fetches venue data from JSON files
- `fetchEvents()` - Fetches event data from JSON files, then brings each event's phase/tags up to date for the visit (`applyRegionPhases`)
- `regionToday(region)` - Today's date (`YYYY-MM-DD`) in the region's time zone
- `derivePhase(start, end, today)` / `applyRegionPhases(events, region)` - Work out upcoming/current/past from the dates in the venue's time zone; phases only move forward. Mirrors `update_event_phases` in `processing.py`

**Usage**:
```javascript
const venues = await window.dataManager.fetchVenues();
const events = await window.dataManager.fetchEvents();
```

### 2. `eventSorter.js`
**Purpose**: Handles event sorting and priority assignment
**Functions**:
- `sortEvents(events)` - Sorts events by priority and date

**Usage**:
```javascript
const sortedEvents = window.eventSorter.sortEvents(unsortedData);
```

### 3. `tableRenderer.js`
**Purpose**: Handles table creation and event row rendering
**Class**: `TableRenderer`
**Methods**:
- `renderEventRow(event)` - Renders a single event row
- `setVenues(venues)` - Sets venue data for map links
- `clearTable()` - Clears the table content

**Usage**:
```javascript
const renderer = new window.TableRenderer('event-list');
renderer.setVenues(venues);
renderer.renderEventRow(event);
```

### 3b. `venueAddresses.js`
**Purpose**: The pure logic (no DOM, unit tested in Node) behind a venue's address(es) and map links. A venue's value in `<region>_venues.json` is a street address string, or a list of `{label, address}` for a venue with more than one space.
**Functions**:
- `normalize(value)` - any accepted shape -> a list of `{label, address}` (empty if there is no usable address)
- `mapLinks(value)` - one map link per address: `{text, href, appleHref, title}` (`href` is Google Maps, `appleHref` the same place in Apple Maps). One address gives plain "Map"; several give "Map: <label>"
- `isAppleDevice(navigator)` - true on an iPhone, iPad or Mac (read from the user agent only)

`tableRenderer.js` (the "Map" link under each event) and `venuesRenderer.js` (the venue directory) both use it, so load `venueAddresses.js` before them (after `dataManager.js`) on every region page and venues page.

### 3c. `mapChoice.js`
**Purpose**: On an iPhone, iPad or Mac, clicking a "Map" link opens a small "Apple Maps / Google Maps" choice instead of going straight to Google Maps. Everywhere else it does nothing and the link goes to Google Maps. `mapChoice.attach(anchor, mapLink)` is called by `tableRenderer.js`, `venuesRenderer.js` and the map pin popups in `mapView.js`; load `mapChoice.js` after `venueAddresses.js` on every region page and venues page. The link keeps its Google href, so a middle or Ctrl/Cmd-click and no-JavaScript still work. Escape, a click elsewhere, scrolling or choosing an app closes it. Tested in `tests/mapChoice.test.js`.

### 3d. `venueSuggest.js`
**Purpose**: Venue names offered under the search box as the visitor types (a combobox: `role="combobox"` on the box, a `listbox` of options, `aria-activedescendant`, and a polite status line). Picking one (click, or the arrow keys and Enter) calls `SearchManager.setVenue(name, { clearSearch: true })`: the "@ Venue" pill appears and the box is emptied. Typing and pressing nothing else is the same text search as before. The matching is `filterState.suggestVenues(counts, typed, limit)` (pure, tested): two letters are needed, a name matches by its start or any word's start (accents and case ignored), whole-name matches first, then names that start with it, then a word inside, then most shows, then A to Z; at most six. The counts come from `SearchManager.venueCounts()`: the shows each venue has under the current filters (apart from the search text and the venue), so a suggested venue always shows something. `SearchManager.initSearchBar` makes it if `window.VenueSuggest` exists, so load `venueSuggest.js` before `scroll.js` on the region pages (not the venues pages, which have no search box). Escape closes the list, leaving the box closes it, and nothing from the data is set as HTML. Tested in `tests/venueSuggest.test.js`. The venue's name in a Map view popup is a link too (`MapView.venueLink`), which filters to that venue and stays in Map view (`?venue=...&view=map`).

### 4. `filterState.js` and `searchManager.js`
**Purpose**: The event filters (search text, phase, ongoing, dates, area, tags) and the table rows they show or hide.

`filterState.js` holds the **pure logic**, with no DOM access, so it is unit tested in Node (`node --test tests/`):
- `TAG_GROUPS` - the tag groups offered as dropdowns (Medium, Theme, Cost, Format). Keep in step with `docs/tags.html` and `APPROVED_TAGS` in `tagging.py`; a test checks the tags are documented
- `parseUrl(search)` / `toQuery(state)` - filters <-> URL (`?q=text&phase=past&tags=photography,latinx`), so a view can be bookmarked or shared. `phase` is one or more of `current`, `ongoing`, `future`, `past` (e.g. `phase=current,past`). The older `?search=Venue` (used by `venues.html`) is still read, and means "every phase"
- **When** is a multi-select over four mutually exclusive buckets: `current` (on view, has an end date), `ongoing` (on view, no end date - `bucketOf(phase, ongoing)`), `future` and `past`. Ticking all four shows everything (there is no separate "All" and no separate "include ongoing" checkbox). **The default is current + ongoing + future**, not the long archive. At least one must stay ticked
- **Dates** (WEBSITE-94) are a second choice inside the When dropdown, "Open on": a quick pick (`today`, `weekend`, `week` = the next 7 days, `closing` = current shows ending in the next 14 days, `opening` = upcoming shows starting in the next 14 days) or two days of the visitor's own. In the URL: `?when=weekend`, or `?from=2026-12-15&to=2026-12-20` (no `to` is one day; a `to` before the `from` is swapped; bad dates are ignored). A quick pick is relative, so a shared "this weekend" link stays "this weekend". **A chosen date replaces the When phases** (a show open on a given day may be past today), and the panel greys the phases out. `timingWindow(timing, today)` turns a pick into days and `timingMatches` decides: a show is open if its run overlaps the days; no end date means open from the start; no dates at all means open if it is on view now (the ticket's "treat ongoing and no-end shows as open"); a past show with no end date is not known to be open. `today` is in the state (`state.today`, the region's today from `dataManager.regionToday`) and is not in the URL
- **Venue** is not a dropdown (the Bay Area alone has 56 venues with shows). The venue's name in each row's "title @ venue" cell is a link (`TableRenderer.venueLink`): a click calls `SearchManager.setVenue(name)`, which shows only that venue's shows, as a removable "@ Venue" pill in the summary line; `?venue=The%20Broad` is the same view as a link, and the venue directory links use it. It matches the venue's *whole name* (`filterState.venueMatches`, accents and case ignored), unlike the search text, which matches words anywhere (so "Broad" finds nothing as a venue, but any show mentioning "broad" as a search). A `?venue=` link with no `phase` shows every date, like a search; clicking a name in the page keeps the visitor's When choice. The older `?search=Name` links still work (they are read as a search).
- **Area** is its own dropdown, `?area=east-bay,north-bay`, for the regions that have an `AREAS` entry: the Bay Area (San Francisco, East Bay, Peninsula, South Bay, North Bay; the Peninsula is San Mateo County plus Palo Alto and Stanford, the South Bay the rest of Santa Clara County; found from the city before `, CA`) Los Angeles (Hollywood and Mid-Wilshire, Westside, Downtown and South LA, Pasadena and San Gabriel Valley; the city of Los Angeles holds most venues, so it is split by the ZIP code after `, CA` (`zips`), and the towns around it (Santa Monica, Pasadena, Long Beach...) by name; Long Beach has one venue and goes with Downtown and South LA) and Istanbul (one area per district, found from a part of the address such as `34433 Beyoğlu` or `Kadıköy/İstanbul`; accents and case ignored, and only a whole part counts, so a street named for another district does not move a venue). `AREAS` lists each area's cities, ZIPs or districts, and `areasOfAddresses(region, addresses)` finds a venue's areas from them in its addresses (`tableRenderer.js` writes them to each row's `data-areas`, with `data-start` and `data-end`). **A new venue in a new town (Bay Area), ZIP or town (Los Angeles) or district (Istanbul) needs it added to `AREAS.sf` / `AREAS.la` / `AREAS.ist`, and every LA address needs a ZIP**: a test over the real venues file fails until it is, the way the coordinates check does. `AREAS.ist` already lists the Asian-side districts (Kadıköy, Üsküdar, Ataşehir, Ümraniye, Maltepe, Kartal, Beykoz) and more European ones, so a venue there gets its own area with no code change; the dropdown offers only areas that have shows. Venues no longer in `sf_venues.json` (the closed Cartoon Art Museum's old events) have no area, so choosing an area hides them. Regions with no `AREAS` entry (Toronto and Montreal: one city, or one building, holds nearly everything) have no Area dropdown, and `areasOfRegion` drops an `?area=` that is not this region's
- Not built (WEBSITE-94): a **venue filter** (the search box already matches venue names, `venues.html` links into it, and a 50-item dropdown suits a phone badly) and a rename of "Theme" (kept)
- `rowMatches(row, state)` - the matching rule: tags in the same group widen the results (photography OR painting), tags in different groups narrow them (photography AND latinx), and a tag outside every group (e.g. `museum`) must always match
- `countTags(rows, state)` / `countPhases(rows, state)` / `countTimings(rows, state)` / `countAreas(rows, state, region)` - the counts shown beside each option in the dropdowns

`searchManager.js` (`SearchManager`) owns the live state: it reads the URL on load, shows/hides rows, keeps the buttons, search box and tag chips in sync, and rewrites the URL (`replaceState`, so the back button isn't filled with every keystroke). `FilterPanel` subscribes to it.

**Usage**:
```javascript
// The search manager is automatically initialized by scroll.js
window.searchManager.setSearchTerm('exhibition');
window.searchManager.togglePhase('past');          // tick/untick one phase in the When filter
window.searchManager.setPhaseFilter('upcoming');   // or set them: a phase, a list, 'upcoming' (current+future) or 'all'
window.searchManager.toggleTagFilter('photography');
window.searchManager.setTiming({ pick: 'weekend' });                    // a date: { pick }, { from, to } or null for any
window.searchManager.setTiming({ from: '2026-12-15', to: '2026-12-20' });
window.searchManager.toggleArea('east-bay');                            // the Bay Area, Los Angeles, Istanbul
window.searchManager.clearFilters();               // back to the default view
```

### 4b. `filterPanel.js`
**Purpose**: Draws the filter controls from `SearchManager`'s state: a single row of independent dropdowns: **When** (Current / Ongoing / Future / Past, with a one-line hint under Current and Ongoing, and under them "Open on": Any date, today, this weekend, next 7 days, closing soon, opening soon, and From / To date fields) first, then **Area** on the Bay Area, Los Angeles and Istanbul pages, then one per tag group in `TAG_GROUPS` (Medium, Theme, Cost, ...). Each opens a popover of checkboxes with counts, and its button shows a badge with how many of its options are selected (for When, only when it differs from the default; a chosen date shows 1). The count line names a chosen date instead of the phases ("open this weekend"), and each date and area gets a pill. Only one popover is open at a time; a click outside or Escape closes it. On phones the row still fits on one line and the popover opens full width underneath. Below the row is the "Showing X of Y events" line, a removable pill for each active filter, and "Clear all".

A group with no tags in a region's data gets no dropdown (so "Cost" only appears where events carry `free`, and "Format" stays hidden until some events carry its tags). Anything the visitor typed (the search text can come from a shared URL) is inserted as text, never as HTML.

### 4c. `nearMe.js` and `nearMeControl.js` ("Use my location")
**Purpose**: Lets a visitor see how far each show is from them and sort nearest first (WEBSITE-104). Works in the event list; the map epic (WEBSITE-76) reuses it for the "you are here" marker.

`nearMe.js` holds the **pure logic**, with no DOM access, so it is unit tested in Node (`node --test tests/`):
- `distanceKm(a, b)` - great-circle distance between two `{lat, lng}` points. Distances are straight-line, so the page calls them approximate
- `unitsFor(region)` / `UNITS` - miles for `sf` and `la`, kilometres for `mtl`, `tor` and `ist`. **Every region needs an entry** (a test checks `region_bounds.json` against it), so a new city is a decision, not a silent default
- `formatDistance(km, units)` - "1.4 mi", "12 mi", "1,234 km", "<0.1 km"
- `nearestKm(user, points)` / `distancesByVenue(user, coordinates)` - a venue with two addresses is as far as its nearest one; a venue with no coordinates has no distance (`null`)
- `isFarFromRegion(user, box)` - more than 100 km from the region's bounding box (`docs/data/region_bounds.json`): the page says how far instead of putting "2,500 mi" on every row, and does not reorder
- `orderByDistance(items, distanceOf)` - nearest first; items with no distance last; ties keep the page's usual order

`nearMeControl.js` (`NearMeControl`) is the DOM part, created by `scroll.js` after the filter panel:
- Adds a **Use my location** button to the filter bar with a small **(i)** beside it: the icon opens a bubble saying the location stays in the browser (click, tap or Enter; Escape or a click elsewhere closes it; the button's tooltip says the same). A one-line note under the bar appears only while there is something to say (finding you, an error, the distances' caveat) and takes no room otherwise. After a location is shared, the button becomes a **Nearest first** toggle (on by default) with a **Turn off** link, each row's Links cell shows "0.4 mi away" (the `.event-distance` span `tableRenderer.js` leaves in it, empty and hidden), and the rows are reordered. Turning it off restores the usual order. Filters keep working: hidden rows are reordered too
- **Nothing is requested until the visitor clicks.** Then it loads `venue_coordinates.json` and `region_bounds.json` (static files, once; `dataManager.fetchNearMeData()`), so the default page is no heavier
- **Privacy**: the position is used to work out each venue's distance. It is kept in memory only while distances are on (the "you are here" dot on Map view needs it, via the `onLocation` callback) and dropped when the visitor turns them off. It is never put in storage or a cookie or the URL, never sent anywhere, and not in the analytics data. Reloading forgets everything. Keep it that way: no `localStorage`, no `?lat=`, nothing in `gtag`
- `onLocation(point | null)` is called after a location is shared and with `null` on **Turn off**; `scroll.js` uses it to move the map's dot. `distanceTextFor(venue)` gives a venue's "0.4 mi away" (or `null`) for the map popup
- Outcomes it handles, each with a short message and the page still usable: permission denied, position unavailable, timed out (10 s), venue data failed to load (retry works), and far from the region
- `SearchManager`'s row model carries `index` (the usual order), `venue` (from the row's `data-venue`) and `distanceEl`, which is how the control finds its rows
- Needs HTTPS (GitHub Pages is; `localhost` is fine) and a browser with `navigator.geolocation`; without it no button is added

**Testing it by hand**: in the browser console, replace what the browser would answer, then click the button: `Geolocation.prototype.getCurrentPosition = (ok) => ok({ coords: { latitude: 37.8044, longitude: -122.2712 } })` (call `err({ code: 1 })` for "denied", `3` for "timed out").

### 4d. `mapView.js` ("List view | Map view")
**Purpose**: The "List view | Map view" toggle on the results line (beside "Showing X of Y events"; full width above the count on a phone) and the map behind it (WEBSITE-102) and the pins on it (WEBSITE-103). Part of the map epic WEBSITE-76.

- The table is the default view. The choice is part of the URL state: `filterState.parseUrl` / `toQuery` carry `view` (`?view=map`, written only for the map), and `SearchManager.setView('list' | 'map')` changes it, so a Map view can be shared and keeps the other parameters (`?q=...&phase=...&tags=...&view=map`). The view is not a filter: `isDefault` ignores it and "Clear all" keeps it. Existing links (`?search=`, `?tags=`, `?phase=`) have no `view`, so they open on the list
- `MapView` subscribes to `SearchManager`. Map view hides the table (the `map-view-on` class on `<body>`; the "Showing X of Y" line and the filter pills stay) and shows a `<section class="map-view">`: the map, then a one-line privacy note beside MapLibre's own attribution
- **Nothing is requested until Map view is opened.** The first open loads the pinned MapLibre GL JS from `docs/vendor/maplibre-gl/` (our own site, see its README for the version, hashes and how to update it) with `import()`, then `region_bounds.json`, then the tiles. The map is built once and reused when the visitor goes back and forth
- The map opens framed on the region's box (`docs/data/region_bounds.json`), with `cooperativeGestures` (two fingers to pan, so a one-finger swipe still scrolls the page on a phone), zoom buttons and the attribution control (it must stay on)
- **The tile provider is one constant**, `MAP_STYLE_URL` at the top of `mapView.js` (OpenFreeMap's "positron" style). See `OPERATIONS.md`, "The map", for what to do if it goes away
- **It never leaves an empty box.** If WebGL is missing, the library or the style can't load (offline, blocked), or nothing has loaded after 15 s of the tab being visible, it removes the map, goes back to the list (which also puts the URL right) and shows a short note beside the filters. The next click on Map view tries again. A tab in the background draws no frames, so the timeout waits until it is visible again. Once the map has loaded, a single failed tile is just a gap
- **Pins** (`mapPins.js` works out what goes where; `mapView.js` draws it). One pin per **location**: venues that share an address share a pin, and a venue with two addresses gets a labelled pin at each. Every number is a count of **shows**, not venues. A cluster adds up its pins' `weight` (`clusterProperties`), and a two-address venue's shows are weighted only at its first pin so they are counted once. Clusters zoom in when clicked; a pin opens a popup (built with `createElement`/`textContent` only, so nothing from the data is ever HTML) listing its venues, shows with dates and links, and the distance when Near me is on
- The pins follow the filters: `SearchManager.matchingRows()` gives the rows that match, the map re-draws only when the pin signature changes (and re-frames only then, so a popup is not lost to an unrelated change). The line above the map says "51 places · 213 shows" and matches the results count; shows whose venue has no coordinates are not pinned and are counted in that line with a pointer to the list view. With nothing matching it says so and offers "Clear all"
- **"Places on the map"** is a `<details>` list of every pin, reachable by keyboard (Enter opens it, Tab to a place, Enter shows it on the map). It is the non-pointer way to use the map
- **"You are here"**: when Near me is on, the map shows a blue dot and frames the nearest few places plus you. The position is held in memory only while Near me is on (see 4c)
- **Phone, touch and keyboard** (WEBSITE-105). Things that are easy to undo by accident:
  - *Taps are forgiving.* A pin is 26 px across and a fingertip is not, so there is one `click` and one `mousemove` handler on the whole map (not one per layer): `featureNear` looks `MAP_TAP_PADDING` (12 px) around the tap on both pin layers and takes the nearest pin or cluster
  - *A popup always fits the map.* Its width is at most `MAP_POPUP_MAX_WIDTH` (340 px) but never more than the map less 48 px, and its height is capped to what the map leaves room for. MapLibre decides which side of the pin to open on from the pin's position alone, so on a short phone map it can still run off an edge: `keepPopupInView` then pans the map by just what brings it back inside (8 px margin). Opened from the places list, that waits for the flight to finish
  - *Choosing a place from the list flies to zoom 15*, not 14.5: pins still cluster at 14.x, which hid the very pin that had been chosen (`MAP_CLUSTER_MAX_ZOOM` is the last zoom that clusters, and a zoom of 14.5 counts as 14)
  - *Focus is not lost.* Closing a popup with Escape or its own close button puts the keyboard back on the place in the list it was opened from (or on the map, for a popup opened from a pin). Without that, focus falls to the top of the page
  - *Fingertip-sized targets*: one block in `styles.css`, under `@media (max-width: 768px), (pointer: coarse)`, enlarges MapLibre's zoom buttons (40 px), the popup's close button (36 px), the rows of the places list, the links in a popup and the (i) beside "Use my location". MapLibre's own defaults are 29 px, 21 px and (for a line of list text) 22 px
  - *Page scrolling is not trapped*: `cooperativeGestures` leaves the canvas at `touch-action: pan-x pan-y`, so one finger scrolls the page and two move the map. Check that if the map library is ever updated
  - *Announcements*: the toggle is a labelled group of `aria-pressed` buttons; the pin summary, the Near me message and the "went back to the list" message are `role="status"`; the map section has `aria-label="Map of venues"`. The places list is the non-pointer way to everything a pin does
- `scroll.js` creates it after the filter panel and "Use my location"; `window.mapView` is there for debugging. `dataManager.fetchNearMeData` is memoized so Near me and the map share one load of the coordinates

**Testing it by hand**: serve `docs/` (for example `python3 -m http.server -d docs`) and open `/sf/?view=map`. To see a failure, in the console set `mapView.loadLibrary = async () => { throw new Error('x') }` or `mapView.styleUrl = 'http://localhost:8000/missing.json'` before clicking Map view. (A browser tab that isn't in front may not draw frames, so a map can sit on "Loading" there until you look at it.)

**Checking the phone layout by hand**: set the browser to 375 px wide (the toggle, the map at about 343 × 568, no sideways scroll), open a pin, and confirm the popup is fully inside the map. `mapView.featureNear({ x, y })` in the console says what a tap at that point of the map would hit (try 8 and 20 px beside a pin, then 40). Tab through the page: every stop should show a focus ring, and Escape on a popup opened from "Places on the map" should leave focus on that place.

### 5. `modalManager.js`
**Purpose**: Handles modal functionality
**Class**: `ModalManager`
**Methods**:
- `openImageModal(imageSrc)` - Opens image modal
- `closeImageModal()` - Closes image modal
- Generic modal methods for future use

**Usage**:
```javascript
window.modalManager.openImageModal('image-url.jpg');
```

### 6. `scroll.js` (Refactored)
**Purpose**: Main orchestrator that coordinates all modules
**New Role**: 
- Waits for all modules to load
- Coordinates data fetching, sorting, and rendering
- Much simpler and focused

### 7. Legacy Files (Deprecated)
- `filter.js` - Functionality moved to `searchManager.js` / `filterState.js`
- Other files remain unchanged:
  - `notify.js` - The Notify Me modal ("Add to calendar"): shows the event, takes the type (opening day, closing day, full run) and the calendar, then opens the link or downloads the `.ics`; the calendar last used is kept in this browser (`localStorage` key `artbasil.calendar`). Needs `calendarLinks.js` loaded first
  - `calendarLinks.js` - The pure logic behind it (no DOM, unit tested in `tests/calendarLinks.test.js`): `resolve(event, type)` gives the title, days and link; `googleUrl`, `outlookUrl` (work, school and Microsoft 365 accounts, outlook.office.com; the personal-account host, outlook.live.com, sends a work account to a login page, and personal Outlook.com users are better served by the `.ics`, so only this one is offered and the modal labels it "Outlook (work or school)"), `yahooUrl` and `icsText` build the targets. Outlook takes its body as HTML, so its line breaks are `<br>` and the text is escaped. Entries are all-day and end on the exclusive next day; dates are handled as `YYYY-MM-DD` strings and UTC so the day never shifts. The `.ics` carries its own alerts at 9:00 in the person's time zone (opening day: the day before; closing day: a week before and on the day; full run: a week before it closes and on the closing day), so their calendar app does the reminding and the site needs no backend. Email and text reminders are a separate matter (WEBSITE-41, WEBSITE-42, spike WEBSITE-113)
  - `feedback.js` - Feedback dialog; sends through `web3forms.js` (needs it loaded first)
  - `web3forms.js` - Sends form submissions to the site inbox via Web3Forms; holds the access key (see OPERATIONS.md, "Forms and feedback")
  - `siteForms.js` - Validation, sending state and messages for the Add Event page's forms
  - `cursorFx.js` / `cursorFx.css` - The visitor's choice of mouse effect (Kid Pix stamps, marker line, pixel squares or off) and cursor (normal, sticker arrow or blob dot), saved in localStorage; a small settings button on every page
  - `venuesRenderer.js` - Renders the venue directory (`<region>/venues.html`)
    from `dataManager.fetchVenues()`. Standalone - only loaded on that page,
    not part of the `scroll.js`-orchestrated event-table pipeline above.

## Loading Order
The modules should be loaded in this order in your HTML:

```html
<!-- Load modules first -->
<script src="dataManager.js"></script>
<script src="venueAddresses.js"></script>
<script src="mapChoice.js"></script>
<script src="eventSorter.js"></script>
<script src="tableRenderer.js"></script>
<script src="filterState.js"></script>
<script src="searchManager.js"></script>
<script src="filterPanel.js"></script>
<script src="nearMe.js"></script>
<script src="nearMeControl.js"></script>
<script src="mapPins.js"></script>
<script src="mapView.js"></script>
<script src="modalManager.js"></script>

<!-- Load main orchestrator last -->
<script src="scroll.js"></script>

<!-- Other functionality -->
<script src="calendarLinks.js"></script>
<script src="notify.js"></script>
<script src="web3forms.js"></script>
<script src="feedback.js"></script>
<script src="cursorFx.js"></script>
```

## Benefits of Refactoring

1. **Single Responsibility**: Each file has one clear purpose
2. **Maintainability**: Easier to find and fix bugs
3. **Testability**: Individual modules can be tested separately
4. **Reusability**: Modules can be reused in other parts of the application
5. **Readability**: Code is easier to understand and navigate
6. **Scalability**: Easier to add new features or modify existing ones

## Migration Notes

- The old `scroll.js` functionality has been completely replaced
- All existing functionality is preserved but reorganized
- The `filter.js` file is deprecated but kept for backward compatibility
- All modules are attached to the `window` object for easy access

## Future Improvements

- Consider using ES6 modules instead of window objects
- Add error handling and loading states
- Implement module dependency management
- Add unit tests for individual modules
