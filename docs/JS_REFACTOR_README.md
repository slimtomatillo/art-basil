# JavaScript Refactoring Documentation

## Overview
The JavaScript code has been refactored from a single monolithic `scroll.js` file into multiple focused modules for better maintainability, testability, and code organization.

## New File Structure

### 1. `dataManager.js`
**Purpose**: Handles data fetching and region detection
**Functions**:
- `getRegion()` - Detects current region (SF/LA) from URL
- `fetchVenues()` - Fetches venue data from JSON files
- `fetchEvents()` - Fetches event data from JSON files

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

### 4. `searchManager.js`
**Purpose**: Handles unified search and filtering functionality
**Class**: `SearchManager`
**Features**:
- Search bar functionality
- Phase filtering (current/future/past/all)
- Combined search and filter logic

**Usage**:
```javascript
// The search manager is automatically initialized
// Access via window.searchManager
window.searchManager.setSearchTerm('exhibition');
window.searchManager.setPhaseFilter('current');
```

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
- `filter.js` - Functionality moved to `searchManager.js`
- Other files remain unchanged:
  - `notify.js` - Notification functionality
  - `feedback.js` - Feedback form functionality
  - `cursorTrail.js` - Cursor trail effects

## Loading Order
The modules should be loaded in this order in your HTML:

```html
<!-- Load modules first -->
<script src="dataManager.js"></script>
<script src="eventSorter.js"></script>
<script src="tableRenderer.js"></script>
<script src="searchManager.js"></script>
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
