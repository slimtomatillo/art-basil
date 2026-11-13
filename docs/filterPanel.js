// Filter Panel - the visible filter controls: a row of independent dropdowns
// (When, Area (the Bay Area only), Medium, Theme, Cost, ...), each opening a popover of checkboxes with
// counts (When also has the "Open on" dates), plus a summary line with the result count, the active filters as
// removable pills, and "Clear all". All state lives in SearchManager; this only
// draws it and forwards clicks.

class FilterPanel {
    constructor(searchManager) {
        this.searchManager = searchManager;
        this.panelEl = document.getElementById('filterPanel');
        this.summaryEl = document.getElementById('filterSummary');
        this.dropdowns = new Map();    // dropdown id -> { toggle, badge, popover }
        this.tagBoxes = new Map();     // tag -> { input, label, count, group }
        this.phaseBoxes = new Map();   // phase -> { input, label, count }
        this.timingBoxes = new Map();  // 'any' | quick pick -> { input, label, count }
        this.areaBoxes = new Map();    // area id -> { input, label, count }
        this.openGroup = null;

        if (this.panelEl) this.buildBar();
        this.buildEmptyState();
        searchManager.subscribe(() => this.update());
        this.update();
    }

    tagLabel(tag) {
        return tag.replace(/-/g, ' ');
    }

    tagColor(tag) {
        // getTagColor comes from tableRenderer.js, so the dots match the table chips
        return typeof getTagColor === 'function' ? getTagColor(tag) : '#6c757d';
    }

    // Built once; update() only changes counts and checked/disabled states, so a
    // popover that is open stays open (and keeps focus) while the visitor ticks options.
    buildBar() {
        const rows = this.searchManager.rows;
        const hidden = typeof HIDDEN_TAGS !== 'undefined' ? HIDDEN_TAGS : new Set();

        const bar = document.createElement('div');
        bar.className = 'filter-bar';

        // When: which phases to show, and (below them) which days. Always first, since it is the biggest cut of the list.
        bar.append(this.buildDropdown('when', 'When', filterState.ALL_PHASES.map(phase => ({
            value: phase,
            label: filterState.PHASE_LABELS[phase],
            hint: filterState.PHASE_HINTS[phase],
            color: this.tagColor(phase),
            onChange: () => this.searchManager.togglePhase(phase),
            register: (box) => this.phaseBoxes.set(phase, box),
        })), () => this.buildTimingSection()));

        // Area: the regions that have AREAS in filterState.js (the Bay Area, Los Angeles, Istanbul), and only the areas that have shows
        this.region = window.dataManager.getRegion();
        const areas = (filterState.AREAS[this.region] || []).filter(area => rows.some(row => row.areas.includes(area.id)));
        if (areas.length > 1) {
            bar.append(this.buildDropdown('area', 'Area', areas.map(area => ({
                value: area.id,
                label: area.label,
                onChange: () => this.searchManager.toggleArea(area.id),
                register: (box) => this.areaBoxes.set(area.id, box),
            }))));
        }

        for (const group of filterState.TAG_GROUPS) {
            // Only offer tags this region actually has, and no dropdown at all if there are none
            const tags = group.tags.filter(tag => !hidden.has(tag) && rows.some(row => row.tags.includes(tag)));
            if (tags.length === 0) continue;
            bar.append(this.buildDropdown(group.id, group.label, tags.map(tag => ({
                value: tag,
                label: this.tagLabel(tag),
                color: this.tagColor(tag),
                onChange: () => this.searchManager.toggleTagFilter(tag),
                register: (box) => this.tagBoxes.set(tag, { ...box, group: group.id }),
            }))));
        }

        // A click anywhere outside the bar, or Escape, closes the open popover
        document.addEventListener('click', (e) => {
            if (this.openGroup && !bar.contains(e.target)) this.closeDropdown();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.openGroup) {
                const { toggle } = this.dropdowns.get(this.openGroup);
                this.closeDropdown();
                toggle.focus();
            }
        });

        this.panelEl.replaceChildren(bar);
    }

    // One dropdown: a button that opens a popover of checkbox options. `extra` (optional) builds more
    // for the popover to show under them.
    buildDropdown(id, labelText, options, extra = null) {
        const wrap = document.createElement('div');
        wrap.className = 'filter-dropdown';
        wrap.dataset.group = id;

        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'filter-dropdown-toggle';
        toggle.setAttribute('aria-haspopup', 'true');
        toggle.setAttribute('aria-expanded', 'false');
        const label = document.createElement('span');
        label.textContent = labelText;
        const badge = document.createElement('span');
        badge.className = 'filter-badge';
        badge.hidden = true;
        const caret = document.createElement('span');
        caret.className = 'filter-caret';
        caret.setAttribute('aria-hidden', 'true');
        toggle.append(label, badge, caret);

        const popover = document.createElement('div');
        popover.className = 'filter-popover';
        popover.setAttribute('role', 'group');
        popover.setAttribute('aria-label', labelText);
        popover.hidden = true;

        const list = document.createElement('div');
        list.className = 'filter-options';
        for (const option of options) {
            const optionLabel = document.createElement('label');
            optionLabel.className = 'filter-option';

            const input = document.createElement('input');
            input.type = 'checkbox';
            input.value = option.value;
            input.addEventListener('change', option.onChange);

            const dot = document.createElement('span');
            dot.className = 'filter-dot';
            if (option.color) dot.style.backgroundColor = option.color;
            else dot.hidden = true;                  // an option with no colour (an area) has no dot

            const name = document.createElement('span');
            name.className = 'filter-name';
            name.textContent = option.label;
            if (option.hint) {
                // one muted line under the name, e.g. "no end date" under Ongoing
                const hint = document.createElement('span');
                hint.className = 'filter-hint';
                hint.textContent = option.hint;
                name.append(hint);
            }

            const count = document.createElement('span');
            count.className = 'filter-n';

            optionLabel.append(input, dot, name, count);
            list.append(optionLabel);
            option.register({ input, label: optionLabel, count });
        }
        popover.append(list);
        if (extra) popover.append(extra());

        toggle.addEventListener('click', () => this.toggleDropdown(id));
        wrap.append(toggle, popover);
        this.dropdowns.set(id, { toggle, badge, popover });
        return wrap;
    }

    // "Open on": any date, a quick pick (one choice at a time) or a range of two days. Choosing a date replaces
    // the phases above it, which the note under the title says and updateBar() makes plain by greying them.
    buildTimingSection() {
        const section = document.createElement('div');
        section.className = 'filter-section';

        const title = document.createElement('div');
        title.className = 'filter-section-title';
        title.textContent = 'Open on';
        this.timingNote = document.createElement('div');
        this.timingNote.className = 'filter-section-note';
        this.timingNote.textContent = 'A date replaces Current, Future and Past above.';
        this.timingNote.hidden = true;

        const list = document.createElement('div');
        list.className = 'filter-options';
        list.setAttribute('role', 'radiogroup');
        list.setAttribute('aria-label', 'Open on');
        const choices = [{ value: 'any', label: 'Any date' },
            ...filterState.TIMING_PICKS.map(pick => ({ value: pick, label: filterState.TIMING_LABELS[pick], hint: filterState.TIMING_HINTS[pick] }))];
        for (const choice of choices) {
            const label = document.createElement('label');
            label.className = 'filter-option';
            const input = document.createElement('input');
            input.type = 'radio';
            input.name = 'filter-timing';
            input.value = choice.value;
            input.addEventListener('change', () => {
                this.searchManager.setTiming(choice.value === 'any' ? null : { pick: choice.value });
            });
            const name = document.createElement('span');
            name.className = 'filter-name';
            name.textContent = choice.label;
            if (choice.hint) {
                const hint = document.createElement('span');
                hint.className = 'filter-hint';
                hint.textContent = choice.hint;
                name.append(hint);
            }
            const count = document.createElement('span');
            count.className = 'filter-n';
            label.append(input, name, count);
            list.append(label);
            this.timingBoxes.set(choice.value, { input, label, count });
        }

        // Or two days of your own. One day is enough; a "to" before the "from" is swapped.
        const dates = document.createElement('div');
        dates.className = 'filter-dates';
        const field = (text, onChange) => {
            const wrap = document.createElement('label');
            wrap.className = 'filter-date';
            const span = document.createElement('span');
            span.textContent = text;
            const input = document.createElement('input');
            input.type = 'date';
            input.addEventListener('change', onChange);
            wrap.append(span, input);
            return { wrap, input };
        };
        const apply = () => {
            if (!this.fromInput.value) {
                if (this.searchManager.getState().timing?.from) this.searchManager.setTiming(null);
                return;
            }
            this.searchManager.setTiming({ from: this.fromInput.value, to: this.toInput.value || this.fromInput.value });
        };
        const from = field('From', apply);
        const to = field('To', apply);
        this.fromInput = from.input;
        this.toInput = to.input;
        dates.append(from.wrap, to.wrap);

        section.append(title, this.timingNote, list, dates);
        return section;
    }

    // Only one popover is open at a time
    toggleDropdown(id) {
        const wasOpen = this.openGroup === id;
        this.closeDropdown();
        if (!wasOpen) {
            const { toggle, popover } = this.dropdowns.get(id);
            popover.hidden = false;
            toggle.setAttribute('aria-expanded', 'true');
            this.openGroup = id;
        }
    }

    closeDropdown() {
        if (!this.openGroup) return;
        const { toggle, popover } = this.dropdowns.get(this.openGroup);
        popover.hidden = true;
        toggle.setAttribute('aria-expanded', 'false');
        this.openGroup = null;
    }

    update() {
        const state = this.searchManager.getState();
        this.updateBar(state);
        this.updateSummary(state);
    }

    // Unavailable = ticking it would show nothing, unless it is already ticked (so it can be unticked)
    setAvailability({ input, label }, selected, count, extraDisabled = false) {
        const empty = count === 0 && !selected;
        input.disabled = empty || extraDisabled;
        label.classList.toggle('is-empty', empty);
    }

    setBadge(id, n, show) {
        const { toggle, badge } = this.dropdowns.get(id);
        badge.textContent = n;
        badge.hidden = !show;
        toggle.classList.toggle('has-selection', show);
    }

    updateBar(state) {
        const rows = this.searchManager.rows;

        // When: the last ticked phase can't be unticked (there'd be nothing to show), and while a date is
        // chosen the phases are not used at all, so they are greyed out
        const dated = !!(state.timing && filterState.timingWindow(state.timing, state.today));
        const phaseCounts = filterState.countPhases(rows, state);
        for (const [phase, box] of this.phaseBoxes) {
            const selected = state.phases.includes(phase);
            box.input.checked = selected;
            box.count.textContent = phaseCounts[phase];
            this.setAvailability(box, selected, phaseCounts[phase], dated || (selected && state.phases.length === 1));
            box.label.classList.toggle('is-overridden', dated);
        }
        const phasesChanged = state.phases.join() !== filterState.DEFAULT_PHASES.join();
        this.setBadge('when', dated ? 1 : state.phases.length, dated || phasesChanged);

        // When, "Open on": one choice (or none, for a range) is ticked, with what each would show
        const timingCounts = filterState.countTimings(rows, state);
        for (const [value, box] of this.timingBoxes) {
            const selected = value === 'any' ? !state.timing : !!(state.timing && state.timing.pick === value);
            box.input.checked = selected;
            box.count.textContent = timingCounts[value];
            this.setAvailability(box, selected, timingCounts[value]);
        }
        const range = state.timing && state.timing.from ? state.timing : null;
        this.fromInput.value = range ? range.from : '';
        this.toInput.value = range ? (range.to || range.from) : '';
        this.timingNote.hidden = !dated;

        // Area: which areas are ticked, and what each would show
        const areaCounts = filterState.countAreas(rows, state, this.region);
        for (const [id, box] of this.areaBoxes) {
            const selected = state.areas.includes(id);
            box.input.checked = selected;
            box.count.textContent = areaCounts[id];
            this.setAvailability(box, selected, areaCounts[id]);
        }
        if (this.areaBoxes.size) this.setBadge('area', state.areas.length, state.areas.length > 0);

        const tagCounts = filterState.countTags(rows, state);
        const selectedPerGroup = {};
        for (const [tag, box] of this.tagBoxes) {
            const selected = state.tags.includes(tag);
            box.input.checked = selected;
            box.count.textContent = tagCounts[tag];
            if (selected) selectedPerGroup[box.group] = (selectedPerGroup[box.group] || 0) + 1;
            this.setAvailability(box, selected, tagCounts[tag]);
        }
        for (const id of this.dropdowns.keys()) {
            if (id === 'when' || id === 'area') continue;
            const n = selectedPerGroup[id] || 0;
            this.setBadge(id, n, n > 0);
        }
    }

    // The friendly card shown in place of the table when nothing matches. Built once
    // from constant text, next to the table; updateEmptyState() fills it in and
    // shows or hides it. (Only the region pages have an event table, so this does
    // nothing elsewhere.)
    buildEmptyState() {
        const table = document.getElementById('eventTable');
        this.tableWrap = table ? table.closest('.table-responsive') : null;
        if (!this.tableWrap) return;

        const el = document.createElement('div');
        el.className = 'empty-state';
        el.hidden = true;

        this.emptyTitle = document.createElement('p');
        this.emptyTitle.className = 'empty-state-title';
        this.emptyText = document.createElement('p');
        this.emptyText.className = 'empty-state-text';

        const actions = document.createElement('div');
        actions.className = 'empty-state-actions';
        this.emptyClear = document.createElement('button');
        this.emptyClear.type = 'button';
        this.emptyClear.className = 'btn btn-primary empty-state-clear';
        this.emptyClear.textContent = 'Clear all filters';
        this.emptyClear.addEventListener('click', () => this.searchManager.clearFilters());
        const add = document.createElement('a');
        add.className = 'empty-state-add';
        add.href = '../add_event.html';
        add.textContent = 'Know a show we\u2019re missing? Add an event';
        actions.append(this.emptyClear, add);

        el.append(this.emptyTitle, this.emptyText, actions);
        this.tableWrap.after(el);
        this.emptyEl = el;
    }

    // Swap the table for the card when there is nothing to show, and say why.
    updateEmptyState(state, visible) {
        if (!this.emptyEl) return;
        const empty = visible === 0;
        this.tableWrap.hidden = empty;
        this.emptyEl.hidden = !empty;
        if (!empty) return;

        if (filterState.isDefault(state)) {
            // No filters at all, so this region just has nothing current listed
            this.emptyTitle.textContent = 'Nothing on right now';
            this.emptyText.textContent = 'There are no current or upcoming art shows listed here yet. Check back soon.';
            this.emptyClear.hidden = true;
        } else {
            this.emptyTitle.textContent = 'Nothing matches that';
            this.emptyText.textContent = state.timing || state.phases.includes('past')
                ? 'Try a different search, or take off a filter.'
                : 'Try a different search, or take off a filter. Past events are hidden unless you include them in the When filter.';
            this.emptyClear.hidden = false;
        }
    }

    updateSummary(state) {
        if (!this.summaryEl) return;
        const total = this.searchManager.totalCount();
        const visible = this.searchManager.visibleCount();

        const count = document.createElement('span');
        count.className = 'filter-result-count';
        count.setAttribute('role', 'status');
        // A chosen date replaces the phases, so it is what the count line names
        const dated = !!(state.timing && filterState.timingWindow(state.timing, state.today));
        const scope = dated ? filterState.describeTiming(state.timing) : filterState.describePhases(state.phases);
        count.textContent = `Showing ${visible.toLocaleString()} of ${total.toLocaleString()} events (${scope})`;

        this.updateEmptyState(state, visible);

        const items = [count];

        const pill = (text, onRemove, what) => {
            const el = document.createElement('span');
            el.className = 'filter-pill';
            const label = document.createElement('span');
            label.textContent = text;
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.setAttribute('aria-label', `Remove filter: ${what}`);
            remove.textContent = '×';
            remove.addEventListener('click', onRemove);
            el.append(label, remove);
            return el;
        };

        if (state.q) {
            items.push(pill(`“${state.q}”`, () => this.searchManager.setSearchTerm(''), `search "${state.q}"`));
        }
        if (dated) {
            const text = filterState.describeTiming(state.timing);
            items.push(pill(text, () => this.searchManager.setTiming(null), text));
        }
        for (const id of state.areas) {
            const area = (filterState.AREAS[this.region] || []).find(a => a.id === id);
            if (area) items.push(pill(area.label, () => this.searchManager.toggleArea(id), area.label));
        }
        for (const tag of state.tags) {
            items.push(pill(this.tagLabel(tag), () => this.searchManager.toggleTagFilter(tag), this.tagLabel(tag)));
        }

        if (!filterState.isDefault(state)) {
            const clear = document.createElement('button');
            clear.type = 'button';
            clear.className = 'btn btn-link btn-sm filter-clear';
            clear.textContent = 'Clear all';
            clear.addEventListener('click', () => this.searchManager.clearFilters());
            items.push(clear);
        }

        this.summaryEl.replaceChildren(...items);
    }
}

window.FilterPanel = FilterPanel;
