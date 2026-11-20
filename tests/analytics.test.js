// Run with: node --test tests/
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const analytics = require('../docs/analytics.js');

function fakePage(hostname) {
    const added = [];
    const win = { location: { hostname } };
    const doc = { createElement: () => ({}), head: { appendChild: (el) => added.push(el) } };
    return { win, doc, added };
}

test('only artbasil.info counts as the live site', () => {
    assert.ok(analytics.isLiveHost('artbasil.info'));
    assert.ok(analytics.isLiveHost('www.artbasil.info'));
    assert.ok(analytics.isLiveHost('ArtBasil.info'));
    for (const host of ['localhost', '127.0.0.1', 'slimtomatillo.github.io', '', undefined, 'artbasil.info.evil.com']) {
        assert.ok(!analytics.isLiveHost(host), `${host} should not be live`);
    }
});

test('on localhost Google\'s script is not added, but gtag still works', () => {
    const { win, doc, added } = fakePage('localhost');
    assert.strictEqual(analytics.start(win, doc), false);
    assert.strictEqual(added.length, 0);
    assert.doesNotThrow(() => win.gtag('event', 'anything'));
});

test('on the live site Google\'s script is added and the page is configured', () => {
    const { win, doc, added } = fakePage('artbasil.info');
    assert.strictEqual(analytics.start(win, doc), true);
    assert.strictEqual(added.length, 1);
    assert.match(added[0].src, /googletagmanager\.com\/gtag\/js\?id=G-G06G4L1YGN$/);
    assert.ok(win.dataLayer.some((args) => args[0] === 'config' && args[1] === analytics.MEASUREMENT_ID));
});

test('no page loads Google\'s tag directly; every page uses analytics.js', () => {
    const docs = path.join(__dirname, '..', 'docs');
    const pages = fs.readdirSync(docs, { recursive: true }).filter((f) => f.endsWith('.html'));
    for (const page of pages) {
        const html = fs.readFileSync(path.join(docs, page), 'utf8');
        assert.ok(!html.includes('googletagmanager.com'), `${page} loads Google's tag directly`);
        assert.match(html, /<script src="(\.\.\/|\/)?analytics\.js"><\/script>/, `${page} is missing analytics.js`);
    }
});
