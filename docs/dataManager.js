// Data Manager - Handles data fetching and region detection

// Get the region from the URL path
const getRegion = () => {
    const path = window.location.pathname;
    
    if (path.includes('/sf/')) {
        return 'sf';
    }
    if (path.includes('/la/')) {
        return 'la';
    }
    if (path.includes('/mtl/')) {
        return 'mtl';
    }
    if (path.includes('/tor/')) {
        return 'tor';
    }
    if (path.includes('/ist/')) {
        return 'ist';
    }

    return 'sf'; // default to SF
};

// Event dates are calendar days at the venue, so whether a show is upcoming, current
// or past depends on today's date in the venue's own time zone - not the viewer's.
// The region -> time zone map lives in one place, docs/data/regions.json, read here
// and by REGION_TIMEZONES in config.py - not duplicated in this file.
let regionTimezones = null; // populated by ensureRegionTimezones(); read synchronously once loaded
let regionTimezonesPromise = null;

async function ensureRegionTimezones() {
    if (!regionTimezonesPromise) {
        regionTimezonesPromise = fetch('../data/regions.json')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(zones => { regionTimezones = zones; })
            .catch(error => {
                regionTimezonesPromise = null; // let the next caller retry rather than cache the failure
                console.error('Failed to fetch region time zones:', error);
                throw error;
            });
    }
    return regionTimezonesPromise;
}

// Today's date in the region's time zone as 'YYYY-MM-DD'. ISO date strings compare
// chronologically as plain strings, so no Date/time-zone arithmetic is needed.
// Synchronous: callers must await ensureRegionTimezones() first (fetchEvents() does).
function regionToday(region, now = new Date()) {
    if (!regionTimezones) {
        throw new Error('Region time zones not loaded yet - await ensureRegionTimezones() (or fetchEvents()) first');
    }
    const timeZone = regionTimezones[region];
    if (!timeZone) {
        throw new Error(`No time zone for region '${region}'; add it to docs/data/regions.json`);
    }
    const parts = new Intl.DateTimeFormat('en-US', {
        timeZone,
        year: 'numeric', month: '2-digit', day: '2-digit',
    }).formatToParts(now);
    const get = type => parts.find(part => part.type === type).value;
    return `${get('year')}-${get('month')}-${get('day')}`;
}

const PHASES = ['future', 'current', 'past'];

// Phase implied by an event's dates ('YYYY-MM-DD' or null), or null if it has none
function derivePhase(start, end, today) {
    if (end && end < today) return 'past';
    if (start && start > today) return 'future';
    if (start || end) return 'current';
    return null;
}

// The day part of a stored date, or null ("2020-02-23 00:00:00" and 'null' are handled)
function dayOf(value) {
    return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value) ? value.slice(0, 10) : null;
}

// The scraper stamps each event's phase once a day, so it can lag the venue's midnight by
// hours, and events nothing re-scrapes (hand-entered ones) never advance. Bring every
// event's phase and tags up to date for the viewer's visit. Mirrors update_event_phases
// in processing.py: phases only move forward (future -> current -> past) and are never
// revived, since a source can mark a show past without recording an end date.
function applyRegionPhases(events, region, now = new Date()) {
    const today = regionToday(region, now);
    Object.values(events).forEach(venueEvents => {
        Object.values(venueEvents).forEach(event => {
            const derived = derivePhase(dayOf(event.dates && event.dates.start), dayOf(event.dates && event.dates.end), today);
            const current = PHASES.indexOf(event.phase);
            if (derived && PHASES.indexOf(derived) > current) {
                event.phase = derived;
                event.tags = (event.tags || []).filter(tag => !PHASES.includes(tag)).concat(derived);
                if (derived === 'past') event.ongoing = false;
            }
        });
    });
    return events;
}

// Load venue data
let venuesCache = null; // Cache for storing the venue data
async function fetchVenues() {
    const region = getRegion();
    
    try {
        const response = await fetch(`../data/${region}_venues.json`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const venues = await response.json();
        return venues;
    } catch (error) {
        console.error('Failed to fetch venues:', error);
        return [];
    }
}

// Load event data
async function fetchEvents() {
    const region = getRegion();

    try {
        await ensureRegionTimezones();
        const response = await fetch(`../data/${region}_events.json`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const events = await response.json();
        return applyRegionPhases(events, region);
    } catch (error) {
        console.error('Failed to fetch events:', error);
        return {};
    }
}

// Export functions for use in other modules
window.dataManager = {
    getRegion,
    fetchVenues,
    fetchEvents,
    ensureRegionTimezones,
    regionToday,
    derivePhase,
    applyRegionPhases
};
