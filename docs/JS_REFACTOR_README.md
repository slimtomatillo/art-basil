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

### 4. `filterState.js` and `searchManager.js`
**Purpose**: The event filters (search text, phase, ongoing, tags) and the table rows they show or hide.

`filterState.js` holds the **pure logic**, with no DOM access, so it is unit tested in Node (`node --test tests/`):
- `TAG_GROUPS` - the tag groups offered as dropdowns (Medium, Theme, Cost, Format). Keep in step with `docs/tags.html` and `APPROVED_TAGS` in `tagging.py`; a test checks the tags are documented
- `parseUrl(search)` / `toQuery(state)` - filters <-> URL (`?q=text&phase=past&tags=photography,latinx&ongoing=0`), so a view can be bookmarked or shared. The older `?search=Venue` (used by `venues.html`) is still read, and means "all phases"
- `rowMatches(row, state)` - the matching rule: tags in the same group widen the results (photography OR painting), tags in different groups narrow them (photography AND latinx), and a tag outside every group (e.g. `museum`) must always match
- `countTags(rows, state)` - the counts shown beside each option in the panel
- Phases: `upcoming` (current + future, **the default**), `current`, `future`, `past`, `all`

`searchManager.js` (`SearchManager`) owns the live state: it reads the URL on load, shows/hides rows, keeps the buttons, search box and tag chips in sync, and rewrites the URL (`replaceState`, so the back button isn't filled with every keystroke). `FilterPanel` subscribes to it.

**Usage**:
```javascript
// The search manager is automatically initialized by scroll.js
window.searchManager.setSearchTerm('exhibition');
window.searchManager.setPhaseFilter('past');       // 'upcoming' | 'current' | 'future' | 'past' | 'all'
window.searchManager.toggleTagFilter('photography');
window.searchManager.clearFilters();               // back to the default view
```

### 4b. `filterPanel.js`
**Purpose**: Draws the filter controls from `SearchManager`'s state: a single row of independent dropdowns (Medium, Theme, Cost, ...), one per tag group in `TAG_GROUPS`. Each opens a popover of checkboxes with counts, and its button shows a badge with how many of its tags are selected. Only one popover is open at a time; a click outside or Escape closes it. On phones the row still fits on one line and the popover opens full width underneath. Below the row is the "Showing X of Y events" line, a removable pill for each active filter, and "Clear all".

A group with no tags in a region's data gets no dropdown (so "Cost" only appears where events carry `free`, and "Format" stays hidden until some events carry its tags). Anything the visitor typed (the search text can come from a shared URL) is inserted as text, never as HTML.

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
  - `feedback.js` - Feedback form functionality
  - `cursorTrail.js` - Cursor trail effects
  - `venuesRenderer.js` - Renders the venue directory (`<region>/venues.html`)
    from `dataManager.fetchVenues()`. Standalone - only loaded on that page,
    not part of the `scroll.js`-orchestrated event-table pipeline above.

## Loading Order
The modules should be loaded in this order in your HTML:

```html
<!-- Load modules first -->
<script src="dataManager.js"></script>
<script src="eventSorter.js"></script>
<script src="tableRenderer.js"></script>
<script src="filterState.js"></script>
<script src="searchManager.js"></script>
<script src="filterPanel.js"></script>
<script src="modalManager.js"></script>

<!-- Load main orchestrator last -->
<script src="scroll.js"></script>

<!-- Other functionality -->
<script src="notify.js"></script>
<script src="feedback.js"></script>
<script src="cursorTrail.js"></script>
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
