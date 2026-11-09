// Map View - the "List view | Map view" toggle and the map behind it (WEBSITE-102, part of the map epic
// WEBSITE-76). This is the shell: the toggle, the lazily loaded map framed on the region, the fallback
// when it can't load, the attribution and the privacy note. Pins, clusters and popups come with WEBSITE-103.
//
// - The table is the default. The choice is in the URL (?view=map, kept by SearchManager with the filters).
// - Nothing about the map is requested until the visitor opens Map view: not the library, not the tiles.
//   The library is a pinned copy kept in docs/vendor/maplibre-gl/ (MapLibre GL JS), so its requests go to
//   our own site; the tiles come from OpenFreeMap (MAP_STYLE_URL is the only provider-specific part).
// - If the map can't be shown (no WebGL, library or tiles blocked or offline, too slow) it says so briefly
//   and goes back to the table, so Map view is never an empty box.
// - Two-finger gestures (cooperativeGestures), so the map doesn't trap page scrolling on a phone.

// The map's tiles and styling. Swap this URL to change provider (see OPERATIONS.md, "The map").
const MAP_STYLE_URL = 'https://tiles.openfreemap.org/styles/positron';
const MAP_LOAD_TIMEOUT_MS = 15000;

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
    // options.loadBounds:  async () => { lat: [south, north], lng: [west, east] } for the region
    // options.styleUrl, options.timeoutMs: for tests
    constructor(searchManager, { loadLibrary = loadMapLibre, loadBounds, styleUrl = MAP_STYLE_URL,
                                 timeoutMs = MAP_LOAD_TIMEOUT_MS } = {}) {
        this.searchManager = searchManager;
        this.loadLibrary = loadLibrary;
        this.loadBounds = loadBounds;
        this.styleUrl = styleUrl;
        this.timeoutMs = timeoutMs;
        this.map = null;
        this.opening = false;       // a map is being created
        this.open = false;          // Map view is showing

        this.bar = document.querySelector('#filterPanel .filter-bar');
        const table = document.getElementById('eventTable');
        this.tableWrap = table ? table.closest('.table-responsive') : null;
        // Only the region pages have an event table and a filter bar
        this.available = !!(this.bar && this.tableWrap && this.loadBounds);
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

        this.canvas = document.createElement('div');
        this.canvas.className = 'map-canvas';

        this.alternative = document.createElement('p');
        this.alternative.className = 'visually-hidden';
        this.alternative.textContent = MAP_MESSAGES.textAlternative;

        this.note = document.createElement('p');
        this.note.className = 'map-note';
        this.note.textContent = MAP_MESSAGES.privacy;

        this.section.append(this.status, this.alternative, this.canvas, this.note);
        this.tableWrap.before(this.section);

        // A message that outlives the map: why the visitor was sent back to the list
        this.message = document.createElement('p');
        this.message.className = 'map-message';
        this.message.setAttribute('role', 'status');
        this.message.hidden = true;
        (this.resultsBar || this.bar).after(this.message);
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
    }

    show() {
        this.open = true;
        this.setMessage('');
        document.body.classList.add('map-view-on');
        this.section.hidden = false;
        if (!this.map && !this.opening) this.createMap();
    }

    hide() {
        this.open = false;
        document.body.classList.remove('map-view-on');
        this.section.hidden = true;
    }

    setStatus(text) {
        this.status.textContent = text || '';
        this.status.hidden = !text;
    }

    // The library and the region's box load now, on the first open, never before
    async createMap() {
        this.opening = true;
        this.setStatus(MAP_MESSAGES.loading);
        try {
            if (!mapHasWebGl()) throw new Error('webgl');
            const [maplibre, bounds] = await Promise.all([this.loadLibrary(), this.loadBounds()]);
            if (!bounds) throw new Error('no bounds for this region');
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
            map.on('load', () => { loaded = true; clearTimeout(timer); this.opening = false; this.setStatus(''); });
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
        if (this.map) {
            try { this.map.remove(); } catch (error) { /* already gone */ }
            this.map = null;
        }
        this.opening = false;
        this.setStatus('');
        this.searchManager.setView('list');
        this.setMessage(text);
    }
}

window.MapView = MapView;
