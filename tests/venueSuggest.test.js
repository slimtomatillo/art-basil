// Run with: node --test tests/
// The venue suggestions under the search box (docs/venueSuggest.js) driven through a tiny fake DOM: nothing appears
// until the visitor types, the list follows the filters' counts, the arrow keys / Enter / Escape work, a pick sets the
// venue and empties the box, and the box is announced as a combobox. No browser.
const test = require('node:test');
const assert = require('node:assert');
const filterState = require('../docs/filterState.js');
const VenueSuggest = require('../docs/venueSuggest.js');

function makeElement(tag) {
    const el = {
        tag, className: '', textContent: '', id: '', hidden: false, value: '', attributes: {}, children: [], listeners: {},
        setAttribute(name, value) { el.attributes[name] = String(value); },
        getAttribute(name) { return name in el.attributes ? el.attributes[name] : null; },
        removeAttribute(name) { delete el.attributes[name]; },
        append(...nodes) { el.children.push(...nodes); },
        replaceChildren(...nodes) { el.children = nodes; },
        addEventListener(name, fn) { el.listeners[name] = fn; },
    };
    return el;
}

function setup(counts = { 'Art Mûr': 4, 'Arter': 5, 'The Broad': 12 }) {
    const parent = makeElement('div');
    const input = makeElement('input');
    input.parentElement = parent;
    const picked = [];
    const manager = { venueCounts: () => counts, setVenue: (name, options) => picked.push([name, options]) };
    const suggest = new VenueSuggest(input, manager, { document: { createElement: makeElement }, filterState });
    const type = text => { input.value = text; input.listeners.input(); };
    const key = (k) => { const e = { key: k, prevented: false, preventDefault() { e.prevented = true; } }; input.listeners.keydown(e); return e; };
    const [list, status] = parent.children;
    const options = () => list.children;
    return { suggest, input, list, status, picked, type, key, options };
}

test('the box becomes a combobox, and nothing is offered until the visitor types', () => {
    const { input, list, status } = setup();
    assert.strictEqual(input.getAttribute('role'), 'combobox');
    assert.strictEqual(input.getAttribute('aria-autocomplete'), 'list');
    assert.strictEqual(input.getAttribute('aria-expanded'), 'false');
    assert.strictEqual(input.getAttribute('aria-controls'), list.id);
    assert.strictEqual(list.getAttribute('role'), 'listbox');
    assert.strictEqual(list.hidden, true);
    assert.strictEqual(status.textContent, '');
});

test('typing offers matching venues with their show counts, and says how many', () => {
    const { input, list, status, type, options } = setup();
    type('ar');
    assert.strictEqual(list.hidden, false);
    assert.strictEqual(input.getAttribute('aria-expanded'), 'true');
    assert.deepStrictEqual(options().map(o => [o.children[0].textContent, o.children[1].textContent]),
        [['Arter', '5 shows'], ['Art Mûr', '4 shows']]);
    assert.ok(options().every(o => o.getAttribute('role') === 'option' && o.getAttribute('aria-selected') === 'false'));
    assert.match(status.textContent, /^2 venue suggestions/);
    type('a');
    assert.strictEqual(list.hidden, true);
    assert.strictEqual(status.textContent, '');
});

test('one show is "1 show", and a single suggestion is announced in the singular', () => {
    const { type, options, status } = setup({ 'Root Division': 1 });
    type('root');
    assert.strictEqual(options()[0].children[1].textContent, '1 show');
    assert.match(status.textContent, /^1 venue suggestion\./);
});

test('the arrow keys move through the list and wrap; the active one is named by aria-activedescendant', () => {
    const { input, type, key, options } = setup();
    type('ar');
    const down = key('ArrowDown');
    assert.ok(down.prevented);
    assert.strictEqual(options()[0].getAttribute('aria-selected'), 'true');
    assert.strictEqual(input.getAttribute('aria-activedescendant'), options()[0].id);
    key('ArrowDown');
    assert.strictEqual(input.getAttribute('aria-activedescendant'), options()[1].id);
    key('ArrowDown');                                              // wraps
    assert.strictEqual(input.getAttribute('aria-activedescendant'), options()[0].id);
    key('ArrowUp');                                                // and back round
    assert.strictEqual(input.getAttribute('aria-activedescendant'), options()[1].id);
    assert.strictEqual(options()[0].getAttribute('aria-selected'), 'false');
});

test('Enter picks the active venue, sets it as the filter and empties the search text', () => {
    const { suggest, input, list, picked, type, key } = setup();
    type('ar');
    key('ArrowDown');
    key('ArrowDown');
    const enter = key('Enter');
    assert.ok(enter.prevented);
    assert.deepStrictEqual(picked, [['Art Mûr', { clearSearch: true }]]);
    assert.strictEqual(list.hidden, true);
    assert.strictEqual(input.getAttribute('aria-expanded'), 'false');
});

test('Enter with nothing highlighted is left alone, and the typed text stays a text search', () => {
    const { picked, type, key } = setup();
    type('ar');
    assert.ok(!key('Enter').prevented);
    assert.deepStrictEqual(picked, []);
});

test('clicking a suggestion picks it; a mouse press on it does not take focus from the box', () => {
    const { picked, type, options } = setup();
    type('broad');
    const option = options()[0];
    const press = { prevented: false, preventDefault() { press.prevented = true; } };
    option.listeners.mousedown(press);
    assert.ok(press.prevented);
    option.listeners.click();
    assert.deepStrictEqual(picked, [['The Broad', { clearSearch: true }]]);
});

test('Escape closes the list without clearing the text; leaving the box closes it too', () => {
    const { input, list, type, key } = setup();
    type('ar');
    assert.ok(key('Escape').prevented);
    assert.strictEqual(list.hidden, true);
    assert.strictEqual(input.value, 'ar');
    type('ar');
    input.listeners.blur();
    assert.strictEqual(list.hidden, true);
    assert.ok(!key('Escape').prevented, 'Escape with the list closed is not captured');
});

test('ArrowDown on a box that already has text opens the suggestions', () => {
    const { input, list, type, key } = setup();
    type('ar');
    input.listeners.blur();
    key('ArrowDown');
    assert.strictEqual(list.hidden, false);
});

test('venue names are set as text, never as HTML', () => {
    const { type, options } = setup({ '<img src=x onerror=alert(1)>': 3 });
    type('<img');
    // (the matching ignores punctuation, so a name like this is found by its words)
    type('img src');
    const option = options()[0];
    assert.strictEqual(option.children[0].textContent, '<img src=x onerror=alert(1)>');
    assert.strictEqual(option.children[0].innerHTML, undefined);
});
