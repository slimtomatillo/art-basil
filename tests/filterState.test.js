// Run with: node --test tests/
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const fs_ = require('../docs/filterState.js');

// A table row as the filters see it. `bucket` is current / ongoing / future / past.
const row = (bucket, tags = [], extra = {}) => ({ bucket, tags, text: 'show @ venue', ...extra });
const state = (overrides = {}) => ({ ...fs_.defaultState(), ...overrides });
const ALL = ['current', 'ongoing', 'future', 'past'];

test('default state is current + ongoing + future with no filters, and round-trips to an empty query', () => {
    const s = fs_.defaultState();
    assert.deepStrictEqual(s.phases, ['current', 'ongoing', 'future']);
    assert.strictEqual(fs_.isDefault(s), true);
    assert.strictEqual(fs_.toQuery(s), '');
    assert.deepStrictEqual(fs_.parseUrl(''), s);
});

test('an ongoing show is its own bucket, but only when it is a current one', () => {
    assert.strictEqual(fs_.bucketOf('current', true), 'ongoing');
    assert.strictEqual(fs_.bucketOf('current', false), 'current');
    assert.strictEqual(fs_.bucketOf('future', false), 'future');
    assert.strictEqual(fs_.bucketOf('past', false), 'past');
    assert.strictEqual(fs_.bucketOf('past', true), 'past');   // never counts as ongoing once it has ended
});

test('URL state round-trips', () => {
    const s = state({ q: 'Asian Art Museum', phases: ['current', 'past'], tags: ['photography', 'latinx', 'museum'] });
    const query = fs_.toQuery(s);
    assert.strictEqual(query, '?q=Asian+Art+Museum&phase=current,past&tags=photography,latinx,museum');
    assert.deepStrictEqual(fs_.parseUrl(query), s);
});

test('a single phase and all phases both round-trip', () => {
    assert.strictEqual(fs_.toQuery(state({ phases: ['past'] })), '?phase=past');
    assert.deepStrictEqual(fs_.parseUrl('?phase=past').phases, ['past']);
    assert.deepStrictEqual(fs_.parseUrl(fs_.toQuery(state({ phases: ALL }))).phases, ALL);
    assert.deepStrictEqual(fs_.parseUrl('?phase=ongoing').phases, ['ongoing']);
});

test('a search keeps its explicit phases through the URL, even the default ones', () => {
    const s = state({ q: 'Wattis', phases: ['current', 'ongoing', 'future'], tags: [] });
    assert.deepStrictEqual(fs_.parseUrl(fs_.toQuery(s)), s);
});

test('the list is the default view and only the map is written to the URL', () => {
    assert.strictEqual(fs_.defaultState().view, 'list');
    assert.strictEqual(fs_.toQuery(state({ view: 'list' })), '');
    assert.strictEqual(fs_.toQuery(state({ view: 'map' })), '?view=map');
    assert.strictEqual(fs_.parseUrl('?view=map').view, 'map');
    assert.strictEqual(fs_.parseUrl('').view, 'list');
});

test('?view=map keeps every other parameter, in both directions', () => {
    const s = state({ q: 'Wattis', phases: ['past'], tags: ['photography'], view: 'map' });
    const query = fs_.toQuery(s);
    assert.strictEqual(query, '?q=Wattis&phase=past&tags=photography&view=map');
    assert.deepStrictEqual(fs_.parseUrl(query), s);
    assert.deepStrictEqual(fs_.parseUrl('?tags=latinx&view=map').tags, ['latinx']);
    assert.deepStrictEqual(fs_.parseUrl('?tags=latinx&view=map').phases, ['current', 'ongoing', 'future']);
});

test('an unknown view, or the existing shared links, open on the list', () => {
    for (const search of ['?view=bogus', '?view=', '?view=MAP', '?search=SFMOMA', '?q=Wattis&phase=past', '?tags=free', '?phase=future']) {
        assert.strictEqual(fs_.parseUrl(search).view, 'list', search);
    }
});

test('the view is not a filter: isDefault ignores it', () => {
    assert.strictEqual(fs_.isDefault(state({ view: 'map' })), true);
    assert.strictEqual(fs_.isDefault(state({ view: 'map', q: 'x' })), false);
});

test('legacy ?search= (venue directory links) is read as q and ticks every phase', () => {
    const s = fs_.parseUrl('?search=SFMOMA');
    assert.strictEqual(s.q, 'SFMOMA');
    assert.deepStrictEqual(s.phases, ALL);
});

test('bad or missing URL values fall back to defaults; phases are ordered and de-duplicated', () => {
    assert.deepStrictEqual(fs_.parseUrl('?phase=bogus').phases, ['current', 'ongoing', 'future']);
    assert.deepStrictEqual(fs_.parseUrl('?phase=past,current,past').phases, ['current', 'past']);
    assert.deepStrictEqual(fs_.parseUrl('?tags=,photography,,photography').tags, ['photography']);
});

test('phases: matches ticked buckets only; ticking all shows everything, even an event with no phase', () => {
    const defaults = ['current', 'ongoing', 'future'];
    assert.ok(fs_.phaseMatches(defaults, 'current'));
    assert.ok(fs_.phaseMatches(defaults, 'ongoing'));
    assert.ok(fs_.phaseMatches(defaults, 'future'));
    assert.ok(!fs_.phaseMatches(defaults, 'past'));
    assert.ok(!fs_.phaseMatches(['current'], 'ongoing'));
    assert.ok(!fs_.phaseMatches(defaults, null));
    assert.ok(fs_.phaseMatches(ALL, null));
});

test('ongoing can be hidden by unticking it, without touching current shows', () => {
    const withoutOngoing = state({ phases: ['current', 'future'] });
    assert.ok(fs_.rowMatches(row('current'), withoutOngoing));
    assert.ok(!fs_.rowMatches(row('ongoing'), withoutOngoing));
    assert.ok(fs_.rowMatches(row('ongoing'), state()));
});

test('phases are described for the result line', () => {
    assert.strictEqual(fs_.describePhases(['current', 'ongoing', 'future']), 'current, ongoing & future');
    assert.strictEqual(fs_.describePhases(['current', 'future']), 'current & future');
    assert.strictEqual(fs_.describePhases(['past']), 'past');
    assert.strictEqual(fs_.describePhases(ALL), 'all dates');
});

test('tags: OR within a group, AND across groups', () => {
    const photo = row('current', ['photography']);
    const paint = row('current', ['painting', 'latinx']);
    const both = row('current', ['photography', 'latinx']);
    const none = row('current', ['sculpture']);
    assert.ok(fs_.tagsMatch(['photography', 'painting'], photo.tags));
    assert.ok(fs_.tagsMatch(['photography', 'painting'], paint.tags));
    assert.ok(!fs_.tagsMatch(['photography', 'painting'], none.tags));
    assert.ok(fs_.tagsMatch(['photography', 'latinx'], both.tags));
    assert.ok(!fs_.tagsMatch(['photography', 'latinx'], photo.tags));
    assert.ok(!fs_.tagsMatch(['photography', 'latinx'], paint.tags));
});

test('tags outside every group (e.g. museum) must each match', () => {
    assert.ok(fs_.tagsMatch(['museum'], ['museum', 'exhibition']));
    assert.ok(!fs_.tagsMatch(['museum', 'gallery'], ['museum']));
    assert.ok(!fs_.tagsMatch(['museum', 'photography'], ['photography']));
});

test('search matches text case-insensitively', () => {
    const r = row('current', [], { text: 'monet at the legion of honor' });
    assert.ok(fs_.rowMatches(r, state({ q: 'LEGION' })));
    assert.ok(!fs_.rowMatches(r, state({ q: 'sfmoma' })));
});

test('foldText lowers case and takes accents off, including letters that do not split', () => {
    assert.strictEqual(fs_.foldText('Art Mûr'), 'art mur');
    assert.strictEqual(fs_.foldText('François Ghebaly'), 'francois ghebaly');
    assert.strictEqual(fs_.foldText('Sakıp Sabancı Müzesi'), 'sakip sabanci muzesi');
    assert.strictEqual(fs_.foldText('İstanbul Şişli'), 'istanbul sisli');
    assert.strictEqual(fs_.foldText('Sprüth Magers, Ørsted, Łódź, Æther, Straße'), 'spruth magers, orsted, lodz, aether, strasse');
    assert.strictEqual(fs_.foldText('plain text'), 'plain text');
});

test('search finds accented names typed without accents, and the other way round', () => {
    const artMur = row('current', [], { text: fs_.foldText('Some Show @ Art Mûr') });
    assert.ok(fs_.rowMatches(artMur, state({ q: 'Art Mur' })));
    assert.ok(fs_.rowMatches(artMur, state({ q: 'art mûr' })));
    assert.ok(fs_.rowMatches(artMur, state({ q: 'ART MÛR' })));
    assert.ok(!fs_.rowMatches(artMur, state({ q: 'Art Murray' })));
    const ghebaly = row('current', [], { text: fs_.foldText('Show @ François Ghebaly') });
    assert.ok(fs_.rowMatches(ghebaly, state({ q: 'francois' })));
    const sakip = row('current', [], { text: fs_.foldText('Show @ Sakıp Sabancı Museum') });
    assert.ok(fs_.rowMatches(sakip, state({ q: 'sakip sabanci' })));
});

test('tag counts show what ticking a tag would add, ignoring that tag\'s own group', () => {
    const rows = [
        row('current', ['photography', 'latinx']),
        row('current', ['painting', 'latinx']),
        row('ongoing', ['painting']),
        row('past', ['photography', 'latinx']),   // hidden by the default phases
    ];
    let counts = fs_.countTags(rows, state());
    assert.strictEqual(counts.photography, 1);
    assert.strictEqual(counts.painting, 2);
    assert.strictEqual(counts.latinx, 2);
    counts = fs_.countTags(rows, state({ tags: ['latinx'] }));
    assert.strictEqual(counts.photography, 1);
    assert.strictEqual(counts.painting, 1);
    assert.strictEqual(counts.latinx, 2);
    counts = fs_.countTags(rows, state({ tags: ['photography'] }));
    assert.strictEqual(counts.painting, 2);
    // ticking Past brings the past photography+latinx show into the counts
    counts = fs_.countTags(rows, state({ phases: ALL }));
    assert.strictEqual(counts.photography, 2);
});

test('phase counts show what ticking each When option would add, given the other filters', () => {
    const rows = [
        row('current', ['photography']),
        row('ongoing', ['painting']),
        row('ongoing', ['photography']),
        row('future', ['photography']),
        row('future', ['painting']),
        row('past', ['photography']),
        row('past', ['painting']),
        row('past', ['painting']),
    ];
    assert.deepStrictEqual(fs_.countPhases(rows, state()), { current: 1, ongoing: 2, future: 2, past: 3 });
    assert.deepStrictEqual(fs_.countPhases(rows, state({ tags: ['photography'] })), { current: 1, ongoing: 1, future: 1, past: 1 });
});

test('every panel tag is documented on tags.html', () => {
    const html = fs.readFileSync(path.join(__dirname, '..', 'docs', 'tags.html'), 'utf8');
    const listed = new Set([...html.matchAll(/list-group-item">([a-z-]+)</g)].map(m => m[1]));
    const missing = fs_.TAG_GROUPS.flatMap(g => g.tags).filter(t => !listed.has(t));
    assert.deepStrictEqual(missing, []);
});


// --- dates and areas (WEBSITE-94) ------------------------------------------------------------------

const venueAddresses = require('../docs/venueAddresses.js');
const TODAY = '2026-11-13';                                      // a Friday
const drow = (bucket, start, end, extra = {}) => ({ bucket, tags: [], text: 'show @ venue', start, end, areas: [], ...extra });
const when = (timing, overrides = {}) => state({ timing, today: TODAY, ...overrides });
const shows = (rows, st) => rows.filter(r => fs_.rowMatches(r, st));

test('quick picks work out their days from today, and a weekend picked on a weekend is what is left of it', () => {
    const win = (pick, today = TODAY) => fs_.timingWindow({ pick }, today);
    assert.deepStrictEqual(win('today'), { kind: 'open', from: '2026-11-13', to: '2026-11-13' });
    assert.deepStrictEqual(win('week'), { kind: 'open', from: '2026-11-13', to: '2026-11-19' });
    assert.deepStrictEqual(win('weekend'), { kind: 'open', from: '2026-11-14', to: '2026-11-15' });     // Friday: Sat+Sun
    assert.deepStrictEqual(win('weekend', '2026-11-14'), { kind: 'open', from: '2026-11-14', to: '2026-11-15' });   // Saturday
    assert.deepStrictEqual(win('weekend', '2026-11-15'), { kind: 'open', from: '2026-11-15', to: '2026-11-15' });   // Sunday: just today
    assert.deepStrictEqual(win('weekend', '2026-11-16'), { kind: 'open', from: '2026-11-21', to: '2026-11-22' });   // Monday: next
    assert.deepStrictEqual(win('closing'), { kind: 'closing', from: '2026-11-13', to: '2026-11-27' });
    assert.deepStrictEqual(win('opening'), { kind: 'opening', from: '2026-11-14', to: '2026-11-27' });
    assert.strictEqual(win('bogus'), null);
    assert.strictEqual(fs_.timingWindow({ pick: 'today' }, null), null);                  // no today: no window
    assert.strictEqual(fs_.timingWindow(null, TODAY), null);
    assert.deepStrictEqual(fs_.timingWindow({ from: '2026-12-15', to: '2026-12-20' }, null), { kind: 'open', from: '2026-12-15', to: '2026-12-20' });
    assert.strictEqual(fs_.addDays('2026-12-31', 1), '2027-01-01');
});

test('a show is open on a day if its run covers it; one with no end is open from its start; undated ones are open', () => {
    const rows = {
        runs: drow('current', '2026-10-01', '2026-12-31'),
        ended: drow('past', '2026-01-01', '2026-11-01'),
        notYet: drow('future', '2026-12-01', '2027-01-31'),
        openEnded: drow('ongoing', '2025-05-01', null),
        pastNoEnd: drow('past', '2025-05-01', null),
        endOnly: drow('current', null, '2026-11-20'),
        undated: drow('current', null, null),
        pastUndated: drow('past', null, null),
        startsToday: drow('current', '2026-11-13', '2026-11-30'),
    };
    const open = (day, extra) => Object.entries(rows).filter(([, r]) => fs_.rowMatches(r, when({ from: day, to: day }, extra))).map(([k]) => k);
    assert.deepStrictEqual(open('2026-11-13'), ['runs', 'openEnded', 'endOnly', 'undated', 'startsToday']);
    assert.deepStrictEqual(open('2026-12-15'), ['runs', 'notYet', 'openEnded', 'undated']);
    // a day in the past: what was open then, whatever it is now (a chosen date replaces the When phases)
    assert.deepStrictEqual(open('2026-06-01'), ['ended', 'openEnded', 'endOnly']);   // 'runs' had not opened; an end-only show is open until its end
    assert.deepStrictEqual(shows(Object.values(rows), when({ from: '2026-12-31', to: '2027-01-02' })).length, 4);
});

test('closing soon is a current show whose end falls in the next 14 days; opening soon, an upcoming one that starts then', () => {
    const rows = [
        drow('current', '2026-10-01', '2026-11-13'),     // 0 ends today
        drow('current', '2026-10-01', '2026-11-27'),     // 1 ends in 14 days
        drow('current', '2026-10-01', '2026-11-28'),     // 2 ends in 15 days
        drow('current', '2026-10-01', '2026-11-12'),     // 3 ended yesterday
        drow('ongoing', '2025-01-01', null),             // 4 no end
        drow('future', '2026-11-14', '2026-12-30'),      // 5 starts tomorrow
        drow('future', '2026-11-27', null),              // 6 starts in 14 days
        drow('future', '2026-11-28', null),              // 7 starts in 15 days
        drow('future', null, null),                      // 8 no date
    ];
    const idx = timing => rows.map((r, i) => fs_.rowMatches(r, when({ pick: timing })) ? i : -1).filter(i => i >= 0);
    assert.deepStrictEqual(idx('closing'), [0, 1]);
    assert.deepStrictEqual(idx('opening'), [5, 6]);
});

test('this weekend and the next 7 days', () => {
    const rows = [drow('current', '2026-10-01', '2026-11-14'), drow('current', '2026-10-01', '2026-11-13'), drow('future', '2026-11-15', '2026-12-01'),
                  drow('future', '2026-11-16', '2026-12-01'), drow('future', '2026-11-19', '2026-12-01'), drow('future', '2026-11-20', '2026-12-01')];
    const idx = pick => rows.map((r, i) => fs_.rowMatches(r, when({ pick })) ? i : -1).filter(i => i >= 0);
    assert.deepStrictEqual(idx('weekend'), [0, 2]);              // ends Saturday; opens Sunday
    assert.deepStrictEqual(idx('week'), [0, 1, 2, 3, 4]);        // up to Thursday the 19th
});

test('a chosen date replaces the When phases, and a timing needs a today to mean anything', () => {
    const past = drow('past', '2026-01-01', '2026-11-20');                  // a bucket that is not past by the dates
    const pastState = when({ from: '2026-11-15', to: '2026-11-15' }, { phases: ['current'] });
    assert.strictEqual(fs_.rowMatches(past, pastState), true);                 // phases are not applied
    assert.strictEqual(fs_.rowMatches(past, { ...pastState, timing: null }), false);
    assert.strictEqual(fs_.rowMatches(past, state({ timing: { pick: 'today' }, today: null, phases: ['current'] })), false);   // no window: phases apply
});

test('timings and areas round-trip through the URL; bad values are ignored', () => {
    for (const timing of [{ pick: 'weekend' }, { pick: 'closing' }, { from: '2026-12-15', to: '2026-12-20' }, { from: '2026-12-15', to: '2026-12-15' }]) {
        const s = state({ timing, areas: ['east-bay', 'north-bay'] });
        assert.deepStrictEqual(fs_.parseUrl(fs_.toQuery(s)), s, JSON.stringify(timing));
    }
    assert.strictEqual(fs_.toQuery(state({ timing: { pick: 'weekend' } })), '?when=weekend');
    assert.strictEqual(fs_.toQuery(state({ timing: { from: '2026-12-15', to: '2026-12-20' } })), '?from=2026-12-15&to=2026-12-20');
    assert.strictEqual(fs_.toQuery(state({ timing: { from: '2026-12-15', to: '2026-12-15' } })), '?from=2026-12-15');   // one day: no "to"
    assert.strictEqual(fs_.toQuery(state({ areas: ['east-bay'] })), '?area=east-bay');
    assert.deepStrictEqual(fs_.parseUrl('?from=2026-12-15').timing, { from: '2026-12-15', to: '2026-12-15' });
    assert.deepStrictEqual(fs_.parseUrl('?from=2026-12-20&to=2026-12-15').timing, { from: '2026-12-15', to: '2026-12-20' });     // swapped
    assert.deepStrictEqual(fs_.parseUrl('?from=2026-12-15&to=nonsense').timing, { from: '2026-12-15', to: '2026-12-15' });
    assert.deepStrictEqual(fs_.parseUrl('?when=weekend&from=2026-12-15').timing, { pick: 'weekend' });                             // a pick wins
    for (const bad of ['?when=bogus', '?from=2026-02-30', '?from=tomorrow', '?to=2026-12-15', '?from=2026-1-5', '?when=']) {
        assert.strictEqual(fs_.parseUrl(bad).timing, null, bad);
    }
    assert.deepStrictEqual(fs_.parseUrl('?area=east-bay,bogus,east-bay,north-bay').areas, ['east-bay', 'north-bay']);
    assert.deepStrictEqual(fs_.parseUrl('').areas, []);
    assert.strictEqual(fs_.parseUrl('?when=today', TODAY).today, TODAY);
});

test('a date or an area is a filter: the view is no longer the default, and the map keeps both', () => {
    assert.strictEqual(fs_.isDefault(state()), true);
    assert.strictEqual(fs_.isDefault(state({ timing: { pick: 'today' } })), false);
    assert.strictEqual(fs_.isDefault(state({ areas: ['east-bay'] })), false);
    assert.strictEqual(fs_.toQuery(state({ timing: { pick: 'week' }, areas: ['east-bay'], view: 'map' })), '?when=week&area=east-bay&view=map');
    assert.deepStrictEqual(fs_.defaultState('2026-11-13').today, '2026-11-13');
});

test('a chosen date is described for the pill and the count', () => {
    assert.strictEqual(fs_.describeTiming({ pick: 'weekend' }), 'open this weekend');
    assert.strictEqual(fs_.describeTiming({ pick: 'closing' }), 'closing soon');
    assert.strictEqual(fs_.describeTiming({ from: '2026-12-15', to: '2026-12-15' }), 'open Dec 15, 2026');
    assert.strictEqual(fs_.describeTiming({ from: '2026-12-15', to: '2026-12-20' }), 'open Dec 15 – Dec 20, 2026');
    assert.strictEqual(fs_.describeTiming({ from: '2026-12-28', to: '2027-01-03' }), 'open Dec 28, 2026 – Jan 3, 2027');
    assert.strictEqual(fs_.describeTiming(null), '');
});

test('areas come from the city in an address', () => {
    assert.strictEqual(fs_.cityOf('151 3rd St, San Francisco, CA 94103'), 'San Francisco');
    assert.strictEqual(fs_.cityOf('Building A, Fort Mason Center, San Francisco, CA 94123'), 'San Francisco');
    assert.strictEqual(fs_.cityOf('1 Somewhere, CA'), null);
    assert.strictEqual(fs_.cityOf(null), null);
    const areas = a => fs_.areasOfAddresses('sf', a);
    assert.deepStrictEqual(areas(['151 3rd St, San Francisco, CA 94103']), ['san-francisco']);
    assert.deepStrictEqual(areas(['2625 Durant Ave, Berkeley, CA 94720']), ['east-bay']);
    assert.deepStrictEqual(areas(['1 A St, oakland, CA', '2 B St, San Rafael, CA']), ['east-bay', 'north-bay']);   // two addresses, two areas
    // the Peninsula and the South Bay are different areas: Stanford and Palo Alto are the Peninsula
    assert.deepStrictEqual(areas(['328 Lomita Dr, Stanford, CA 94305']), ['peninsula']);
    assert.deepStrictEqual(areas(['1313 Newell Rd, Palo Alto, CA 94303']), ['peninsula']);
    assert.deepStrictEqual(areas(['1 Sanchez St, Pacifica, CA 94044']), ['peninsula']);
    assert.deepStrictEqual(areas(['110 S Market St, San Jose, CA 95113']), ['south-bay']);
    assert.deepStrictEqual(areas(['1 A St, Mountain View, CA']), ['south-bay']);
    assert.deepStrictEqual(areas(['1 A St, Stanford, CA', '2 B St, San Jose, CA']), ['peninsula', 'south-bay']);
    assert.deepStrictEqual(areas(['1 A St, Nowheresville, CA']), []);
    assert.deepStrictEqual(fs_.areasOfAddresses('tor', ['1 A St, Toronto, ON']), []);                                // Toronto and Montreal have no areas
});

test('Los Angeles areas come from the town, or for the city of Los Angeles from the ZIP code', () => {
    const areas = a => fs_.areasOfAddresses('la', a);
    assert.strictEqual(fs_.zipOf('5905 Wilshire Blvd, Los Angeles, CA 90036'), '90036');
    assert.strictEqual(fs_.zipOf('5905 Wilshire Blvd, Los Angeles, CA'), null);
    assert.strictEqual(fs_.zipOf('10899 Wilshire Blvd, Los Angeles, CA'), null);                                     // the street number is not a ZIP
    // the city of Los Angeles is split by ZIP
    assert.deepStrictEqual(areas(['5905 Wilshire Blvd, Los Angeles, CA 90036']), ['hollywood-mid-wilshire']);
    assert.deepStrictEqual(areas(['6750 Santa Monica Blvd, Los Angeles, CA 90038']), ['hollywood-mid-wilshire']);
    assert.deepStrictEqual(areas(['10899 Wilshire Blvd, Los Angeles, CA 90024']), ['westside']);
    assert.deepStrictEqual(areas(['1200 Getty Center Dr, Los Angeles, CA 90049']), ['westside']);
    assert.deepStrictEqual(areas(['250 S Grand Ave, Los Angeles, CA 90012']), ['downtown-south-la']);
    assert.deepStrictEqual(areas(['600 State Dr, Los Angeles, CA 90037']), ['downtown-south-la']);
    // the towns around it are placed by name, with or without a ZIP
    assert.deepStrictEqual(areas(['1639 18th St, Santa Monica, CA 90404']), ['westside']);
    assert.deepStrictEqual(areas(['10808 Culver Blvd, Culver City, CA']), ['westside']);
    assert.deepStrictEqual(areas(['456 N Camden Dr, Beverly Hills, CA 90210']), ['westside']);
    assert.deepStrictEqual(areas(['8980 Santa Monica Blvd, West Hollywood, CA 90069']), ['westside']);
    assert.deepStrictEqual(areas(['411 W Colorado Blvd, Pasadena, CA']), ['pasadena-sgv']);
    assert.deepStrictEqual(areas(['1151 Oxford Rd, San Marino, CA 91108']), ['pasadena-sgv']);
    assert.deepStrictEqual(areas(['1301 Avenida Cesar Chavez, Monterey Park, CA 91754']), ['pasadena-sgv']);
    assert.deepStrictEqual(areas(['628 Alamitos Ave, Long Beach, CA 90802']), ['downtown-south-la']);               // too small to stand alone
    // a venue with two addresses can be in two areas (Francois Ghebaly)
    assert.deepStrictEqual(areas(['2245 E Washington Blvd, Los Angeles, CA 90021', '417 N Camden Dr, Beverly Hills, CA 90210']),
        ['downtown-south-la', 'westside']);
    // a Los Angeles address with no ZIP cannot be placed, which is why every address needs one
    assert.deepStrictEqual(areas(['5905 Wilshire Blvd, Los Angeles, CA']), []);
    assert.deepStrictEqual(areas(['1 A St, Los Angeles, CA 99999']), []);
    // other regions' areas do not apply here, and these do not apply elsewhere
    assert.deepStrictEqual(fs_.areasOfRegion('la', ['westside', 'east-bay', 'kadikoy']), ['westside']);
    assert.deepStrictEqual(fs_.areasOfRegion('sf', ['westside']), []);
    assert.deepStrictEqual(fs_.areasOfAddresses('sf', ['5905 Wilshire Blvd, Los Angeles, CA 90036']), []);
});

test('every real Los Angeles venue address is in an area, so a venue with an address we cannot place fails here', () => {
    const venues = JSON.parse(fs.readFileSync(path.join(__dirname, '../docs/data/la_venues.json'), 'utf8'));
    const unplaced = [];
    const noZip = [];
    for (const [name, value] of Object.entries(venues)) {
        for (const { address } of venueAddresses.normalize(value)) {
            if (fs_.areasOfAddresses('la', [address]).length === 0) unplaced.push(`${name}: ${address}`);
            if (!fs_.zipOf(address)) noZip.push(`${name}: ${address}`);
        }
    }
    assert.deepStrictEqual(unplaced, [], 'give the address a ZIP code, or add the town or ZIP to AREAS.la in docs/filterState.js');
    // the geocoder can put an address with no ZIP on another city's street of the same name (WEBSITE-110)
    assert.deepStrictEqual(noZip, [], 'add the ZIP code to the address in docs/data/la_venues.json');
});

test('only the areas of the region count, so a Bay Area link opened elsewhere cannot hide everything', () => {
    assert.deepStrictEqual(fs_.areasOfRegion('sf', ['east-bay', 'bogus', 'north-bay']), ['east-bay', 'north-bay']);
    assert.deepStrictEqual(fs_.areasOfRegion('tor', ['east-bay']), []);
    assert.deepStrictEqual(fs_.areasOfRegion('ist', undefined), []);
});

test('an area filter shows a row in any chosen area, and counts what each area would show', () => {
    const rows = [drow('current', null, null, { areas: ['san-francisco'] }), drow('current', null, null, { areas: ['east-bay'] }),
                  drow('current', null, null, { areas: ['east-bay', 'north-bay'] }), drow('past', null, null, { areas: ['east-bay'] }), drow('current', null, null)];
    assert.strictEqual(shows(rows, state({ areas: [] })).length, 4);
    assert.strictEqual(shows(rows, state({ areas: ['east-bay'] })).length, 2);
    assert.strictEqual(shows(rows, state({ areas: ['east-bay', 'san-francisco'] })).length, 3);
    assert.strictEqual(shows(rows, state({ areas: ['north-bay'] })).length, 1);
    assert.deepStrictEqual(fs_.countAreas(rows, state({ areas: ['east-bay'] }), 'sf'),
        { 'san-francisco': 1, 'east-bay': 2, peninsula: 0, 'south-bay': 0, 'north-bay': 1 });
    assert.deepStrictEqual(fs_.countAreas(rows, state(), 'tor'), {});
});

test('counts for each Dates option follow the other filters', () => {
    const rows = [drow('current', '2026-10-01', '2026-11-20', { tags: ['free'] }), drow('current', '2026-10-01', '2026-12-31'), drow('future', '2026-11-20', '2026-12-31', { tags: ['free'] })];
    const base = state({ today: TODAY });
    assert.deepStrictEqual(fs_.countTimings(rows, base), { any: 3, today: 2, weekend: 2, week: 2, closing: 1, opening: 1 });
    assert.deepStrictEqual(fs_.countTimings(rows, { ...base, tags: ['free'] }), { any: 2, today: 1, weekend: 1, week: 1, closing: 1, opening: 1 });
});

test('every real Bay Area venue address is in an area, so a venue in a new town fails here until the town is added', () => {
    const venues = JSON.parse(fs.readFileSync(path.join(__dirname, '../docs/data/sf_venues.json'), 'utf8'));
    const unplaced = [];
    for (const [name, value] of Object.entries(venues)) {
        const addresses = venueAddresses.normalize(value).map(entry => entry.address);
        if (fs_.areasOfAddresses('sf', addresses).length === 0) unplaced.push(`${name}: ${addresses.join(' | ')}`);
    }
    assert.deepStrictEqual(unplaced, [], 'add the town to AREAS.sf in docs/filterState.js');
    // no town sits in two areas
    const seen = new Map();
    for (const area of fs_.AREAS.sf) {
        for (const city of area.cities) {
            assert.ok(!seen.has(city.toLowerCase()), `${city} is in two areas`);
            seen.set(city.toLowerCase(), area.id);
        }
    }
});

test('Istanbul areas are districts, found from a part of the address, so Kadikoy and Uskudar are their own areas', () => {
    const areas = a => fs_.areasOfAddresses('ist', a);
    // real addresses: the district is a comma-separated part, with or without a postcode in front
    assert.deepStrictEqual(areas(['Kılıç Ali Paşa, Tophane İskele Cd. No:1/1, 34433 Beyoğlu, Istanbul, Türkiye']), ['beyoglu']);
    assert.deepStrictEqual(areas(['İstiklal Caddesi No:136, Beyoğlu, 34430 Istanbul, Türkiye']), ['beyoglu']);
    assert.deepStrictEqual(areas(['Dolapdere Caddesi No:1, 34384 Şişli, Istanbul, Türkiye']), ['sisli']);
    assert.deepStrictEqual(areas(['Baltalimanı Hisar Caddesi, Perili Köşk No:5, 34470 Rumelihisarı, Sarıyer, Istanbul, Türkiye']), ['sariyer']);
    // places not added yet: the Asian side, each district on its own
    assert.deepStrictEqual(areas(['Caferağa, Moda Cd. No:1, 34710 Kadıköy, Istanbul, Türkiye']), ['kadikoy']);
    assert.deepStrictEqual(areas(['Bağlarbaşı, Çamlıca Cd. No:2, 34662 Üsküdar, Istanbul, Türkiye']), ['uskudar']);
    assert.deepStrictEqual(areas(['Moda Caddesi 1, Kadıköy/İstanbul']), ['kadikoy']);                                // a slash
    assert.deepStrictEqual(areas(['Moda Caddesi 1, Kadikoy, Istanbul', 'Cami Sk. 2, uskudar, Istanbul']), ['kadikoy', 'uskudar']);   // accents and case ignored, two addresses
    // only a whole part counts: a street named for another district does not put the venue there
    assert.deepStrictEqual(areas(['Kadıköy Caddesi No:5, Beyoğlu, Istanbul, Türkiye']), ['beyoglu']);
    assert.deepStrictEqual(areas(['1 A St, Istanbul, Türkiye']), []);
    assert.deepStrictEqual(fs_.areasOfRegion('ist', ['kadikoy', 'east-bay', 'uskudar']), ['kadikoy', 'uskudar']);
    assert.deepStrictEqual(fs_.areasOfRegion('sf', ['kadikoy']), []);
});

test('every real Istanbul venue address is in a district area, so a venue in a new district fails here until it is added', () => {
    const venues = JSON.parse(fs.readFileSync(path.join(__dirname, '../docs/data/ist_venues.json'), 'utf8'));
    const unplaced = [];
    for (const [name, value] of Object.entries(venues)) {
        const addresses = venueAddresses.normalize(value).map(entry => entry.address);
        if (fs_.areasOfAddresses('ist', addresses).length === 0) unplaced.push(`${name}: ${addresses.join(' | ')}`);
    }
    assert.deepStrictEqual(unplaced, [], 'add the district to AREAS.ist in docs/filterState.js');
});

test('no town, ZIP or district is in two areas of a region, and every area id is unique', () => {
    const ids = new Set();
    for (const [region, areas] of Object.entries(fs_.AREAS)) {
        const seen = new Map();
        for (const area of areas) {
            assert.ok(!ids.has(area.id), `${area.id} is used twice`);
            ids.add(area.id);
            for (const place of [...(area.cities || []), ...(area.zips || []), ...(area.districts || [])]) {
                const key = fs_.foldText(place);
                assert.ok(!seen.has(key), `${region}: ${place} is in two areas`);
                seen.set(key, area.id);
            }
        }
    }
});

// --- one venue's shows (WEBSITE-111) ---------------------------------------------------------------

test('a venue is in the URL, and with no phase it shows every phase, like a search', () => {
    const s = fs_.parseUrl('?venue=The%20Broad');
    assert.strictEqual(s.venue, 'The Broad');
    assert.deepStrictEqual(s.phases, ALL);
    // the phase is always written beside a venue, so the link reads back the same
    const written = fs_.toQuery(state({ venue: 'The Broad', phases: ['current', 'ongoing', 'future'] }));
    assert.strictEqual(written, '?venue=The+Broad&phase=current,ongoing,future');
    assert.deepStrictEqual(fs_.parseUrl(written), state({ venue: 'The Broad' }));
});

test('a venue combines with the other filters in the URL, and old ?search= and ?q= links still work', () => {
    const s = state({ venue: 'Asian Art Museum', phases: ['current'], tags: ['photography'], q: 'ink' });
    assert.deepStrictEqual(fs_.parseUrl(fs_.toQuery(s)), s);
    assert.strictEqual(fs_.parseUrl('?search=Pera').q, 'Pera');
    assert.strictEqual(fs_.parseUrl('?search=Pera').venue, '');
    assert.strictEqual(fs_.parseUrl('?q=Pera&phase=past').venue, '');
});

test('a venue is a filter: isDefault is false with one, and the default state has none', () => {
    assert.strictEqual(fs_.defaultState().venue, '');
    assert.strictEqual(fs_.isDefault(state({ venue: 'The Broad' })), false);
    assert.strictEqual(fs_.isDefault(state({ venue: '' })), true);
});

test('a venue matches on its whole name, not as text anywhere in the row', () => {
    const broad = row('current', [], { venue: 'The Broad', text: 'a broad survey @ the broad' });
    const other = row('current', [], { venue: 'Wattis Institute', text: 'a broad survey @ wattis institute' });
    const s = state({ venue: 'The Broad', phases: ALL });
    assert.strictEqual(fs_.rowMatches(broad, s), true);
    assert.strictEqual(fs_.rowMatches(other, s), false, 'a show that only says "broad" is not at The Broad');
    // a search for the same words would have found both
    assert.strictEqual(fs_.rowMatches(other, state({ q: 'broad', phases: ALL })), true);
});

test('a venue matches regardless of case and accents, and a short name is not matched inside a longer one', () => {
    const arter = row('current', [], { venue: 'Arter' });
    const kadikoy = row('current', [], { venue: 'Arter Kadıköy' });
    const mur = row('current', [], { venue: 'Art Mûr' });
    assert.strictEqual(fs_.rowMatches(arter, state({ venue: 'arter' })), true);
    assert.strictEqual(fs_.rowMatches(kadikoy, state({ venue: 'Arter' })), false);
    assert.strictEqual(fs_.rowMatches(mur, state({ venue: 'art mur' })), true);
    assert.strictEqual(fs_.rowMatches(row('current', [], {}), state({ venue: 'Arter' })), false, 'a row with no venue never matches');
});

test('a venue narrows along with the When phase, a tag and a search', () => {
    const r = row('past', ['photography'], { venue: 'SFMOMA', text: 'ansel adams @ sfmoma' });
    assert.strictEqual(fs_.rowMatches(r, state({ venue: 'SFMOMA', phases: ALL, tags: ['photography'], q: 'ansel' })), true);
    assert.strictEqual(fs_.rowMatches(r, state({ venue: 'SFMOMA' })), false, 'past is hidden by the default phases');
    assert.strictEqual(fs_.rowMatches(r, state({ venue: 'SFMOMA', phases: ALL, tags: ['painting'] })), false);
});

// --- venue suggestions in the search box (WEBSITE-112) ---------------------------------------------

const COUNTS = { 'Art Mûr': 4, 'Arter': 5, 'Arter Kadıköy': 2, 'Oakland Museum of California': 9, 'Museum of the African Diaspora': 3,
                 'Dictée Art & Exhibition': 1, 'Gallery 16': 0, 'The Broad': 12 };
const names = list => list.map(s => s.name);

test('suggestions need two letters, and ignore case and accents', () => {
    assert.deepStrictEqual(fs_.suggestVenues(COUNTS, ''), []);
    assert.deepStrictEqual(fs_.suggestVenues(COUNTS, 'a'), []);
    assert.deepStrictEqual(names(fs_.suggestVenues(COUNTS, 'ART MUR')), ['Art Mûr']);
    assert.deepStrictEqual(names(fs_.suggestVenues(COUNTS, 'dictee')), ['Dictée Art & Exhibition']);
    assert.deepStrictEqual(names(fs_.suggestVenues(COUNTS, 'kadikoy')), ['Arter Kadıköy']);
});

test('a venue is found by the start of its name or of any word in it, best first', () => {
    // "mus": a name that starts with it leads, even with fewer shows than one where it starts a later word
    assert.deepStrictEqual(names(fs_.suggestVenues(COUNTS, 'mus')), ['Museum of the African Diaspora', 'Oakland Museum of California']);
    // "ar": names that start with it come before ones where it starts a later word
    assert.deepStrictEqual(names(fs_.suggestVenues(COUNTS, 'ar')), ['Arter', 'Art Mûr', 'Arter Kadıköy', 'Dictée Art & Exhibition']);
    // the whole name beats a longer name that starts with it, even with fewer shows
    assert.deepStrictEqual(names(fs_.suggestVenues({ 'Arter': 1, 'Arter Kadıköy': 8 }, 'arter')), ['Arter', 'Arter Kadıköy']);
    // two words, and a word that is not the start of one
    assert.deepStrictEqual(names(fs_.suggestVenues(COUNTS, 'museum of c')), ['Oakland Museum of California']);
    assert.deepStrictEqual(names(fs_.suggestVenues(COUNTS, 'useum')), []);
});

test('suggestions leave out venues with no shows, and are limited', () => {
    assert.deepStrictEqual(names(fs_.suggestVenues(COUNTS, 'gallery')), [], 'Gallery 16 has no shows under the current filters');
    const many = Object.fromEntries(Array.from({ length: 20 }, (_, i) => [`Gallery ${String.fromCharCode(65 + i)}`, i + 1]));
    assert.strictEqual(fs_.suggestVenues(many, 'gal').length, 6);
    assert.strictEqual(fs_.suggestVenues(many, 'gal', 3).length, 3);
    assert.deepStrictEqual(fs_.suggestVenues(undefined, 'gal'), []);
    assert.deepStrictEqual(fs_.suggestVenues(COUNTS, 'the broad'), [{ name: 'The Broad', count: 12 }]);
});
