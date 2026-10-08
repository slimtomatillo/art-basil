// Filter Panel - the visible filter controls: a row of independent dropdowns
// (When, Medium, Theme, Cost, ...), each opening a popover of checkboxes with
// counts, plus a summary line with the result count, the active filters as
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
        this.openGroup = null;

        if (this.panelEl) this.buildBar();
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

        // When: which phases to show. Always first, since it is the biggest cut of the list.
        bar.append(this.buildDropdown('when', 'When', filterState.ALL_PHASES.map(phase => ({
            value: phase,
            label: filterState.PHASE_LABELS[phase],
            color: this.tagColor(phase),
            onChange: () => this.searchManager.togglePhase(phase),
            register: (box) => this.phaseBoxes.set(phase, box),
        }))));

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

    // One dropdown: a button that opens a popover of checkbox options
    buildDropdown(id, labelText, options) {
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
            dot.style.backgroundColor = option.color;

            const name = document.createElement('span');
            name.className = 'filter-name';
            name.textContent = option.label;

            const count = document.createElement('span');
            count.className = 'filter-n';

            optionLabel.append(input, dot, name, count);
            list.append(optionLabel);
            option.register({ input, label: optionLabel, count });
        }
        popover.append(list);

        toggle.addEventListener('click', () => this.toggleDropdown(id));
        wrap.append(toggle, popover);
        this.dropdowns.set(id, { toggle, badge, popover });
        return wrap;
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

        // When: the last ticked phase can't be unticked (there'd be nothing to show)
        const phaseCounts = filterState.countPhases(rows, state);
        for (const [phase, box] of this.phaseBoxes) {
            const selected = state.phases.includes(phase);
            box.input.checked = selected;
            box.count.textContent = phaseCounts[phase];
            this.setAvailability(box, selected, phaseCounts[phase], selected && state.phases.length === 1);
        }
        const phasesChanged = state.phases.join() !== filterState.DEFAULT_PHASES.join();
        this.setBadge('when', state.phases.length, phasesChanged);

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
            if (id === 'when') continue;
            const n = selectedPerGroup[id] || 0;
            this.setBadge(id, n, n > 0);
        }
    }

    updateSummary(state) {
        if (!this.summaryEl) return;
        const total = this.searchManager.totalCount();
        const visible = this.searchManager.visibleCount();

        const count = document.createElement('span');
        count.className = 'filter-result-count';
        count.setAttribute('role', 'status');
        count.textContent = visible === 0
            ? 'No events match these filters.'
            : `Showing ${visible.toLocaleString()} of ${total.toLocaleString()} events (${filterState.describePhases(state.phases)})`;

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
        for (const tag of state.tags) {
            items.push(pill(this.tagLabel(tag), () => this.searchManager.toggleTagFilter(tag), this.tagLabel(tag)));
        }
        if (!state.ongoing) {
            items.push(pill('ongoing hidden', () => this.searchManager.setOngoingFilter(true), 'ongoing hidden'));
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
