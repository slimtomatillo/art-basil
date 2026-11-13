// Filter State - the pure logic behind the event filters (no DOM access, so it
// can be unit tested in Node: `node --test tests/`). SearchManager owns the
// live state and the table; FilterPanel draws the controls. Both use this.

(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.filterState = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {

    // The tags worth offering as filters, grouped. Keep in step with
    // docs/tags.html and APPROVED_TAGS in tagging.py. A tag not listed here
    // (e.g. "museum", or one added later) still filters when selected by
    // clicking its chip; it just isn't offered in the panel.
    const TAG_GROUPS = [
        { id: 'medium', label: 'Medium', tags: [
            'architecture', 'ceramics', 'drawing', 'fashion', 'film-video', 'installation',
            'painting', 'photography', 'printmaking', 'sculpture', 'textiles'] },
        { id: 'theme', label: 'Theme', tags: [
            'asian-american', 'black-art', 'immigrant', 'indigenous', 'latinx', 'queer',
            'refugee', 'south-asian'] },
        { id: 'cost', label: 'Cost', tags: ['free'] },
        // No events carry these yet (only `free` is used today), so this group stays hidden until some do.
        { id: 'format', label: 'Format', tags: [
            'audio', 'closing', 'family', 'performance', 'symposium', 'talk',
            'tour', 'virtual', 'workshop'] },
    ];

    // "When" is a multi-select over four mutually exclusive buckets: Current
    // (on view, with an end date), Ongoing (on view, no end date), Future and
    // Past. Ticking all four shows everything, so there is no separate "All".
    // By default a visitor sees what is on and what is coming, not the archive.
    const ALL_PHASES = ['current', 'ongoing', 'future', 'past'];
    const DEFAULT_PHASES = ['current', 'ongoing', 'future'];
    const PHASE_LABELS = { current: 'Current', ongoing: 'Ongoing', future: 'Future', past: 'Past' };
    const PHASE_HINTS = { current: 'has an end date', ongoing: 'no end date' };

    // An ongoing show is always a current one (the scrapers never flag a past or
    // future show), so it gets its own bucket instead of overlapping "current".
    function bucketOf(phase, ongoing) {
        return phase === 'current' && ongoing ? 'ongoing' : phase;
    }

    function groupOf(tag) {
        const group = TAG_GROUPS.find(g => g.tags.includes(tag));
        return group ? group.id : null;
    }

    // Keep phases in canonical order, valid and without duplicates
    function normalizePhases(phases) {
        return ALL_PHASES.filter(phase => phases.includes(phase));
    }

    function samePhases(a, b) {
        return a.length === b.length && a.every((phase, i) => phase === b[i]);
    }

    // Which way the results are shown: the table ('list', the default) or the map ('map'). It is part of the
    // view in the URL (?view=map) but is not a filter: "Clear all" leaves it alone and isDefault ignores it.
    const VIEWS = ['list', 'map'];
    const DEFAULT_VIEW = 'list';

    // --- dates and areas (WEBSITE-94) ----------------------------------------

    // "Dates" is a second choice inside the When dropdown. A quick pick is relative to today (so a shared
    // ?when=weekend link is "this weekend" whenever it is opened); a custom range is two fixed days. Choosing
    // one REPLACES the When phases: a show that is open on a given day may count as past today.
    //   today / weekend / week   shows open on that day or range (the weekend is this Saturday and Sunday)
    //   closing                  current shows whose end date falls in the next SOON_DAYS days
    //   opening                  upcoming shows whose start date falls in the next SOON_DAYS days
    const TIMING_PICKS = ['today', 'weekend', 'week', 'closing', 'opening'];
    const TIMING_LABELS = {
        today: 'Open today', weekend: 'Open this weekend', week: 'Open in the next 7 days',
        closing: 'Closing soon', opening: 'Opening soon',
    };
    const SOON_DAYS = 14;
    const TIMING_HINTS = { closing: `in the next ${SOON_DAYS} days`, opening: `in the next ${SOON_DAYS} days` };

    const DAY_RE = /^\d{4}-\d{2}-\d{2}$/;

    // A real calendar day as 'YYYY-MM-DD', or null ('2026-02-30' and '2026-2-3' are not)
    function validDay(value) {
        if (typeof value !== 'string' || !DAY_RE.test(value)) return null;
        const date = new Date(`${value}T00:00:00Z`);
        return Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== value ? null : value;
    }

    function addDays(day, n) {
        const date = new Date(`${day}T00:00:00Z`);
        date.setUTCDate(date.getUTCDate() + n);
        return date.toISOString().slice(0, 10);
    }

    // The days a timing covers, as { kind, from, to } ('open' | 'closing' | 'opening'), or null when
    // there is no timing or no today to work it out from. Days are 'YYYY-MM-DD', so comparing them as text
    // compares them as dates.
    function timingWindow(timing, today) {
        if (!timing) return null;
        if (timing.from) return { kind: 'open', from: timing.from, to: timing.to || timing.from };
        if (!validDay(today)) return null;
        switch (timing.pick) {
            case 'today': return { kind: 'open', from: today, to: today };
            case 'week': return { kind: 'open', from: today, to: addDays(today, 6) };
            case 'weekend': {
                const weekday = new Date(`${today}T00:00:00Z`).getUTCDay();          // 0 Sunday ... 6 Saturday
                const saturday = weekday === 6 ? today : weekday === 0 ? addDays(today, -1) : addDays(today, 6 - weekday);
                return { kind: 'open', from: saturday < today ? today : saturday, to: addDays(saturday, 1) };
            }
            case 'closing': return { kind: 'closing', from: today, to: addDays(today, SOON_DAYS) };
            case 'opening': return { kind: 'opening', from: addDays(today, 1), to: addDays(today, SOON_DAYS) };
            default: return null;
        }
    }

    // Does a row's run fit the window? `row` has bucket, start and end ('YYYY-MM-DD' or null).
    //  - closing / opening look at the one date that matters (the end / the start);
    //  - otherwise it is open if its run overlaps the window. A show with no end date is open from its start
    //    on, and one with no dates at all (a long-running display) is open if it is on view now and the
    //    window does not lie wholly in the past. A past show with no end date is not known to be open.
    function timingMatches(row, window, today) {
        if (!window) return true;
        if (window.kind === 'closing') return row.bucket === 'current' && !!row.end && row.end >= window.from && row.end <= window.to;
        if (window.kind === 'opening') return row.bucket === 'future' && !!row.start && row.start >= window.from && row.start <= window.to;
        if (row.start && row.start > window.to) return false;
        if (row.end && row.end < window.from) return false;
        if (!row.start && !row.end) return (row.bucket === 'current' || row.bucket === 'ongoing') && window.to >= today;
        if (!row.end && row.bucket === 'past') return false;
        return true;
    }

    // "Dec 15, 2026" / "Dec 15-20, 2026" / "Dec 28 - Jan 3, 2027" for the pill and the result count
    function formatDay(day, withYear = true) {
        const options = { month: 'short', day: 'numeric', timeZone: 'UTC' };
        if (withYear) options.year = 'numeric';
        return new Intl.DateTimeFormat('en-US', options).format(new Date(`${day}T00:00:00Z`));
    }

    function describeTiming(timing) {
        if (!timing) return '';
        if (!timing.from) return TIMING_LABELS[timing.pick] ? TIMING_LABELS[timing.pick].toLowerCase() : '';
        const to = timing.to || timing.from;
        if (to === timing.from) return `open ${formatDay(timing.from)}`;
        const sameYear = timing.from.slice(0, 4) === to.slice(0, 4);
        return `open ${formatDay(timing.from, !sameYear)} \u2013 ${formatDay(to)}`;
    }

    // Areas of a region (the Bay Area only for now), found from the city in a venue's address. Every venue
    // address needs a city that is listed here: tests/filterState.test.js checks the real venues, so a new
    // venue in a new town fails there until the town is added.
    const AREAS = {
        sf: [
            { id: 'san-francisco', label: 'San Francisco', cities: ['San Francisco'] },
            { id: 'east-bay', label: 'East Bay', cities: [
                'Oakland', 'Berkeley', 'Albany', 'El Cerrito', 'Richmond', 'Emeryville', 'Alameda', 'Piedmont',
                'San Leandro', 'Hayward', 'Walnut Creek', 'Orinda', 'Lafayette', 'Pleasanton', 'Fremont'] },
            // The Peninsula is San Mateo County, with Palo Alto and Stanford (in Santa Clara County, but
            // the classic Peninsula); the South Bay is the rest of Santa Clara County
            { id: 'peninsula', label: 'Peninsula', cities: [
                'Palo Alto', 'Stanford', 'Menlo Park', 'Pacifica', 'Daly City', 'South San Francisco', 'San Bruno',
                'Millbrae', 'Burlingame', 'San Mateo', 'Foster City', 'Belmont', 'San Carlos', 'Redwood City',
                'Atherton', 'Woodside', 'Half Moon Bay'] },
            { id: 'south-bay', label: 'South Bay', cities: [
                'San Jose', 'Santa Clara', 'Sunnyvale', 'Mountain View', 'Los Altos', 'Cupertino', 'Saratoga',
                'Campbell', 'Los Gatos', 'Milpitas', 'Morgan Hill', 'Gilroy'] },
            { id: 'north-bay', label: 'North Bay', cities: [
                'San Rafael', 'Sausalito', 'Napa', 'Sonoma', 'Mill Valley', 'Novato', 'Petaluma', 'Santa Rosa',
                'Larkspur', 'Tiburon', 'Fairfax', 'San Anselmo', 'Belvedere', 'Point Reyes Station', 'Bolinas',
                'Healdsburg', 'Yountville', 'St. Helena', 'Calistoga', 'Sebastopol'] },
        ],
    };

    // The city of an address ("151 3rd St, San Francisco, CA 94103" -> "San Francisco"), or null
    function cityOf(address) {
        const matches = [...String(address || '').matchAll(/,\s*([^,]+?),\s*CA\b/g)];
        return matches.length ? matches[matches.length - 1][1].trim() : null;
    }

    // The area ids a venue is in, given its addresses (a venue with two addresses can be in two areas)
    function areasOfAddresses(region, addresses) {
        const areas = AREAS[region] || [];
        const found = [];
        for (const address of addresses || []) {
            const city = cityOf(address);
            const area = city && areas.find(a => a.cities.some(c => c.toLowerCase() === city.toLowerCase()));
            if (area && !found.includes(area.id)) found.push(area.id);
        }
        return found;
    }

    function areaIds() {
        return Object.values(AREAS).flat().map(area => area.id);
    }

    // The ids that are areas of this region (a ?area= link made for the Bay Area means nothing in Toronto, and
    // would show nothing there with no control to take it off)
    function areasOfRegion(region, ids) {
        const known = (AREAS[region] || []).map(area => area.id);
        return (ids || []).filter(id => known.includes(id));
    }

    // No area chosen shows everything; otherwise a row matches if it is in any chosen area
    function areasMatch(selected, rowAreas) {
        return selected.length === 0 || selected.some(id => (rowAreas || []).includes(id));
    }

    function defaultState(today = null) {
        return { q: '', phases: [...DEFAULT_PHASES], tags: [], timing: null, areas: [], view: DEFAULT_VIEW, today };
    }

    function isDefault(state) {
        return state.q === '' && samePhases(state.phases, DEFAULT_PHASES) && state.tags.length === 0
            && !state.timing && (state.areas || []).length === 0;
    }

    // "current, ongoing & future", "past", "all dates" - for the result count line
    function describePhases(phases) {
        if (phases.length === ALL_PHASES.length) return 'all dates';
        const names = phases.map(phase => PHASE_LABELS[phase].toLowerCase());
        return names.length > 1 ? `${names.slice(0, -1).join(', ')} & ${names[names.length - 1]}` : names[0];
    }

    // --- URL <-> state -------------------------------------------------------

    // ?q=text&phase=past&tags=photography,latinx&when=weekend&area=east-bay&view=map, where phase is one or more of
    // current, ongoing, future, past (e.g. phase=current,past). The older
    // ?search=name (used by the venue directory links) is still read as q.
    // A search with no explicit phase means "show everything for that venue"
    // (its shows may all be past), so it starts with every phase ticked.
    function parseUrl(search, today = null) {
        const params = new URLSearchParams(search || '');
        const q = (params.get('q') ?? params.get('search') ?? '').trim();
        const requested = normalizePhases((params.get('phase') || '').split(',').map(p => p.trim()));
        const phases = requested.length ? requested : (q ? [...ALL_PHASES] : [...DEFAULT_PHASES]);
        const tags = [...new Set((params.get('tags') || '').split(',').map(t => t.trim()).filter(Boolean))];
        const view = VIEWS.includes(params.get('view')) ? params.get('view') : DEFAULT_VIEW;
        const known = areaIds();
        const areas = [...new Set((params.get('area') || '').split(',').map(a => a.trim()).filter(a => known.includes(a)))];
        // ?when=weekend (a quick pick), or ?from=2026-12-15&to=2026-12-20 (a custom range; no "to" is one day)
        let timing = null;
        const pick = (params.get('when') || '').trim();
        const from = validDay((params.get('from') || '').trim());
        if (TIMING_PICKS.includes(pick)) {
            timing = { pick };
        } else if (from) {
            const to = validDay((params.get('to') || '').trim()) || from;
            timing = to < from ? { from: to, to: from } : { from, to };
        }
        return { q, phases, tags, timing, areas, view, today };
    }

    // Inverse of parseUrl: '' for the default view, else '?...'. The phase is
    // always written when there is a search, because parseUrl treats a search
    // with no phase as "every phase". ?view=map is written only for the map (the table is the default).
    function toQuery(state) {
        const params = new URLSearchParams();
        if (state.q) params.set('q', state.q);
        if (state.q || !samePhases(state.phases, DEFAULT_PHASES)) params.set('phase', state.phases.join(','));
        if (state.tags.length) params.set('tags', state.tags.join(','));
        if (state.timing && state.timing.pick) {
            params.set('when', state.timing.pick);
        } else if (state.timing && state.timing.from) {
            params.set('from', state.timing.from);
            if (state.timing.to && state.timing.to !== state.timing.from) params.set('to', state.timing.to);
        }
        if ((state.areas || []).length) params.set('area', state.areas.join(','));
        if (state.view === 'map') params.set('view', 'map');
        const query = params.toString().replace(/%2C/g, ',');
        return query ? `?${query}` : '';
    }

    // --- matching ------------------------------------------------------------

    // Lower case with the accents taken off, so "Art Mur" finds "Art Mûr", "francois" finds "François
    // Ghebaly" and "sakip" finds "Sakıp". Letters that don't split into a base letter plus an accent
    // (the Turkish dotless ı, ł, ø, æ, ß...) are mapped by hand. Both the search box text and the
    // table text go through this.
    const UNSPLIT_LETTERS = { 'ı': 'i', 'ł': 'l', 'ø': 'o', 'đ': 'd', 'ð': 'd', 'þ': 'th', 'æ': 'ae', 'œ': 'oe', 'ß': 'ss' };
    function foldText(text) {
        return String(text)
            .normalize('NFD')
            .replace(/[̀-ͯ]/g, '')
            .toLowerCase()
            .replace(/[ıłøđðþæœß]/g, ch => UNSPLIT_LETTERS[ch]);
    }

    // With every phase ticked nothing is excluded, including an event with no phase
    function phaseMatches(phases, eventPhase) {
        return phases.length === ALL_PHASES.length || phases.includes(eventPhase);
    }

    // Within a group any selected tag matches (photography OR painting); across
    // groups, and for tags outside every group, all must match (photography AND
    // latinx). `skipGroup` leaves one group out, to count what selecting a tag
    // in that group would show.
    function tagsMatch(selected, rowTags, skipGroup = null) {
        const byGroup = new Map();
        for (const tag of selected) {
            const group = groupOf(tag);
            if (group !== null && group === skipGroup) continue;
            const key = group === null ? `tag:${tag}` : group;
            if (!byGroup.has(key)) byGroup.set(key, []);
            byGroup.get(key).push(tag);
        }
        for (const tags of byGroup.values()) {
            if (!tags.some(tag => rowTags.includes(tag))) return false;
        }
        return true;
    }

    // `row` is { bucket, tags: [...], text: foldText(searchable text) } where bucket
    // is bucketOf(phase, ongoing).
    // `skipGroup` / `skipPhase` leave one filter out, to count what changing it would show.
    // `skipTiming` / `skipAreas` likewise. A chosen date replaces the When phases (see timingMatches).
    function rowMatches(row, state, { skipGroup = null, skipPhase = false, skipTiming = false, skipAreas = false } = {}) {
        if (state.q && !row.text.includes(foldText(state.q))) return false;
        const window = skipTiming ? null : timingWindow(state.timing, state.today);
        if (window) {
            if (!timingMatches(row, window, state.today)) return false;
        } else if (!skipPhase && !phaseMatches(state.phases, row.bucket)) {
            return false;
        }
        if (!skipAreas && !areasMatch(state.areas || [], row.areas)) return false;
        return tagsMatch(state.tags, row.tags, skipGroup);
    }

    // How many rows each tag would show: the rows matching every other filter
    // (including the other groups' selections and the When choice) that carry the tag.
    function countTags(rows, state) {
        const counts = {};
        for (const group of TAG_GROUPS) {
            const eligible = rows.filter(row => rowMatches(row, state, { skipGroup: group.id }));
            for (const tag of group.tags) {
                counts[tag] = eligible.filter(row => row.tags.includes(tag)).length;
            }
        }
        return counts;
    }

    // How many rows each When option would show, given every other filter
    function countPhases(rows, state) {
        const eligible = rows.filter(row => rowMatches(row, state, { skipPhase: true }));
        const counts = {};
        for (const phase of ALL_PHASES) {
            counts[phase] = eligible.filter(row => row.bucket === phase).length;
        }
        return counts;
    }

    // How many rows each Dates option would show, given every other filter ('any' is no date chosen,
    // so the When phases apply)
    function countTimings(rows, state) {
        const counts = { any: rows.filter(row => rowMatches(row, { ...state, timing: null })).length };
        for (const pick of TIMING_PICKS) {
            counts[pick] = rows.filter(row => rowMatches(row, { ...state, timing: { pick } })).length;
        }
        return counts;
    }

    // How many rows each area would show, given every other filter
    function countAreas(rows, state, region) {
        const eligible = rows.filter(row => rowMatches(row, state, { skipAreas: true }));
        const counts = {};
        for (const area of AREAS[region] || []) {
            counts[area.id] = eligible.filter(row => (row.areas || []).includes(area.id)).length;
        }
        return counts;
    }

    return {
        TAG_GROUPS, ALL_PHASES, DEFAULT_PHASES, PHASE_LABELS, PHASE_HINTS, VIEWS, DEFAULT_VIEW,
        TIMING_PICKS, TIMING_LABELS, TIMING_HINTS, SOON_DAYS, AREAS,
        groupOf, bucketOf, normalizePhases, defaultState, isDefault, describePhases, parseUrl, toQuery,
        validDay, addDays, timingWindow, timingMatches, describeTiming, cityOf, areasOfAddresses, areasOfRegion, areasMatch,
        foldText, phaseMatches, tagsMatch, rowMatches, countTags, countPhases, countTimings, countAreas,
    };
}));
