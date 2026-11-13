// Run with: node --test tests/
// The "What's new" page (docs/whatsNew.js and docs/data/whats_new.json): the date wording and grouping, drawing
// the entries as text, and the real data file being well formed so a typo in a new entry fails here, not on the site.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const wn = require('../docs/whatsNew.js');

const entry = (date, title = 't', text = 'x') => ({ date, title, text });

test('days are read from the text and worded without a time zone', () => {
    assert.deepStrictEqual(wn.parseDay('2026-11-13'), { year: 2026, month: 11, day: 13 });
    assert.strictEqual(wn.dayLabel('2026-11-03'), 'Nov 3');
    assert.strictEqual(wn.dayLabel('2026-01-31'), 'Jan 31');
    assert.strictEqual(wn.monthLabel('2026-10'), 'October 2026');
    for (const bad of [undefined, null, '', '2026-13-01', '2026-02-30', '13 Nov 2026', '2026-11-13T10:00', 20261113]) {
        assert.strictEqual(wn.parseDay(bad), null, String(bad));
    }
    assert.strictEqual(wn.dayLabel('nonsense'), '');
});

test('entries are shown newest first, with same-day entries kept in file order', () => {
    const list = wn.usableEntries([entry('2026-10-26', 'old'), entry('2026-11-13', 'a'), entry('2026-11-13', 'b'), entry('2026-11-02', 'mid')]);
    assert.deepStrictEqual(list.map(e => e.title), ['a', 'b', 'mid', 'old']);
});

test('an entry without a real date, a title or text is left out; a non-list shows nothing', () => {
    const list = wn.usableEntries([entry('2026-11-13', 'ok'), entry('soon', 'x'), entry('2026-11-12', ''), entry('2026-11-11', 'no text', ''), null, 'x']);
    assert.deepStrictEqual(list.map(e => e.title), ['ok']);
    assert.deepStrictEqual(wn.usableEntries(undefined), []);
    assert.deepStrictEqual(wn.usableEntries({}), []);
});

test('entries are grouped by month, newest month first, across a year boundary', () => {
    const groups = wn.groupByMonth([entry('2025-01-05'), entry('2026-11-13'), entry('2026-11-02'), entry('2026-10-31')]);
    assert.deepStrictEqual(groups.map(g => [g.key, g.label, g.entries.length]),
        [['2026-11', 'November 2026', 2], ['2026-10', 'October 2026', 1], ['2025-01', 'January 2025', 1]]);
});

// A tiny DOM: enough for render()
function fakeDoc() {
    const make = tag => ({ tag, className: '', id: '', textContent: '', dateTime: '', attributes: {}, children: [],
        setAttribute(n, v) { this.attributes[n] = v; }, append(...c) { this.children.push(...c); },
        replaceChildren(...c) { this.children = c; } });
    return { createElement: make };
}
const findAll = (node, test, out = []) => { if (test(node)) out.push(node); (node.children || []).forEach(c => findAll(c, test, out)); return out; };

test('the page draws a heading per month and an item per entry, as text and with a machine-readable date', () => {
    const doc = fakeDoc();
    const container = doc.createElement('div');
    const count = wn.render(container, [entry('2026-11-13', '<b>Bold</b>', 'Fish & chips <img src=x>'), entry('2026-10-26', 'Old')], doc);
    assert.strictEqual(count, 2);
    assert.deepStrictEqual(findAll(container, n => n.tag === 'h2').map(n => n.textContent), ['November 2026', 'October 2026']);
    const [time] = findAll(container, n => n.tag === 'time');
    assert.strictEqual(time.dateTime, '2026-11-13');
    assert.strictEqual(time.textContent, 'Nov 13');
    const [title] = findAll(container, n => n.tag === 'h3');
    assert.strictEqual(title.textContent, '<b>Bold</b>');                     // set as text, so it is just text
    assert.strictEqual(title.innerHTML, undefined);
    // each month's heading names its list for screen readers
    const [section] = findAll(container, n => n.tag === 'section');
    assert.strictEqual(section.attributes['aria-labelledby'], 'whats-new-2026-11');
});

test('with nothing to show the page says so kindly', () => {
    const doc = fakeDoc();
    const container = doc.createElement('div');
    assert.strictEqual(wn.render(container, [], doc), 0);
    assert.match(container.children[0].textContent, /Nothing to show yet/);
});

test('the real data file is well formed: real dates, a title and text, newest first, no work-item or PR numbers', () => {
    const data = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'docs', 'data', 'whats_new.json'), 'utf8'));
    assert.ok(Array.isArray(data) && data.length > 0);
    data.forEach((e, i) => {
        assert.ok(wn.parseDay(e.date), `entry ${i} has no real date: ${e.date}`);
        assert.ok(e.title && e.title.trim() === e.title, `entry ${i} needs a title with no stray spaces`);
        assert.ok(e.text && e.text.length > 3, `entry ${i} needs text`);
        assert.ok(!/WEBSITE-\d+|#\d{1,4}\b/.test(`${e.title} ${e.text}`), `entry ${i} mentions a ticket or pull request number`);
    });
    const dates = data.map(e => e.date);
    assert.deepStrictEqual(dates, [...dates].sort().reverse(), 'entries are not sorted newest first');
    assert.strictEqual(wn.usableEntries(data).length, data.length, 'every entry is shown');
});

test('every city page, and the home page, link to the What\'s new page', () => {
    const docs = path.join(__dirname, '..', 'docs');
    for (const page of ['sf', 'la', 'mtl', 'tor', 'ist']) {
        const html = fs.readFileSync(path.join(docs, page, 'index.html'), 'utf8');
        assert.ok(html.includes('href="../whats-new.html"'), `${page}/index.html has no What's new link`);
    }
    assert.ok(fs.readFileSync(path.join(docs, 'index.html'), 'utf8').includes('href="whats-new.html"'));
});
