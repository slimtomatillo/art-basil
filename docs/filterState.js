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

    // "upcoming" is current + future together (what a visitor usually wants).
    const PHASES = ['upcoming', 'current', 'future', 'past', 'all'];
    const DEFAULT_PHASE = 'upcoming';

    const PHASE_LABELS = {
        upcoming: 'Now & upcoming', current: 'Current', future: 'Future', past: 'Past', all: 'All',
    };

    function groupOf(tag) {
        const group = TAG_GROUPS.find(g => g.tags.includes(tag));
        return group ? group.id : null;
    }

    function defaultState() {
        return { q: '', phase: DEFAULT_PHASE, ongoing: true, tags: [] };
    }

    function isDefault(state) {
        return state.q === '' && state.phase === DEFAULT_PHASE && state.ongoing && state.tags.length === 0;
    }

    // --- URL <-> state -------------------------------------------------------

    // ?q=text&phase=past&tags=photography,latinx&ongoing=0. The older
    // ?search=name (used by the venue directory links) is still read as q.
    // A search with no explicit phase means "show everything for that venue"
    // (its shows may all be past), so it starts on "all".
    function parseUrl(search) {
        const params = new URLSearchParams(search || '');
        const q = (params.get('q') ?? params.get('search') ?? '').trim();
        const requestedPhase = params.get('phase');
        const phase = PHASES.includes(requestedPhase) ? requestedPhase : (q ? 'all' : DEFAULT_PHASE);
        const tags = [...new Set((params.get('tags') || '').split(',').map(t => t.trim()).filter(Boolean))];
        return { q, phase, ongoing: params.get('ongoing') !== '0', tags };
    }

    // Inverse of parseUrl: '' for the default view, else '?...'. The phase is
    // always written when there is a search, because parseUrl treats a search
    // with no phase as "all".
    function toQuery(state) {
        const params = new URLSearchParams();
        if (state.q) params.set('q', state.q);
        if (state.phase !== DEFAULT_PHASE || state.q) params.set('phase', state.phase);
        if (state.tags.length) params.set('tags', state.tags.join(','));
        if (!state.ongoing) params.set('ongoing', '0');
        const query = params.toString().replace(/%2C/g, ',');
        return query ? `?${query}` : '';
    }

    // --- matching ------------------------------------------------------------

    function phaseMatches(phase, eventPhase) {
        if (phase === 'all') return true;
        if (phase === 'upcoming') return eventPhase === 'current' || eventPhase === 'future';
        return eventPhase === phase;
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

    // `row` is { phase, ongoing, tags: [...], text: 'lowercased searchable text' }
    function rowMatches(row, state, skipGroup = null) {
        if (state.q && !row.text.includes(state.q.toLowerCase())) return false;
        if (!phaseMatches(state.phase, row.phase)) return false;
        if (!state.ongoing && row.ongoing) return false;
        return tagsMatch(state.tags, row.tags, skipGroup);
    }

    // How many rows each tag in the panel would show: the rows matching every
    // other filter (including the other groups' selections) that carry the tag.
    function countTags(rows, state) {
        const counts = {};
        for (const group of TAG_GROUPS) {
            const eligible = rows.filter(row => rowMatches(row, state, group.id));
            for (const tag of group.tags) {
                counts[tag] = eligible.filter(row => row.tags.includes(tag)).length;
            }
        }
        return counts;
    }

    return {
        TAG_GROUPS, PHASES, PHASE_LABELS, DEFAULT_PHASE,
        groupOf, defaultState, isDefault, parseUrl, toQuery,
        phaseMatches, tagsMatch, rowMatches, countTags,
    };
}));
