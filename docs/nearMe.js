// Near Me - the pure logic behind "Use my location" (no DOM access, so it can be unit
// tested in Node: `node --test tests/`). NearMeControl (nearMeControl.js) draws the
// control and the distances and reorders the table; this only does the sums.
//
// Distances are straight-line ("as the crow flies") between the visitor's position and a
// venue's coordinates (docs/data/venue_coordinates.json), so they are approximate and are
// shown that way. Nothing here stores or sends a position.

(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.nearMe = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {

    const EARTH_RADIUS_KM = 6371;
    const KM_PER_MILE = 1.609344;

    // Miles where people think in miles (the US regions), kilometres elsewhere. Every region in
    // docs/data/region_bounds.json needs an entry here (a test checks), so a new city is a
    // decision made on purpose rather than a silent default. See ADDING_A_REGION.md.
    const UNITS = { sf: 'mi', la: 'mi', mtl: 'km', tor: 'km', ist: 'km' };

    // A visitor further than this from the box around a region's venues is "far away": showing
    // "2,900 mi" on every row would be noise, so distances are left off and the page says why.
    // Generous, because a region such as the Bay Area is itself about 200 km across.
    const FAR_FROM_REGION_KM = 100;

    const toRadians = degrees => degrees * Math.PI / 180;

    // A point is { lat, lng } in degrees
    function isValidPoint(point) {
        return !!point && Number.isFinite(point.lat) && Number.isFinite(point.lng) &&
            point.lat >= -90 && point.lat <= 90 && point.lng >= -180 && point.lng <= 180;
    }

    // Great-circle (haversine) distance in kilometres
    function distanceKm(a, b) {
        const dLat = toRadians(b.lat - a.lat);
        const dLng = toRadians(b.lng - a.lng);
        const h = Math.sin(dLat / 2) ** 2 +
            Math.cos(toRadians(a.lat)) * Math.cos(toRadians(b.lat)) * Math.sin(dLng / 2) ** 2;
        return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(h)));
    }

    // Kilometres from a point to a region's bounding box ({ lat: [south, north], lng: [west, east] },
    // docs/data/region_bounds.json): 0 inside it, else the distance to the nearest point of it.
    function distanceToBoxKm(point, box) {
        const nearest = {
            lat: Math.min(Math.max(point.lat, box.lat[0]), box.lat[1]),
            lng: Math.min(Math.max(point.lng, box.lng[0]), box.lng[1]),
        };
        return distanceKm(point, nearest);
    }

    function isFarFromRegion(point, box, limitKm = FAR_FROM_REGION_KM) {
        return distanceToBoxKm(point, box) > limitKm;
    }

    function unitsFor(region) {
        return UNITS[region] || 'km';
    }

    // "1.4 mi", "12 mi", "<0.1 km": one decimal under 10, whole numbers above, thousands separated
    function formatDistance(km, units) {
        const value = units === 'mi' ? km / KM_PER_MILE : km;
        if (value < 0.1) return `<0.1 ${units}`;
        const text = value < 10 ? value.toFixed(1) : Math.round(value).toLocaleString('en-US');
        return `${text} ${units}`;
    }

    // The distance to the nearest of a venue's coordinates (a venue with two spaces has two), or
    // null when it has none. Entries that are not valid points are ignored.
    function nearestKm(user, points) {
        let best = null;
        for (const point of points || []) {
            if (!isValidPoint(point)) continue;
            const km = distanceKm(user, point);
            if (best === null || km < best) best = km;
        }
        return best;
    }

    // { venue name: kilometres | null } for every venue in a region's coordinates
    // ({ venue: [{ lat, lng }, ...] }, one region's part of venue_coordinates.json)
    function distancesByVenue(user, coordinates) {
        const distances = {};
        for (const [venue, points] of Object.entries(coordinates || {})) {
            distances[venue] = nearestKm(user, points);
        }
        return distances;
    }

    // `items` nearest first. Ones with no distance go last, and equal distances (two events at one
    // venue, or two venues at one address) keep the order they came in, so pass the items in the
    // page's usual order.
    function orderByDistance(items, distanceOf) {
        return items
            .map((item, position) => ({ item, position, distance: distanceOf(item) }))
            .sort((a, b) => {
                const aNone = a.distance === null || a.distance === undefined;
                const bNone = b.distance === null || b.distance === undefined;
                if (aNone !== bNone) return aNone ? 1 : -1;
                if (!aNone && a.distance !== b.distance) return a.distance - b.distance;
                return a.position - b.position;
            })
            .map(entry => entry.item);
    }

    return {
        UNITS, FAR_FROM_REGION_KM,
        isValidPoint, distanceKm, distanceToBoxKm, isFarFromRegion, unitsFor, formatDistance,
        nearestKm, distancesByVenue, orderByDistance,
    };
}));
