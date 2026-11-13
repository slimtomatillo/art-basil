// Run with: node --test tests/
// The table shows an event's own picture, or its venue's logo when it has none (docs/venue_images.json).
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// A tiny stand-in for the DOM: enough for renderImageCell
function loadRenderer() {
    const created = [];
    const document = {
        getElementById: () => null,
        createElement: (tag) => {
            const el = { tag, style: {}, children: [], listeners: {}, className: '', removed: false,
                appendChild(child) { this.children.push(child); },
                addEventListener(name, fn) { this.listeners[name] = fn; },
                remove() { this.removed = true; } };
            created.push(el);
            return el;
        },
    };
    const opened = [];
    const window = { modalManager: { openImageModal: (src) => opened.push(src) } };
    const sandbox = { window, document, console };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../docs/tableRenderer.js'), 'utf8'), sandbox);
    return { renderer: new window.TableRenderer('x'), created, opened, window };
}

const cell = () => ({ children: [], textContent: 'unset', appendChild(c) { this.children.push(c); } });

test("an event's own picture is used, and the venue logo is not", () => {
    const { renderer } = loadRenderer();
    renderer.setVenueImages({ 'Gallery': 'https://g.example/logo.png' });
    const c = cell();
    renderer.renderImageCell(c, { name: 'Show', venue: 'Gallery', links: [{ link: 'https://g.example/show.jpg', description: 'Image' }] });
    assert.strictEqual(c.children[0].src, 'https://g.example/show.jpg');
    assert.strictEqual(c.children[0].className, 'event-image');
    assert.strictEqual(c.children[0].alt, 'Show @ Gallery');
});

test('an event with no picture shows its venue logo, marked as a logo', () => {
    const { renderer, opened } = loadRenderer();
    renderer.setVenueImages({ 'Gallery': 'https://g.example/logo.png' });
    const c = cell();
    renderer.renderImageCell(c, { name: 'Show', venue: 'Gallery', links: [{ link: 'https://g.example/s', description: 'Event Page' }] });
    const img = c.children[0];
    assert.strictEqual(img.src, 'https://g.example/logo.png');
    assert.strictEqual(img.className, 'event-image venue-logo');
    assert.strictEqual(img.alt, 'Gallery logo');
    img.listeners.click({ stopPropagation() {} });
    assert.deepStrictEqual(opened, ['https://g.example/logo.png']);
});

test('no picture and no venue logo leaves the cell empty', () => {
    const { renderer } = loadRenderer();
    const c = cell();
    renderer.renderImageCell(c, { name: 'Show', venue: 'Other', links: [] });
    assert.strictEqual(c.children.length, 0);
    assert.strictEqual(c.textContent, '');
});

test('a missing or empty venue image list is harmless', () => {
    const { renderer } = loadRenderer();
    renderer.setVenueImages(undefined);
    const c = cell();
    renderer.renderImageCell(c, { name: 'Show', venue: 'Gallery', links: [] });
    assert.strictEqual(c.children.length, 0);
});

test('every venue in venue_images.json is a real venue with an https picture or one of our own', () => {
    const images = JSON.parse(fs.readFileSync(path.join(__dirname, '../docs/data/venue_images.json'), 'utf8'));
    const known = new Set();
    for (const region of ['sf', 'la', 'nyc', 'mtl', 'tor', 'ist']) {
        const venues = JSON.parse(fs.readFileSync(path.join(__dirname, `../docs/data/${region}_venues.json`), 'utf8'));
        Object.keys(venues).forEach(v => known.add(v));
    }
    for (const [venue, url] of Object.entries(images)) {
        assert.ok(known.has(venue), `${venue} is not in any *_venues.json`);
        // a logo kept in docs/images/venues/ is given as a site path ("/images/venues/x.jpg"); anything else must be https
        if (url.startsWith('/images/venues/')) {
            assert.ok(fs.existsSync(path.join(__dirname, '../docs', url)), `${venue}: ${url} is missing from docs/`);
        } else {
            assert.ok(url.startsWith('https://'), `${venue}: picture must be https`);
        }
    }
});

test("the venue's name in a row is a link to that venue's shows", () => {
    const { renderer, created } = loadRenderer();
    const link = renderer.venueLink('Art Mûr');
    assert.strictEqual(link.tag, 'a');
    assert.strictEqual(link.textContent, 'Art Mûr');
    assert.strictEqual(link.href, '?venue=Art%20M%C3%BBr');
    assert.strictEqual(link.className, 'venue-link');
    assert.ok(created.includes(link));
});

test('a plain click filters to the venue; a new-tab click and a missing search manager are left to the link', () => {
    const { renderer, window } = loadRenderer();
    const chosen = [];
    const link = renderer.venueLink('The Broad');
    const click = (extra = {}) => {
        const event = { button: 0, prevented: false, preventDefault() { event.prevented = true; }, ...extra };
        link.listeners.click(event);
        return event;
    };
    assert.ok(!click().prevented, 'before the filters are ready the link just works');
    window.searchManager = { setVenue: name => chosen.push(name) };
    assert.ok(click().prevented);
    assert.deepStrictEqual(chosen, ['The Broad']);
    for (const extra of [{ metaKey: true }, { ctrlKey: true }, { shiftKey: true }, { button: 1 }]) {
        assert.ok(!click(extra).prevented, JSON.stringify(extra));
    }
    assert.deepStrictEqual(chosen, ['The Broad']);
});
