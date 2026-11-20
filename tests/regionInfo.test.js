// Run with: node --test tests/
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const RegionInfo = require('../docs/regionInfo.js');

const DOCS = path.join(__dirname, '../docs');
const info = JSON.parse(fs.readFileSync(path.join(DOCS, 'data/region_info.json'), 'utf8'));
const zones = JSON.parse(fs.readFileSync(path.join(DOCS, 'data/regions.json'), 'utf8'));

// ---- the real file ----

test('every region in region_info.json has a name, place, country, colour and map point', () => {
    assert.deepStrictEqual(RegionInfo.problems(info), []);
});

test('region_info.json and regions.json list the same regions', () => {
    assert.deepStrictEqual(Object.keys(info).sort(), Object.keys(zones).sort(),
        'A region has to be in both docs/data/region_info.json and docs/data/regions.json (see ADDING_A_REGION.md).');
});

test('every region has its pages, in the same colour as its entry', () => {
    for (const [code, region] of Object.entries(info)) {
        for (const page of ['index.html', 'venues.html']) {
            const file = path.join(DOCS, code, page);
            assert.ok(fs.existsSync(file), `docs/${code}/${page} is missing`);
            const colour = (fs.readFileSync(file, 'utf8').match(/--region-c:\s*(#[0-9a-fA-F]{6})/) || [])[1];
            assert.strictEqual((colour || '').toLowerCase(), region.colour.toLowerCase(),
                `docs/${code}/${page} uses a different colour from region_info.json`);
        }
    }
});

test('the home page and the 404 page only link to regions that exist', () => {
    for (const page of ['index.html', '404.html']) {
        const html = fs.readFileSync(path.join(DOCS, page), 'utf8');
        const nav = (html.match(/<nav class="region-blobs"[\s\S]*?<\/nav>/) || [''])[0];
        for (const match of nav.matchAll(/href="\/?([a-z]+)\/index\.html"/g)) {
            assert.ok(info[match[1]], `${page} links to "${match[1]}", which is not in region_info.json`);
        }
    }
});

// ---- the functions ----

test('placeLine gives "state, country", or just the country when there is no state', () => {
    assert.strictEqual(RegionInfo.placeLine(info.pdx), 'Oregon, USA');
    assert.strictEqual(RegionInfo.placeLine(info.mtl), 'Québec, Canada');
    assert.strictEqual(RegionInfo.placeLine(info.ist), 'Türkiye');
});

test('search ignores accents and capital letters', () => {
    assert.deepStrictEqual(RegionInfo.matchingCodes(info, 'MONTREAL'), ['mtl']);
    assert.deepStrictEqual(RegionInfo.matchingCodes(info, 'Montréal'), ['mtl']);
    assert.deepStrictEqual(RegionInfo.matchingCodes(info, 'quebec'), ['mtl']);
    assert.deepStrictEqual(RegionInfo.matchingCodes(info, 'turkiye'), ['ist']);
});

test('search knows country and nickname words', () => {
    assert.deepStrictEqual(RegionInfo.matchingCodes(info, 'turkey'), ['ist']);
    assert.deepStrictEqual(RegionInfo.matchingCodes(info, 'canada'), ['mtl', 'tor']);
    assert.deepStrictEqual(RegionInfo.matchingCodes(info, 'usa'), ['sf', 'la', 'nyc', 'pdx']);
    assert.deepStrictEqual(RegionInfo.matchingCodes(info, 'united states'), ['sf', 'la', 'nyc', 'pdx']);
    assert.deepStrictEqual(RegionInfo.matchingCodes(info, 'oregon'), ['pdx']);
    assert.deepStrictEqual(RegionInfo.matchingCodes(info, 'san francisco'), ['sf']);
    assert.deepStrictEqual(RegionInfo.matchingCodes(info, 'nyc'), ['nyc']);
});

test('search matches the start of words, and every typed word must match', () => {
    assert.deepStrictEqual(RegionInfo.matchingCodes(info, 'port'), ['pdx']);
    assert.deepStrictEqual(RegionInfo.matchingCodes(info, 'york'), ['nyc']);
    assert.deepStrictEqual(RegionInfo.matchingCodes(info, 'ork'), []);
    assert.deepStrictEqual(RegionInfo.matchingCodes(info, 'new york usa'), ['nyc']);
    assert.deepStrictEqual(RegionInfo.matchingCodes(info, 'new canada'), []);
});

test('an empty search matches every region, a search with nothing in it matches none', () => {
    assert.deepStrictEqual(RegionInfo.matchingCodes(info, ''), Object.keys(info));
    assert.deepStrictEqual(RegionInfo.matchingCodes(info, '   '), Object.keys(info));
    assert.deepStrictEqual(RegionInfo.matchingCodes(info, 'chicago'), []);
});

test('groupByCountry keeps the file order, and can be limited to some regions', () => {
    assert.deepStrictEqual(RegionInfo.groupByCountry(info), [
        { country: 'USA', codes: ['sf', 'la', 'nyc', 'pdx'] },
        { country: 'Canada', codes: ['mtl', 'tor'] },
        { country: 'Türkiye', codes: ['ist'] },
    ]);
    assert.deepStrictEqual(RegionInfo.groupByCountry(info, ['tor', 'ist']), [
        { country: 'Canada', codes: ['tor'] },
        { country: 'Türkiye', codes: ['ist'] },
    ]);
});

test('a region with no blob settings still gets a steady blob look', () => {
    assert.deepStrictEqual(RegionInfo.blobLook({}, 0), { shape: 'a', tilt: 1.8, width: 215, dur: 6.2 });
    assert.deepStrictEqual(RegionInfo.blobLook({}, 1), { shape: 'b', tilt: -1.8, width: 215, dur: 6.2 });
    assert.deepStrictEqual(RegionInfo.blobLook({ blob: { shape: 'c', tilt: 2, width: 300, dur: 5 } }, 0),
        { shape: 'c', tilt: 2, width: 300, dur: 5 });
});

test('problems names every region that is missing its place or country', () => {
    const broken = {
        ok: { name: 'A', label: 'A', place: '', country: 'X', colour: '#111111', lat: 1, lng: 2 },
        noCountry: { name: 'B', label: 'B', place: 'P', colour: '#111111', lat: 1, lng: 2 },
        noPlace: { name: 'C', label: 'C', country: 'X', colour: '#111111', lat: 1, lng: 2 },
        badColour: { name: 'D', label: 'D', place: '', country: 'X', colour: 'red', lat: 1, lng: 2 },
        noPoint: { name: 'E', label: 'E', place: '', country: 'X', colour: '#111111' },
    };
    const found = RegionInfo.problems(broken).join('\n');
    assert.match(found, /noCountry: "country" is missing/);
    assert.match(found, /noPlace: "place" is missing/);
    assert.match(found, /badColour: "colour"/);
    assert.match(found, /noPoint: "lat"/);
    assert.doesNotMatch(found, /^ok:/m);
});

test('load fetches the file once and shares it', async () => {
    let calls = 0;
    const fetchFn = async () => { calls += 1; return { ok: true, json: async () => ({ sf: {} }) }; };
    // The module remembers its one request, so load it in a fresh copy
    delete require.cache[require.resolve('../docs/regionInfo.js')];
    const fresh = require('../docs/regionInfo.js');
    const [a, b] = await Promise.all([fresh.load('x.json', fetchFn), fresh.load('x.json', fetchFn)]);
    assert.strictEqual(calls, 1);
    assert.deepStrictEqual(a, b);
});

test('load does not remember a failed request', async () => {
    delete require.cache[require.resolve('../docs/regionInfo.js')];
    const fresh = require('../docs/regionInfo.js');
    await assert.rejects(fresh.load('x.json', async () => ({ ok: false, status: 404 })));
    const result = await fresh.load('x.json', async () => ({ ok: true, json: async () => ({ pdx: {} }) }));
    assert.deepStrictEqual(result, { pdx: {} });
});
