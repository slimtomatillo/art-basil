// Venue suggest - as the visitor types in the search box, offer the names of venues that match, so a venue can be
// picked rather than searched for as text. Picking one filters to that venue (SearchManager.setVenue: the "@ Venue"
// pill) and empties the box; typing and pressing nothing else is the same text search as ever.
//
//   new VenueSuggest(inputElement, searchManager)
//
// The matching is filterState.suggestVenues; this file is the combobox around it: a list under the box, arrow
// keys and Enter, Escape to close, and a polite status line for screen readers. The list is made only when
// the box is used, and nothing from the data is ever treated as HTML.

(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.VenueSuggest = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {

    const MAX_SUGGESTIONS = 6;
    let instances = 0;

    class VenueSuggest {
        // `env` lets a test pass its own { document, filterState }
        constructor(input, searchManager, env = {}) {
            this.input = input;
            this.manager = searchManager;
            this.doc = env.document || (typeof document !== 'undefined' ? document : null);
            this.filterState = env.filterState || (typeof window !== 'undefined' ? window.filterState : null);
            this.items = [];      // [{ name, count }] now offered
            this.active = -1;     // which one the arrow keys are on
            this.optionEls = [];
            if (!this.doc || !this.filterState || !input.parentElement) return;
            instances += 1;
            this.id = `venueSuggest${instances}`;

            this.list = this.doc.createElement('div');
            this.list.id = `${this.id}List`;
            this.list.className = 'venue-suggest';
            this.list.setAttribute('role', 'listbox');
            this.list.setAttribute('aria-label', 'Venues');
            this.list.hidden = true;
            this.status = this.doc.createElement('div');
            this.status.className = 'visually-hidden';
            this.status.setAttribute('role', 'status');
            this.status.setAttribute('aria-live', 'polite');
            input.parentElement.append(this.list, this.status);

            input.setAttribute('role', 'combobox');
            input.setAttribute('aria-autocomplete', 'list');
            input.setAttribute('aria-expanded', 'false');
            input.setAttribute('aria-controls', this.list.id);
            input.setAttribute('autocomplete', 'off');

            input.addEventListener('input', () => this.update());
            input.addEventListener('keydown', (e) => this.onKey(e));
            input.addEventListener('blur', () => this.close());
        }

        update() {
            const counts = this.manager.venueCounts ? this.manager.venueCounts() : {};
            this.items = this.filterState.suggestVenues(counts, this.input.value, MAX_SUGGESTIONS);
            this.active = -1;
            this.render();
        }

        render() {
            this.optionEls = this.items.map((item, i) => {
                const option = this.doc.createElement('div');
                option.id = `${this.id}Option${i}`;
                option.className = 'venue-suggest-option';
                option.setAttribute('role', 'option');
                option.setAttribute('aria-selected', 'false');
                const name = this.doc.createElement('span');
                name.textContent = item.name;
                const count = this.doc.createElement('span');
                count.className = 'venue-suggest-count';
                count.textContent = `${item.count} ${item.count === 1 ? 'show' : 'shows'}`;
                option.append(name, count);
                // mousedown would take focus from the box, which would close the list before the click lands
                option.addEventListener('mousedown', (e) => e.preventDefault());
                option.addEventListener('click', () => this.choose(item.name));
                return option;
            });
            this.list.replaceChildren(...this.optionEls);
            const open = this.items.length > 0;
            this.list.hidden = !open;
            this.input.setAttribute('aria-expanded', String(open));
            this.input.removeAttribute('aria-activedescendant');
            this.status.textContent = open
                ? `${this.items.length} venue ${this.items.length === 1 ? 'suggestion' : 'suggestions'}. Use the up and down arrow keys, then Enter.`
                : '';
        }

        close() {
            this.items = [];
            this.active = -1;
            this.render();
        }

        move(step) {
            if (!this.items.length) return;
            this.active = (this.active + step + this.items.length) % this.items.length;
            this.optionEls.forEach((el, i) => el.setAttribute('aria-selected', String(i === this.active)));
            this.input.setAttribute('aria-activedescendant', this.optionEls[this.active].id);
            const el = this.optionEls[this.active];
            if (el.scrollIntoView) el.scrollIntoView({ block: 'nearest' });
        }

        onKey(e) {
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                if (!this.items.length) this.update();
                if (!this.items.length) return;
                e.preventDefault();
                this.move(e.key === 'ArrowDown' ? 1 : -1);
            } else if (e.key === 'Enter' && this.active >= 0) {
                e.preventDefault();
                this.choose(this.items[this.active].name);
            } else if (e.key === 'Escape' && this.items.length) {
                e.preventDefault();
                this.close();
            }
        }

        choose(name) {
            this.close();
            this.manager.setVenue(name, { clearSearch: true });
        }
    }

    return VenueSuggest;
}));
