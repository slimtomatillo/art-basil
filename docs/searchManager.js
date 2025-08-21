// Search Manager - Handles unified search and filtering functionality

class SearchManager {
    constructor() {
        this.currentSearchTerm = '';
        this.currentPhaseFilter = 'all';
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

            // Show row if it matches both search and phase
            if (matchesSearch && matchesPhase) {
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

    // Method to clear all filters
    clearFilters() {
        this.currentSearchTerm = '';
        this.currentPhaseFilter = 'all';
        this.filterEvents();
        
        // Clear search bar
        const searchBar = document.getElementById('searchBar');
        if (searchBar) {
            searchBar.value = '';
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
