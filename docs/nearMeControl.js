// Near Me Control - the "Use my location" button in the filter bar, the distance shown on
// each event row, and "Nearest first" ordering of the table. The sums live in nearMe.js.
//
// Privacy, by design:
//  - The browser's permission prompt appears only when the visitor clicks the button, never on load.
//  - The position is used once to work out each venue's distance and then dropped: it is not kept
//    in a variable, storage or a cookie, not put in the URL, and not sent anywhere. (The only
//    requests are for the venue coordinates and the region's bounding box, which are static files.)
//  - Reloading the page forgets everything.

const NEAR_ME_MESSAGES = {
    locating: 'Finding your location…',
    denied: 'Your browser blocked location for this site. Allow it in the site settings, then try again.',
    unavailable: 'Couldn’t work out where you are. Try again in a moment.',
    timeout: 'Finding your location took too long. Try again.',
    data: 'Couldn’t load the venue locations. Try again.',
    on: nearestFirst => `Showing how far each show is from where you are${nearestFirst ? ', nearest first' : ''}. ` +
        'Distances are straight-line, so approximate.',
    far: distance => `You’re about ${distance} from the venues listed here, so distances aren’t shown.`,
    privacy: 'Your location stays in this browser: it isn’t saved or sent anywhere.',
};

class NearMeControl {
    // options.region: 'sf', 'la', ...   (picks miles or kilometres)
    // options.loadData: async () => ({ coordinates: { venue: [{lat, lng}] }, bounds: {lat: [s, n], lng: [w, e]} | null })
    // options.geolocation: navigator.geolocation (a test can pass its own)
    constructor(searchManager, { region, loadData, geolocation } = {}) {
        this.searchManager = searchManager;
        this.units = nearMe.unitsFor(region);
        this.loadData = loadData;
        this.geolocation = geolocation || (typeof navigator !== 'undefined' ? navigator.geolocation : null);
        this.phase = 'off';          // 'off' | 'locating' | 'on'
        this.nearestFirst = true;    // once the visitor shares a location, nearest first is the point
        this.distances = {};         // { venue: km | null }, only while 'on'
        this.data = null;

        this.panelEl = document.getElementById('filterPanel');
        this.bar = this.panelEl && this.panelEl.querySelector('.filter-bar');
        // No filter bar (not a region page) or a browser with no location support: offer nothing
        this.available = !!(this.bar && this.geolocation && this.loadData);
        if (!this.available) return;
        this.build();
        this.render();
    }

    build() {
        const group = document.createElement('div');
        group.className = 'near-me';

        this.mainButton = document.createElement('button');
        this.mainButton.type = 'button';
        this.mainButton.className = 'filter-dropdown-toggle near-me-main';
        // Constant markup only (a map pin); nothing from the data goes in here
        this.mainButton.innerHTML =
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" ' +
            'stroke-linejoin="round" aria-hidden="true" width="16" height="16"><path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/>' +
            '<circle cx="12" cy="10" r="2.5"/></svg><span class="near-me-label"></span>';
        this.label = this.mainButton.querySelector('.near-me-label');
        this.mainButton.addEventListener('click', () => this.onMainClick());

        this.offButton = document.createElement('button');
        this.offButton.type = 'button';
        this.offButton.className = 'near-me-off';
        this.offButton.textContent = 'Turn off';
        this.offButton.addEventListener('click', () => this.turnOff());

        group.append(this.mainButton, this.offButton);
        this.bar.append(group);

        // Under the bar (FilterPanel redraws only inside the bar and the summary, so this stays)
        this.note = document.createElement('div');
        this.note.className = 'near-me-note';
        this.message = document.createElement('span');
        this.message.className = 'near-me-message';
        this.message.setAttribute('role', 'status');
        this.privacy = document.createElement('span');
        this.privacy.className = 'near-me-privacy';
        this.privacy.textContent = NEAR_ME_MESSAGES.privacy;
        this.note.append(this.message, this.privacy);
        this.panelEl.append(this.note);
    }

    setMessage(text) {
        this.message.textContent = text || '';
        this.message.hidden = !text;
    }

    // Bring the button, the extra link and the note in line with the phase
    render() {
        const on = this.phase === 'on';
        const locating = this.phase === 'locating';
        this.mainButton.disabled = locating;
        this.mainButton.classList.toggle('has-selection', on && this.nearestFirst);
        this.mainButton.setAttribute('aria-busy', locating ? 'true' : 'false');
        if (on) {
            this.label.textContent = 'Nearest first';
            this.mainButton.setAttribute('aria-pressed', String(this.nearestFirst));
            this.mainButton.removeAttribute('aria-label');
        } else {
            this.label.textContent = locating ? 'Finding you…' : 'Use my location';
            this.mainButton.removeAttribute('aria-pressed');
            // Starts with the visible words, and says what it does for a screen reader
            if (locating) this.mainButton.removeAttribute('aria-label');
            else this.mainButton.setAttribute('aria-label', 'Use my location to show how far each show is');
        }
        this.offButton.hidden = !on;
    }

    onMainClick() {
        if (this.phase === 'on') {
            this.nearestFirst = !this.nearestFirst;
            this.applyOrder();
            this.setMessage(NEAR_ME_MESSAGES.on(this.nearestFirst));
            this.render();
        } else {
            this.start();
        }
    }

    start() {
        if (this.phase === 'locating') return;
        this.phase = 'locating';
        this.setMessage(NEAR_ME_MESSAGES.locating);
        this.render();
        // A cached position up to five minutes old is fine for "how far is it"; low accuracy saves battery
        this.geolocation.getCurrentPosition(
            position => this.onPosition(position),
            error => this.onError(error),
            { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 });
    }

    fail(text) {
        this.phase = 'off';
        this.setMessage(text);
        this.render();
    }

    onError(error) {
        const code = error && error.code;
        this.fail(code === 1 ? NEAR_ME_MESSAGES.denied : code === 3 ? NEAR_ME_MESSAGES.timeout : NEAR_ME_MESSAGES.unavailable);
    }

    async onPosition(position) {
        const coords = position && position.coords;
        const user = coords ? { lat: coords.latitude, lng: coords.longitude } : null;
        if (!nearMe.isValidPoint(user)) return this.fail(NEAR_ME_MESSAGES.unavailable);

        try {
            if (!this.data) this.data = await this.loadData();
        } catch (error) {
            console.error('Failed to load venue locations:', error);
            return this.fail(NEAR_ME_MESSAGES.data);
        }
        const { coordinates, bounds } = this.data;

        // Far from everything listed here (a visitor in New York looking at San Francisco)
        if (bounds && nearMe.isFarFromRegion(user, bounds)) {
            const distance = nearMe.formatDistance(nearMe.distanceToBoxKm(user, bounds), this.units);
            return this.fail(NEAR_ME_MESSAGES.far(distance));
        }

        // The position has done its job once each venue's distance is known; it is not kept
        this.distances = nearMe.distancesByVenue(user, coordinates);
        this.phase = 'on';
        this.nearestFirst = true;
        this.showDistances();
        this.applyOrder();
        this.setMessage(NEAR_ME_MESSAGES.on(this.nearestFirst));
        this.render();
    }

    turnOff() {
        this.phase = 'off';
        this.distances = {};
        this.showDistances();
        this.applyOrder();
        this.setMessage('');
        this.render();
        this.mainButton.focus();     // the button the "Turn off" link replaced
    }

    // The "1.4 mi away" line in each row's Links cell (empty and hidden when there is no distance)
    showDistances() {
        for (const row of this.searchManager.rows) {
            if (!row.distanceEl) continue;
            const km = this.phase === 'on' ? this.distances[row.venue] : null;
            const has = km !== null && km !== undefined;
            row.distanceEl.textContent = has ? `${nearMe.formatDistance(km, this.units)} away` : '';
            row.distanceEl.title = has ? 'Straight-line distance from you (approximate)' : '';
            row.distanceEl.hidden = !has;
        }
    }

    // Nearest first, or back to the page's usual order. Hidden (filtered-out) rows move too, so
    // changing a filter later needs no re-sorting.
    applyOrder() {
        const body = this.searchManager.tableBody;
        if (!body) return;
        const usual = [...this.searchManager.rows].sort((a, b) => a.index - b.index);
        const ordered = this.phase === 'on' && this.nearestFirst
            ? nearMe.orderByDistance(usual, row => this.distances[row.venue])
            : usual;
        body.append(...ordered.map(row => row.el));
    }
}

window.NearMeControl = NearMeControl;
