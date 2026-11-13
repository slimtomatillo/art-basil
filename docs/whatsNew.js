// What's new - the visitor-facing "What's new" page (whats-new.html): what changed on Art Basil, newest first, grouped
// by month (the page shows the month, not the day). The entries are hand-written in docs/data/whats_new.json
// ({ date: 'YYYY-MM-DD', title, text }); the full date is kept so entries sort within their month and so the month
// is right. This file sorts, groups and draws them. The grouping is pure (no DOM) so it can be tested in Node:
// `node --test tests/`. To add an entry, see "What's new" in OPERATIONS.md.

(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.whatsNew = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {

    const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

    // "2026-11-13" -> { year: 2026, month: 11, day: 13 }; anything else (or a day that does not exist) -> null.
    // Read from the text, never through Date's local time zone, so the day cannot shift.
    function parseDay(value) {
        const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ''));
        if (!m) return null;
        const [year, month, day] = [+m[1], +m[2], +m[3]];
        const real = new Date(Date.UTC(year, month - 1, day));
        return real.getUTCFullYear() === year && real.getUTCMonth() === month - 1 && real.getUTCDate() === day ? { year, month, day } : null;
    }

    const monthLabel = key => { const [y, m] = key.split('-').map(Number); return `${MONTHS[m - 1]} ${y}`; };

    // The entries that can be shown (a real date, a title and text), newest first; entries on the same day
    // keep the order they have in the file. [{ date, title, text }]
    function usableEntries(entries) {
        const good = (Array.isArray(entries) ? entries : []).filter(e => e && parseDay(e.date) && e.title && e.text);
        return good.map((e, i) => ({ e, i }))
            .sort((a, b) => (a.e.date < b.e.date ? 1 : a.e.date > b.e.date ? -1 : a.i - b.i))
            .map(({ e }) => ({ date: e.date, title: String(e.title), text: String(e.text) }));
    }

    // [{ key: '2026-11', label: 'November 2026', entries: [...] }, ...], newest month first
    function groupByMonth(entries) {
        const groups = [];
        for (const entry of usableEntries(entries)) {
            const key = entry.date.slice(0, 7);
            let group = groups[groups.length - 1];
            if (!group || group.key !== key) {
                group = { key, label: monthLabel(key), entries: [] };
                groups.push(group);
            }
            group.entries.push(entry);
        }
        return groups;
    }

    // Draw the groups into `container`. Everything is set as text, never as HTML.
    function render(container, entries, doc = document) {
        const groups = groupByMonth(entries);
        if (!groups.length) {
            const empty = doc.createElement('p');
            empty.className = 'text-center text-muted';
            empty.textContent = 'Nothing to show yet. Check back soon.';
            container.replaceChildren(empty);
            return 0;
        }
        const sections = groups.map(group => {
            const section = doc.createElement('section');
            section.className = 'whats-new-month';
            section.setAttribute('aria-labelledby', `whats-new-${group.key}`);
            const heading = doc.createElement('h2');
            heading.id = `whats-new-${group.key}`;
            heading.className = 'h5 whats-new-month-title';
            heading.textContent = group.label;
            const list = doc.createElement('ul');
            list.className = 'whats-new-list';
            for (const entry of group.entries) {
                const item = doc.createElement('li');
                item.className = 'whats-new-item';
                const title = doc.createElement('h3');
                title.className = 'h6 whats-new-title';
                title.textContent = entry.title;
                const text = doc.createElement('p');
                text.className = 'whats-new-text';
                text.textContent = entry.text;
                item.append(title, text);
                list.append(item);
            }
            section.append(heading, list);
            return section;
        });
        container.replaceChildren(...sections);
        return groups.reduce((n, g) => n + g.entries.length, 0);
    }

    // Load the entries and draw them; says so if they cannot be loaded
    async function load(container, url = 'data/whats_new.json') {
        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            render(container, await response.json());
        } catch (error) {
            console.error('Failed to load what\'s new:', error);
            const message = document.createElement('p');
            message.className = 'text-center text-muted';
            message.textContent = 'We couldn\'t load this just now. Please try again in a moment.';
            container.replaceChildren(message);
        }
    }

    return { parseDay, monthLabel, usableEntries, groupByMonth, render, load };
}));
