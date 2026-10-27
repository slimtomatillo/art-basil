// Run with: node --test tests/
const test = require('node:test');
const assert = require('node:assert');
const w = require('../docs/web3forms.js');

const fakeResponse = (status, json) => ({ status, json: async () => { if (json === undefined) throw new Error('no json'); return json; } });

test('the payload carries the key, subject and sender, labels fields, and drops empty ones', () => {
    const p = w.buildPayload(
        { 'Event title': '  Numina  ', 'Venue': 'Art Works Downtown', 'Notes': '   ', 'Price': undefined, 'Other links': null, 'email': 'a@b.co' },
        { accessKey: 'KEY', subject: 'New event' });
    assert.deepStrictEqual(p, { access_key: 'KEY', subject: 'New event', from_name: 'Art Basil website', 'Event title': 'Numina', Venue: 'Art Works Downtown', email: 'a@b.co' });
});

test('a 200 with a message is a success; other statuses and success:false are failures', () => {
    assert.deepStrictEqual(w.interpretResponse(200, { success: true, message: 'ok' }), { ok: true, message: 'ok' });
    assert.strictEqual(w.interpretResponse(200, { message: 'sent' }).ok, true, 'no success field still counts');
    assert.strictEqual(w.interpretResponse(200, null).ok, true);
    assert.strictEqual(w.interpretResponse(200, { success: false, message: 'bad key' }).ok, false);
    assert.strictEqual(w.interpretResponse(400, { message: 'Invalid key' }).ok, false);
    assert.strictEqual(w.interpretResponse(429, null).ok, false);
    assert.strictEqual(w.interpretResponse(500, { message: 'x' }).message, 'x');
});

test('bots are caught by the hidden checkbox or by being too fast', () => {
    assert.strictEqual(w.looksLikeBot({ botcheck: true, elapsedMs: 60000 }), true);
    assert.strictEqual(w.looksLikeBot({ botcheck: false, elapsedMs: 500 }), true);
    assert.strictEqual(w.looksLikeBot({ botcheck: false, elapsedMs: w.MIN_FILL_MS }), false);
    assert.strictEqual(w.looksLikeBot({ botcheck: false, elapsedMs: 30000 }), false);
});

test('the email fallback is a mailto: link to the site address with the labelled fields in the body', () => {
    const link = w.mailtoFallback({ 'Event title': 'A & B', Venue: '', Region: 'LA' }, 'Art Basil: new event');
    assert.ok(link.startsWith('mailto:info.artbasil@gmail.com?subject='));
    const body = decodeURIComponent(link.split('&body=')[1]);
    assert.strictEqual(body, 'Event title: A & B\nRegion: LA');
});

test('submit posts JSON to Web3Forms and reports success', async () => {
    let seen;
    const result = await w.submit({ 'Event title': 'X' }, {
        subject: 'S', accessKey: 'KEY', elapsedMs: 10000,
        fetchImpl: async (url, init) => { seen = { url, init }; return fakeResponse(200, { success: true, message: 'Email sent' }); },
    });
    assert.deepStrictEqual(result, { ok: true, message: 'Email sent', spam: false });
    assert.strictEqual(seen.url, 'https://api.web3forms.com/submit');
    assert.strictEqual(seen.init.method, 'POST');
    assert.strictEqual(seen.init.headers['Content-Type'], 'application/json');
    assert.strictEqual(JSON.parse(seen.init.body).access_key, 'KEY');
    assert.strictEqual(JSON.parse(seen.init.body)['Event title'], 'X');
});

test('without an access key it fails honestly and sends nothing', async () => {
    let called = false;
    const result = await w.submit({ a: 'b' }, { subject: 'S', accessKey: '', elapsedMs: 10000, fetchImpl: async () => { called = true; } });
    assert.strictEqual(result.ok, false);
    assert.strictEqual(called, false);
});

test('a bot submission looks successful but is never sent', async () => {
    let called = false;
    const fetchImpl = async () => { called = true; return fakeResponse(200, {}); };
    for (const opts of [{ honeypot: true, elapsedMs: 60000 }, { honeypot: false, elapsedMs: 100 }]) {
        const result = await w.submit({ a: 'b' }, { subject: 'S', accessKey: 'KEY', fetchImpl, ...opts });
        assert.deepStrictEqual(result, { ok: true, message: '', spam: true });
    }
    assert.strictEqual(called, false);
});

test('network errors, bad statuses and non-JSON replies come back as failures, never as exceptions', async () => {
    const base = { subject: 'S', accessKey: 'KEY', elapsedMs: 10000 };
    assert.strictEqual((await w.submit({ a: 'b' }, { ...base, fetchImpl: async () => { throw new Error('offline'); } })).ok, false);
    assert.strictEqual((await w.submit({ a: 'b' }, { ...base, fetchImpl: async () => fakeResponse(500, { message: 'boom' }) })).ok, false);
    assert.strictEqual((await w.submit({ a: 'b' }, { ...base, fetchImpl: async () => fakeResponse(502, undefined) })).ok, false);
    assert.strictEqual((await w.submit({ a: 'b' }, { ...base, fetchImpl: async () => fakeResponse(200, undefined) })).ok, true, 'a 200 with no JSON body is still a success');
});
