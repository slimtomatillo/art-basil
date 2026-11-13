// Search Manager - owns the filter state (search text, phases, tags),
// shows/hides the table rows to match it, and keeps the URL in step so a
// filtered view can be bookmarked or shared. The matching rules live in
// filterState.js; FilterPanel draws the tag/summary controls and subscribes
// to changes here.

class SearchManager {
    constructor() {
        // Initial state comes from the URL, e.g. ?phase=past&tags=photography,latinx
        // (or ?venue=Venue from a venues.html link), so shared links reproduce a view.
        this.state = filterState.parseUrl(window.location.search, SearchManager.regionToday());
        // Only this region's areas count (a Bay Area ?area= link opened on another region's page is ignored)
        this.state.areas = filterState.areasOfRegion(window.dataManager.getRegion(), this.state.areas);
        this.rows = [];
        this.tableBody = null;
        this.listeners = [];
        this.init();
    }

    // Today in the region's time zone ('YYYY-MM-DD'), which the "open this weekend" kind of date works from;
    // null if the region's time zone is not known yet
    static regionToday() {
        try {
            return window.dataManager.regionToday(window.dataManager.getRegion());
        } catch (error) {
            return null;
        }
    }

    init() {
        this.tableBody = document.getElementById('eventTable')?.getElementsByTagName('tbody')[0] ||
                        document.getElementById('event-list');

        this.buildRowModel();
        this.initSearchBar();

        // Show the results for whatever the URL asked for (the URL itself is
        // already right, so don't rewrite it).
        this.applyFilters({ updateUrl: false });
    }

    // One pass over the rendered table, so each filter change is just in-memory matching.
    buildRowModel() {
        if (!this.tableBody) return;
        this.rows = Array.from(this.tableBody.getElementsByTagName('tr')).flatMap((el, index) => {
            const cells = el.getElementsByTagName('td');
            if (cells.length < 5) return [];
            // Columns: 0 image, 1 date, 2 "title @ venue", 3 tags, 4 links. The
            // text search covers date, title/venue and tags, as it always has.
            const text = filterState.foldText([1, 2, 3].map(i => cells[i]?.textContent || '').join('\n'));
            return [{
                el,
                index,                                       // the page's usual order (Near Me can reorder the rows)
                venue: el.getAttribute('data-venue') || '',  // for the "Use my location" distances
                distanceEl: el.querySelector('.event-distance'),
                event: el.eventData || null,                 // for Map view's popups
                dateText: cells[1]?.textContent || '',
                // when the show runs and where, for the dates and Area filters
                start: el.getAttribute('data-start') || null,
                end: el.getAttribute('data-end') || null,
                areas: (el.getAttribute('data-areas') || '').split('|').filter(Boolean),
                // current / ongoing / future / past: what the "When" filter works on
                bucket: filterState.bucketOf(el.getAttribute('data-phase'), el.getAttribute('data-ongoing') === 'true'),
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
        const searchBar = document.getElementById('searchBar');
        if (searchBar && searchBar.value.trim() !== this.state.q) searchBar.value = this.state.q;
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
        return { ...this.state, tags: [...this.state.tags], areas: [...this.state.areas],
                 timing: this.state.timing ? { ...this.state.timing } : null };
    }

    totalCount() {
        return this.rows.length;
    }

    visibleCount() {
        return this.matchingRows().length;
    }

    // The rows that match the current filters (what the table shows, and what Map view puts on the map)
    matchingRows() {
        return this.rows.filter(row => filterState.rowMatches(row, this.state));
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

    // Show one venue's shows ('' for every venue). The match is on the venue's whole name (filterState.venueMatches),
    // and the other filters, including the When phases, stay as they are. From a venue name in a row
    // and from the venue directory (?venue=).
    setVenue(name) {
        this.state.venue = String(name || '').trim();
        this.applyFilters();
    }

    // Tick or untick one phase in the "When" filter. The last ticked phase can't
    // be unticked, so the view is never empty by construction.
    togglePhase(phase) {
        const phases = this.state.phases;
        if (!filterState.ALL_PHASES.includes(phase)) return;
        if (phases.includes(phase)) {
            if (phases.length > 1) this.state.phases = phases.filter(p => p !== phase);
        } else {
            this.state.phases = filterState.normalizePhases([...phases, phase]);
        }
        this.applyFilters();
    }

    // Set the phases directly: a phase name, a list of them, or 'upcoming'
    // (current, ongoing & future) / 'all' for convenience.
    setPhaseFilter(phase) {
        const aliases = { upcoming: filterState.DEFAULT_PHASES, all: filterState.ALL_PHASES };
        const phases = filterState.normalizePhases([].concat(aliases[phase] || phase));
        if (phases.length === 0) return;
        this.state.phases = phases;
        this.applyFilters();
    }

    // Choose which days to show (replacing the When phases): null for any date, { pick } for a quick pick
    // (today, weekend, week, closing, opening) or { from, to } ('YYYY-MM-DD') for a range
    setTiming(timing) {
        if (timing && timing.pick) {
            if (!filterState.TIMING_PICKS.includes(timing.pick)) return;
            this.state.timing = { pick: timing.pick };
        } else if (timing && timing.from) {
            const from = filterState.validDay(timing.from);
            const to = filterState.validDay(timing.to) || from;
            if (!from) return;
            this.state.timing = to < from ? { from: to, to: from } : { from, to };
        } else {
            this.state.timing = null;
        }
        this.applyFilters();
    }

    // Tick or untick an area (the Bay Area only); several widen the results
    toggleArea(id) {
        const region = window.dataManager.getRegion();
        if (!(filterState.AREAS[region] || []).some(area => area.id === id)) return;
        const areas = this.state.areas;
        const index = areas.indexOf(id);
        if (index === -1) areas.push(id); else areas.splice(index, 1);
        this.applyFilters();
    }

    // Show the results as the table ('list') or on the map ('map'); the choice is in the URL (?view=map)
    setView(view) {
        if (!filterState.VIEWS.includes(view) || view === this.state.view) return;
        this.state.view = view;
        this.applyFilters();
    }

    // Back to the default filters: current, ongoing & future, no date, area or tag chosen, nothing searched.
    // The way the results are shown (list or map) is not a filter, so it stays.
    clearFilters() {
        this.state = { ...filterState.defaultState(this.state.today), view: this.state.view };
        this.applyFilters();
    }
}

// SearchManager will be initialized by scroll.js after events are rendered
// This prevents timing issues and ensures the table is populated before search is enabled
