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
- `mapLinks(value)` - one Google Maps link per address: `{text, href, title}`. One address gives plain "Map"; several give "Map: <label>"

`tableRenderer.js` (the "Map" link under each event) and `venuesRenderer.js` (the venue directory) both use it, so load `venueAddresses.js` before them (after `dataManager.js`) on every region page and venues page.

### 4. `filterState.js` and `searchManager.js`
**Purpose**: The event filters (search text, phase, ongoing, tags) and the table rows they show or hide.

`filterState.js` holds the **pure logic**, with no DOM access, so it is unit tested in Node (`node --test tests/`):
- `TAG_GROUPS` - the tag groups offered as dropdowns (Medium, Theme, Cost, Format). Keep in step with `docs/tags.html` and `APPROVED_TAGS` in `tagging.py`; a test checks the tags are documented
- `parseUrl(search)` / `toQuery(state)` - filters <-> URL (`?q=text&phase=past&tags=photography,latinx`), so a view can be bookmarked or shared. `phase` is one or more of `current`, `ongoing`, `future`, `past` (e.g. `phase=current,past`). The older `?search=Venue` (used by `venues.html`) is still read, and means "every phase"
- **When** is a multi-select over four mutually exclusive buckets: `current` (on view, has an end date), `ongoing` (on view, no end date - `bucketOf(phase, ongoing)`), `future` and `past`. Ticking all four shows everything (there is no separate "All" and no separate "include ongoing" checkbox). **The default is current + ongoing + future**, not the long archive. At least one must stay ticked
- `rowMatches(row, state)` - the matching rule: tags in the same group widen the results (photography OR painting), tags in different groups narrow them (photography AND latinx), and a tag outside every group (e.g. `museum`) must always match
- `countTags(rows, state)` / `countPhases(rows, state)` - the counts shown beside each option in the dropdowns

`searchManager.js` (`SearchManager`) owns the live state: it reads the URL on load, shows/hides rows, keeps the buttons, search box and tag chips in sync, and rewrites the URL (`replaceState`, so the back button isn't filled with every keystroke). `FilterPanel` subscribes to it.

**Usage**:
```javascript
// The search manager is automatically initialized by scroll.js
window.searchManager.setSearchTerm('exhibition');
window.searchManager.togglePhase('past');          // tick/untick one phase in the When filter
window.searchManager.setPhaseFilter('upcoming');   // or set them: a phase, a list, 'upcoming' (current+future) or 'all'
window.searchManager.toggleTagFilter('photography');
window.searchManager.clearFilters();               // back to the default view
```

### 4b. `filterPanel.js`
**Purpose**: Draws the filter controls from `SearchManager`'s state: a single row of independent dropdowns: **When** (Current / Ongoing / Future / Past, with a one-line hint under Current and Ongoing) first, then one per tag group in `TAG_GROUPS` (Medium, Theme, Cost, ...). Each opens a popover of checkboxes with counts, and its button shows a badge with how many of its options are selected (for When, only when it differs from the default). Only one popover is open at a time; a click outside or Escape closes it. On phones the row still fits on one line and the popover opens full width underneath. Below the row is the "Showing X of Y events" line, a removable pill for each active filter, and "Clear all".

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
- Adds a **Use my location** button to the filter bar and a note under it. After a location is shared, the button becomes a **Nearest first** toggle (on by default) with a **Turn off** link, each row's Links cell shows "0.4 mi away" (the `.event-distance` span `tableRenderer.js` leaves in it, empty and hidden), and the rows are reordered. Turning it off restores the usual order. Filters keep working: hidden rows are reordered too
- **Nothing is requested until the visitor clicks.** Then it loads `venue_coordinates.json` and `region_bounds.json` (static files, once; `dataManager.fetchNearMeData()`), so the default page is no heavier
- **Privacy**: the position is used once to work out each venue's distance and then dropped. It is not kept in a variable, storage or a cookie, not put in the URL, not sent anywhere, and not in the analytics data. Reloading forgets everything. Keep it that way: no `localStorage`, no `?lat=`, nothing in `gtag`
- Outcomes it handles, each with a short message and the page still usable: permission denied, position unavailable, timed out (10 s), venue data failed to load (retry works), and far from the region
- `SearchManager`'s row model carries `index` (the usual order), `venue` (from the row's `data-venue`) and `distanceEl`, which is how the control finds its rows
- Needs HTTPS (GitHub Pages is; `localhost` is fine) and a browser with `navigator.geolocation`; without it no button is added

**Testing it by hand**: in the browser console, replace what the browser would answer, then click the button: `Geolocation.prototype.getCurrentPosition = (ok) => ok({ coords: { latitude: 37.8044, longitude: -122.2712 } })` (call `err({ code: 1 })` for "denied", `3` for "timed out").

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
  - `notify.js` - Notification functionality
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
<script src="eventSorter.js"></script>
<script src="tableRenderer.js"></script>
<script src="filterState.js"></script>
<script src="searchManager.js"></script>
<script src="filterPanel.js"></script>
<script src="nearMe.js"></script>
<script src="nearMeControl.js"></script>
<script src="modalManager.js"></script>

<!-- Load main orchestrator last -->
<script src="scroll.js"></script>

<!-- Other functionality -->
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
