// Run with: node --test tests/
// The "Use my location" control (docs/nearMeControl.js) driven through a tiny fake DOM and a fake
// geolocation: nothing is asked until the click, what each outcome says, nearest-first ordering, and
// that the visitor's position is not kept. No browser, no network.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// --- a very small DOM: just what the control touches ---------------------------------------------
function makeElement(tag) {
    const el = {
        tag, className: '', textContent: '', title: '', hidden: false, disabled: false, type: '',
        attributes: {}, children: [], listeners: {}, focused: false,
        classList: {
            toggle(name, on) { const set = new Set(el.className.split(' ').filter(Boolean)); (on ? set.add(name) : set.delete(name)); el.className = [...set].join(' '); },
            contains(name) { return el.className.split(' ').includes(name); },
        },
        setAttribute(name, value) { el.attributes[name] = String(value); },
        removeAttribute(name) { delete el.attributes[name]; },
        getAttribute(name) { return name in el.attributes ? el.attributes[name] : null; },
        append(...nodes) { el.children.push(...nodes); },
        addEventListener(name, fn) { el.listeners[name] = fn; },
        focus() { el.focused = true; },
        click() { el.listeners.click(); },
        querySelector(selector) { return selector === '.near-me-label' ? (el.labelEl ||= makeElement('span')) : null; },
    };
    return el;
}

function setup({ geolocation, loadData, region = 'sf', rows } = {}) {
    const bar = makeElement('div');
    const panel = makeElement('div');
    panel.querySelector = selector => (selector === '.filter-bar' ? bar : null);
    const document = { getElementById: id => (id === 'filterPanel' ? panel : null), createElement: makeElement };
    const sandbox = { window: {}, document, console, navigator: {} };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../docs/nearMe.js'), 'utf8') + '\nglobalThis.nearMe = nearMe;', sandbox);
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../docs/nearMeControl.js'), 'utf8')
        .replace('window.NearMeControl = NearMeControl;', 'globalThis.NearMeControl = NearMeControl;'), sandbox);

    const makeRow = (venue, index) => {
        const distanceEl = makeElement('span');
        distanceEl.hidden = true;                  // as tableRenderer.js creates it
        return { el: { name: `row${index}` }, index, venue, distanceEl };
    };
    rows = rows || [makeRow('Far', 0), makeRow('Near', 1), makeRow('Nowhere', 2), makeRow('Near', 3)];
    const shown = { order: rows.map(r => r.el.name) };
    const searchManager = { rows, tableBody: { append: (...els) => { shown.order = els.map(e => e.name); } } };
    const control = new sandbox.NearMeControl(searchManager, { region, loadData, geolocation });
    return { control, bar, panel, rows, shown, searchManager };
}

const SF = { latitude: 37.7749, longitude: -122.4194 };
const COORDS = { Near: [{ lat: 37.78, lng: -122.41 }], Far: [{ lat: 37.87, lng: -122.27 }], Nowhere: [] };
const BAY_AREA = { lat: [36.9, 38.6], lng: [-123.1, -121.5] };

function fakeGeolocation(outcome) {
    const calls = [];
    return {
        calls,
        getCurrentPosition(onSuccess, onError, options) {
            calls.push(options);
            if (outcome.error) onError({ code: outcome.error }); else onSuccess({ coords: outcome.coords });
        },
    };
}

const loadOk = async () => ({ coordinates: COORDS, bounds: BAY_AREA });
const settle = () => new Promise(resolve => setImmediate(resolve));
const main = ({ bar }) => bar.children[0].children[0];
const text = ({ control }) => control.message.textContent;

test('nothing is asked or loaded until the visitor clicks', () => {
    let loaded = 0;
    const geolocation = fakeGeolocation({ coords: SF });
    const ctx = setup({ geolocation, loadData: async () => { loaded++; return {}; } });
    assert.strictEqual(geolocation.calls.length, 0);
    assert.strictEqual(loaded, 0);
    assert.strictEqual(main(ctx).attributes['aria-label'], 'Use my location to show how far each show is');
    assert.strictEqual(ctx.control.label.textContent, 'Use my location');
    assert.match(ctx.control.privacy.textContent, /stays in this browser/);
});

test('a browser with no location support, or a page with no filter bar, gets nothing added', () => {
    const noSupport = setup({ geolocation: null, loadData: loadOk });
    // (navigator is an empty object in the sandbox, so there is no geolocation to fall back to)
    assert.strictEqual(noSupport.control.available, false);
    assert.strictEqual(noSupport.bar.children.length, 0);
});

test('sharing a location shows each venue’s distance and puts the nearest first', async () => {
    const geolocation = fakeGeolocation({ coords: SF });
    const ctx = setup({ geolocation, loadData: loadOk });
    main(ctx).click();
    await settle();
    assert.deepStrictEqual(JSON.parse(JSON.stringify(geolocation.calls)), [{ enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }]);
    const [far, near, nowhere, near2] = ctx.rows;
    assert.match(near.distanceEl.textContent, /^\d(\.\d)? mi away$/);      // miles in the Bay Area
    assert.strictEqual(near.distanceEl.hidden, false);
    assert.strictEqual(near.distanceEl.textContent, near2.distanceEl.textContent);
    assert.notStrictEqual(far.distanceEl.textContent, near.distanceEl.textContent);
    assert.strictEqual(nowhere.distanceEl.hidden, true);                    // no coordinates: no distance
    assert.deepStrictEqual(ctx.shown.order, ['row1', 'row3', 'row0', 'row2']);   // near, near, far, then the one without
    assert.strictEqual(ctx.control.label.textContent, 'Nearest first');
    assert.strictEqual(main(ctx).attributes['aria-pressed'], 'true');
    assert.match(text(ctx), /nearest first.*straight-line, so approximate/);
});

test('kilometres outside the US regions', async () => {
    const ctx = setup({ region: 'mtl', geolocation: fakeGeolocation({ coords: SF }), loadData: loadOk });
    main(ctx).click();
    await settle();
    assert.match(ctx.rows[1].distanceEl.textContent, /^\d(\.\d)? km away$/);
});

test('the visitor’s position is not kept anywhere on the control', async () => {
    const ctx = setup({ geolocation: fakeGeolocation({ coords: SF }), loadData: loadOk });
    main(ctx).click();
    await settle();
    const kept = JSON.stringify(ctx.control, (key, value) => (key === 'searchManager' || key === 'bar' || key === 'panelEl' ? undefined : value),
        0).replace(/"(mainButton|offButton|note|message|privacy|label|geolocation|loadData)":\{[^}]*\}/g, '');
    assert.ok(!kept.includes('37.7749') && !kept.includes('122.4194'), kept);
    assert.deepStrictEqual(Object.keys(ctx.control).filter(key => /user|position|coords|lat|lng/i.test(key)), []);
});

test('the Nearest first button turns ordering off and on; the distances stay', async () => {
    const ctx = setup({ geolocation: fakeGeolocation({ coords: SF }), loadData: loadOk });
    main(ctx).click();
    await settle();
    main(ctx).click();                                                      // nearest first off
    assert.deepStrictEqual(ctx.shown.order, ['row0', 'row1', 'row2', 'row3']);
    assert.strictEqual(main(ctx).attributes['aria-pressed'], 'false');
    assert.strictEqual(ctx.rows[1].distanceEl.hidden, false);
    main(ctx).click();                                                      // and on again
    assert.deepStrictEqual(ctx.shown.order, ['row1', 'row3', 'row0', 'row2']);
});

test('"Turn off" forgets the distances and restores the usual order', async () => {
    const ctx = setup({ geolocation: fakeGeolocation({ coords: SF }), loadData: loadOk });
    main(ctx).click();
    await settle();
    const off = ctx.bar.children[0].children[1];
    assert.strictEqual(off.hidden, false);
    off.click();
    assert.deepStrictEqual(ctx.shown.order, ['row0', 'row1', 'row2', 'row3']);
    assert.ok(ctx.rows.every(row => row.distanceEl.hidden && row.distanceEl.textContent === ''));
    assert.strictEqual(ctx.control.label.textContent, 'Use my location');
    assert.strictEqual(off.hidden, true);
    assert.strictEqual(text(ctx), '');
});

test('each way location can fail says so plainly and leaves the page as it was', async () => {
    const expected = { 1: /blocked location for this site/, 2: /work out where you are/, 3: /took too long/ };
    for (const [code, pattern] of Object.entries(expected)) {
        const ctx = setup({ geolocation: fakeGeolocation({ error: Number(code) }), loadData: loadOk });
        main(ctx).click();
        await settle();
        assert.match(text(ctx), pattern, `code ${code}`);
        assert.deepStrictEqual(ctx.shown.order, ['row0', 'row1', 'row2', 'row3']);
        assert.ok(ctx.rows.every(row => row.distanceEl.hidden));
        assert.strictEqual(ctx.control.label.textContent, 'Use my location');   // the button is the retry
        assert.strictEqual(main(ctx).disabled, false);
    }
});

test('a position the browser gets wrong is treated as unavailable', async () => {
    const ctx = setup({ geolocation: fakeGeolocation({ coords: { latitude: NaN, longitude: 0 } }), loadData: loadOk });
    main(ctx).click();
    await settle();
    assert.match(text(ctx), /work out where you are/);
});

test('venue data that will not load is reported and can be retried', async () => {
    let attempts = 0;
    const loadData = async () => { attempts++; if (attempts === 1) throw new Error('offline'); return { coordinates: COORDS, bounds: BAY_AREA }; };
    const ctx = setup({ geolocation: fakeGeolocation({ coords: SF }), loadData });
    const quiet = console.error; console.error = () => {};
    main(ctx).click();
    await settle();
    console.error = quiet;
    assert.match(text(ctx), /load the venue locations/);
    main(ctx).click();
    await settle();
    assert.strictEqual(attempts, 2);
    assert.match(text(ctx), /nearest first/);
});

test('a visitor far from the region is told how far, and nothing is shown or reordered', async () => {
    const newYork = { latitude: 40.7128, longitude: -74.0060 };
    const ctx = setup({ geolocation: fakeGeolocation({ coords: newYork }), loadData: loadOk });
    main(ctx).click();
    await settle();
    assert.match(text(ctx), /^You.re about [\d,]+ mi from the venues listed here, so distances aren.t shown\.$/);
    assert.deepStrictEqual(ctx.shown.order, ['row0', 'row1', 'row2', 'row3']);
    assert.ok(ctx.rows.every(row => row.distanceEl.hidden));
});

test('while it looks for you the button is disabled and says so', () => {
    const geolocation = { getCurrentPosition() { /* never answers */ } };
    const ctx = setup({ geolocation, loadData: loadOk });
    main(ctx).click();
    assert.strictEqual(main(ctx).disabled, true);
    assert.strictEqual(ctx.control.label.textContent, 'Finding you…');
    assert.strictEqual(main(ctx).attributes['aria-busy'], 'true');
    assert.strictEqual(text(ctx), 'Finding your location…');
});
