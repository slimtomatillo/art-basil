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
            'refugee', 'south-asian', 'woman-artist'] },
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

    function defaultState() {
        return { q: '', phases: [...DEFAULT_PHASES], tags: [] };
    }

    function isDefault(state) {
        return state.q === '' && samePhases(state.phases, DEFAULT_PHASES) && state.tags.length === 0;
    }

    // "current, ongoing & future", "past", "all dates" - for the result count line
    function describePhases(phases) {
        if (phases.length === ALL_PHASES.length) return 'all dates';
        const names = phases.map(phase => PHASE_LABELS[phase].toLowerCase());
        return names.length > 1 ? `${names.slice(0, -1).join(', ')} & ${names[names.length - 1]}` : names[0];
    }

    // --- URL <-> state -------------------------------------------------------

    // ?q=text&phase=past&tags=photography,latinx, where phase is one or more of
    // current, ongoing, future, past (e.g. phase=current,past). The older
    // ?search=name (used by the venue directory links) is still read as q.
    // A search with no explicit phase means "show everything for that venue"
    // (its shows may all be past), so it starts with every phase ticked.
    function parseUrl(search) {
        const params = new URLSearchParams(search || '');
        const q = (params.get('q') ?? params.get('search') ?? '').trim();
        const requested = normalizePhases((params.get('phase') || '').split(',').map(p => p.trim()));
        const phases = requested.length ? requested : (q ? [...ALL_PHASES] : [...DEFAULT_PHASES]);
        const tags = [...new Set((params.get('tags') || '').split(',').map(t => t.trim()).filter(Boolean))];
        return { q, phases, tags };
    }

    // Inverse of parseUrl: '' for the default view, else '?...'. The phase is
    // always written when there is a search, because parseUrl treats a search
    // with no phase as "every phase".
    function toQuery(state) {
        const params = new URLSearchParams();
        if (state.q) params.set('q', state.q);
        if (state.q || !samePhases(state.phases, DEFAULT_PHASES)) params.set('phase', state.phases.join(','));
        if (state.tags.length) params.set('tags', state.tags.join(','));
        const query = params.toString().replace(/%2C/g, ',');
        return query ? `?${query}` : '';
    }

    // --- matching ------------------------------------------------------------

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

    // `row` is { bucket, tags: [...], text: 'lowercased searchable text' } where bucket
    // is bucketOf(phase, ongoing).
    // `skipGroup` / `skipPhase` leave one filter out, to count what changing it would show.
    function rowMatches(row, state, { skipGroup = null, skipPhase = false } = {}) {
        if (state.q && !row.text.includes(state.q.toLowerCase())) return false;
        if (!skipPhase && !phaseMatches(state.phases, row.bucket)) return false;
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

    return {
        TAG_GROUPS, ALL_PHASES, DEFAULT_PHASES, PHASE_LABELS, PHASE_HINTS,
        groupOf, bucketOf, normalizePhases, defaultState, isDefault, describePhases, parseUrl, toQuery,
        phaseMatches, tagsMatch, rowMatches, countTags, countPhases,
    };
}));
