// Region info: what every page knows about a region, read from docs/data/region_info.json.
// One entry per region (name, place, country, colour, map point, search words, blob look),
// so adding a city is one entry there and no change to the layout. The functions here are
// plain (no page needed) so they can be tested; regionPicker.js and regionPlace.js use them.
(function (root, factory) {
    if (typeof module === 'object' && module.exports) module.exports = factory();
    else root.RegionInfo = factory();
}(typeof self !== 'undefined' ? self : this, function () {
    // Words a visitor might type for a country, besides the name we show
    const COUNTRY_WORDS = {
        'USA': ['united states', 'us', 'america'],
        'Türkiye': ['turkey', 'turkiye'],
    };

    const SHAPES = ['a', 'b', 'c'];

    // Lower case with accents taken off, so "Montréal" and "montreal" are the same word
    function normalize(text) {
        return String(text == null ? '' : text).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
    }

    // "Oregon, USA", or just "Türkiye" for a region with no state or province
    function placeLine(region) {
        return [region.place, region.country].filter(Boolean).join(', ');
    }

    // The words search looks at for a region
    function searchWords(region) {
        const text = [
            region.name, region.label, region.place, region.country,
            ...(region.aliases || []), ...(COUNTRY_WORDS[region.country] || []),
        ].join(' ');
        return normalize(text).split(/[^a-z0-9]+/).filter(Boolean);
    }

    // Does the region match what was typed? Every typed word has to begin a word the region has,
    // so "port" finds Portland and "york" finds New York, but "ork" finds nothing.
    function matches(region, query) {
        const typed = normalize(query).split(/[^a-z0-9]+/).filter(Boolean);
        if (!typed.length) return true;
        const words = searchWords(region);
        return typed.every(t => words.some(w => w.startsWith(t)));
    }

    // The codes of the regions that match, in the file's order
    function matchingCodes(info, query) {
        return Object.keys(info).filter(code => matches(info[code], query));
    }

    // [{ country, codes: [...] }], countries in the order they first appear in the file
    function groupByCountry(info, codes) {
        const groups = [];
        (codes || Object.keys(info)).forEach(code => {
            const country = info[code].country;
            let group = groups.find(g => g.country === country);
            if (!group) groups.push(group = { country, codes: [] });
            group.codes.push(code);
        });
        return groups;
    }

    // How a region's blob looks. A region with no "blob" settings gets a plain, steady look
    // (shape rotating a, b, c down the list; a gentle tilt that alternates; middling size).
    function blobLook(region, index) {
        const blob = region.blob || {};
        return {
            shape: SHAPES.includes(blob.shape) ? blob.shape : SHAPES[index % SHAPES.length],
            tilt: typeof blob.tilt === 'number' ? blob.tilt : (index % 2 ? -1.8 : 1.8),
            width: typeof blob.width === 'number' ? blob.width : 215,
            dur: typeof blob.dur === 'number' ? blob.dur : 6.2,
        };
    }

    // What is wrong with the file, as readable lines (empty when it is fine). Used by the tests.
    function problems(info) {
        const found = [];
        const codes = Object.keys(info);
        if (!codes.length) found.push('No regions in the file.');
        codes.forEach(code => {
            const r = info[code];
            ['name', 'label', 'country'].forEach(field => {
                if (!r[field] || typeof r[field] !== 'string') found.push(`${code}: "${field}" is missing.`);
            });
            if (typeof r.place !== 'string') found.push(`${code}: "place" is missing (use "" for a region with no state or province).`);
            if (!/^#[0-9a-fA-F]{6}$/.test(r.colour || '')) found.push(`${code}: "colour" must be a hex colour like #14806b.`);
            if (typeof r.lat !== 'number' || r.lat < -90 || r.lat > 90) found.push(`${code}: "lat" must be a number from -90 to 90.`);
            if (typeof r.lng !== 'number' || r.lng < -180 || r.lng > 180) found.push(`${code}: "lng" must be a number from -180 to 180.`);
            if (r.aliases !== undefined && !Array.isArray(r.aliases)) found.push(`${code}: "aliases" must be a list.`);
            if (r.blob !== undefined && (typeof r.blob !== 'object' || r.blob === null)) found.push(`${code}: "blob" must be an object.`);
        });
        return found;
    }

    // Fetch the file once per page. `url` is where this page can reach docs/data/region_info.json.
    let loading = null;
    function load(url, fetchFn) {
        if (!loading) {
            loading = (fetchFn || fetch)(url)
                .then(response => {
                    if (!response.ok) throw new Error(`Could not load ${url} (${response.status})`);
                    return response.json();
                })
                .catch(error => { loading = null; throw error; });
        }
        return loading;
    }

    return { normalize, placeLine, searchWords, matches, matchingCodes, groupByCountry, blobLook, problems, load };
}));
