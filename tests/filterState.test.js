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
    const s = { q: 'Asian Art Museum', phases: ['current', 'past'], tags: ['photography', 'latinx', 'museum'], view: 'list' };
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
    const s = { q: 'Wattis', phases: ['current', 'ongoing', 'future'], tags: [], view: 'list' };
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
    const s = { q: 'Wattis', phases: ['past'], tags: ['photography'], view: 'map' };
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
    // immigrant, refugee and south-asian are real tags in the data that predate tags.html's current sections
    const undocumentedByDesign = new Set(['immigrant', 'refugee', 'south-asian']);
    const missing = fs_.TAG_GROUPS.flatMap(g => g.tags).filter(t => !listed.has(t) && !undocumentedByDesign.has(t));
    assert.deepStrictEqual(missing, []);
});
