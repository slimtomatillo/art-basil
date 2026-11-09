// Run with: node --test tests/
// The sums behind "Use my location" (docs/nearMe.js): distance, units, formatting, nearest-address
// choice, "far from the region", and nearest-first ordering. No DOM, no network.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const nearMe = require('../docs/nearMe.js');

const SF = { lat: 37.7749, lng: -122.4194 };
const OAKLAND = { lat: 37.8044, lng: -122.2712 };
const NEW_YORK = { lat: 40.7128, lng: -74.0060 };
const BAY_AREA = { lat: [36.9, 38.6], lng: [-123.1, -121.5] };      // docs/data/region_bounds.json

test('the distance between two points is the great-circle distance in kilometres', () => {
    assert.ok(Math.abs(nearMe.distanceKm(SF, OAKLAND) - 13.4) < 0.3);
    assert.ok(Math.abs(nearMe.distanceKm(SF, NEW_YORK) - 4129) < 15);
    assert.strictEqual(nearMe.distanceKm(SF, SF), 0);
    assert.strictEqual(nearMe.distanceKm(SF, OAKLAND), nearMe.distanceKm(OAKLAND, SF));
});

test('a point is valid only with finite latitude and longitude in range', () => {
    assert.ok(nearMe.isValidPoint(SF));
    for (const bad of [null, undefined, {}, { lat: 91, lng: 0 }, { lat: 0, lng: 181 }, { lat: NaN, lng: 0 }, { lat: '37', lng: '-122' }]) {
        assert.strictEqual(nearMe.isValidPoint(bad), false, JSON.stringify(bad));
    }
});

test('miles for the US regions and kilometres elsewhere', () => {
    assert.strictEqual(nearMe.unitsFor('sf'), 'mi');
    assert.strictEqual(nearMe.unitsFor('la'), 'mi');
    for (const region of ['mtl', 'tor', 'ist']) assert.strictEqual(nearMe.unitsFor(region), 'km');
    assert.strictEqual(nearMe.unitsFor('somewhere-new'), 'km');
});

test('every region has its units chosen on purpose', () => {
    const bounds = JSON.parse(fs.readFileSync(path.join(__dirname, '../docs/data/region_bounds.json'), 'utf8'));
    for (const region of Object.keys(bounds)) {
        assert.ok(nearMe.UNITS[region], `add "${region}" to UNITS in docs/nearMe.js (mi or km)`);
    }
});

test('distances read as 1.4 mi, 12 mi, 1,234 km and <0.1 km', () => {
    assert.strictEqual(nearMe.formatDistance(2.25, 'mi'), '1.4 mi');
    assert.strictEqual(nearMe.formatDistance(20, 'mi'), '12 mi');
    assert.strictEqual(nearMe.formatDistance(1234.4, 'km'), '1,234 km');
    assert.strictEqual(nearMe.formatDistance(2.25, 'km'), '2.3 km');
    assert.strictEqual(nearMe.formatDistance(0.05, 'km'), '<0.1 km');
    assert.strictEqual(nearMe.formatDistance(0, 'mi'), '<0.1 mi');
    assert.strictEqual(nearMe.formatDistance(9.96, 'km'), '10.0 km');          // rounds to one decimal below 10
});

test('a venue with two spaces is as far as its nearest one', () => {
    const near = { lat: 37.78, lng: -122.41 };
    const far = { lat: 37.87, lng: -122.27 };
    assert.strictEqual(nearMe.nearestKm(SF, [far, near]), nearMe.distanceKm(SF, near));
    assert.strictEqual(nearMe.nearestKm(SF, [far]), nearMe.distanceKm(SF, far));
});

test('a venue with no usable coordinates has no distance', () => {
    assert.strictEqual(nearMe.nearestKm(SF, []), null);
    assert.strictEqual(nearMe.nearestKm(SF, undefined), null);
    assert.strictEqual(nearMe.nearestKm(SF, [null, {}, { lat: 'x', lng: 1 }]), null);
});

test('distancesByVenue gives one distance per venue, null when it has none', () => {
    const distances = nearMe.distancesByVenue(SF, { Near: [OAKLAND], Nowhere: [], Odd: [{ lat: NaN, lng: 0 }] });
    assert.deepStrictEqual(Object.keys(distances), ['Near', 'Nowhere', 'Odd']);
    assert.ok(distances.Near > 13 && distances.Near < 14);
    assert.strictEqual(distances.Nowhere, null);
    assert.strictEqual(distances.Odd, null);
    assert.deepStrictEqual(nearMe.distancesByVenue(SF, undefined), {});
});

test('a visitor inside the region box is 0 km from it; outside, the distance to its nearest edge', () => {
    assert.strictEqual(nearMe.distanceToBoxKm(SF, BAY_AREA), 0);
    const west = { lat: 37.5, lng: -124.1 };                                   // 1 degree of longitude west of the box
    const km = nearMe.distanceToBoxKm(west, BAY_AREA);
    assert.ok(km > 85 && km < 95, km);
});

test('far from the region means more than 100 km from its box', () => {
    assert.strictEqual(nearMe.isFarFromRegion(SF, BAY_AREA), false);
    assert.strictEqual(nearMe.isFarFromRegion({ lat: 38.58, lng: -121.49 }, BAY_AREA), false);   // Sacramento
    assert.strictEqual(nearMe.isFarFromRegion({ lat: 34.05, lng: -118.24 }, BAY_AREA), true);    // Los Angeles
    assert.strictEqual(nearMe.isFarFromRegion(NEW_YORK, BAY_AREA), true);
    assert.strictEqual(nearMe.isFarFromRegion({ lat: 37.5, lng: -124.1 }, BAY_AREA, 100), false);
    assert.strictEqual(nearMe.isFarFromRegion({ lat: 37.5, lng: -124.1 }, BAY_AREA, 50), true);
});

test('nearest first: venues without a distance go last and ties keep the page order', () => {
    const rows = [
        { id: 'a', venue: 'Far' }, { id: 'b', venue: 'Near' }, { id: 'c', venue: 'Nowhere' },
        { id: 'd', venue: 'Near' }, { id: 'e', venue: 'Middle' }, { id: 'f', venue: 'Unknown' },
    ];
    const distances = { Far: 9, Near: 1, Middle: 4, Nowhere: null };
    const ordered = nearMe.orderByDistance(rows, row => distances[row.venue]);
    assert.deepStrictEqual(ordered.map(row => row.id), ['b', 'd', 'e', 'a', 'c', 'f']);
    assert.deepStrictEqual(rows.map(row => row.id), ['a', 'b', 'c', 'd', 'e', 'f']);            // the input is not changed
});

test('a distance of 0 is a distance (it sorts first, not last)', () => {
    const ordered = nearMe.orderByDistance(['x', 'y'], item => ({ x: null, y: 0 })[item]);
    assert.deepStrictEqual(ordered, ['y', 'x']);
});
