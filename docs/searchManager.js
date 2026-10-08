// Search Manager - owns the filter state (search text, phase, ongoing, tags),
// shows/hides the table rows to match it, and keeps the URL in step so a
// filtered view can be bookmarked or shared. The matching rules live in
// filterState.js; FilterPanel draws the tag/summary controls and subscribes
// to changes here.

const PHASE_BUTTONS = {
    upcomingButton: 'upcoming',
    currentButton: 'current',
    futureButton: 'future',
    pastButton: 'past',
    allButton: 'all',
};

class SearchManager {
    constructor() {
        // Initial state comes from the URL, e.g. ?phase=past&tags=photography,latinx
        // (or ?search=Venue from a venues.html link), so shared links reproduce a view.
        this.state = filterState.parseUrl(window.location.search);
        this.rows = [];
        this.tableBody = null;
        this.listeners = [];
        this.init();
    }

    init() {
        this.tableBody = document.getElementById('eventTable')?.getElementsByTagName('tbody')[0] ||
                        document.getElementById('event-list');

        this.buildRowModel();
        this.initSearchBar();
        this.initFilterButtons();
        this.initOngoingCheckbox();

        // Show the results for whatever the URL asked for (the URL itself is
        // already right, so don't rewrite it).
        this.applyFilters({ updateUrl: false });
    }

    // One pass over the rendered table, so each filter change is just in-memory matching.
    buildRowModel() {
        if (!this.tableBody) return;
        this.rows = Array.from(this.tableBody.getElementsByTagName('tr')).flatMap(el => {
            const cells = el.getElementsByTagName('td');
            if (cells.length < 5) return [];
            // Columns: 0 image, 1 date, 2 "title @ venue", 3 tags, 4 links. The
            // text search covers date, title/venue and tags, as it always has.
            const text = [1, 2, 3].map(i => cells[i]?.textContent?.toLowerCase() || '').join('\n');
            return [{
                el,
                phase: el.getAttribute('data-phase'),
                ongoing: el.getAttribute('data-ongoing') === 'true',
                tags: (el.getAttribute('data-tags') || '').split('|').filter(Boolean),
                text,
            }];
        });
    }

    initSearchBar() {
        const searchBar = document.getElementById('searchBar');
        if (!searchBar) return;
        searchBar.value = this.state.q;
        // "input" rather than "keyup" so pasting and the clear (x) button count too
        searchBar.addEventListener('input', (e) => {
            this.state.q = e.target.value.trim();
            this.applyFilters();
        });
    }

    initFilterButtons() {
        for (const [id, phase] of Object.entries(PHASE_BUTTONS)) {
            document.getElementById(id)?.addEventListener('click', () => this.setPhaseFilter(phase));
        }
    }

    initOngoingCheckbox() {
        const ongoingCheckbox = document.getElementById('ongoingCheckbox');
        if (!ongoingCheckbox) return;
        ongoingCheckbox.checked = this.state.ongoing;
        ongoingCheckbox.addEventListener('change', () => {
            this.state.ongoing = ongoingCheckbox.checked;
            this.applyFilters();
        });
    }

    // Show/hide rows, then bring every control and the URL in line with the state.
    applyFilters({ updateUrl = true } = {}) {
        this.rows.forEach(row => {
            row.el.style.display = filterState.rowMatches(row, this.state) ? '' : 'none';
        });
        this.syncControls();
        if (updateUrl) this.updateUrl();
        this.listeners.forEach(listener => listener(this));
    }

    syncControls() {
        for (const [id, phase] of Object.entries(PHASE_BUTTONS)) {
            document.getElementById(id)?.classList.toggle('active', this.state.phase === phase);
        }
        const searchBar = document.getElementById('searchBar');
        if (searchBar && searchBar.value.trim() !== this.state.q) searchBar.value = this.state.q;
        const ongoingCheckbox = document.getElementById('ongoingCheckbox');
        if (ongoingCheckbox) ongoingCheckbox.checked = this.state.ongoing;
        this.updateTagChipStates();
    }

    // replaceState (not pushState) so typing and clicking don't fill the back button
    updateUrl() {
        const url = window.location.pathname + filterState.toQuery(this.state) + window.location.hash;
        window.history.replaceState(null, '', url);
    }

    // FilterPanel registers here to redraw whenever the state changes
    subscribe(listener) {
        this.listeners.push(listener);
    }

    getState() {
        return { ...this.state, tags: [...this.state.tags] };
    }

    totalCount() {
        return this.rows.length;
    }

    visibleCount() {
        return this.rows.filter(row => filterState.rowMatches(row, this.state)).length;
    }

    // Toggle a tag filter (from a table chip or the panel). Several tags can be
    // selected: tags in the same group widen the results (photography OR
    // painting), tags in different groups narrow them (photography AND latinx).
    toggleTagFilter(tag) {
        const tags = this.state.tags;
        const index = tags.indexOf(tag);
        if (index === -1) {
            tags.push(tag);
        } else {
            tags.splice(index, 1);
        }
        this.applyFilters();
    }

    // The selected chip looks normal and every other chip dims while any tag is selected.
    updateTagChipStates() {
        document.querySelectorAll('.tag-chip').forEach(chip => {
            const isSelected = this.state.tags.includes(chip.dataset.tag);
            const isDimmed = this.state.tags.length > 0 && !isSelected;
            chip.classList.toggle('selected', isSelected);
            chip.classList.toggle('dimmed', isDimmed);
        });
    }

    setSearchTerm(term) {
        this.state.q = term.trim();
        this.applyFilters();
    }

    setPhaseFilter(phase) {
        if (!filterState.PHASES.includes(phase)) return;
        this.state.phase = phase;
        this.applyFilters();
    }

    setOngoingFilter(include) {
        this.state.ongoing = include;
        this.applyFilters();
    }

    // Back to the default view: now & upcoming, nothing searched or selected.
    clearFilters() {
        this.state = filterState.defaultState();
        this.applyFilters();
    }
}

// SearchManager will be initialized by scroll.js after events are rendered
// This prevents timing issues and ensures the table is populated before search is enabled
