// Run with: node --test tests/
// The "List view | Map view" toggle and the map shell (docs/mapView.js), driven through a tiny fake DOM, a
// fake search manager and a fake MapLibre: nothing is loaded until Map view is opened, what the map is
// given (region box, style, two-finger gestures), and every way it can fail going back to the list.
// No browser, no network.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const filterState = require('../docs/filterState.js');

// --- a very small DOM: just what MapView touches -------------------------------------------------
function makeElement(tag) {
    const el = {
        tag, className: '', textContent: '', hidden: false, type: '', attributes: {}, children: [], listeners: {},
        classList: { add(name) { el.className = `${el.className} ${name}`.trim(); }, remove(name) { el.className = el.className.split(' ').filter(c => c && c !== name).join(' '); } },
        setAttribute(name, value) { el.attributes[name] = String(value); },
        append(...nodes) { el.children.push(...nodes); },
        before(node) { el.beforeNode = node; },
        after(node) { el.afterNode = node; },
        addEventListener(name, fn) { el.listeners[name] = fn; },
        click() { el.listeners.click(); },
        closest() { return el.wrap; },
        querySelector(selector) { return selector === 'span' ? (el.spanEl ||= makeElement('span')) : null; },
        insertBefore(node, reference) { el.inserted = { node, reference }; },
    };
    return el;
}

// A search manager with the real filterState rules for the view, and the real URL writing
function makeSearchManager(search = '') {
    const manager = {
        state: filterState.parseUrl(search), listeners: [], url: search,
        subscribe(fn) { manager.listeners.push(fn); },
        setView(view) {
            if (!filterState.VIEWS.includes(view) || view === manager.state.view) return;
            manager.state.view = view;
            manager.url = filterState.toQuery(manager.state);
            manager.listeners.forEach(fn => fn());
        },
    };
    return manager;
}

// A fake MapLibre: records how the Map was made and lets a test fire its events
function makeLibrary() {
    const library = { maps: [], controls: [] };
    library.Map = class {
        constructor(options) {
            this.options = options; this.handlers = {}; this.removed = false; this.controls = [];
            library.maps.push(this);
        }
        on(name, fn) { this.handlers[name] = fn; }
        addControl(control, where) { this.controls.push({ control, where }); }
        remove() { this.removed = true; }
        fire(name) { if (this.handlers[name]) this.handlers[name](); }
    };
    library.NavigationControl = class { constructor(options) { this.options = options; } };
    return library;
}

const BOUNDS = { lat: [36.9, 38.6], lng: [-123.1, -121.5] };

function setup({ search = '', webgl = true, loadLibrary, loadBounds, timeoutMs = 50, summary = true } = {}) {
    const bar = makeElement('div');
    const table = makeElement('table');
    const wrap = makeElement('div');
    table.wrap = wrap;
    const bodyClasses = makeElement('body');
    const page = makeElement('div');                              // what holds #filterSummary on the real page
    const summaryEl = summary ? makeElement('div') : null;
    if (summaryEl) summaryEl.parentNode = page;
    const document = {
        querySelector: selector => (selector === '#filterPanel .filter-bar' ? bar : null),
        getElementById: id => (id === 'eventTable' ? table : (id === 'filterSummary' ? summaryEl : null)),
        createElement: tag => {
            const el = makeElement(tag);
            if (tag === 'canvas') el.getContext = () => (webgl ? {} : null);
            return el;
        },
        body: bodyClasses, baseURI: 'http://localhost/sf/', head: makeElement('head'), currentScript: null,
    };
    const sandbox = { window: {}, document, console, URL, setTimeout, clearTimeout };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../docs/mapView.js'), 'utf8')
        .replace('window.MapView = MapView;', 'globalThis.MapView = MapView; globalThis.MAP_STYLE_URL = MAP_STYLE_URL;'), sandbox);

    const library = makeLibrary();
    const calls = { library: 0, bounds: 0 };
    const manager = makeSearchManager(search);
    const quiet = console.error; console.error = () => {};
    const view = new sandbox.MapView(manager, {
        loadLibrary: loadLibrary || (async () => { calls.library++; return library; }),
        loadBounds: loadBounds || (async () => { calls.bounds++; return BOUNDS; }),
        timeoutMs,
    });
    return { view, manager, library, calls, bar, wrap, page, summaryEl, body: bodyClasses, sandbox, restore: () => { console.error = quiet; } };
}

const settle = () => new Promise(resolve => setImmediate(resolve));
const buttons = ctx => ctx.view.buttons;

test('opens on the list: nothing is loaded or asked for, and the toggle says so', () => {
    const ctx = setup();
    assert.strictEqual(ctx.calls.library, 0);
    assert.strictEqual(ctx.calls.bounds, 0);
    assert.strictEqual(ctx.library.maps.length, 0);
    assert.strictEqual(ctx.view.section.hidden, true);
    assert.strictEqual(ctx.body.className, '');
    assert.strictEqual(buttons(ctx).list.attributes['aria-pressed'], 'true');
    assert.strictEqual(buttons(ctx).map.attributes['aria-pressed'], 'false');
    assert.strictEqual(ctx.view.toggle.attributes.role, 'group');
    ctx.restore();
});

test('the toggle sits on the results line, beside the "Showing X of Y" summary, not among the filters', () => {
    const ctx = setup();
    assert.deepStrictEqual(ctx.view.resultsBar.children, [ctx.summaryEl, ctx.view.toggle]);
    assert.strictEqual(ctx.view.resultsBar.className, 'results-bar');
    assert.strictEqual(ctx.page.inserted.node, ctx.view.resultsBar);          // put where the summary was
    assert.strictEqual(ctx.page.inserted.reference, ctx.summaryEl);
    assert.deepStrictEqual(ctx.bar.children, []);                             // nothing added to the filter bar
    assert.match(ctx.view.buttons.list.innerHTML, /<svg/);                    // each segment has its icon
    assert.match(ctx.view.buttons.map.innerHTML, /<svg/);
    assert.strictEqual(ctx.view.buttons.list.spanEl.textContent, 'List view');
    assert.strictEqual(ctx.view.buttons.map.spanEl.textContent, 'Map view');
    assert.strictEqual(ctx.view.resultsBar.afterNode, ctx.view.message);      // a "why you're back on the list" note sits right under it
    ctx.restore();
});

test('on a page with no results line the toggle falls back to the end of the filter bar', () => {
    const ctx = setup({ summary: false });
    assert.strictEqual(ctx.view.resultsBar, undefined);
    assert.deepStrictEqual(ctx.bar.children, [ctx.view.toggle]);
    ctx.restore();
});

test('the map goes before the table and a one-line privacy note sits with it', () => {
    const ctx = setup();
    assert.strictEqual(ctx.wrap.beforeNode, ctx.view.section);
    assert.match(ctx.view.note.textContent, /shares your IP address with OpenFreeMap/);
    assert.match(ctx.view.note.textContent, /location is never sent/);
    assert.match(ctx.view.alternative.textContent, /list view has the same information as text/);
    ctx.restore();
});

test('opening Map view loads the library, frames the region, and turns on two-finger gestures', async () => {
    const ctx = setup();
    buttons(ctx).map.click();
    await settle();
    assert.strictEqual(ctx.manager.url, '?view=map');
    assert.strictEqual(ctx.calls.library, 1);
    assert.strictEqual(ctx.calls.bounds, 1);
    assert.strictEqual(ctx.library.maps.length, 1);
    const options = ctx.library.maps[0].options;
    assert.strictEqual(options.container, ctx.view.canvas);
    assert.strictEqual(options.style, 'https://tiles.openfreemap.org/styles/positron');
    assert.deepStrictEqual(JSON.parse(JSON.stringify(options.bounds)), [[-123.1, 36.9], [-121.5, 38.6]]);   // [[west, south], [east, north]]
    assert.strictEqual(options.cooperativeGestures, true);
    assert.notStrictEqual(options.attributionControl, false);                                                // attribution stays on
    assert.strictEqual(ctx.library.maps[0].controls[0].where, 'top-right');
    assert.strictEqual(ctx.view.section.hidden, false);
    assert.strictEqual(ctx.body.className, 'map-view-on');
    assert.strictEqual(buttons(ctx).map.attributes['aria-pressed'], 'true');
    ctx.library.maps[0].fire('load');
    assert.strictEqual(ctx.view.status.hidden, true);
    ctx.restore();
});

test('the map is made once; going back and forth reuses it and loads nothing more', async () => {
    const ctx = setup();
    buttons(ctx).map.click();
    await settle();
    ctx.library.maps[0].fire('load');
    buttons(ctx).list.click();
    assert.strictEqual(ctx.view.section.hidden, true);
    assert.strictEqual(ctx.body.className, '');
    assert.strictEqual(ctx.manager.url, '');
    buttons(ctx).map.click();
    await settle();
    assert.strictEqual(ctx.library.maps.length, 1);
    assert.strictEqual(ctx.calls.library, 1);
    assert.strictEqual(ctx.view.section.hidden, false);
    ctx.restore();
});

test('a shared ?view=map link opens the map straight away, and keeps the other filters in the URL', async () => {
    const ctx = setup({ search: '?q=Wattis&phase=past&view=map' });
    await settle();
    assert.strictEqual(ctx.library.maps.length, 1);
    assert.strictEqual(buttons(ctx).map.attributes['aria-pressed'], 'true');
    buttons(ctx).list.click();
    assert.strictEqual(ctx.manager.url, '?q=Wattis&phase=past');
    ctx.restore();
});

test('the existing shared links open on the list and load nothing', () => {
    for (const search of ['?search=SFMOMA', '?phase=future', '?tags=free', '?q=Wattis&phase=past']) {
        const ctx = setup({ search });
        assert.strictEqual(ctx.calls.library, 0, search);
        assert.strictEqual(ctx.view.section.hidden, true, search);
        ctx.restore();
    }
});

test('a library that will not load sends the visitor back to the list with a short note', async () => {
    const ctx = setup({ search: '?view=map', loadLibrary: async () => { throw new Error('blocked'); } });
    await settle();
    assert.match(ctx.view.message.textContent, /couldn.t load/);
    assert.strictEqual(ctx.view.message.hidden, false);
    assert.strictEqual(ctx.manager.state.view, 'list');
    assert.strictEqual(ctx.manager.url, '');                                  // the URL no longer says map
    assert.strictEqual(ctx.view.section.hidden, true);
    assert.strictEqual(ctx.body.className, '');
    assert.strictEqual(buttons(ctx).list.attributes['aria-pressed'], 'true');
    ctx.restore();
});

test('a browser with no WebGL says so and shows the list, without loading the library', async () => {
    const ctx = setup({ webgl: false });
    buttons(ctx).map.click();
    await settle();
    assert.match(ctx.view.message.textContent, /needs WebGL/);
    assert.strictEqual(ctx.calls.library, 0);
    assert.strictEqual(ctx.manager.state.view, 'list');
    ctx.restore();
});

test('a style that cannot be fetched (offline) removes the map and goes back to the list', async () => {
    const ctx = setup();
    buttons(ctx).map.click();
    await settle();
    ctx.library.maps[0].fire('error');                                        // before it ever loaded
    assert.match(ctx.view.message.textContent, /couldn.t load/);
    assert.strictEqual(ctx.library.maps[0].removed, true);
    assert.strictEqual(ctx.manager.state.view, 'list');
    ctx.restore();
});

test('a tile that fails after the map has loaded is just a gap, not a failure', async () => {
    const ctx = setup();
    buttons(ctx).map.click();
    await settle();
    ctx.library.maps[0].fire('load');
    ctx.library.maps[0].fire('error');
    assert.strictEqual(ctx.manager.state.view, 'map');
    assert.strictEqual(ctx.view.message.hidden, true);
    ctx.restore();
});

test('a map that never loads is given up on after the timeout', async () => {
    const ctx = setup({ timeoutMs: 20 });
    buttons(ctx).map.click();
    await settle();
    await new Promise(resolve => setTimeout(resolve, 60));
    assert.match(ctx.view.message.textContent, /couldn.t load/);
    assert.strictEqual(ctx.manager.state.view, 'list');
    ctx.restore();
});

test('a map opened in a tab that goes to the background is not given up on until the visitor is back', async () => {
    const ctx = setup({ timeoutMs: 20 });
    ctx.sandbox.document.hidden = true;                                       // the tab is in the background: no frames, so no load
    buttons(ctx).map.click();
    await settle();
    await new Promise(resolve => setTimeout(resolve, 70));                    // well past the timeout, twice over
    assert.strictEqual(ctx.manager.state.view, 'map');
    assert.strictEqual(ctx.view.message.hidden, true);
    ctx.library.maps[0].fire('load');                                         // back in front, it finishes loading
    await new Promise(resolve => setTimeout(resolve, 40));
    assert.strictEqual(ctx.manager.state.view, 'map');
    assert.strictEqual(ctx.view.status.hidden, true);
    ctx.restore();
});

test('a visible tab whose map still has not loaded is given up on', async () => {
    const ctx = setup({ timeoutMs: 20 });
    ctx.sandbox.document.hidden = false;
    buttons(ctx).map.click();
    await settle();
    await new Promise(resolve => setTimeout(resolve, 60));
    assert.strictEqual(ctx.manager.state.view, 'list');
    ctx.restore();
});

test('after a failure the next click on Map view tries again from scratch', async () => {
    let attempts = 0;
    const library = makeLibrary();
    const ctx = setup({ loadLibrary: async () => { attempts++; if (attempts === 1) throw new Error('offline'); return library; } });
    buttons(ctx).map.click();
    await settle();
    assert.strictEqual(ctx.manager.state.view, 'list');
    buttons(ctx).map.click();
    await settle();
    assert.strictEqual(attempts, 2);
    assert.strictEqual(library.maps.length, 1);
    assert.strictEqual(ctx.view.message.hidden, true);                        // the old note is cleared when the map is tried again
    ctx.restore();
});

test('a region with no box on file cannot be framed, so it falls back to the list', async () => {
    const ctx = setup({ loadBounds: async () => null });
    buttons(ctx).map.click();
    await settle();
    assert.strictEqual(ctx.manager.state.view, 'list');
    assert.match(ctx.view.message.textContent, /couldn.t load/);
    ctx.restore();
});

test('going back to the list while the library is still loading does not build a hidden map', async () => {
    let release;
    const library = makeLibrary();
    const ctx = setup({ loadLibrary: () => new Promise(resolve => { release = () => resolve(library); }) });
    buttons(ctx).map.click();
    buttons(ctx).list.click();
    release();
    await settle();
    assert.strictEqual(library.maps.length, 0);
    assert.strictEqual(ctx.view.status.hidden, true);
    ctx.restore();
});

test('a page with no filter bar or table (not a region page) gets nothing added', () => {
    const document = { querySelector: () => null, getElementById: () => null, createElement: makeElement, body: makeElement('body'), baseURI: 'http://x/', currentScript: null };
    const sandbox = { window: {}, document, console, URL, setTimeout, clearTimeout };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../docs/mapView.js'), 'utf8').replace('window.MapView = MapView;', 'globalThis.MapView = MapView;'), sandbox);
    const none = new sandbox.MapView(makeSearchManager(), { loadBounds: async () => BOUNDS });
    assert.strictEqual(none.available, false);
});
