// Run with: node --test tests/
// The logic behind the pins on Map view (docs/mapPins.js): one pin per location, shows counted once, venues with
// no coordinates left off (and counted), the GeoJSON, framing, the nearest places and the summary line.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const mapPins = require('../docs/mapPins.js');
const venueAddresses = require('../docs/venueAddresses.js');

const row = (venue, name, extra = {}) => ({
    venue,
    dateText: extra.dateText || 'Through Dec 1, 2026',
    event: { name, phase: extra.phase || 'current', links: extra.links || [{ link: `https://x.example/${name}`, description: 'Event Page' }] },
});

const COORDINATES = {
    'Gallery A': [{ lat: 37.78, lng: -122.41 }],
    'Gallery B': [{ lat: 37.78, lng: -122.41 }],                                   // the same address as A
    'Museum': [{ lat: 37.8, lng: -122.3 }],
    'Two Spaces': [{ lat: 34.05, lng: -118.25 }, { lat: 34.06, lng: -118.3 }],
    'Rough': [{ lat: 41.03, lng: 28.98, approx: true }],
    'No Coordinates': [],
};
const addressesOf = venue => venueAddresses.normalize({
    'Two Spaces': [{ label: 'Downtown', address: '1 A St' }, { label: 'Hollywood', address: '2 B St' }],
    'Gallery A': '10 Main St',
}[venue]);

test('a show is placed at its venue, with the address and its own details for the popup', () => {
    const { locations, placed, unplaced } = mapPins.groupByLocation(
        [row('Gallery A', 'Show 1', { dateText: 'Opens Nov 20, 2026', phase: 'future' })], COORDINATES, addressesOf);
    assert.strictEqual(locations.length, 1);
    assert.strictEqual(placed, 1);
    assert.strictEqual(unplaced, 0);
    const [location] = locations;
    assert.deepStrictEqual([location.lat, location.lng, location.count, location.weight], [37.78, -122.41, 1, 1]);
    assert.deepStrictEqual(location.venues.map(v => ({ name: v.name, label: v.label, address: v.address })), [{ name: 'Gallery A', label: '', address: '10 Main St' }]);
    assert.deepStrictEqual(location.venues[0].shows, [{ name: 'Show 1', dates: 'Opens Nov 20, 2026', url: 'https://x.example/Show 1', phase: 'future' }]);
});

test('two venues at one address share a pin whose popup lists both, and the pin counts all their shows', () => {
    const { locations } = mapPins.groupByLocation(
        [row('Gallery B', 'B1'), row('Gallery A', 'A1'), row('Gallery A', 'A2')], COORDINATES, addressesOf);
    assert.strictEqual(locations.length, 1);
    assert.deepStrictEqual(locations[0].venues.map(v => v.name), ['Gallery A', 'Gallery B']);        // by name
    assert.strictEqual(locations[0].count, 3);
    assert.strictEqual(locations[0].weight, 3);
});

test('a venue with two addresses gets a pin at each, labelled, and its shows are added up only once', () => {
    const { locations, placed } = mapPins.groupByLocation([row('Two Spaces', 'S1'), row('Two Spaces', 'S2')], COORDINATES, addressesOf);
    assert.strictEqual(locations.length, 2);
    assert.deepStrictEqual(locations.map(l => l.venues[0].label), ['Downtown', 'Hollywood']);
    assert.deepStrictEqual(locations.map(l => l.venues[0].address), ['1 A St', '2 B St']);
    assert.deepStrictEqual(locations.map(l => l.venues[0].index), [0, 1]);
    assert.deepStrictEqual(locations.map(l => l.count), [2, 2]);                                      // each pin shows both shows
    assert.deepStrictEqual(locations.map(l => l.weight), [2, 0]);                                     // a cluster counts them once
    assert.strictEqual(placed, 2);
    assert.strictEqual(locations.reduce((sum, l) => sum + l.weight, 0), 2);
});

test('a venue with two addresses and no label is told apart by its position', () => {
    const { locations } = mapPins.groupByLocation([row('Two Spaces', 'S1')], COORDINATES, () => [{ label: '', address: 'a' }, { label: '', address: 'b' }]);
    assert.deepStrictEqual(locations.map(l => l.venues[0].label), ['1', '2']);
});

test('a show whose venue has no coordinates is not on the map, and is counted as such', () => {
    const result = mapPins.groupByLocation(
        [row('No Coordinates', 'N1'), row('Unknown Venue', 'U1'), row('Museum', 'M1')], COORDINATES, addressesOf);
    assert.strictEqual(result.locations.length, 1);
    assert.strictEqual(result.placed, 1);
    assert.strictEqual(result.unplaced, 2);
});

test('a rough location (the street or area) is flagged, and a bad entry is skipped', () => {
    const { locations } = mapPins.groupByLocation([row('Rough', 'R1')], COORDINATES, addressesOf);
    assert.strictEqual(locations[0].approx, true);
    const odd = mapPins.groupByLocation([row('Odd', 'O1')], { Odd: [{ lat: 'x', lng: 1 }, null, {}] });
    assert.deepStrictEqual([odd.locations.length, odd.unplaced], [0, 1]);
});

test('a show without an Event Page link still has a name and dates, with no link', () => {
    const { locations } = mapPins.groupByLocation([row('Museum', 'M1', { links: [{ link: 'https://x.example/i.jpg', description: 'Image' }] })], COORDINATES, addressesOf);
    assert.strictEqual(locations[0].venues[0].shows[0].url, null);
});

test('no matching shows gives no pins', () => {
    const result = mapPins.groupByLocation([], COORDINATES, addressesOf);
    assert.deepStrictEqual([result.locations, result.placed, result.unplaced], [[], 0, 0]);
});

test('the GeoJSON puts longitude first and carries what the pin and the cluster need', () => {
    const { locations } = mapPins.groupByLocation([row('Two Spaces', 'S1')], COORDINATES, addressesOf);
    const collection = mapPins.toFeatureCollection(locations);
    assert.strictEqual(collection.type, 'FeatureCollection');
    assert.deepStrictEqual(collection.features[0].geometry.coordinates, [-118.25, 34.05]);
    assert.deepStrictEqual(collection.features[0].properties, { key: locations[0].key, count: 1, weight: 1 });
    assert.strictEqual(collection.features[1].properties.weight, 0);
});

test('bounds cover every pin and any extra point, and a single point is recognised', () => {
    const { locations } = mapPins.groupByLocation([row('Museum', 'M'), row('Gallery A', 'A')], COORDINATES, addressesOf);
    assert.deepStrictEqual(mapPins.boundsOf(locations), [[-122.41, 37.78], [-122.3, 37.8]]);
    assert.deepStrictEqual(mapPins.boundsOf(locations, [{ lat: 37.7, lng: -122.5 }]), [[-122.5, 37.7], [-122.3, 37.8]]);
    assert.strictEqual(mapPins.boundsOf([]), null);
    assert.strictEqual(mapPins.isSinglePoint(mapPins.boundsOf([locations[0]])), true);
    assert.strictEqual(mapPins.isSinglePoint(mapPins.boundsOf(locations)), false);
    assert.strictEqual(mapPins.isSinglePoint(null), false);
});

test('the nearest places to a point come nearest first', () => {
    const { locations } = mapPins.groupByLocation(
        [row('Museum', 'M'), row('Gallery A', 'A'), row('Two Spaces', 'T')], COORDINATES, addressesOf);
    const sfLike = { lat: 37.79, lng: -122.4 };
    assert.deepStrictEqual(mapPins.nearestLocations(locations, sfLike, 2).map(l => l.venues[0].name), ['Gallery A', 'Museum']);
    assert.strictEqual(mapPins.nearestLocations(locations, sfLike, 10).length, locations.length);
});

test('the summary line says places and shows, and what could not be placed', () => {
    const summary = (placed, places, unplaced) => mapPins.summaryText({ locations: new Array(places), placed, unplaced });
    assert.strictEqual(summary(213, 61, 0), '61 places · 213 shows');
    assert.strictEqual(summary(1, 1, 0), '1 place · 1 show');
    assert.strictEqual(summary(1234, 61, 3), '61 places · 1,234 shows (3 shows have no map location; see the list view)');
    assert.strictEqual(summary(5, 2, 1), '2 places · 5 shows (1 show has no map location; see the list view)');
    assert.strictEqual(summary(0, 0, 4), '4 shows have no map location; see the list view.');
    assert.strictEqual(summary(0, 0, 0), 'No shows match these filters.');
});

test('the signature changes only when the pins would', () => {
    const a = mapPins.groupByLocation([row('Museum', 'M1')], COORDINATES, addressesOf).locations;
    const same = mapPins.groupByLocation([row('Museum', 'Another title')], COORDINATES, addressesOf).locations;
    const more = mapPins.groupByLocation([row('Museum', 'M1'), row('Museum', 'M2')], COORDINATES, addressesOf).locations;
    assert.strictEqual(mapPins.signature(a), mapPins.signature(same));
    assert.notStrictEqual(mapPins.signature(a), mapPins.signature(more));
    assert.strictEqual(mapPins.signature([]), '');
});

test('every real venue that has coordinates can be placed with the real data', () => {
    // A guard on the data this runs on: each region's venues file and coordinates file line up for the grouping
    const data = name => JSON.parse(fs.readFileSync(path.join(__dirname, '../docs/data', name), 'utf8'));
    const coordinates = data('venue_coordinates.json');
    for (const region of Object.keys(coordinates)) {
        const venues = data(`${region}_venues.json`);
        const rows = Object.keys(venues).map(venue => row(venue, 'x'));
        const { locations, unplaced } = mapPins.groupByLocation(rows, coordinates[region], v => venueAddresses.normalize(venues[v]));
        assert.strictEqual(unplaced, 0, `${region}: a venue has no usable coordinates`);
        assert.ok(locations.length > 0 && locations.length <= rows.length + 3, region);          // shared addresses merge; two-address venues add pins
        for (const location of locations) {
            for (const v of location.venues) assert.ok(v.address, `${region}: ${v.name} has no address text for its pin`);
        }
    }
});
