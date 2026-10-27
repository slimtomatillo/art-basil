// Run with: node --test tests/
const test = require('node:test');
const assert = require('node:assert');
const fx = require('../docs/cursorFx.js');

test('defaults are pixel squares and the sticker cursor', () => {
    assert.deepStrictEqual(fx.DEFAULTS, { effect: 'pixels', cursor: 'sticker' });
    const { settings, explicitEffect } = fx.sanitize(null);
    assert.deepStrictEqual(settings, fx.DEFAULTS);
    assert.strictEqual(explicitEffect, false);
});

test('the choices on offer are exactly the agreed ones', () => {
    assert.deepStrictEqual(fx.EFFECTS.map(([v]) => v), ['stamps', 'marker', 'pixels', 'off']);
    assert.deepStrictEqual(fx.CURSORS.map(([v]) => v), ['normal', 'sticker', 'dot']);
});

test('a saved valid choice is kept and counts as an explicit effect choice', () => {
    const { settings, explicitEffect } = fx.sanitize({ effect: 'marker', cursor: 'dot' });
    assert.deepStrictEqual(settings, { effect: 'marker', cursor: 'dot' });
    assert.strictEqual(explicitEffect, true);
    assert.strictEqual(fx.sanitize({ effect: 'off', cursor: 'normal' }).settings.effect, 'off');
});

test('unknown or malformed saved values fall back to the defaults, field by field', () => {
    assert.deepStrictEqual(fx.sanitize({ effect: 'lasers', cursor: 'dot' }).settings, { effect: 'pixels', cursor: 'dot' });
    assert.deepStrictEqual(fx.sanitize({ effect: 'stamps', cursor: '<script>' }).settings, { effect: 'stamps', cursor: 'sticker' });
    for (const bad of ['stamps', 42, [], undefined, true]) {
        assert.deepStrictEqual(fx.sanitize(bad).settings, fx.DEFAULTS);
    }
});

test('the normal cursor adds no CSS', () => {
    assert.strictEqual(fx.cursorCss('normal', '#14806b'), '');
});

test('the sticker and dot cursors are SVG data URIs with a hotspot, and keep the text cursor in inputs', () => {
    for (const kind of ['sticker', 'dot']) {
        const css = fx.cursorCss(kind, '#14806b');
        assert.match(css, /cursor:url\("data:image\/svg\+xml;utf8,/);
        assert.match(css, /textarea\{cursor:text!important\}/);
        assert.ok(!/<svg/.test(css), 'the SVG must be URL-encoded inside the CSS');
    }
    assert.match(fx.cursorCss('sticker', null), /%23ffd23f/i, 'no accent: links use the yellow');
    assert.match(fx.cursorCss('sticker', '#14806b'), /%2314806b/i, 'accent colours the link cursor');
});

test('once the PNG versions are ready they follow the SVG line, which stays as the fallback', () => {
    const { base, link } = fx.cursorShapes('sticker', '#14806b');
    const images = new Map([[base[0], 'image-set(url("b.png") 1x)'], [link[0], 'image-set(url("l.png") 1x)']]);
    const css = fx.cursorCss('sticker', '#14806b', images);
    assert.match(css, /html\{cursor:url\("data:image\/svg.*?,auto;cursor:image-set\(url\("b\.png"\) 1x\) 4 3,auto\}/);
    assert.match(css, /cursor:image-set\(url\("l\.png"\) 1x\) 4 3,pointer!important/);
    assert.strictEqual(fx.cursorShapes('normal', null), null);
});

test('colours: with an accent most picks are the accent; without one it is always the palette', () => {
    assert.strictEqual(fx.pickColour('#14806b', () => 0.1), '#14806b');
    assert.ok(fx.POP.includes(fx.pickColour('#14806b', () => 0.9)));
    for (const r of [0, 0.3, 0.99]) assert.ok(fx.POP.includes(fx.pickColour(null, () => r)));
});
