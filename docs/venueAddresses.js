// Venue Addresses - the pure logic behind a venue's address(es) and its map links
// (no DOM access, so it can be unit tested in Node: `node --test tests/`).
// TableRenderer (the "Map" link under each event) and VenuesRenderer (the venue
// directory) both use it.
//
// A venue's value in docs/data/<region>_venues.json is either
//   - a street address string (the usual case), or
//   - a list of { "label": "Hart House", "address": "7 Hart House Circle, Toronto, ON" }
//     for a venue with more than one space that shows its exhibitions together
//     (see "A venue with more than one space" in ADDING_A_REGION.md).

(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.venueAddresses = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {

    const MAPS_SEARCH_URL = 'https://www.google.com/maps/search/?api=1&query=';
    // Opens the Apple Maps app on an iPhone, iPad or Mac (and Apple's web map elsewhere)
    const APPLE_MAPS_SEARCH_URL = 'https://maps.apple.com/?q=';

    /** True on an iPhone, iPad or Mac, where the Map link offers Apple Maps as well as Google Maps.
     *  `nav` is the browser's navigator (passed in so it can be tested). iPadOS Safari reports itself
     *  as a Mac ("Macintosh"), so it is covered too. Only the user agent is read: the platform value
     *  is not reliable (a phone emulated on a Mac keeps the Mac's). */
    function isAppleDevice(nav) {
        if (!nav) return false;
        return /iPhone|iPad|iPod|Macintosh|Mac OS X/.test(String(nav.userAgent || ''));
    }

    /** A venue's value from the venues file -> a list of { label, address } (empty if it has none).
     *  A plain string, a list of strings and a list of { label, address } objects are all accepted. */
    function normalize(value) {
        if (typeof value === 'string') {
            const address = value.trim();
            return address ? [{ label: '', address }] : [];
        }
        if (!Array.isArray(value)) return [];
        const entries = [];
        value.forEach(item => {
            const address = typeof item === 'string' ? item : (item && typeof item.address === 'string' ? item.address : '');
            if (!address.trim()) return;
            const label = item && typeof item.label === 'string' ? item.label.trim() : '';
            entries.push({ label, address: address.trim() });
        });
        return entries;
    }

    /** One map link per address: [{ text, href, appleHref, title, label, address }]. `href` is Google Maps
     *  (what everyone gets by default); `appleHref` is the same place in Apple Maps.
     *  A venue with a single address gets plain "Map"; with several, "Map: <label>"
     *  (or "Map: 2" for an entry that has no label). `title` is the address, for a tooltip. */
    function mapLinks(value) {
        const entries = normalize(value);
        return entries.map((entry, i) => ({
            text: entries.length === 1 ? 'Map' : `Map: ${entry.label || i + 1}`,
            href: MAPS_SEARCH_URL + encodeURIComponent(entry.address),
            appleHref: APPLE_MAPS_SEARCH_URL + encodeURIComponent(entry.address),
            title: entry.address,
            label: entry.label,
            address: entry.address,
        }));
    }

    return { MAPS_SEARCH_URL, APPLE_MAPS_SEARCH_URL, isAppleDevice, normalize, mapLinks };
}));
