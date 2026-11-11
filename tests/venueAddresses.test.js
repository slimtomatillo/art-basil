// Run with: node --test tests/
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const va = require('../docs/venueAddresses.js');

const HART = { label: 'Hart House', address: '7 Hart House Circle, Toronto, ON M5S 3H3' };
const KINGS = { label: "King's College Circle", address: "15 King's College Circle, Toronto, ON M5S 3H7" };

test('a plain address is one entry with no label', () => {
    assert.deepStrictEqual(va.normalize('  1380 Sherbrooke St W, Montreal, QC '), [{ label: '', address: '1380 Sherbrooke St W, Montreal, QC' }]);
});

test('a list of { label, address } keeps both, in order', () => {
    assert.deepStrictEqual(va.normalize([HART, KINGS]), [HART, KINGS]);
});

test('empty, missing and malformed values give no entries', () => {
    for (const value of [undefined, null, '', '   ', [], {}, 42, [{}], [{ label: 'x' }], [null], [{ address: '' }]]) {
        assert.deepStrictEqual(va.normalize(value), [], JSON.stringify(value));
    }
});

test('a list may also hold plain strings, and bad items are dropped', () => {
    assert.deepStrictEqual(va.normalize(['1 A St', null, { address: '2 B St', label: ' B ' }]),
        [{ label: '', address: '1 A St' }, { label: 'B', address: '2 B St' }]);
});

test('a single address gets one plain "Map" link, as before', () => {
    const links = va.mapLinks('1380 Sherbrooke St W, Montreal, QC');
    assert.strictEqual(links.length, 1);
    assert.strictEqual(links[0].text, 'Map');
    assert.strictEqual(links[0].href, 'https://www.google.com/maps/search/?api=1&query=1380%20Sherbrooke%20St%20W%2C%20Montreal%2C%20QC');
});

test('a list of one address is also a plain "Map" link, whatever its label', () => {
    assert.deepStrictEqual(va.mapLinks([HART]).map(l => l.text), ['Map']);
});

test('several addresses get one labelled link each, and the address as the tooltip', () => {
    const links = va.mapLinks([HART, KINGS]);
    assert.deepStrictEqual(links.map(l => l.text), ['Map: Hart House', "Map: King's College Circle"]);
    assert.strictEqual(links[1].title, KINGS.address);
    assert.ok(links[1].href.endsWith(encodeURIComponent(KINGS.address)));
});

test('an entry with no label is numbered', () => {
    assert.deepStrictEqual(va.mapLinks([{ address: '1 A St' }, { address: '2 B St' }]).map(l => l.text), ['Map: 1', 'Map: 2']);
});

test('a venue with no address has no links', () => {
    assert.deepStrictEqual(va.mapLinks(undefined), []);
    assert.deepStrictEqual(va.mapLinks(''), []);
});

test('every committed venues file only holds addresses this module can read', () => {
    const dataDir = path.join(__dirname, '..', 'docs', 'data');
    const files = fs.readdirSync(dataDir).filter(f => f.endsWith('_venues.json'));
    assert.ok(files.length >= 5);
    for (const file of files) {
        const venues = JSON.parse(fs.readFileSync(path.join(dataDir, file), 'utf8'));
        for (const [name, value] of Object.entries(venues)) {
            const entries = va.normalize(value);
            assert.ok(entries.length > 0, `${file}: "${name}" has no readable address`);
            if (entries.length > 1) {
                assert.ok(entries.every(e => e.label), `${file}: "${name}" has several addresses, so each needs a label`);
            }
        }
    }
});

test('each map link also has an Apple Maps link for the same address', () => {
    const [link] = va.mapLinks('1380 Sherbrooke St W, Montreal, QC');
    assert.strictEqual(link.href, 'https://www.google.com/maps/search/?api=1&query=1380%20Sherbrooke%20St%20W%2C%20Montreal%2C%20QC');
    assert.strictEqual(link.appleHref, 'https://maps.apple.com/?q=1380%20Sherbrooke%20St%20W%2C%20Montreal%2C%20QC');
});

test('iPhone, iPad and Mac are Apple devices; Android, Windows and Linux are not', () => {
    const IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1';
    const MAC = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.0 Safari/605.1.15';
    assert.ok(va.isAppleDevice({ userAgent: IPHONE }));
    // iPadOS Safari reports itself as a Mac, so the Mac user agent covers it
    assert.ok(va.isAppleDevice({ userAgent: MAC, platform: 'MacIntel', maxTouchPoints: 5 }));
    // The platform is not trusted: a phone emulated on a Mac keeps platform 'MacIntel'
    assert.ok(!va.isAppleDevice({ userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/120 Mobile Safari/537.36', platform: 'MacIntel', maxTouchPoints: 5 }));
    assert.ok(!va.isAppleDevice({ userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/120 Mobile Safari/537.36' }));
    assert.ok(!va.isAppleDevice({ userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36', platform: 'Win32' }));
    assert.ok(!va.isAppleDevice(undefined));
    assert.ok(!va.isAppleDevice({}));
});
