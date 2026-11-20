// The home page's region picker: the paint blobs, a Blobs / Map / List toggle and a search box,
// all drawn from docs/data/region_info.json (see regionInfo.js), so a new region is one entry there.
//
// - Blobs is the default. Each blob shows the region name and its place ("Oregon, USA").
// - List groups the regions by country and shows each one's venue count.
// - Map is one world map with a coloured dot per region and a key under it. It is only loaded
//   (the library and the tiles) when the visitor opens it, because the tiles come from OpenFreeMap,
//   which sees the visitor's IP address.
// - The search box filters all three at once.
//
// The 404 page uses renderBlobs on its own. Everything here takes the page's `document`, so it can
// be tested without a browser.
(function (root, factory) {
    if (typeof module === 'object' && module.exports) module.exports = factory(require('./regionInfo.js'));
    else root.RegionPicker = factory(root.RegionInfo);
}(typeof self !== 'undefined' ? self : this, function (RegionInfo) {
    const VIEWS = ['blobs', 'map', 'list'];
    const VIEW_LABELS = { blobs: 'Blobs', map: 'Map', list: 'List' };
    const STORAGE_KEY = 'artbasil.homeView';
    const MAP_STYLE_URL = 'https://tiles.openfreemap.org/styles/positron';
    const MESSAGES = {
        privacy: 'Loading the map shares your IP address with OpenFreeMap, which provides the map tiles. ' +
            'Your location is never sent to them.',
        mapFailed: 'The map couldn’t load (you may be offline, or something is blocking it), so here is the list instead.',
        noWebGl: 'Your browser can’t draw the map (it needs WebGL), so here is the list instead.',
    };

    // Where this script lives, so the map library files next to it are found whatever page loads it
    const SCRIPT_URL = (typeof document !== 'undefined' && document.currentScript && document.currentScript.src) || '';

    // ---- small helpers ----

    // Make an element: attrs are set as attributes ("class" and "text" are special), kids are appended
    function make(doc, tag, attrs, kids) {
        const node = doc.createElement(tag);
        Object.entries(attrs || {}).forEach(([key, value]) => {
            if (value === undefined || value === null || value === false) return;
            if (key === 'text') node.textContent = value;
            else if (key === 'class') node.className = value;
            else node.setAttribute(key, value === true ? '' : String(value));
        });
        (kids || []).forEach(kid => node.appendChild(kid));
        return node;
    }

    function plural(n, one, many) {
        return `${n} ${n === 1 ? one : many}`;
    }

    // A saved view is only used if it is one we know. The map is never opened for the visitor
    // on arrival: its tiles share their IP address, so they open it themselves each time.
    function startingView(saved) {
        return saved === 'list' ? 'list' : 'blobs';
    }

    function homeUrl(base, code) {
        return `${base}${code}/index.html`;
    }

    // ---- the blobs (used by the home page and the 404 page) ----

    function buildBlob(doc, code, region, index, base) {
        const look = RegionInfo.blobLook(region, index);
        const place = RegionInfo.placeLine(region);
        const link = make(doc, 'a', {
            href: homeUrl(base, code),
            class: `region-blob shape-${look.shape}`,
            'aria-label': `${region.name}, ${place}`,
            'data-region': code,
        }, [
            make(doc, 'span', { class: 'blob-body' }, [
                make(doc, 'span', { class: 'region-name', text: region.name }),
                make(doc, 'span', { class: 'region-place', text: place }),
            ]),
        ]);
        link.style.setProperty('--c', region.colour);
        link.style.setProperty('--t', `${look.tilt}deg`);
        link.style.setProperty('--w', `${look.width}px`);
        link.style.setProperty('--dur', `${look.dur}s`);
        return link;
    }

    // Fill a <nav class="region-blobs"> with one blob per region. Returns { code: blob }.
    function renderBlobs(nav, info, options) {
        const doc = nav.ownerDocument;
        const base = (options && options.base) || '';
        const blobs = {};
        const links = Object.keys(info).map((code, index) => {
            blobs[code] = buildBlob(doc, code, info[code], index, base);
            return blobs[code];
        });
        nav.replaceChildren(...links);
        return blobs;
    }

    // ---- the picker ----

    // options: { root, info, base, storage, loadVenueCount(code), loadMapLibrary(), hasWebGl() }
    function create(options) {
        const { root, info } = options;
        const doc = root.ownerDocument;
        const base = options.base || '';
        const codes = Object.keys(info);
        const state = { view: 'blobs', query: '', map: null, mapFailed: false, countsLoaded: false };

        // The Blobs / Map / List toggle and the search box
        const toggle = make(doc, 'div', { class: 'picker-toggle', role: 'group', 'aria-label': 'How to show the places' });
        const toggleButtons = {};
        VIEWS.forEach(view => {
            const button = make(doc, 'button', { type: 'button', class: 'picker-toggle-button', text: VIEW_LABELS[view], 'data-view': view });
            button.addEventListener('click', () => setView(view));
            toggleButtons[view] = button;
            toggle.appendChild(button);
        });

        const input = make(doc, 'input', {
            type: 'search', id: 'pickerSearch', class: 'picker-search-input', placeholder: 'Search places',
            autocomplete: 'off', enterkeyhint: 'search',
        });
        const label = make(doc, 'label', { class: 'picker-search', for: 'pickerSearch' }, [
            make(doc, 'span', { class: 'visually-hidden', text: 'Search places by city, state or country' }),
            input,
        ]);
        input.addEventListener('input', () => { state.query = input.value; applyFilter(); });
        const bar = make(doc, 'div', { class: 'picker-bar' }, [toggle, label]);

        // Blobs
        const nav = make(doc, 'nav', { class: 'region-blobs', 'aria-label': 'Choose a region' });
        const blobs = renderBlobs(nav, info, { base });

        // List, grouped by country
        const listView = make(doc, 'div', { class: 'picker-list-view' });
        const rows = {};
        const counts = {};
        const groups = [];
        RegionInfo.groupByCountry(info).forEach(group => {
            const list = make(doc, 'ul', { class: 'picker-list' });
            group.codes.forEach(code => {
                const region = info[code];
                const count = make(doc, 'span', { class: 'picker-count' });
                counts[code] = count;
                const item = make(doc, 'li', { 'data-region': code }, [
                    make(doc, 'a', { class: 'picker-row', href: homeUrl(base, code) }, [
                        make(doc, 'span', { class: 'picker-dot', 'aria-hidden': 'true' }),
                        make(doc, 'span', { class: 'picker-row-text' }, [
                            make(doc, 'span', { class: 'picker-row-name', text: region.name }),
                            make(doc, 'span', { class: 'picker-row-place', text: RegionInfo.placeLine(region) }),
                        ]),
                        count,
                    ]),
                ]);
                item.firstChild.firstChild.style.background = region.colour;
                rows[code] = item;
                list.appendChild(item);
            });
            const heading = make(doc, 'h2', { class: 'picker-country', text: group.country });
            const section = make(doc, 'section', { 'aria-label': group.country }, [heading, list]);
            groups.push({ country: group.country, codes: group.codes, section });
            listView.appendChild(section);
        });

        // Map and its key (the map itself is only made when it is first opened)
        const mapBox = make(doc, 'div', { class: 'picker-map', role: 'region', 'aria-label': 'Map of the places' });
        const keyItems = {};
        const key = make(doc, 'ul', { class: 'picker-key' });
        codes.forEach(code => {
            const dot = make(doc, 'span', { class: 'picker-dot', 'aria-hidden': 'true' });
            dot.style.background = info[code].colour;
            const item = make(doc, 'li', { 'data-region': code }, [
                make(doc, 'a', { href: homeUrl(base, code) }, [dot, make(doc, 'span', { text: info[code].name })]),
            ]);
            item.firstChild.addEventListener('mouseenter', () => highlight(code, true));
            item.firstChild.addEventListener('mouseleave', () => highlight(code, false));
            item.firstChild.addEventListener('focus', () => highlight(code, true));
            item.firstChild.addEventListener('blur', () => highlight(code, false));
            keyItems[code] = item;
            key.appendChild(item);
        });
        const mapNote = make(doc, 'p', { class: 'picker-note', text: MESSAGES.privacy });
        const mapMessage = make(doc, 'p', { class: 'picker-note picker-note-warn', role: 'status', hidden: true });
        const mapView = make(doc, 'div', { class: 'picker-map-view' }, [mapBox, key, mapNote, mapMessage]);

        // What the search found, for everyone, and the "nothing matched" message for everyone too
        const status = make(doc, 'p', { class: 'picker-status', role: 'status', hidden: true });

        root.replaceChildren(bar, nav, listView, mapView, status);

        // ---- behaviour ----

        const pins = {};

        function highlight(code, on) {
            if (pins[code]) pins[code].classList.toggle('on', on);
        }

        function matchingNow() {
            return RegionInfo.matchingCodes(info, state.query);
        }

        function applyFilter() {
            const found = new Set(matchingNow());
            codes.forEach(code => {
                const shown = found.has(code);
                blobs[code].hidden = !shown;
                rows[code].hidden = !shown;
                keyItems[code].hidden = !shown;
                if (pins[code]) pins[code].hidden = !shown;
            });
            groups.forEach(group => { group.section.hidden = !group.codes.some(code => found.has(code)); });
            const typed = state.query.trim();
            if (!typed) {
                status.hidden = true;
                status.textContent = '';
            } else {
                status.hidden = false;
                status.textContent = found.size
                    ? `${plural(found.size, 'place matches', 'places match')} “${typed}”.`
                    : `Nothing matches “${typed}” yet. Try a city, state or country, or tell us about your area below.`;
                status.classList.toggle('picker-status-empty', !found.size);
            }
        }

        async function loadCounts() {
            if (state.countsLoaded || !options.loadVenueCount) return;
            state.countsLoaded = true;
            await Promise.all(codes.map(async code => {
                try {
                    const n = await options.loadVenueCount(code);
                    if (Number.isFinite(n)) counts[code].textContent = plural(n, 'venue', 'venues');
                } catch (error) { /* leave this one blank */ }
            }));
        }

        function showMapMessage(text) {
            mapMessage.textContent = text;
            mapMessage.hidden = !text;
        }

        async function openMap() {
            if (state.map || state.mapFailed) {
                if (state.map && state.map.resize) state.map.resize();
                return;
            }
            const fail = text => {
                state.mapFailed = true;
                showMapMessage(text);
                setView('list');
            };
            try {
                if (options.hasWebGl && !options.hasWebGl()) return fail(MESSAGES.noWebGl);
                const lib = await options.loadMapLibrary();
                const lngs = codes.map(code => info[code].lng);
                const lats = codes.map(code => info[code].lat);
                const map = new lib.Map({
                    container: mapBox,
                    style: MAP_STYLE_URL,
                    bounds: [[Math.min(...lngs), Math.min(...lats)], [Math.max(...lngs), Math.max(...lats)]],
                    fitBoundsOptions: { padding: 40, maxZoom: 5 },
                    attributionControl: { compact: true },
                    dragRotate: false,
                    scrollZoom: false,
                });
                let loaded = false;
                map.once('load', () => { loaded = true; });
                map.on('error', () => { if (!loaded && !state.mapFailed) fail(MESSAGES.mapFailed); });
                codes.forEach(code => {
                    const region = info[code];
                    const dot = make(doc, 'span', { class: 'picker-pin-dot' });
                    dot.style.background = region.colour;
                    const pin = make(doc, 'a', {
                        class: 'picker-pin', href: homeUrl(base, code),
                        'aria-label': `${region.name}, ${RegionInfo.placeLine(region)}`,
                    }, [dot]);
                    pin.addEventListener('mouseenter', () => highlight(code, true));
                    pin.addEventListener('mouseleave', () => highlight(code, false));
                    pin.hidden = !matchingNow().includes(code);
                    pins[code] = pin;
                    new lib.Marker({ element: pin }).setLngLat([region.lng, region.lat]).addTo(map);
                });
                state.map = map;
            } catch (error) {
                fail(MESSAGES.mapFailed);
            }
        }

        function setView(view) {
            if (!VIEWS.includes(view)) return;
            state.view = view;
            VIEWS.forEach(name => toggleButtons[name].setAttribute('aria-pressed', String(name === view)));
            nav.hidden = view !== 'blobs';
            listView.hidden = view !== 'list';
            mapView.hidden = view !== 'map';
            if (view === 'list') loadCounts();
            if (view === 'map') openMap();
            if (options.storage) {
                try { options.storage.setItem(STORAGE_KEY, view); } catch (error) { /* private mode: not remembered */ }
            }
        }

        let saved = null;
        try { saved = options.storage && options.storage.getItem(STORAGE_KEY); } catch (error) { /* ignore */ }
        setView(startingView(saved));
        applyFilter();

        return { state, setView, applyFilter, input, blobs, rows, keyItems, pins, toggleButtons, nav, listView, mapView, status, counts };
    }

    // ---- the real browser's pieces ----

    async function loadMapLibrary() {
        const url = file => new URL(`vendor/maplibre-gl/${file}`, SCRIPT_URL || document.baseURI).href;
        await new Promise((resolve, reject) => {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = url('maplibre-gl.css');
            link.addEventListener('load', resolve, { once: true });
            link.addEventListener('error', () => reject(new Error('maplibre-gl.css failed to load')), { once: true });
            document.head.appendChild(link);
        });
        const maplibre = await import(url('maplibre-gl.js'));
        maplibre.setWorkerUrl(url('maplibre-gl-worker.js'));
        return maplibre;
    }

    function hasWebGl() {
        try {
            const canvas = document.createElement('canvas');
            return !!(canvas.getContext('webgl2') || canvas.getContext('webgl'));
        } catch (error) {
            return false;
        }
    }

    // The home page: fetch the data, then take over the page's static blobs
    function boot(rootId) {
        const rootEl = document.getElementById(rootId);
        if (!rootEl) return Promise.resolve();
        return RegionInfo.load('data/region_info.json')
            .then(info => {
                let storage = null;
                try { storage = window.localStorage; } catch (error) { /* blocked */ }
                return create({
                    root: rootEl, info, base: '', storage, loadMapLibrary, hasWebGl,
                    loadVenueCount: async code => {
                        const response = await fetch(`data/${code}_venues.json`);
                        return Object.keys(await response.json()).length;
                    },
                });
            })
            .catch(error => { console.error('The region picker could not load; the plain links stay.', error); });
    }

    return { VIEWS, STORAGE_KEY, MESSAGES, startingView, renderBlobs, create, boot };
}));
