// Map Pins - the pure logic behind the pins on Map view (WEBSITE-103; no DOM, so it is unit tested in Node:
// `node --test tests/`). MapView (mapView.js) draws them; this works out what goes where.
//
//  - One pin per LOCATION, not per venue: venues that share an address share a pin, and a venue with two
//    addresses (docs/data/venue_coordinates.json lists one entry per address) gets a pin at each.
//  - Every number is a number of SHOWS. A pin says how many matching shows are at that location. A cluster adds
//    up the pins inside it, counting a show once even when its venue has two pins (`weight`).
//  - A show whose venue has no coordinates cannot be placed; it is counted as `unplaced`, so the page can say so.

(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory(require('./nearMe.js'));
    } else {
        root.mapPins = factory(root.nearMe);
    }
}(typeof self !== 'undefined' ? self : this, function (nearMe) {

    const KEY_DECIMALS = 5;                   // about a metre: two venues at one address get one key

    const isPlace = point => !!point && Number.isFinite(point.lat) && Number.isFinite(point.lng);

    function locationKey(lat, lng) {
        return `${lat.toFixed(KEY_DECIMALS)},${lng.toFixed(KEY_DECIMALS)}`;
    }

    // A table row that matches the filters -> what a popup lists for the show
    function showOf(row) {
        const event = row.event || {};
        const page = (event.links || []).find(link => link.description === 'Event Page');
        return { name: event.name || '', dates: row.dateText || '', url: page ? page.link : null, phase: event.phase || '' };
    }

    // rows:        the rows that match the current filters: { venue, event, dateText }
    // coordinates: { venue: [{ lat, lng, approx? }, ...] }, one entry per address of the venue
    // addressesOf: venue -> [{ label, address }, ...] in the same order (docs/venueAddresses.js normalize)
    // Returns { locations, placed, unplaced, venues }:
    //   locations: [{ key, lat, lng, approx, count, weight, venues: [{ name, label, address, index, shows }] }]
    //   placed / unplaced: how many of the rows' shows are on the map / have no location
    function groupByLocation(rows, coordinates, addressesOf = () => []) {
        const byVenue = new Map();
        for (const row of rows) {
            if (!byVenue.has(row.venue)) byVenue.set(row.venue, []);
            byVenue.get(row.venue).push(row);
        }

        const byKey = new Map();
        let placed = 0, unplaced = 0, venuesPlaced = 0;
        for (const [venue, venueRows] of byVenue) {
            const entries = (coordinates && coordinates[venue]) || [];
            const usable = entries.map((entry, index) => ({ entry, index })).filter(({ entry }) => isPlace(entry));
            if (usable.length === 0) {
                unplaced += venueRows.length;
                continue;
            }
            placed += venueRows.length;
            venuesPlaced += 1;
            const addresses = addressesOf(venue) || [];
            const labelOf = ({ entry, index }) => (addresses[index] || {}).label || String(index + 1);
            // Where each show is shown: the addresses it names (an event's `locations`, address labels), or every address of
            // its venue when it names none, or none that this venue has (a mistyped label must not make a show vanish)
            const placesOf = row => {
                const named = (row.event && Array.isArray(row.event.locations)) ? row.event.locations : [];
                const hits = usable.filter(pin => named.includes(labelOf(pin)));
                return hits.length ? hits : usable;
            };
            const placements = venueRows.map(row => ({ show: showOf(row), pins: placesOf(row) }));
            usable.forEach((pin, n) => {
                const { entry, index } = pin;
                const shows = placements.filter(p => p.pins.includes(pin)).map(p => p.show);
                if (shows.length === 0) return;                       // no show of this venue is at this address
                const key = locationKey(entry.lat, entry.lng);
                if (!byKey.has(key)) {
                    byKey.set(key, { key, lat: entry.lat, lng: entry.lng, approx: false, count: 0, weight: 0, venues: [] });
                }
                const location = byKey.get(key);
                location.approx = location.approx || !!entry.approx;
                // A venue with several addresses is told apart by the address's label ("Hart House")
                const address = addresses[index] || {};
                location.venues.push({
                    name: venue,
                    label: entries.length > 1 ? (address.label || String(index + 1)) : '',
                    address: address.address || '',
                    index,
                    shows,
                });
                location.count += shows.length;
                // a show counts once in a cluster, at the first address it is at
                location.weight += placements.filter(p => p.pins[0] === pin).length;
            });
        }
        const locations = [...byKey.values()];
        locations.forEach(location => location.venues.sort((a, b) => a.name.localeCompare(b.name)));
        return { locations, placed, unplaced, venues: venuesPlaced };
    }

    // The GeoJSON the map draws. `count` is what the pin says; `weight` is what a cluster adds up.
    function toFeatureCollection(locations) {
        return {
            type: 'FeatureCollection',
            features: locations.map(location => ({
                type: 'Feature',
                geometry: { type: 'Point', coordinates: [location.lng, location.lat] },
                properties: { key: location.key, count: location.count, weight: location.weight },
            })),
        };
    }

    // [[west, south], [east, north]] around the locations and any extra { lat, lng } points, or null
    function boundsOf(locations, extra = []) {
        const points = [...locations, ...extra].filter(isPlace);
        if (points.length === 0) return null;
        const lats = points.map(p => p.lat), lngs = points.map(p => p.lng);
        return [[Math.min(...lngs), Math.min(...lats)], [Math.max(...lngs), Math.max(...lats)]];
    }

    function isSinglePoint(bounds) {
        return !!bounds && bounds[0][0] === bounds[1][0] && bounds[0][1] === bounds[1][1];
    }

    // The n locations nearest a point, nearest first
    function nearestLocations(locations, point, n = 3) {
        return locations
            .map(location => ({ location, km: nearMe.distanceKm(point, location) }))
            .sort((a, b) => a.km - b.km)
            .slice(0, n)
            .map(entry => entry.location);
    }

    // "61 places · 213 shows", or "No shows match these filters." `unplaced` shows have no map location, so the
    // line says so (they are in the list view)
    function summaryText({ locations, placed, unplaced }) {
        const n = value => value.toLocaleString('en-US');
        const noLocation = `${n(unplaced)} ${unplaced === 1 ? 'show has' : 'shows have'} no map location`;
        if (placed === 0 && unplaced === 0) return 'No shows match these filters.';
        if (placed === 0) return `${noLocation}; see the list view.`;
        const places = locations.length === 1 ? '1 place' : `${n(locations.length)} places`;
        const shows = placed === 1 ? '1 show' : `${n(placed)} shows`;
        return unplaced ? `${places} · ${shows} (${noLocation}; see the list view)` : `${places} · ${shows}`;
    }

    // Changes only when the pins would: used to skip redrawing (and re-framing the map) for a change that doesn't matter
    function signature(locations) {
        return locations.map(location => `${location.key}:${location.count}:${location.weight}`).join('|');
    }

    return { locationKey, showOf, groupByLocation, toFeatureCollection, boundsOf, isSinglePoint, nearestLocations, summaryText, signature };
}));
