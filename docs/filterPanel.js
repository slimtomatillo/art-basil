// Filter Panel - the visible filter controls: a collapsible panel of tag
// checkboxes (grouped, with counts) and a summary line with the result count,
// the active filters as removable pills, and "Clear all". All state lives in
// SearchManager; this only draws it and forwards clicks.

class FilterPanel {
    constructor(searchManager) {
        this.searchManager = searchManager;
        this.panelEl = document.getElementById('filterPanel');
        this.summaryEl = document.getElementById('filterSummary');
        this.checkboxes = new Map();   // tag -> { input, label, count }
        this.badge = null;

        if (this.panelEl) this.buildPanel();
        searchManager.subscribe(() => this.update());
        this.update();
    }

    tagLabel(tag) {
        return tag.replace(/-/g, ' ');
    }

    tagColor(tag) {
        // getTagColor comes from tableRenderer.js, so panel dots match the table chips
        return typeof getTagColor === 'function' ? getTagColor(tag) : '#6c757d';
    }

    // Built once; update() only changes counts and checked/disabled states, so
    // the panel's open/closed state and the visitor's focus aren't lost.
    buildPanel() {
        const rows = this.searchManager.rows;
        const hidden = typeof HIDDEN_TAGS !== 'undefined' ? HIDDEN_TAGS : new Set();

        const details = document.createElement('details');
        details.className = 'filter-panel';
        // Open on wide screens (so the options are discoverable); closed on phones, where it would push the table down
        details.open = window.matchMedia('(min-width: 768px)').matches;

        const summary = document.createElement('summary');
        summary.className = 'filter-panel-toggle';
        summary.append('Filter by medium, theme & type ');
        this.badge = document.createElement('span');
        this.badge.className = 'filter-badge';
        this.badge.hidden = true;
        summary.append(this.badge);
        details.append(summary);

        const groups = document.createElement('div');
        groups.className = 'filter-groups';

        for (const group of filterState.TAG_GROUPS) {
            // Only offer tags this region actually has
            const tags = group.tags.filter(tag => !hidden.has(tag) && rows.some(row => row.tags.includes(tag)));
            if (tags.length === 0) continue;

            const fieldset = document.createElement('fieldset');
            fieldset.className = 'filter-group';
            fieldset.dataset.group = group.id;
            const legend = document.createElement('legend');
            legend.textContent = group.label;
            fieldset.append(legend);

            for (const tag of tags) {
                const label = document.createElement('label');
                label.className = 'filter-option';

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

                label.append(input, dot, name, count);
                fieldset.append(label);
                this.checkboxes.set(tag, { input, label, count });
            }
            groups.append(fieldset);
        }

        details.append(groups);
        this.panelEl.replaceChildren(details);
    }

    update() {
        const state = this.searchManager.getState();
        this.updatePanel(state);
        this.updateSummary(state);
    }

    updatePanel(state) {
        if (this.checkboxes.size === 0) return;
        const counts = filterState.countTags(this.searchManager.rows, state);
        for (const [tag, { input, label, count }] of this.checkboxes) {
            const selected = state.tags.includes(tag);
            input.checked = selected;
            count.textContent = counts[tag];
            // A tag that would show nothing is unavailable, unless it is already selected (so it can be unticked)
            const empty = counts[tag] === 0 && !selected;
            input.disabled = empty;
            label.classList.toggle('is-empty', empty);
        }
        const selectedInPanel = state.tags.filter(tag => this.checkboxes.has(tag)).length;
        this.badge.textContent = selectedInPanel;
        this.badge.hidden = selectedInPanel === 0;
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
