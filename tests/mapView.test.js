// Run with: node --test tests/
// The "List view | Map view" toggle, the map and its pins (docs/mapView.js), driven through a tiny fake DOM, a
// fake search manager and a fake MapLibre: nothing is loaded until Map view is opened, what the map is
// given (region box, style, two-finger gestures), every way it can fail going back to the list, and the pins:
// clustering, popups, the list of places, framing, the empty state and the "you are here" dot.
// No browser, no network.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const filterState = require('../docs/filterState.js');
const venueAddresses = require('../docs/venueAddresses.js');

// --- a very small DOM: just what MapView touches -------------------------------------------------
function makeElement(tag) {
    const el = {
        tag, className: '', textContent: '', hidden: false, type: '', attributes: {}, children: [], listeners: {}, style: {},
        classList: { add(name) { el.className = `${el.className} ${name}`.trim(); }, remove(name) { el.className = el.className.split(' ').filter(c => c && c !== name).join(' '); } },
        setAttribute(name, value) { el.attributes[name] = String(value); },
        append(...nodes) { el.children.push(...nodes); },
        replaceChildren(...nodes) { el.children = nodes; },
        before(node) { el.beforeNode = node; },
        after(node) { el.afterNode = node; },
        addEventListener(name, fn) { el.listeners[name] = fn; },
        click() { el.listeners.click(); },
        closest() { return el.wrap; },
        contains(node) { return node === el || el.children.some(child => child.contains && child.contains(node)); },
        focus() { el.focused = (el.focused || 0) + 1; },
        querySelector(selector) { return selector === 'span' ? (el.spanEl ||= makeElement('span')) : null; },
        insertBefore(node, reference) { el.inserted = { node, reference }; },
    };
    return el;
}

// A search manager with the real filterState rules for the view, and the real URL writing
function makeSearchManager(search = '', rows = []) {
    const manager = {
        state: filterState.parseUrl(search), listeners: [], url: search, rows, cleared: 0,
        subscribe(fn) { manager.listeners.push(fn); },
        matchingRows() { return manager.rows; },
        clearFilters() { manager.cleared += 1; },
        changeRows(rows) { manager.rows = rows; manager.listeners.forEach(fn => fn()); },
        setView(view) {
            if (!filterState.VIEWS.includes(view) || view === manager.state.view) return;
            manager.state.view = view;
            manager.url = filterState.toQuery(manager.state);
            manager.listeners.forEach(fn => fn());
        },
    };
    return manager;
}

// A fake MapLibre: records how the Map was made, what is drawn on it, and lets a test fire its events
function makeLibrary() {
    const library = { maps: [], popups: [], markers: [], popupRect: { left: 40, top: 100, right: 300, bottom: 300 } };   // a popup that fits
    library.Map = class {
        constructor(options) {
            Object.assign(this, { options, handlers: {}, sources: {}, layers: [], fitted: [], eased: [],
                                  flown: [], controls: [], removed: false, zoom: 8, canvasStyle: {}, containerWidth: 800, containerHeight: 600, queries: [], rendered: [], panned: [], onceHandlers: {} });
            library.maps.push(this);
        }
        on(name, handler) { this.handlers[name] = handler; }
        addControl(control, where) { this.controls.push({ control, where }); }
        addSource(id, definition) {
            this.sources[id] = { definition, data: definition.data, setCalls: 0,
                setData(data) { this.data = data; this.setCalls += 1; },
                getClusterExpansionZoom: async clusterId => 9 + clusterId };
        }
        addLayer(layer) { this.layers.push(layer); }
        getSource(id) { return this.sources[id]; }
        getCanvas() { return this.canvas || (this.canvas = { style: this.canvasStyle, focus() { this.focused = (this.focused || 0) + 1; } }); }
        // The map's box on the page (the popup tests check it against the popup's box)
        getContainer() {
            return { clientWidth: this.containerWidth, clientHeight: this.containerHeight,
                     getBoundingClientRect: () => ({ left: 0, top: 0, right: this.containerWidth, bottom: this.containerHeight }) };
        }
        once(name, handler) { this.onceHandlers[name] = handler; }
        panBy(offset, options) { this.panned.push({ offset, options }); }
        // What is drawn near a tap: a test sets `rendered`; project() puts [lng, lat] at x = lng, y = lat
        queryRenderedFeatures(box, options) { this.queries.push({ box, options }); return this.rendered; }
        project(coordinates) { return { x: coordinates[0], y: coordinates[1] }; }
        getZoom() { return this.zoom; }
        fitBounds(bounds, options) { this.fitted.push({ bounds, options }); }
        easeTo(options) { this.eased.push(options); }
        flyTo(options) { this.flown.push(options); }
        remove() { this.removed = true; }
        fire(name, event) {
            if (this.handlers[name]) this.handlers[name](event);
            if (this.onceHandlers[name]) { const handler = this.onceHandlers[name]; delete this.onceHandlers[name]; handler(event); }
        }
    };
    library.NavigationControl = class { constructor(options) { this.options = options; } };
    library.Popup = class {
        constructor(options) { this.options = options; this.removed = false; this.rect = library.popupRect; this.listeners = {}; library.popups.push(this); }
        on(name, handler) { this.listeners[name] = handler; return this; }
        setLngLat(lngLat) { this.lngLat = lngLat; return this; }
        setDOMContent(content) { this.content = content; return this; }
        getElement() { return { getBoundingClientRect: () => this.rect }; }
        addTo(map) { this.map = map; return this; }
        remove() { this.removed = true; if (this.listeners.close) this.listeners.close(); }   // MapLibre fires 'close' for any removal
    };
    library.Marker = class {
        constructor(options) { this.options = options; this.removed = false; library.markers.push(this); }
        setLngLat(lngLat) { this.lngLat = lngLat; return this; }
        addTo(map) { this.map = map; return this; }
        remove() { this.removed = true; }
    };
    return library;
}

const BOUNDS = { lat: [36.9, 38.6], lng: [-123.1, -121.5] };

const COORDINATES = {
    'Gallery A': [{ lat: 37.78, lng: -122.41 }],
    'Gallery B': [{ lat: 37.78, lng: -122.41 }],
    'Museum': [{ lat: 37.8, lng: -122.3 }],
    'Two Spaces': [{ lat: 34.05, lng: -118.25 }, { lat: 34.06, lng: -118.3 }],
};
const VENUES = {
    'Gallery A': '10 Main St, San Francisco, CA',
    'Gallery B': '10 Main St, San Francisco, CA',
    'Museum': '1 Museum Way, Oakland, CA',
    'Two Spaces': [{ label: 'Downtown', address: '1 A St, Los Angeles' }, { label: 'Hollywood', address: '2 B St, Los Angeles' }],
    'No Coordinates': '5 Nowhere Rd',
};
const showRow = (venue, name, dateText = 'Through Dec 1, 2026') => ({
    venue, dateText, event: { name, phase: 'current', links: [{ link: `https://shows.example/${name.replace(/ /g, '-')}`, description: 'Event Page' }] },
});
const DATA = { coordinates: COORDINATES, bounds: BOUNDS_FOR_DATA() };
function BOUNDS_FOR_DATA() { return { lat: [36.9, 38.6], lng: [-123.1, -121.5] }; }

// The map gives up if it has not loaded within `timeoutMs` of real time. A test that is not about that timeout must not
// race a clock: with a short default, a pause of 50 ms between the click and the test firing the fake map's "load" (a
// cold or busy process: the first deepStrictEqual loads Node's comparison code) made the map give up, go back to the
// list and empty the URL, so "opening Map view" failed about 1 run in 7. So the default is long, and the three tests
// of the timeout itself pass a short one.
const NO_TIMEOUT_MS = 30000;

function setup({ search = '', webgl = true, loadLibrary, loadData, timeoutMs = NO_TIMEOUT_MS, summary = true, rows = [], distances = {} } = {}) {
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
    document.listeners = {};
    document.addEventListener = (name, fn) => { document.listeners[name] = fn; };
    // Timers the page code starts must not keep Node alive: a long timeout that a test never reaches would otherwise
    // hold the process for its whole length
    const unrefTimeout = (fn, ms, ...args) => { const timer = setTimeout(fn, ms, ...args); if (timer.unref) timer.unref(); return timer; };
    const sandbox = { window: {}, document, console, URL, setTimeout: unrefTimeout, clearTimeout };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../docs/nearMe.js'), 'utf8'), sandbox);        // mapPins needs nearMe
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../docs/mapPins.js'), 'utf8'), sandbox);
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../docs/mapView.js'), 'utf8')
        .replace('window.MapView = MapView;', 'globalThis.MapView = MapView; globalThis.MAP_STYLE_URL = MAP_STYLE_URL;'), sandbox);

    const library = makeLibrary();
    const calls = { library: 0, data: 0 };
    const manager = makeSearchManager(search, rows);
    const quiet = console.error; console.error = () => {};
    const view = new sandbox.MapView(manager, {
        loadLibrary: loadLibrary || (async () => { calls.library++; return library; }),
        loadData: loadData || (async () => { calls.data++; return DATA; }),
        venues: VENUES,
        addressesOf: venue => venueAddresses.normalize(VENUES[venue]),
        mapLinksFor: venue => venueAddresses.mapLinks(VENUES[venue]),
        distanceTextFor: venue => distances[venue] || null,
        accent: '#14806b',
        timeoutMs,
    });
    return { view, manager, library, calls, bar, wrap, page, summaryEl, body: bodyClasses, sandbox, document, restore: () => { console.error = quiet; } };
}

const settle = () => new Promise(resolve => setImmediate(resolve));
const buttons = ctx => ctx.view.buttons;

test('opens on the list: nothing is loaded or asked for, and the toggle says so', () => {
    const ctx = setup();
    assert.strictEqual(ctx.calls.library, 0);
    assert.strictEqual(ctx.calls.data, 0);
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
    assert.strictEqual(ctx.calls.data, 1);
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
    const ctx = setup({ loadData: async () => ({ coordinates: {}, bounds: null }) });
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
    const none = new sandbox.MapView(makeSearchManager(), { loadData: async () => DATA });
    assert.strictEqual(none.available, false);
});

// ---------------------------------------------------------------------------------------------------------------
// The pins (WEBSITE-103)

const textOf = node => (node === undefined || node === null ? '' : typeof node === 'string' ? node
    : [node.textContent || '', ...(node.children || []).map(textOf)].join(' ').replace(/\s+/g, ' ').trim());
function findAll(node, predicate, found = []) {
    if (node && typeof node === 'object') {
        if (predicate(node)) found.push(node);
        (node.children || []).forEach(child => findAll(child, predicate, found));
    }
    return found;
}
const openMap = async ctx => {
    buttons(ctx).map.click();
    await settle();
    const map = ctx.library.maps[0];
    map.fire('load');
    return map;
};
const keyOf = (ctx, venue) => ctx.view.locations.find(location => location.venues.some(v => v.name === venue)).key;
// A tap on a pin: the map reports the pin it drew there (at point (0, 0), where the tap is)
const pinFeature = (key, at = [0, 0]) => ({ properties: { key }, geometry: { coordinates: at } });
const clusterFeature = (clusterId, at = [0, 0]) => ({ properties: { cluster: true, cluster_id: clusterId }, geometry: { coordinates: at } });
const tapAt = (map, features, point = { x: 0, y: 0 }) => { map.rendered = features; map.fire('click', { point }); };
const clickPin = (map, key) => tapAt(map, [pinFeature(key)]);

test('a clustered source and four layers are added, drawn in the region colour, with show counts', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'M1'), showRow('Gallery A', 'A1')] });
    const map = await openMap(ctx);
    const { definition } = map.sources.locations;
    assert.strictEqual(definition.type, 'geojson');
    assert.strictEqual(definition.cluster, true);
    assert.strictEqual(definition.clusterRadius, 46);
    assert.strictEqual(definition.clusterMaxZoom, 14);
    assert.deepStrictEqual(JSON.parse(JSON.stringify(definition.clusterProperties)), { shows: ['+', ['get', 'weight']] });
    assert.deepStrictEqual(map.layers.map(layer => layer.id), ['cluster-circles', 'cluster-counts', 'pins', 'pin-counts']);
    assert.strictEqual(map.layers[0].paint['circle-color'], '#14806b');
    assert.strictEqual(map.layers[2].paint['circle-color'], '#14806b');
    assert.deepStrictEqual(JSON.parse(JSON.stringify(map.layers[1].layout['text-field'])), ['to-string', ['get', 'shows']]);
    assert.deepStrictEqual(JSON.parse(JSON.stringify(map.layers[3].layout['text-field'])), ['to-string', ['get', 'count']]);
    assert.deepStrictEqual(JSON.parse(JSON.stringify(map.layers[1].layout['text-font'])), ['Noto Sans Bold']);
    assert.strictEqual(map.sources.locations.data.features.length, 2);
    assert.strictEqual(ctx.view.pinSummary.textContent, '2 places · 2 shows');
    ctx.restore();
});

test('the map is framed on the pins when it opens', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'M1'), showRow('Gallery A', 'A1')] });
    const map = await openMap(ctx);
    assert.strictEqual(map.fitted.length, 1);
    assert.deepStrictEqual(JSON.parse(JSON.stringify(map.fitted[0].bounds)), [[-122.41, 37.78], [-122.3, 37.8]]);
    assert.strictEqual(map.fitted[0].options.maxZoom, 15);
    ctx.restore();
});

test('changing the filters redraws the pins and re-frames; a change that moves no pin does neither', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'M1'), showRow('Gallery A', 'A1')] });
    const map = await openMap(ctx);
    const source = map.sources.locations;
    assert.strictEqual(source.setCalls, 1);
    ctx.manager.changeRows([showRow('Museum', 'M1')]);                         // fewer shows: one pin
    assert.strictEqual(source.setCalls, 2);
    assert.strictEqual(source.data.features.length, 1);
    assert.strictEqual(ctx.view.pinSummary.textContent, '1 place · 1 show');
    assert.strictEqual(map.eased.length, 1);                                   // one pin: ease to it rather than fit a box
    ctx.manager.changeRows([showRow('Museum', 'Another title')]);              // same pin, same count
    assert.strictEqual(source.setCalls, 2);
    ctx.manager.changeRows([showRow('Museum', 'M1'), showRow('Museum', 'M2')]);   // the pin says 2 now
    assert.strictEqual(source.setCalls, 3);
    assert.strictEqual(source.data.features[0].properties.count, 2);
    ctx.restore();
});

test('going to the list and back leaves the pins alone unless the filters changed meanwhile', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'M1')] });
    const map = await openMap(ctx);
    const source = map.sources.locations;
    buttons(ctx).list.click();
    buttons(ctx).map.click();
    assert.strictEqual(source.setCalls, 1);
    buttons(ctx).list.click();
    ctx.manager.rows = [showRow('Museum', 'M1'), showRow('Gallery A', 'A1')];          // filters changed while the table was showing
    buttons(ctx).map.click();
    assert.strictEqual(source.setCalls, 2);
    assert.strictEqual(source.data.features.length, 2);
    ctx.restore();
});

test('clicking a pin opens a popup with the venue, address, shows with links and dates, and the Map link', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'Big Show', 'Through Jan 3, 2027')], distances: { Museum: '0.4 mi away' } });
    const map = await openMap(ctx);
    clickPin(map, keyOf(ctx, 'Museum'));
    const popup = ctx.library.popups[0];
    assert.deepStrictEqual(JSON.parse(JSON.stringify(popup.lngLat)), [-122.3, 37.8]);
    assert.strictEqual(popup.map, map);
    const text = textOf(popup.content);
    for (const expected of ['Museum', '1 Museum Way, Oakland, CA', '0.4 mi away', 'Big Show', 'Through Jan 3, 2027', 'Map']) {
        assert.ok(text.includes(expected), `${expected} is in: ${text}`);
    }
    const [showLink] = findAll(popup.content, n => n.tag === 'a' && n.textContent === 'Big Show');
    assert.strictEqual(showLink.href, 'https://shows.example/Big-Show');
    assert.strictEqual(showLink.target, '_blank');
    assert.match(showLink.rel, /noopener/);
    const [mapLink] = findAll(popup.content, n => n.className === 'map-popup-map');
    assert.strictEqual(mapLink.textContent, 'Map');
    assert.strictEqual(mapLink.href, 'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent('1 Museum Way, Oakland, CA'));
    ctx.restore();
});

test('a popup shows no distance when "Use my location" is off, and never treats data as HTML', async () => {
    const ctx = setup({ rows: [showRow('Museum', '<img src=x onerror=alert(1)>')] });
    const map = await openMap(ctx);
    clickPin(map, keyOf(ctx, 'Museum'));
    const popup = ctx.library.popups[0];
    assert.strictEqual(findAll(popup.content, n => n.className === 'map-popup-distance').length, 0);
    const [link] = findAll(popup.content, n => n.tag === 'a' && n.className !== 'map-popup-map' && n.className !== 'map-popup-venue-link');
    assert.strictEqual(link.textContent, '<img src=x onerror=alert(1)>');           // set as text, so it is just text
    assert.strictEqual(link.innerHTML, undefined);
    ctx.restore();
});

test('two venues at one address share a pin and one popup lists both', async () => {
    const ctx = setup({ rows: [showRow('Gallery B', 'B1'), showRow('Gallery A', 'A1')] });
    const map = await openMap(ctx);
    assert.strictEqual(map.sources.locations.data.features.length, 1);
    assert.strictEqual(map.sources.locations.data.features[0].properties.count, 2);
    clickPin(map, keyOf(ctx, 'Gallery A'));
    const titles = findAll(ctx.library.popups[0].content, n => n.className === 'map-popup-venue-link').map(n => n.textContent);
    assert.deepStrictEqual(titles, ['Gallery A', 'Gallery B']);
    ctx.restore();
});

test('a venue with two addresses gets two labelled pins, each popup with its own address and Map link, counted once in a cluster', async () => {
    const ctx = setup({ rows: [showRow('Two Spaces', 'S1')] });
    const map = await openMap(ctx);
    const features = map.sources.locations.data.features;
    assert.deepStrictEqual(JSON.parse(JSON.stringify(features.map(f => [f.properties.count, f.properties.weight]))), [[1, 1], [1, 0]]);
    clickPin(map, keyOf(ctx, 'Two Spaces'));                                    // the first pin
    let popup = ctx.library.popups[0];
    assert.strictEqual(textOf(popup.content.children[0].children[0]), 'Two Spaces (Downtown)');
    assert.ok(textOf(popup.content).includes('1 A St, Los Angeles'));
    assert.strictEqual(findAll(popup.content, n => n.className === 'map-popup-map')[0].textContent, 'Map: Downtown');
    clickPin(map, ctx.view.locations[1].key);                                   // the second
    popup = ctx.library.popups[1];
    assert.strictEqual(textOf(popup.content.children[0].children[0]), 'Two Spaces (Hollywood)');
    assert.ok(findAll(popup.content, n => n.className === 'map-popup-map')[0].href.endsWith(encodeURIComponent('2 B St, Los Angeles')));
    ctx.restore();
});

test('a popup closes on Escape, when another opens, when the filters change and when going back to the list', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'M1'), showRow('Gallery A', 'A1')] });
    const map = await openMap(ctx);
    ctx.document.listeners.keydown({ key: 'Escape' });                         // nothing open: nothing happens
    clickPin(map, keyOf(ctx, 'Museum'));
    ctx.document.listeners.keydown({ key: 'Enter' });
    assert.strictEqual(ctx.library.popups[0].removed, false);
    ctx.document.listeners.keydown({ key: 'Escape' });
    assert.strictEqual(ctx.library.popups[0].removed, true);
    clickPin(map, keyOf(ctx, 'Museum'));
    clickPin(map, keyOf(ctx, 'Gallery A'));
    assert.strictEqual(ctx.library.popups[1].removed, true);
    ctx.manager.changeRows([showRow('Gallery A', 'A1'), showRow('Gallery A', 'A2')]);
    assert.strictEqual(ctx.library.popups[2].removed, true);
    clickPin(map, keyOf(ctx, 'Gallery A'));
    buttons(ctx).list.click();
    assert.strictEqual(ctx.library.popups[3].removed, true);
    ctx.restore();
});

test('clicking a cluster zooms in to where it breaks up', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'M1'), showRow('Gallery A', 'A1')] });
    const map = await openMap(ctx);
    tapAt(map, [clusterFeature(3, [-122.35, 37.79])], { x: -122.35, y: 37.79 });
    await settle();
    assert.deepStrictEqual(JSON.parse(JSON.stringify(map.eased[map.eased.length - 1])), { center: [-122.35, 37.79], zoom: 12 });
    ctx.restore();
});

test('the pointer shows a hand over pins and clusters, and only there', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'M1')] });
    const map = await openMap(ctx);
    map.rendered = [pinFeature(keyOf(ctx, 'Museum'))];
    map.fire('mousemove', { point: { x: 0, y: 0 } });
    assert.strictEqual(map.canvasStyle.cursor, 'pointer');
    map.rendered = [];
    map.fire('mousemove', { point: { x: 300, y: 300 } });
    assert.strictEqual(map.canvasStyle.cursor, '');
    ctx.restore();
});

test('a tap a little beside a pin still finds it: the search covers a fingertip, around the tap, on both layers', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'M1')] });
    const map = await openMap(ctx);
    tapAt(map, [pinFeature(keyOf(ctx, 'Museum'), [9, 0])], { x: 0, y: 0 });             // the pin is 9 px from the tap
    assert.deepStrictEqual(JSON.parse(JSON.stringify(map.queries[map.queries.length - 1])),
        { box: [[-12, -12], [12, 12]], options: { layers: ['cluster-circles', 'pins'] } });
    assert.strictEqual(ctx.library.popups.length, 1);
    ctx.restore();
});

test('when a tap is near several pins the nearest one opens', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'M1'), showRow('Gallery A', 'A1')] });
    const map = await openMap(ctx);
    tapAt(map, [pinFeature(keyOf(ctx, 'Museum'), [10, 0]), pinFeature(keyOf(ctx, 'Gallery A'), [3, 4])]);   // 10 px and 5 px away
    assert.strictEqual(ctx.library.popups.length, 1);
    assert.deepStrictEqual(JSON.parse(JSON.stringify(ctx.library.popups[0].lngLat)), [-122.41, 37.78]);                             // Gallery A's pin
    ctx.restore();
});

test('a tap with no pin or cluster near it does nothing, and leaves an open popup alone', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'M1')] });
    const map = await openMap(ctx);
    clickPin(map, keyOf(ctx, 'Museum'));
    const eased = map.eased.length;
    tapAt(map, []);
    assert.strictEqual(ctx.library.popups.length, 1);
    assert.strictEqual(ctx.library.popups[0].removed, false);
    assert.strictEqual(map.eased.length, eased);
    ctx.restore();
});

const popupOpenedWith = async (rect, { width = 343, height = 568 } = {}) => {
    const ctx = setup({ rows: [showRow('Museum', 'M1')] });
    const map = await openMap(ctx);
    map.containerWidth = width;
    map.containerHeight = height;
    ctx.library.popupRect = rect;
    clickPin(map, keyOf(ctx, 'Museum'));
    return { ctx, map };
};

test('a popup that fits in the map leaves the map where it is', async () => {
    const { ctx, map } = await popupOpenedWith({ left: 40, top: 100, right: 300, bottom: 300 });
    assert.deepStrictEqual(map.panned, []);
    ctx.restore();
});

test('a popup running off the bottom of the map pans it up by just enough, keeping a margin', async () => {
    const { ctx, map } = await popupOpenedWith({ left: 40, top: 300, right: 300, bottom: 588 });   // 20 px below a 568 px map
    assert.deepStrictEqual(JSON.parse(JSON.stringify(map.panned)), [{ offset: [0, 28], options: { duration: 250 } }]);
    ctx.restore();
});

test('a popup running off the right or the left of the map pans it back in', async () => {
    const right = await popupOpenedWith({ left: 100, top: 100, right: 373, bottom: 300 });        // 30 px past a 343 px map
    assert.deepStrictEqual(JSON.parse(JSON.stringify(right.map.panned.map(p => p.offset))), [[38, 0]]);
    right.ctx.restore();
    const left = await popupOpenedWith({ left: -20, top: 100, right: 260, bottom: 300 });
    assert.deepStrictEqual(JSON.parse(JSON.stringify(left.map.panned.map(p => p.offset))), [[-28, 0]]);
    left.ctx.restore();
});

test('a popup opened from the places list is brought into view once the map has flown there', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'M1')] });
    const map = await openMap(ctx);
    map.containerHeight = 568;
    ctx.library.popupRect = { left: 40, top: 300, right: 300, bottom: 588 };
    ctx.view.placesList.children[0].children[0].click();
    assert.deepStrictEqual(map.panned, []);                                                  // still flying
    map.fire('moveend');
    assert.strictEqual(map.panned.length, 1);
    ctx.restore();
});

test('a popup is never taller than the map leaves room for', async () => {
    for (const [height, expected] of [[568, '256px'], [300, '160px'], [150, '120px']]) {
        const ctx = setup({ rows: [showRow('Museum', 'M1')] });
        const map = await openMap(ctx);
        map.containerHeight = height;
        clickPin(map, keyOf(ctx, 'Museum'));
        assert.strictEqual(ctx.library.popups[0].content.style.maxHeight, expected, `map ${height} px tall`);
        ctx.restore();
    }
});

test('closing a popup with Escape puts the keyboard back on the place in the list it was opened from', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'M1'), showRow('Gallery A', 'A1')] });
    const map = await openMap(ctx);
    const item = ctx.view.placesList.children[1].children[0];
    ctx.document.activeElement = item;                                        // the visitor pressed Enter on it
    item.click();
    ctx.document.activeElement = null;                                        // focus moves into the popup (the real one does that)
    ctx.document.listeners.keydown({ key: 'Escape' });
    assert.strictEqual(item.focused, 1);
    ctx.restore();
});

test('closing a popup with its own close button also returns the keyboard, and only the visitor closing it does', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'M1'), showRow('Gallery A', 'A1')] });
    const map = await openMap(ctx);
    const item = ctx.view.placesList.children[0].children[0];
    ctx.document.activeElement = item;
    item.click();
    ctx.library.popups[0].remove();                                           // the close button
    assert.strictEqual(item.focused, 1);
    // Another popup replacing it, or the filters changing, is not the visitor closing it: focus stays where it is
    const other = ctx.view.placesList.children[1].children[0];
    ctx.document.activeElement = item; item.click();
    ctx.document.activeElement = other; other.click();                        // replaces the first
    ctx.manager.changeRows([showRow('Museum', 'M1')]);                        // and the filters change
    assert.strictEqual(item.focused, 1);
    assert.ok(!other.focused);
    ctx.restore();
});

test('a popup opened from a pin returns the keyboard to the map when it closes with Escape', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'M1')] });
    const map = await openMap(ctx);
    clickPin(map, keyOf(ctx, 'Museum'));
    ctx.document.listeners.keydown({ key: 'Escape' });
    assert.strictEqual(map.getCanvas().focused, 1);
    ctx.restore();
});

test('a popup is never wider than the map less a margin, so on a phone it fits inside it', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'M1')] });
    const map = await openMap(ctx);
    map.containerWidth = 343;                                                              // a phone
    clickPin(map, keyOf(ctx, 'Museum'));
    assert.strictEqual(ctx.library.popups[0].options.maxWidth, '295px');
    map.containerWidth = 1200;                                                             // a desktop: the usual width
    clickPin(map, keyOf(ctx, 'Museum'));
    assert.strictEqual(ctx.library.popups[1].options.maxWidth, '340px');
    map.containerWidth = 150;                                                              // absurdly narrow: still readable
    clickPin(map, keyOf(ctx, 'Museum'));
    assert.strictEqual(ctx.library.popups[2].options.maxWidth, '200px');
    ctx.restore();
});

test('the places list has a button for every pin, by name, that flies there and opens its popup', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'M1'), showRow('Museum', 'M2'), showRow('Gallery A', 'A1'), showRow('Two Spaces', 'T1')] });
    const map = await openMap(ctx);
    assert.strictEqual(ctx.view.places.hidden, false);
    assert.strictEqual(ctx.view.placesSummary.textContent, 'Places on the map (4)');
    const labels = ctx.view.placesList.children.map(item => item.children[0].textContent);
    assert.deepStrictEqual(labels, ['Gallery A: 1 show', 'Museum: 2 shows', 'Two Spaces (Downtown): 1 show', 'Two Spaces (Hollywood): 1 show']);
    ctx.view.placesList.children[1].children[0].click();                       // Museum
    assert.deepStrictEqual(JSON.parse(JSON.stringify(map.flown[0].center)), [-122.3, 37.8]);
    assert.ok(map.flown[0].zoom >= 15, 'clusters still form below zoom 15, which would hide the place that was chosen');
    assert.ok(textOf(ctx.library.popups[0].content).includes('Museum'));
    ctx.restore();
});

test('a place with two venues is named for both in the list', async () => {
    const ctx = setup({ rows: [showRow('Gallery B', 'B1'), showRow('Gallery A', 'A1')] });
    await openMap(ctx);
    assert.deepStrictEqual(ctx.view.placesList.children.map(item => item.children[0].textContent), ['Gallery A, Gallery B: 2 shows']);
    ctx.restore();
});

test('when nothing matches the map says so, offers to clear the filters, and keeps its list hidden', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'M1')] });
    const map = await openMap(ctx);
    ctx.manager.changeRows([]);
    assert.strictEqual(ctx.view.pinSummary.textContent, 'No shows match these filters.');
    assert.strictEqual(ctx.view.clearButton.hidden, false);
    assert.strictEqual(ctx.view.places.hidden, true);
    assert.strictEqual(map.sources.locations.data.features.length, 0);
    ctx.view.clearButton.click();
    assert.strictEqual(ctx.manager.cleared, 1);
    ctx.manager.changeRows([showRow('Museum', 'M1')]);
    assert.strictEqual(ctx.view.clearButton.hidden, true);
    ctx.restore();
});

test('shows at a venue with no map location are counted in the summary, not drawn', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'M1'), showRow('No Coordinates', 'N1'), showRow('Never Heard Of It', 'X1')] });
    const map = await openMap(ctx);
    assert.strictEqual(map.sources.locations.data.features.length, 1);
    assert.strictEqual(ctx.view.pinSummary.textContent, '1 place · 1 show (2 shows have no map location; see the list view)');
    ctx.manager.changeRows([showRow('No Coordinates', 'N1')]);
    assert.strictEqual(ctx.view.pinSummary.textContent, '1 show has no map location; see the list view.');
    assert.strictEqual(ctx.view.clearButton.hidden, true);                    // there ARE matches: they just can't be placed
    ctx.restore();
});

test('the visitor shows as a dot, and the map frames them with the nearest pins', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'M1'), showRow('Gallery A', 'A1'), showRow('Two Spaces', 'T1')] });
    const map = await openMap(ctx);
    ctx.view.setYouAreHere({ lat: 37.79, lng: -122.4 });
    const [dot] = ctx.library.markers;
    assert.deepStrictEqual(JSON.parse(JSON.stringify(dot.lngLat)), [-122.4, 37.79]);
    assert.strictEqual(dot.options.element.attributes['aria-label'], 'Your location');
    assert.strictEqual(dot.options.element.className, 'map-you');
    const framed = map.fitted[map.fitted.length - 1];
    // the nearest three of the four pins (the Hollywood pin is nearer to San Francisco than Downtown), so the box is wide
    assert.deepStrictEqual(JSON.parse(JSON.stringify(framed.bounds)), [[-122.41, 34.06], [-118.3, 37.8]]);
    ctx.view.setYouAreHere({ lat: 37.79, lng: -122.4 });
    assert.strictEqual(ctx.library.markers[0].removed, true);                  // never two dots
    ctx.view.setYouAreHere(null);
    assert.strictEqual(ctx.library.markers[1].removed, true);
    assert.strictEqual(ctx.view.you, null);
    ctx.restore();
});

test('the framing keeps to the nearest few pins when there are more', async () => {
    const coordinates = { ...COORDINATES, 'Far One': [{ lat: 40.7, lng: -74 }], 'Far Two': [{ lat: 41.8, lng: -87.6 }] };
    const ctx = setup({ loadData: async () => ({ coordinates, bounds: BOUNDS_FOR_DATA() }),
                        rows: [showRow('Museum', 'M1'), showRow('Gallery A', 'A1'), showRow('Two Spaces', 'T1'), showRow('Far One', 'F1'), showRow('Far Two', 'F2')] });
    VENUES['Far One'] = '1 Far St'; VENUES['Far Two'] = '2 Far St';
    const map = await openMap(ctx);
    ctx.view.setYouAreHere({ lat: 37.79, lng: -122.4 });
    const framed = JSON.parse(JSON.stringify(map.fitted[map.fitted.length - 1].bounds));
    assert.deepStrictEqual(framed, [[-122.41, 34.06], [-118.3, 37.8]]);        // not New York or Chicago
    delete VENUES['Far One']; delete VENUES['Far Two'];
    ctx.restore();
});

test('a visitor located before the map was opened is drawn when it loads, and the map frames them', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'M1'), showRow('Gallery A', 'A1')] });
    ctx.view.setYouAreHere({ lat: 37.79, lng: -122.4 });                       // map not created yet: held for when it is
    assert.strictEqual(ctx.library.markers.length, 0);
    assert.strictEqual(ctx.calls.library, 0);
    const map = await openMap(ctx);
    assert.strictEqual(ctx.library.markers.length, 1);
    assert.deepStrictEqual(JSON.parse(JSON.stringify(map.fitted[0].bounds)), [[-122.41, 37.78], [-122.3, 37.8]]);
    ctx.restore();
});

test('a visitor located while the list is showing is drawn, and framed when the map is next shown', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'M1'), showRow('Gallery A', 'A1')] });
    const map = await openMap(ctx);
    buttons(ctx).list.click();
    const before = map.fitted.length;
    ctx.view.setYouAreHere({ lat: 37.79, lng: -122.4 });
    assert.strictEqual(ctx.library.markers.length, 1);
    assert.strictEqual(map.fitted.length, before);                             // a hidden map can't be framed
    assert.strictEqual(ctx.view.needsFrame, true);
    buttons(ctx).map.click();
    assert.strictEqual(map.fitted.length, before + 1);
    assert.strictEqual(ctx.view.needsFrame, false);
    ctx.restore();
});

test('losing the map removes the popup and the dot', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'M1')] });
    const map = await openMap(ctx);
    clickPin(map, keyOf(ctx, 'Museum'));
    ctx.view.setYouAreHere({ lat: 37.79, lng: -122.4 });
    ctx.view.fail('gone');
    assert.strictEqual(ctx.library.popups[0].removed, true);
    assert.strictEqual(ctx.library.markers[0].removed, true);
    assert.strictEqual(map.removed, true);
    assert.strictEqual(ctx.view.pinsReady, false);
    ctx.restore();
});

test('the privacy of the visitor: the dot is the only place the map keeps their position, and turning it off forgets it', async () => {
    const ctx = setup({ rows: [showRow('Museum', 'M1')] });
    const map = await openMap(ctx);
    ctx.view.setYouAreHere({ lat: 37.123456, lng: -122.987654 });
    assert.deepStrictEqual(JSON.parse(JSON.stringify(ctx.view.you)), { lat: 37.123456, lng: -122.987654 });
    ctx.view.setYouAreHere(null);
    const kept = JSON.stringify(ctx.view, (key, value) => (['map', 'maplibre', 'searchManager', 'bar', 'tableWrap', 'section', 'resultsBar', 'summary', 'toggle', 'buttons'].includes(key) ? undefined : value));
    assert.ok(!kept.includes('37.123456') && !kept.includes('122.987654'), 'the position is still held after turning off');
    assert.ok(map.fitted.length >= 1);
    ctx.restore();
});


test("a popup's venue name is a link to that venue's shows, and a plain click filters without leaving the map", async () => {
    const ctx = setup({ rows: [showRow('Gallery A', 'A1')] });
    const map = await openMap(ctx);
    clickPin(map, keyOf(ctx, 'Gallery A'));
    const [link] = findAll(ctx.library.popups[0].content, n => n.className === 'map-popup-venue-link');
    assert.strictEqual(link.textContent, 'Gallery A');
    assert.strictEqual(link.href, '?venue=Gallery%20A&view=map');
    const chosen = [];
    ctx.manager.setVenue = name => chosen.push(name);
    const click = (extra = {}) => {
        const event = { button: 0, prevented: false, preventDefault() { event.prevented = true; }, ...extra };
        link.listeners.click(event);
        return event;
    };
    assert.ok(click().prevented);
    assert.deepStrictEqual(chosen, ['Gallery A']);
    for (const extra of [{ metaKey: true }, { ctrlKey: true }, { shiftKey: true }, { button: 1 }]) {
        assert.ok(!click(extra).prevented, JSON.stringify(extra));
    }
    assert.deepStrictEqual(chosen, ['Gallery A']);
    assert.strictEqual(ctx.manager.state.view, 'map');
    ctx.restore();
});
