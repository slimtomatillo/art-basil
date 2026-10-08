// Run with: node --test tests/
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const fs_ = require('../docs/filterState.js');

const row = (phase, tags, extra = {}) => ({ phase, ongoing: false, tags, text: 'show @ venue', ...extra });

test('default state is "now & upcoming" with no filters, and round-trips to an empty query', () => {
    const state = fs_.defaultState();
    assert.strictEqual(fs_.isDefault(state), true);
    assert.strictEqual(fs_.toQuery(state), '');
    assert.deepStrictEqual(fs_.parseUrl(''), state);
});

test('URL state round-trips', () => {
    const state = { q: 'Asian Art Museum', phase: 'past', ongoing: false, tags: ['photography', 'latinx', 'museum'] };
    const query = fs_.toQuery(state);
    assert.strictEqual(query, '?q=Asian+Art+Museum&phase=past&tags=photography,latinx,museum&ongoing=0');
    assert.deepStrictEqual(fs_.parseUrl(query), state);
});

test('a search keeps its explicit phase through the URL, even "upcoming"', () => {
    const state = { q: 'Wattis', phase: 'upcoming', ongoing: true, tags: [] };
    assert.deepStrictEqual(fs_.parseUrl(fs_.toQuery(state)), state);
});

test('legacy ?search= (venue directory links) is read as q and shows every phase', () => {
    const state = fs_.parseUrl('?search=SFMOMA');
    assert.strictEqual(state.q, 'SFMOMA');
    assert.strictEqual(state.phase, 'all');
});

test('bad or missing URL values fall back to defaults', () => {
    assert.strictEqual(fs_.parseUrl('?phase=bogus').phase, 'upcoming');
    assert.deepStrictEqual(fs_.parseUrl('?tags=,photography,,photography').tags, ['photography']);
    assert.strictEqual(fs_.parseUrl('?ongoing=1').ongoing, true);
});

test('phase "upcoming" is current + future; "all" is everything', () => {
    assert.ok(fs_.phaseMatches('upcoming', 'current'));
    assert.ok(fs_.phaseMatches('upcoming', 'future'));
    assert.ok(!fs_.phaseMatches('upcoming', 'past'));
    assert.ok(fs_.phaseMatches('all', 'past'));
    assert.ok(!fs_.phaseMatches('current', 'future'));
});

test('tags: OR within a group, AND across groups', () => {
    const photo = row('current', ['photography']);
    const paint = row('current', ['painting', 'latinx']);
    const both = row('current', ['photography', 'latinx']);
    const none = row('current', ['sculpture']);
    // photography OR painting (same group)
    assert.ok(fs_.tagsMatch(['photography', 'painting'], photo.tags));
    assert.ok(fs_.tagsMatch(['photography', 'painting'], paint.tags));
    assert.ok(!fs_.tagsMatch(['photography', 'painting'], none.tags));
    // medium AND theme (different groups)
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
    assert.ok(fs_.rowMatches(ongoing, { ...fs_.defaultState(), ongoing: true }));
    assert.ok(!fs_.rowMatches(ongoing, { ...fs_.defaultState(), ongoing: false }));
    assert.ok(fs_.rowMatches(row('current', []), { ...fs_.defaultState(), ongoing: false }));
});

test('search matches text case-insensitively', () => {
    const r = row('current', [], { text: 'monet at the legion of honor' });
    assert.ok(fs_.rowMatches(r, { ...fs_.defaultState(), q: 'LEGION' }));
    assert.ok(!fs_.rowMatches(r, { ...fs_.defaultState(), q: 'sfmoma' }));
});

test('counts show what selecting a tag would add, ignoring that tag\'s own group', () => {
    const rows = [
        row('current', ['photography', 'latinx']),
        row('current', ['painting', 'latinx']),
        row('current', ['painting']),
        row('past', ['photography', 'latinx']),   // hidden by the default phase
    ];
    // nothing selected: current rows only
    let counts = fs_.countTags(rows, fs_.defaultState());
    assert.strictEqual(counts.photography, 1);
    assert.strictEqual(counts.painting, 2);
    assert.strictEqual(counts.latinx, 2);
    // latinx selected: medium counts are within latinx rows; latinx itself is not narrowed by itself
    counts = fs_.countTags(rows, { ...fs_.defaultState(), tags: ['latinx'] });
    assert.strictEqual(counts.photography, 1);
    assert.strictEqual(counts.painting, 1);
    assert.strictEqual(counts.latinx, 2);
    // photography selected: other medium tags still show what they would add (OR within the group)
    counts = fs_.countTags(rows, { ...fs_.defaultState(), tags: ['photography'] });
    assert.strictEqual(counts.painting, 2);
});

test('every panel tag is documented on tags.html', () => {
    const html = fs.readFileSync(path.join(__dirname, '..', 'docs', 'tags.html'), 'utf8');
    const listed = new Set([...html.matchAll(/list-group-item">([a-z-]+)</g)].map(m => m[1]));
    // immigrant, refugee and south-asian are real tags in the data that predate tags.html's current sections
    const undocumentedByDesign = new Set(['immigrant', 'refugee', 'south-asian']);
    const missing = fs_.TAG_GROUPS.flatMap(g => g.tags).filter(t => !listed.has(t) && !undocumentedByDesign.has(t));
    assert.deepStrictEqual(missing, []);
});
