// Run with: node --test tests/
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const RegionPicker = require('../docs/regionPicker.js');

const DOCS = path.join(__dirname, '../docs');
const info = JSON.parse(fs.readFileSync(path.join(DOCS, 'data/region_info.json'), 'utf8'));

// ---- a tiny page, just enough for the picker to draw into ----

class FakeElement {
    constructor(doc, tag) {
        this.ownerDocument = doc;
        this.tagName = tag.toUpperCase();
        this.children = [];
        this.attributes = {};
        this.listeners = {};
        this.style = { props: {}, setProperty(name, value) { this.props[name] = value; } };
        this.classes = new Set();
        this.hidden = false;
        this.textContent = '';
        this.value = '';
    }
    get firstChild() { return this.children[0] || null; }
    set className(value) { this.classes = new Set(String(value).split(/\s+/).filter(Boolean)); }
    get className() { return [...this.classes].join(' '); }
    get classList() {
        const classes = this.classes;
        return { toggle(name, on) { (on === undefined ? !classes.has(name) : on) ? classes.add(name) : classes.delete(name); }, contains: name => classes.has(name) };
    }
    setAttribute(name, value) { this.attributes[name] = String(value); }
    getAttribute(name) { return name in this.attributes ? this.attributes[name] : null; }
    appendChild(child) { this.children.push(child); return child; }
    replaceChildren(...kids) { this.children = [...kids]; }
    addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); }
    fire(type) { (this.listeners[type] || []).forEach(fn => fn({ target: this })); }
    // every element below this one, this one first
    all() { return [this, ...this.children.flatMap(child => child.all())]; }
    find(predicate) { return this.all().filter(predicate); }
}

function fakePage() {
    const doc = { createElement: tag => new FakeElement(doc, tag) };
    return { doc, root: new FakeElement(doc, 'div') };
}

function memoryStorage(initial) {
    const data = initial ? { [RegionPicker.STORAGE_KEY]: initial } : {};
    return { getItem: key => (key in data ? data[key] : null), setItem: (key, value) => { data[key] = value; }, data };
}

function makePicker(extra) {
    const { root } = fakePage();
    const picker = RegionPicker.create({ root, info, storage: memoryStorage(), ...extra });
    return { picker, root };
}

const shownBlobs = picker => Object.keys(picker.blobs).filter(code => !picker.blobs[code].hidden);
const shownRows = picker => Object.keys(picker.rows).filter(code => !picker.rows[code].hidden);
const type = (picker, text) => { picker.input.value = text; picker.input.fire('input'); };

// ---- the blobs ----

test('every region gets a blob that shows its name and its place, and links to its page', () => {
    const { picker } = makePicker();
    assert.deepStrictEqual(Object.keys(picker.blobs), Object.keys(info));
    const pdx = picker.blobs.pdx;
    assert.strictEqual(pdx.getAttribute('href'), 'pdx/index.html');
    assert.strictEqual(pdx.getAttribute('aria-label'), 'Portland, Oregon, USA');
    assert.deepStrictEqual(pdx.find(el => el.classes.has('region-name')).map(el => el.textContent), ['Portland']);
    assert.deepStrictEqual(pdx.find(el => el.classes.has('region-place')).map(el => el.textContent), ['Oregon, USA']);
    assert.strictEqual(pdx.style.props['--c'], '#00748f');
    assert.strictEqual(pdx.style.props['--w'], '210px');
});

test('a region with no state or province shows just its country', () => {
    const { picker } = makePicker();
    assert.strictEqual(picker.blobs.ist.getAttribute('aria-label'), 'Istanbul, Türkiye');
    assert.deepStrictEqual(picker.blobs.ist.find(el => el.classes.has('region-place')).map(el => el.textContent), ['Türkiye']);
});

test('renderBlobs draws into a page for the 404 page, with links from the site root', () => {
    const { doc } = fakePage();
    const nav = new FakeElement(doc, 'nav');
    nav.appendChild(new FakeElement(doc, 'a'));
    const blobs = RegionPicker.renderBlobs(nav, info, { base: '/' });
    assert.strictEqual(nav.children.length, Object.keys(info).length);
    assert.strictEqual(blobs.sf.getAttribute('href'), '/sf/index.html');
});

test('a region added to the data gets a blob, a list row and a key entry with no other change', () => {
    const more = { ...info, chi: { name: 'Chicago', label: 'Chicago', place: 'Illinois', country: 'USA', colour: '#336699', lat: 41.88, lng: -87.63 } };
    const { root } = fakePage();
    const picker = RegionPicker.create({ root, info: more, storage: memoryStorage() });
    assert.ok(picker.blobs.chi && picker.rows.chi && picker.keyItems.chi);
    assert.strictEqual(picker.blobs.chi.getAttribute('aria-label'), 'Chicago, Illinois, USA');
    // and it sits with the other US regions in the list
    const usa = picker.listView.children.find(section => section.getAttribute('aria-label') === 'USA');
    assert.strictEqual(usa.find(el => el.tagName === 'LI').length, 5);
});

// ---- the toggle ----

test('the picker opens on Blobs, and the toggle changes which view shows', () => {
    const { picker } = makePicker();
    assert.strictEqual(picker.state.view, 'blobs');
    assert.deepStrictEqual([picker.nav.hidden, picker.listView.hidden, picker.mapView.hidden], [false, true, true]);
    assert.strictEqual(picker.toggleButtons.blobs.getAttribute('aria-pressed'), 'true');

    picker.toggleButtons.list.fire('click');
    assert.deepStrictEqual([picker.nav.hidden, picker.listView.hidden, picker.mapView.hidden], [true, false, true]);
    assert.strictEqual(picker.toggleButtons.list.getAttribute('aria-pressed'), 'true');
    assert.strictEqual(picker.toggleButtons.blobs.getAttribute('aria-pressed'), 'false');
});

test('an unknown view is ignored', () => {
    const { picker } = makePicker();
    picker.setView('carousel');
    assert.strictEqual(picker.state.view, 'blobs');
});

test('the last view is remembered, but the map is never opened for the visitor on arrival', () => {
    assert.strictEqual(RegionPicker.startingView('list'), 'list');
    assert.strictEqual(RegionPicker.startingView('blobs'), 'blobs');
    assert.strictEqual(RegionPicker.startingView('map'), 'blobs');
    assert.strictEqual(RegionPicker.startingView(null), 'blobs');
    assert.strictEqual(RegionPicker.startingView('nonsense'), 'blobs');

    const storage = memoryStorage();
    const first = RegionPicker.create({ root: fakePage().root, info, storage });
    first.setView('list');
    assert.strictEqual(storage.data[RegionPicker.STORAGE_KEY], 'list');
    const second = RegionPicker.create({ root: fakePage().root, info, storage });
    assert.strictEqual(second.state.view, 'list');
});

test('the picker still works when the browser will not store anything', () => {
    const storage = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } };
    const picker = RegionPicker.create({ root: fakePage().root, info, storage });
    picker.setView('list');
    assert.strictEqual(picker.state.view, 'list');
});

// ---- the list ----

test('the list is grouped by country and fills in venue counts when it is first opened', async () => {
    const asked = [];
    const { picker } = makePicker({ loadVenueCount: async code => { asked.push(code); return code === 'pdx' ? 1 : 20; } });
    assert.deepStrictEqual(asked, [], 'no venue files are fetched until the list is opened');
    const headings = picker.listView.find(el => el.classes.has('picker-country')).map(el => el.textContent);
    assert.deepStrictEqual(headings, ['USA', 'Canada', 'Türkiye']);

    picker.setView('list');
    await new Promise(resolve => setImmediate(resolve));
    assert.deepStrictEqual(asked.sort(), Object.keys(info).sort());
    assert.strictEqual(picker.counts.pdx.textContent, '1 venue');
    assert.strictEqual(picker.counts.sf.textContent, '20 venues');

    picker.setView('blobs');
    picker.setView('list');
    assert.strictEqual(asked.length, Object.keys(info).length, 'they are only fetched once');
});

test('a venue count that cannot be fetched is left blank', async () => {
    const { picker } = makePicker({ loadVenueCount: async code => { if (code === 'sf') throw new Error('offline'); return 5; } });
    picker.setView('list');
    await new Promise(resolve => setImmediate(resolve));
    assert.strictEqual(picker.counts.sf.textContent, '');
    assert.strictEqual(picker.counts.la.textContent, '5 venues');
});

// ---- the search ----

test('the search filters the blobs and the list together', () => {
    const { picker } = makePicker();
    type(picker, 'canada');
    assert.deepStrictEqual(shownBlobs(picker), ['mtl', 'tor']);
    assert.deepStrictEqual(shownRows(picker), ['mtl', 'tor']);
    assert.match(picker.status.textContent, /2 places match/);
    assert.strictEqual(picker.status.hidden, false);

    type(picker, 'montreal');
    assert.deepStrictEqual(shownBlobs(picker), ['mtl']);
    assert.match(picker.status.textContent, /1 place matches/);
});

test('a country heading in the list goes when none of its regions match', () => {
    const { picker } = makePicker();
    type(picker, 'turkey');
    const shown = picker.listView.children.filter(section => !section.hidden).map(section => section.getAttribute('aria-label'));
    assert.deepStrictEqual(shown, ['Türkiye']);
});

test('a search with no match says so, and clearing it brings everything back', () => {
    const { picker } = makePicker();
    type(picker, 'chicago');
    assert.deepStrictEqual(shownBlobs(picker), []);
    assert.match(picker.status.textContent, /Nothing matches “chicago” yet/);

    type(picker, '');
    assert.deepStrictEqual(shownBlobs(picker), Object.keys(info));
    assert.strictEqual(picker.status.hidden, true);
});

// ---- the map ----

test('the map library is not loaded until the Map view is opened', async () => {
    let loads = 0;
    const loadMapLibrary = async () => { loads += 1; throw new Error('offline'); };
    const { picker } = makePicker({ loadMapLibrary, hasWebGl: () => true });
    assert.strictEqual(loads, 0);
    type(picker, 'port');
    picker.setView('list');
    assert.strictEqual(loads, 0);

    picker.setView('map');
    await new Promise(resolve => setImmediate(resolve));
    assert.strictEqual(loads, 1);
});

test('if the map cannot load, the visitor is shown the list and told why', async () => {
    const { picker } = makePicker({ loadMapLibrary: async () => { throw new Error('offline'); }, hasWebGl: () => true });
    picker.setView('map');
    await new Promise(resolve => setImmediate(resolve));
    assert.strictEqual(picker.state.view, 'list');
    const warning = picker.mapView.find(el => el.classes.has('picker-note-warn'))[0];
    assert.strictEqual(warning.hidden, false);
    assert.match(warning.textContent, /couldn’t load/);
});

test('without WebGL the library is not even loaded', async () => {
    let loads = 0;
    const { picker } = makePicker({ loadMapLibrary: async () => { loads += 1; }, hasWebGl: () => false });
    picker.setView('map');
    await new Promise(resolve => setImmediate(resolve));
    assert.strictEqual(loads, 0);
    assert.strictEqual(picker.state.view, 'list');
});

test('the map gets a dot at each region, with a link and a name for it, and the privacy note is shown', async () => {
    const markers = [];
    class FakeMap {
        constructor(options) { this.options = options; FakeMap.last = this; }
        once() {} on() {} resize() {}
    }
    class FakeMarker {
        constructor(options) { this.element = options.element; }
        setLngLat(lngLat) { this.lngLat = lngLat; return this; }
        addTo() { markers.push(this); return this; }
    }
    const { picker } = makePicker({ loadMapLibrary: async () => ({ Map: FakeMap, Marker: FakeMarker }), hasWebGl: () => true });
    picker.setView('map');
    await new Promise(resolve => setImmediate(resolve));
    assert.strictEqual(picker.state.view, 'map');
    assert.strictEqual(markers.length, Object.keys(info).length);
    const portland = markers.find(marker => marker.element.getAttribute('href') === 'pdx/index.html');
    assert.deepStrictEqual(portland.lngLat, [info.pdx.lng, info.pdx.lat]);
    assert.strictEqual(portland.element.getAttribute('aria-label'), 'Portland, Oregon, USA');
    assert.match(RegionPicker.MESSAGES.privacy, /shares your IP address with OpenFreeMap/);
    assert.ok(picker.mapView.find(el => el.classes.has('picker-note') && el.textContent === RegionPicker.MESSAGES.privacy).length);

    // a search hides the dots that do not match
    type(picker, 'canada');
    assert.deepStrictEqual(markers.filter(marker => !marker.element.hidden).map(marker => marker.element.getAttribute('href')),
        ['mtl/index.html', 'tor/index.html']);
});

// ---- the pages ----

test('the home page loads the picker, and its plain links name every blob the same way', () => {
    const html = fs.readFileSync(path.join(DOCS, 'index.html'), 'utf8');
    assert.match(html, /<script src="regionInfo\.js"><\/script>/);
    assert.match(html, /<script src="regionPicker\.js"><\/script>/);
    assert.match(html, /RegionPicker\.boot\('regionPicker'\)/);
    assert.match(html, /<div id="regionPicker">/);
    // the plain links (shown if the script cannot load) carry each region's place
    for (const [code, region] of Object.entries(info)) {
        const place = [region.place, region.country].filter(Boolean).join(', ');
        assert.ok(html.includes(`aria-label="${region.name}, ${place}" data-region="${code}"`), `index.html's plain link for ${code} is out of date`);
    }
});

test('every region page shows its place under the title and says it in its page title', () => {
    for (const [code, region] of Object.entries(info)) {
        const tail = region.place || region.country;
        for (const page of ['index.html', 'venues.html']) {
            const html = fs.readFileSync(path.join(DOCS, code, page), 'utf8');
            assert.ok(html.includes(`data-region-place="${code}"`), `docs/${code}/${page} has no place line`);
            assert.match(html, /<script src="\.\.\/regionInfo\.js"><\/script>/, `docs/${code}/${page} does not load regionInfo.js`);
            assert.match(html, /<script src="\.\.\/regionPlace\.js"><\/script>/, `docs/${code}/${page} does not load regionPlace.js`);
            const title = (html.match(/<title>([^<]*)<\/title>/) || [])[1] || '';
            assert.ok(title.includes(`, ${tail}`), `docs/${code}/${page} title "${title}" does not say ${tail}`);
        }
    }
});
