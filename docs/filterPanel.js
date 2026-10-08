// Filter Panel - the visible filter controls: a row of independent dropdowns
// (Medium, Theme, Cost, ...), each opening a popover of tag checkboxes with
// counts, plus a summary line with the result count, the active filters as
// removable pills, and "Clear all". All state lives in SearchManager; this only
// draws it and forwards clicks.

class FilterPanel {
    constructor(searchManager) {
        this.searchManager = searchManager;
        this.panelEl = document.getElementById('filterPanel');
        this.summaryEl = document.getElementById('filterSummary');
        this.dropdowns = new Map();    // group id -> { wrap, toggle, badge, popover }
        this.checkboxes = new Map();   // tag -> { input, label, count, group }
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

        for (const group of filterState.TAG_GROUPS) {
            // Only offer tags this region actually has, and no dropdown at all if there are none
            const tags = group.tags.filter(tag => !hidden.has(tag) && rows.some(row => row.tags.includes(tag)));
            if (tags.length === 0) continue;

            const wrap = document.createElement('div');
            wrap.className = 'filter-dropdown';
            wrap.dataset.group = group.id;

            const toggle = document.createElement('button');
            toggle.type = 'button';
            toggle.className = 'filter-dropdown-toggle';
            toggle.setAttribute('aria-haspopup', 'true');
            toggle.setAttribute('aria-expanded', 'false');
            const label = document.createElement('span');
            label.textContent = group.label;
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
            popover.setAttribute('aria-label', group.label);
            popover.hidden = true;

            const options = document.createElement('div');
            options.className = 'filter-options';
            for (const tag of tags) {
                const optionLabel = document.createElement('label');
                optionLabel.className = 'filter-option';

                const input = document.createElement('input');
                input.type = 'checkbox';
                input.value = tag;
                input.addEventListener('change', () => this.searchManager.toggleTagFilter(tag));

                const dot = document.createElement('span');
                dot.className = 'filter-dot';
                dot.style.backgroundColor = this.tagColor(tag);

                const name = document.createElement('span');
                name.className = 'filter-name';
                name.textContent = this.tagLabel(tag);

                const count = document.createElement('span');
                count.className = 'filter-n';

                optionLabel.append(input, dot, name, count);
                options.append(optionLabel);
                this.checkboxes.set(tag, { input, label: optionLabel, count, group: group.id });
            }
            popover.append(options);

            toggle.addEventListener('click', () => this.toggleDropdown(group.id));
            wrap.append(toggle, popover);
            bar.append(wrap);
            this.dropdowns.set(group.id, { wrap, toggle, badge, popover });
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

    // Only one popover is open at a time
    toggleDropdown(groupId) {
        const wasOpen = this.openGroup === groupId;
        this.closeDropdown();
        if (!wasOpen) {
            const { toggle, popover } = this.dropdowns.get(groupId);
            popover.hidden = false;
            toggle.setAttribute('aria-expanded', 'true');
            this.openGroup = groupId;
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

    updateBar(state) {
        if (this.checkboxes.size === 0) return;
        const counts = filterState.countTags(this.searchManager.rows, state);
        const selectedPerGroup = {};
        for (const [tag, { input, label, count, group }] of this.checkboxes) {
            const selected = state.tags.includes(tag);
            input.checked = selected;
            count.textContent = counts[tag];
            if (selected) selectedPerGroup[group] = (selectedPerGroup[group] || 0) + 1;
            // A tag that would show nothing is unavailable, unless it is already selected (so it can be unticked)
            const empty = counts[tag] === 0 && !selected;
            input.disabled = empty;
            label.classList.toggle('is-empty', empty);
        }
        for (const [groupId, { toggle, badge }] of this.dropdowns) {
            const n = selectedPerGroup[groupId] || 0;
            badge.textContent = n;
            badge.hidden = n === 0;
            toggle.classList.toggle('has-selection', n > 0);
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
            : `Showing ${visible.toLocaleString()} of ${total.toLocaleString()} events (${filterState.PHASE_LABELS[state.phase]})`;

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
