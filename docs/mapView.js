// Map View - the "List view | Map view" toggle and the map behind it (the map epic WEBSITE-76: WEBSITE-102 made
// the toggle and the shell, WEBSITE-103 adds the pins).
//
// - The table is the default. The choice is in the URL (?view=map, kept by SearchManager with the filters).
// - Nothing about the map is requested until the visitor opens Map view: not the library, the venue
//   coordinates, nor the tiles. The library is a pinned copy kept in docs/vendor/maplibre-gl/ (MapLibre GL JS),
//   so its requests go to our own site; the tiles come from OpenFreeMap (MAP_STYLE_URL is the only
//   provider-specific part).
// - If the map can't be shown (no WebGL, library or tiles blocked or offline, too slow) it says so briefly
//   and goes back to the table, so Map view is never an empty box.
// - Two-finger gestures (cooperativeGestures), so the map doesn't trap page scrolling on a phone.
// - Pins: one per location with a show matching the filters (mapPins.js works out what goes where). Nearby
//   pins merge into numbered clusters that zoom in when clicked; every number is a number of shows. A pin opens
//   a popup with the venue, its address, its shows, the distance (when "Use my location" is on) and the Map link.
//   The map frames the pins and re-frames when the filters change. A "Places on the map" list under the map
//   does everything a pin does and is reachable by keyboard and screen reader.
// - While "Use my location" is on, a dot shows where the visitor is, and the map frames it with the nearest pins.
//   That position is held in memory only while distances are on (Turn off clears it): never stored or sent.

// The map's tiles and styling. Swap this URL to change provider (see OPERATIONS.md, "The map").
const MAP_STYLE_URL = 'https://tiles.openfreemap.org/styles/positron';
const MAP_LOAD_TIMEOUT_MS = 15000;
const MAP_CLUSTER_RADIUS = 46;         // pixels: pins closer than this merge into a cluster
const MAP_CLUSTER_MAX_ZOOM = 14;       // beyond this every pin stands alone
const MAP_FRAME_MAX_ZOOM = 15;         // framing a few pins doesn't zoom in past street level
const MAP_NEAREST_PINS = 3;            // how many pins to frame with the visitor's dot
const MAP_GLYPH_FONT = ['Noto Sans Bold'];   // a font the style's glyph server has

// Where this script lives, so the library files next to it are found whatever page loads it
const MAP_SCRIPT_URL = (typeof document !== 'undefined' && document.currentScript && document.currentScript.src) || '';

const MAP_MESSAGES = {
    loading: 'Loading the map…',
    failed: 'The map couldn’t load (you may be offline, or something is blocking it), so here is the list instead.',
    noWebGl: 'Your browser can’t draw the map (it needs WebGL), so here is the list instead.',
    privacy: 'Loading the map shares your IP address with OpenFreeMap, which provides the map tiles. ' +
        'Your location is never sent to them.',
    textAlternative: 'This map shows where the venues are. The list view has the same information as text.',
};

// The toggle's two icons (list lines; a pin on a map), drawn in the button's text colour
const MAP_ICONS = {
    list: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.4" ' +
        'stroke-linecap="round" aria-hidden="true"><path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01"/></svg>',
    map: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.4" ' +
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 21s-6.5-5.7-6.5-10.5a6.5 6.5 0 0 1 13 0C18.5 15.3 12 21 12 21z"/>' +
        '<circle cx="12" cy="10.5" r="2.3"/></svg>',
};

// Can this browser draw a WebGL map at all? (MapLibre needs it.)
function mapHasWebGl() {
    try {
        const canvas = document.createElement('canvas');
        return !!(canvas.getContext('webgl2') || canvas.getContext('webgl'));
    } catch (error) {
        return false;
    }
}

// The real library loader: the stylesheet, then the ES module and its worker, all from docs/vendor/maplibre-gl/
async function loadMapLibre() {
    const url = file => new URL(`vendor/maplibre-gl/${file}`, MAP_SCRIPT_URL || document.baseURI).href;
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

class MapView {
    // options.loadLibrary: async () => the MapLibre module (a test passes a fake)
    // options.loadData:    async () => { coordinates: { venue: [{lat, lng}] }, bounds: { lat: [s, n], lng: [w, e] } }
    // options.venues:      { venue: address or list of addresses } (the venues file), for the popups' addresses and Map links
    // options.distanceTextFor: venue => "0.4 mi away" or null (from "Use my location")
    // options.addressesOf / options.mapLinksFor: how to read a venue's addresses and Map links (default: venueAddresses.js)
    // options.styleUrl, options.timeoutMs, options.accent: for tests
    constructor(searchManager, { loadLibrary = loadMapLibre, loadData, venues = {}, distanceTextFor = () => null,
                                 addressesOf, mapLinksFor, styleUrl = MAP_STYLE_URL, timeoutMs = MAP_LOAD_TIMEOUT_MS,
                                 accent } = {}) {
        this.searchManager = searchManager;
        this.loadLibrary = loadLibrary;
        this.loadData = loadData;
        this.venues = venues;
        this.distanceTextFor = distanceTextFor;
        this.addressesOf = addressesOf || (venue => window.venueAddresses.normalize(this.venues[venue]));
        this.mapLinksFor = mapLinksFor || (venue => window.venueAddresses.mapLinks(this.venues[venue]));
        this.styleUrl = styleUrl;
        this.timeoutMs = timeoutMs;
        this.accent = accent;
        this.map = null;
        this.maplibre = null;
        this.coordinates = {};
        this.pinsReady = false;     // the map has loaded and the pin layers are in
        this.locations = [];
        this.result = null;
        this.lastSignature = null;
        this.popup = null;
        this.you = null;            // { lat, lng } while "Use my location" is on; null otherwise
        this.youMarker = null;
        this.needsFrame = false;
        this.opening = false;       // a map is being created
        this.open = false;          // Map view is showing

        this.bar = document.querySelector('#filterPanel .filter-bar');
        const table = document.getElementById('eventTable');
        this.tableWrap = table ? table.closest('.table-responsive') : null;
        // Only the region pages have an event table and a filter bar
        this.available = !!(this.bar && this.tableWrap && this.loadData);
        if (!this.available) return;

        this.build();
        searchManager.subscribe(() => this.sync());
        this.sync();
    }

    build() {
        // The toggle: a two-segment control on the results line, beside "Showing X of Y events", since it
        // changes how those results are shown (the filters above stay filters). On phones it spans the
        // width above the count.
        this.toggle = document.createElement('div');
        this.toggle.className = 'view-toggle';
        this.toggle.setAttribute('role', 'group');
        this.toggle.setAttribute('aria-label', 'How to show the results');
        this.buttons = {};
        for (const [view, label] of [['list', 'List view'], ['map', 'Map view']]) {
            const button = document.createElement('button');
            button.type = 'button';
            // Constant markup only: a small icon, then the label
            button.innerHTML = MAP_ICONS[view] + '<span></span>';
            button.querySelector('span').textContent = label;
            button.addEventListener('click', () => this.searchManager.setView(view));
            this.buttons[view] = button;
            this.toggle.append(button);
        }
        this.summary = document.getElementById('filterSummary');
        if (this.summary && this.summary.parentNode) {
            this.resultsBar = document.createElement('div');
            this.resultsBar.className = 'results-bar';
            this.summary.parentNode.insertBefore(this.resultsBar, this.summary);
            this.resultsBar.append(this.summary, this.toggle);     // FilterPanel keeps redrawing the same summary element
        } else {
            this.bar.append(this.toggle);                          // no results line on this page: the filter bar will do
        }

        // The map, in place of the table
        this.section = document.createElement('section');
        this.section.className = 'map-view';
        this.section.hidden = true;
        this.section.setAttribute('aria-label', 'Map of venues');

        this.status = document.createElement('p');
        this.status.className = 'map-status';
        this.status.setAttribute('role', 'status');
        this.status.hidden = true;

        // "61 places · 213 shows", and the way out when nothing matches
        this.pinSummary = document.createElement('p');
        this.pinSummary.className = 'map-pin-summary';
        this.pinSummary.setAttribute('role', 'status');
        this.pinSummary.hidden = true;
        this.clearButton = document.createElement('button');
        this.clearButton.type = 'button';
        this.clearButton.className = 'map-clear';
        this.clearButton.textContent = 'Clear all filters';
        this.clearButton.hidden = true;
        this.clearButton.addEventListener('click', () => this.searchManager.clearFilters());

        this.canvas = document.createElement('div');
        this.canvas.className = 'map-canvas';

        this.alternative = document.createElement('p');
        this.alternative.className = 'visually-hidden';
        this.alternative.textContent = MAP_MESSAGES.textAlternative;

        // Everything a pin does, as a list: the way to the venues for keyboard and screen reader users
        this.places = document.createElement('details');
        this.places.className = 'map-places';
        this.places.hidden = true;
        this.placesSummary = document.createElement('summary');
        this.placesList = document.createElement('ul');
        this.places.append(this.placesSummary, this.placesList);

        this.note = document.createElement('p');
        this.note.className = 'map-note';
        this.note.textContent = MAP_MESSAGES.privacy;

        this.section.append(this.status, this.pinSummary, this.clearButton, this.alternative, this.canvas, this.places, this.note);
        this.tableWrap.before(this.section);

        // A message that outlives the map: why the visitor was sent back to the list
        this.message = document.createElement('p');
        this.message.className = 'map-message';
        this.message.setAttribute('role', 'status');
        this.message.hidden = true;
        (this.resultsBar || this.bar).after(this.message);

        // Escape closes an open popup
        document.addEventListener('keydown', event => {
            if (event.key === 'Escape' && this.popup) this.closePopup();
        });
    }

    setMessage(text) {
        this.message.textContent = text || '';
        this.message.hidden = !text;
    }

    // Bring the page in line with the state's view (the URL is already right)
    sync() {
        const wantMap = this.searchManager.state.view === 'map';
        for (const [view, button] of Object.entries(this.buttons)) {
            button.setAttribute('aria-pressed', String((view === 'map') === wantMap));
        }
        if (wantMap && !this.open) this.show();
        else if (!wantMap && this.open) this.hide();
        else if (this.open) this.updatePins();                      // a filter changed while the map is showing
    }

    show() {
        this.open = true;
        this.setMessage('');
        document.body.classList.add('map-view-on');
        this.section.hidden = false;
        if (!this.map && !this.opening) {
            this.createMap();
        } else if (this.pinsReady) {
            this.updatePins();                                      // the filters may have changed while the list was showing
            if (this.needsFrame) this.frame();
        }
    }

    hide() {
        this.open = false;
        document.body.classList.remove('map-view-on');
        this.section.hidden = true;
        this.closePopup();
    }

    setStatus(text) {
        this.status.textContent = text || '';
        this.status.hidden = !text;
    }

    // The library, the venue coordinates and the region's box load now, on the first open, never before
    async createMap() {
        this.opening = true;
        this.setStatus(MAP_MESSAGES.loading);
        try {
            if (!mapHasWebGl()) throw new Error('webgl');
            const [maplibre, data] = await Promise.all([this.loadLibrary(), this.loadData()]);
            const bounds = data && data.bounds;
            if (!bounds) throw new Error('no bounds for this region');
            this.maplibre = maplibre;
            this.coordinates = data.coordinates || {};
            if (!this.open) { this.opening = false; this.setStatus(''); return; }   // the visitor went back to the list meanwhile; the library stays cached

            const map = new maplibre.Map({
                container: this.canvas,
                style: this.styleUrl,
                bounds: [[bounds.lng[0], bounds.lat[0]], [bounds.lng[1], bounds.lat[1]]],   // [[west, south], [east, north]]
                fitBoundsOptions: { padding: 24 },
                cooperativeGestures: true,      // two fingers to pan: the page still scrolls under a finger
                attributionControl: { compact: false },
            });
            this.map = map;
            map.addControl(new maplibre.NavigationControl({ showCompass: false }), 'top-right');

            let loaded = false;
            let timer = null;
            // Give up if it hasn't loaded in time. A tab in the background draws no frames, so the map
            // cannot finish loading there: keep waiting until the visitor is looking at it again.
            const arm = () => setTimeout(() => {
                if (loaded || this.map !== map) return;
                if (document.hidden) timer = arm();
                else this.fail(MAP_MESSAGES.failed);
            }, this.timeoutMs);
            timer = arm();
            map.on('load', () => {
                loaded = true;
                clearTimeout(timer);
                this.opening = false;
                this.setStatus('');
                this.addPinLayers();
                this.updatePins();                  // frames the pins (or the visitor and the nearest ones)
                this.drawYouAreHere();
            });
            // Before the map has loaded, an error (the style can't be fetched) means there is no map;
            // afterwards a tile that fails is just a gap
            map.on('error', () => { if (!loaded) { clearTimeout(timer); this.fail(MAP_MESSAGES.failed); } });
        } catch (error) {
            console.error('Map view could not start:', error);
            this.fail(error && error.message === 'webgl' ? MAP_MESSAGES.noWebGl : MAP_MESSAGES.failed);
        }
    }

    // No map: say so, take the map away, and go back to the list (which also puts the URL right)
    fail(text) {
        this.closePopup();
        if (this.youMarker) { try { this.youMarker.remove(); } catch (error) { /* gone */ } this.youMarker = null; }
        if (this.map) {
            try { this.map.remove(); } catch (error) { /* already gone */ }
            this.map = null;
        }
        this.pinsReady = false;
        this.locations = [];
        this.lastSignature = null;
        this.opening = false;
        this.setStatus('');
        this.searchManager.setView('list');
        this.setMessage(text);
    }

    // ---- the pins ---------------------------------------------------------------------------------------------

    accentColour() {
        if (this.accent) return this.accent;
        const value = getComputedStyle(document.body).getPropertyValue('--region-c');
        return (value && value.trim()) || '#14806b';
    }

    // One clustered GeoJSON source and four layers: clusters and their numbers, single pins and theirs
    addPinLayers() {
        const map = this.map;
        const accent = this.accentColour();
        map.addSource('locations', {
            type: 'geojson',
            data: { type: 'FeatureCollection', features: [] },
            cluster: true,
            clusterRadius: MAP_CLUSTER_RADIUS,
            clusterMaxZoom: MAP_CLUSTER_MAX_ZOOM,
            clusterProperties: { shows: ['+', ['get', 'weight']] },   // a cluster adds up shows, counting each once
        });
        const circle = (id, filter, radius) => map.addLayer({
            id, type: 'circle', source: 'locations', filter,
            paint: { 'circle-color': accent, 'circle-radius': radius, 'circle-stroke-width': 2, 'circle-stroke-color': '#111' },
        });
        const label = (id, filter, text, size) => map.addLayer({
            id, type: 'symbol', source: 'locations', filter,
            layout: { 'text-field': ['to-string', ['get', text]], 'text-font': MAP_GLYPH_FONT, 'text-size': size, 'text-allow-overlap': true },
            paint: { 'text-color': '#ffffff' },
        });
        const isCluster = ['has', 'point_count'];
        const isPin = ['!', ['has', 'point_count']];
        circle('cluster-circles', isCluster, ['step', ['get', 'shows'], 16, 5, 20, 15, 25, 40, 31]);
        label('cluster-counts', isCluster, 'shows', 13);
        circle('pins', isPin, 13);
        label('pin-counts', isPin, 'count', 12);

        map.on('click', 'cluster-circles', event => this.zoomIntoCluster(event.features && event.features[0]));
        map.on('click', 'pins', event => {
            const key = event.features && event.features[0] && event.features[0].properties.key;
            const location = this.locations.find(candidate => candidate.key === key);
            if (location) this.openPopup(location);
        });
        for (const layer of ['cluster-circles', 'pins']) {
            map.on('mouseenter', layer, () => { map.getCanvas().style.cursor = 'pointer'; });
            map.on('mouseleave', layer, () => { map.getCanvas().style.cursor = ''; });
        }
        this.pinsReady = true;
    }

    zoomIntoCluster(feature) {
        if (!feature) return;
        this.closePopup();
        const source = this.map.getSource('locations');
        Promise.resolve(source.getClusterExpansionZoom(feature.properties.cluster_id)).then(zoom => {
            this.map.easeTo({ center: feature.geometry.coordinates, zoom });
        }).catch(() => { /* the map went away */ });
    }

    // Work out the pins for the current filters; redraw (and re-frame) only if they changed
    updatePins() {
        if (!this.pinsReady || !this.open) return;
        const result = mapPins.groupByLocation(this.searchManager.matchingRows(), this.coordinates, venue => this.addressesOf(venue));
        const signature = mapPins.signature(result.locations) + `|unplaced:${result.unplaced}`;
        if (signature === this.lastSignature) return;
        this.lastSignature = signature;
        this.result = result;
        this.locations = result.locations;
        this.closePopup();
        this.map.getSource('locations').setData(mapPins.toFeatureCollection(result.locations));
        this.renderSummary();
        this.renderPlaces();
        if (result.locations.length) this.frame();
    }

    renderSummary() {
        const result = this.result;
        this.pinSummary.textContent = mapPins.summaryText(result);
        this.pinSummary.hidden = false;
        this.clearButton.hidden = !(result.placed === 0 && result.unplaced === 0);
    }

    // The pins as a list of buttons; each does what clicking its pin does
    renderPlaces() {
        const items = [...this.locations]
            .sort((a, b) => a.venues[0].name.localeCompare(b.venues[0].name))
            .map(location => {
                const item = document.createElement('li');
                const button = document.createElement('button');
                button.type = 'button';
                const names = location.venues.map(venue => venue.label ? `${venue.name} (${venue.label})` : venue.name).join(', ');
                button.textContent = `${names}: ${location.count} ${location.count === 1 ? 'show' : 'shows'}`;
                button.addEventListener('click', () => this.goTo(location));
                item.append(button);
                return item;
            });
        this.placesSummary.textContent = `Places on the map (${this.locations.length})`;
        this.placesList.replaceChildren(...items);
        this.places.hidden = this.locations.length === 0;
    }

    // Fly to a place and open its popup (from the list)
    goTo(location) {
        this.map.flyTo({ center: [location.lng, location.lat], zoom: Math.max(this.map.getZoom(), MAP_CLUSTER_MAX_ZOOM + 0.5), duration: 600 });
        this.openPopup(location);
    }

    // Frame what matters: the visitor and the nearest pins if they are on the map, otherwise every pin.
    // (Framing a map that is hidden would measure it as empty, so that waits until Map view is showing.)
    frame() {
        if (!this.map || !this.pinsReady) return;
        if (!this.open) { this.needsFrame = true; return; }
        this.needsFrame = false;
        const nearest = this.you ? mapPins.nearestLocations(this.locations, this.you, MAP_NEAREST_PINS) : [];
        const bounds = nearest.length ? mapPins.boundsOf(nearest, [this.you]) : mapPins.boundsOf(this.locations);
        if (!bounds) return;
        if (mapPins.isSinglePoint(bounds)) {
            this.map.easeTo({ center: bounds[0], zoom: MAP_FRAME_MAX_ZOOM - 1 });
        } else {
            this.map.fitBounds(bounds, { padding: 56, maxZoom: MAP_FRAME_MAX_ZOOM, duration: 500 });
        }
    }

    // ---- popups -----------------------------------------------------------------------------------------------

    closePopup() {
        if (!this.popup) return;
        try { this.popup.remove(); } catch (error) { /* already gone */ }
        this.popup = null;
    }

    openPopup(location) {
        this.closePopup();
        this.popup = new this.maplibre.Popup({ offset: 16, maxWidth: '340px' })
            .setLngLat([location.lng, location.lat])
            .setDOMContent(this.popupContent(location))
            .addTo(this.map);
    }

    // Built with createElement and textContent only: nothing from the data is ever treated as HTML
    popupContent(location) {
        const root = document.createElement('div');
        root.className = 'map-popup';
        for (const venue of location.venues) {
            const section = document.createElement('div');
            section.className = 'map-popup-venue';

            const title = document.createElement('h3');
            title.className = 'map-popup-title';
            title.textContent = venue.label ? `${venue.name} (${venue.label})` : venue.name;
            section.append(title);

            if (venue.address) {
                const address = document.createElement('p');
                address.className = 'map-popup-address';
                address.textContent = venue.address;
                section.append(address);
            }
            const distance = this.distanceTextFor(venue.name);
            if (distance) {
                const away = document.createElement('p');
                away.className = 'map-popup-distance';
                away.textContent = distance;
                section.append(away);
            }

            const shows = document.createElement('ul');
            shows.className = 'map-popup-shows';
            for (const show of venue.shows) {
                const item = document.createElement('li');
                if (show.url) {
                    const link = document.createElement('a');
                    link.href = show.url;
                    link.target = '_blank';
                    link.rel = 'noopener noreferrer';
                    link.textContent = show.name;
                    item.append(link);
                } else {
                    item.append(show.name);
                }
                if (show.dates) {
                    const dates = document.createElement('span');
                    dates.className = 'map-popup-dates';
                    dates.textContent = show.dates;
                    item.append(dates);
                }
                shows.append(item);
            }
            section.append(shows);

            const link = (this.mapLinksFor(venue.name) || [])[venue.index];
            if (link) {
                const maps = document.createElement('a');
                maps.className = 'map-popup-map';
                maps.href = link.href;
                maps.target = '_blank';
                maps.rel = 'noopener noreferrer';
                maps.textContent = link.text;
                if (window.mapChoice) window.mapChoice.attach(maps, link); // Apple devices: Apple or Google Maps
                section.append(maps);
            }
            root.append(section);
        }
        return root;
    }

    // ---- "you are here" ---------------------------------------------------------------------------------------

    // Called by "Use my location" with the visitor's position, and with null when it is turned off. The position is
    // kept here only while it is on, to draw the dot; turning it off forgets it.
    setYouAreHere(point) {
        this.you = point ? { lat: point.lat, lng: point.lng } : null;
        this.drawYouAreHere();
        if (this.you) this.frame();
    }

    drawYouAreHere() {
        if (!this.map || !this.pinsReady) return;
        if (this.youMarker) { try { this.youMarker.remove(); } catch (error) { /* gone */ } this.youMarker = null; }
        if (!this.you) return;
        const dot = document.createElement('div');
        dot.className = 'map-you';
        dot.setAttribute('role', 'img');
        dot.setAttribute('aria-label', 'Your location');
        this.youMarker = new this.maplibre.Marker({ element: dot }).setLngLat([this.you.lng, this.you.lat]).addTo(this.map);
    }
}

window.MapView = MapView;
