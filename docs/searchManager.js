// Search Manager - Handles unified search and filtering functionality

class SearchManager {
    constructor() {
        this.currentSearchTerm = '';
        this.currentPhaseFilter = 'all';
        this.includeOngoing = true;
        this.currentTagFilters = new Set();
        this.tableBody = null;
        this.init();
    }

    init() {
        // Get table body reference
        this.tableBody = document.getElementById('eventTable')?.getElementsByTagName('tbody')[0] ||
                        document.getElementById('event-list');

        // Initialize search bar
        this.initSearchBar();

        // Initialize filter buttons
        this.initFilterButtons();

        // Initialize ongoing-events checkbox
        this.initOngoingCheckbox();
    }

    initSearchBar() {
        const searchBar = document.getElementById('searchBar');
        if (searchBar) {
            searchBar.addEventListener('keyup', (e) => {
                this.currentSearchTerm = e.target.value.toLowerCase();
                this.filterEvents();
            });
        }
    }

    initFilterButtons() {
        const currentButton = document.getElementById('currentButton');
        const futureButton = document.getElementById('futureButton');
        const pastButton = document.getElementById('pastButton');
        const allButton = document.getElementById('allButton');

        if (currentButton) {
            currentButton.addEventListener('click', () => {
                this.currentPhaseFilter = 'current';
                this.filterEvents();
                this.setActiveButton(currentButton);
            });
        }

        if (futureButton) {
            futureButton.addEventListener('click', () => {
                this.currentPhaseFilter = 'future';
                this.filterEvents();
                this.setActiveButton(futureButton);
            });
        }

        if (pastButton) {
            pastButton.addEventListener('click', () => {
                this.currentPhaseFilter = 'past';
                this.filterEvents();
                this.setActiveButton(pastButton);
            });
        }

        if (allButton) {
            allButton.addEventListener('click', () => {
                this.currentPhaseFilter = 'all';
                this.filterEvents();
                this.setActiveButton(allButton);
            });
            
            // Set initial active button
            this.setActiveButton(allButton);
        }
    }

    initOngoingCheckbox() {
        const ongoingCheckbox = document.getElementById('ongoingCheckbox');
        if (ongoingCheckbox) {
            ongoingCheckbox.addEventListener('change', () => {
                this.includeOngoing = ongoingCheckbox.checked;
                this.filterEvents();
            });
        }
    }

    // Toggle a tag chip filter: multiple tags can be selected at once. An
    // event must carry every selected tag to match (selecting more tags
    // narrows the results, like most faceted filters).
    toggleTagFilter(tag) {
        if (this.currentTagFilters.has(tag)) {
            this.currentTagFilters.delete(tag);
        } else {
            this.currentTagFilters.add(tag);
        }
        this.updateTagChipStates();
        this.filterEvents();
    }

    // Reflect the current tag selection on every chip in the table: a
    // selected chip looks the same as it would with no filter active: every
    // unselected chip dims while at least one tag is selected.
    updateTagChipStates() {
        const chips = document.querySelectorAll('.tag-chip');
        chips.forEach(chip => {
            const isSelected = this.currentTagFilters.has(chip.dataset.tag);
            const isDimmed = this.currentTagFilters.size > 0 && !isSelected;
            chip.classList.toggle('selected', isSelected);
            chip.classList.toggle('dimmed', isDimmed);
        });
    }

    setActiveButton(activeButton) {
        const buttons = document.querySelectorAll('.filter-button');
        buttons.forEach(button => {
            if (button === activeButton) {
                button.classList.add('active');
            } else {
                button.classList.remove('active');
            }
        });
    }

    filterEvents() {
        if (!this.tableBody) return;

        const rows = this.tableBody.getElementsByTagName('tr');

        Array.from(rows).forEach(row => {
            const eventPhase = row.getAttribute('data-phase');
            const isOngoing = row.getAttribute('data-ongoing') === 'true';
            const rowTags = (row.getAttribute('data-tags') || '').split('|');

            // Get cell content for search
            const cells = row.getElementsByTagName('td');
            if (cells.length < 5) return;

            // Column mapping based on actual table structure:
            // Column 0: Image (empty, skip for search)
            // Column 1: Date
            // Column 2: Show @ Venue (title + venue)
            // Column 3: Tags
            // Column 4: Links (skip for search)

            const date = cells[1]?.textContent?.toLowerCase() || '';
            const titleVenue = cells[2]?.textContent?.toLowerCase() || '';
            const tags = cells[3]?.textContent?.toLowerCase() || '';

            // Check if row matches the search term
            const matchesSearch =
                date.includes(this.currentSearchTerm) ||
                titleVenue.includes(this.currentSearchTerm) ||
                tags.includes(this.currentSearchTerm);

            // Check if row matches the phase filter
            const matchesPhase = this.currentPhaseFilter === 'all' || eventPhase === this.currentPhaseFilter;

            // Check if row matches the ongoing filter (only excludes ongoing events, never non-ongoing ones)
            const matchesOngoing = this.includeOngoing || !isOngoing;

            // Check if row matches the selected tag chip, if any
            const matchesTag = Array.from(this.currentTagFilters).every(tag => rowTags.includes(tag));

            // Show row if it matches search, phase, ongoing, and tag filters
            if (matchesSearch && matchesPhase && matchesOngoing && matchesTag) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    }

    // Method to update search term programmatically
    setSearchTerm(term) {
        this.currentSearchTerm = term.toLowerCase();
        this.filterEvents();
    }

    // Method to update phase filter programmatically
    setPhaseFilter(phase) {
        this.currentPhaseFilter = phase;
        this.filterEvents();
    }

    // Method to update the ongoing-events filter programmatically
    setOngoingFilter(include) {
        this.includeOngoing = include;
        const ongoingCheckbox = document.getElementById('ongoingCheckbox');
        if (ongoingCheckbox) {
            ongoingCheckbox.checked = include;
        }
        this.filterEvents();
    }

    // Method to clear all filters
    clearFilters() {
        this.currentSearchTerm = '';
        this.currentPhaseFilter = 'all';
        this.includeOngoing = true;
        this.currentTagFilters.clear();
        this.updateTagChipStates();
        this.filterEvents();

        // Clear search bar
        const searchBar = document.getElementById('searchBar');
        if (searchBar) {
            searchBar.value = '';
        }

        // Reset ongoing checkbox
        const ongoingCheckbox = document.getElementById('ongoingCheckbox');
        if (ongoingCheckbox) {
            ongoingCheckbox.checked = true;
        }

        // Reset active button
        const allButton = document.getElementById('allButton');
        if (allButton) {
            this.setActiveButton(allButton);
        }
    }
}

// SearchManager will be initialized by scroll.js after events are rendered
// This prevents timing issues and ensures the table is populated before search is enabled
