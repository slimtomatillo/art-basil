// Run with: node --test tests/
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const fs_ = require('../docs/filterState.js');

const row = (phase, tags, extra = {}) => ({ phase, ongoing: false, tags, text: 'show @ venue', ...extra });
const state = (overrides = {}) => ({ ...fs_.defaultState(), ...overrides });

test('default state is current + future with no filters, and round-trips to an empty query', () => {
    const s = fs_.defaultState();
    assert.deepStrictEqual(s.phases, ['current', 'future']);
    assert.strictEqual(fs_.isDefault(s), true);
    assert.strictEqual(fs_.toQuery(s), '');
    assert.deepStrictEqual(fs_.parseUrl(''), s);
});

test('URL state round-trips', () => {
    const s = { q: 'Asian Art Museum', phases: ['current', 'past'], ongoing: false, tags: ['photography', 'latinx', 'museum'] };
    const query = fs_.toQuery(s);
    assert.strictEqual(query, '?q=Asian+Art+Museum&phase=current,past&tags=photography,latinx,museum&ongoing=0');
    assert.deepStrictEqual(fs_.parseUrl(query), s);
});

test('a single phase and all phases both round-trip', () => {
    assert.strictEqual(fs_.toQuery(state({ phases: ['past'] })), '?phase=past');
    assert.deepStrictEqual(fs_.parseUrl('?phase=past').phases, ['past']);
    const all = state({ phases: ['current', 'future', 'past'] });
    assert.deepStrictEqual(fs_.parseUrl(fs_.toQuery(all)).phases, ['current', 'future', 'past']);
});

test('a search keeps its explicit phases through the URL, even the default ones', () => {
    const s = { q: 'Wattis', phases: ['current', 'future'], ongoing: true, tags: [] };
    assert.deepStrictEqual(fs_.parseUrl(fs_.toQuery(s)), s);
});

test('legacy ?search= (venue directory links) is read as q and ticks every phase', () => {
    const s = fs_.parseUrl('?search=SFMOMA');
    assert.strictEqual(s.q, 'SFMOMA');
    assert.deepStrictEqual(s.phases, ['current', 'future', 'past']);
});

test('bad or missing URL values fall back to defaults; phases are ordered and de-duplicated', () => {
    assert.deepStrictEqual(fs_.parseUrl('?phase=bogus').phases, ['current', 'future']);
    assert.deepStrictEqual(fs_.parseUrl('?phase=past,current,past').phases, ['current', 'past']);
    assert.deepStrictEqual(fs_.parseUrl('?tags=,photography,,photography').tags, ['photography']);
    assert.strictEqual(fs_.parseUrl('?ongoing=1').ongoing, true);
});

test('phases: matches ticked phases only; ticking all shows everything, even an event with no phase', () => {
    assert.ok(fs_.phaseMatches(['current', 'future'], 'current'));
    assert.ok(fs_.phaseMatches(['current', 'future'], 'future'));
    assert.ok(!fs_.phaseMatches(['current', 'future'], 'past'));
    assert.ok(fs_.phaseMatches(['past'], 'past'));
    assert.ok(!fs_.phaseMatches(['past'], 'current'));
    assert.ok(!fs_.phaseMatches(['current', 'future'], null));
    assert.ok(fs_.phaseMatches(['current', 'future', 'past'], null));
});

test('phases are described for the result line', () => {
    assert.strictEqual(fs_.describePhases(['current', 'future']), 'current & future');
    assert.strictEqual(fs_.describePhases(['past']), 'past');
    assert.strictEqual(fs_.describePhases(['current', 'future', 'past']), 'all dates');
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

test('ongoing shows are hidden only when "include ongoing" is off', () => {
    const ongoing = row('current', [], { ongoing: true });
    assert.ok(fs_.rowMatches(ongoing, state({ ongoing: true })));
    assert.ok(!fs_.rowMatches(ongoing, state({ ongoing: false })));
    assert.ok(fs_.rowMatches(row('current', []), state({ ongoing: false })));
});

test('search matches text case-insensitively', () => {
    const r = row('current', [], { text: 'monet at the legion of honor' });
    assert.ok(fs_.rowMatches(r, state({ q: 'LEGION' })));
    assert.ok(!fs_.rowMatches(r, state({ q: 'sfmoma' })));
});

test('tag counts show what ticking a tag would add, ignoring that tag\'s own group', () => {
    const rows = [
        row('current', ['photography', 'latinx']),
        row('current', ['painting', 'latinx']),
        row('current', ['painting']),
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
    counts = fs_.countTags(rows, state({ phases: ['current', 'future', 'past'] }));
    assert.strictEqual(counts.photography, 2);
});

test('phase counts show what ticking each When option would add, given the other filters', () => {
    const rows = [
        row('current', ['photography']),
        row('future', ['photography']),
        row('future', ['painting']),
        row('past', ['photography']),
        row('past', ['painting']),
        row('past', ['painting']),
    ];
    assert.deepStrictEqual(fs_.countPhases(rows, state()), { current: 1, future: 2, past: 3 });
    // with photography selected, only photography shows are counted
    assert.deepStrictEqual(fs_.countPhases(rows, state({ tags: ['photography'] })), { current: 1, future: 1, past: 1 });
});

test('every panel tag is documented on tags.html', () => {
    const html = fs.readFileSync(path.join(__dirname, '..', 'docs', 'tags.html'), 'utf8');
    const listed = new Set([...html.matchAll(/list-group-item">([a-z-]+)</g)].map(m => m[1]));
    // immigrant, refugee and south-asian are real tags in the data that predate tags.html's current sections
    const undocumentedByDesign = new Set(['immigrant', 'refugee', 'south-asian']);
    const missing = fs_.TAG_GROUPS.flatMap(g => g.tags).filter(t => !listed.has(t) && !undocumentedByDesign.has(t));
    assert.deepStrictEqual(missing, []);
});
