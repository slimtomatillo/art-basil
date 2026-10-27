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

test('the sticker and dot cursors hide the real cursor but keep the text cursor in fields', () => {
    for (const kind of ['sticker', 'dot']) {
        const css = fx.cursorCss(kind);
        assert.match(css, /html\.fx-own-cursor,html\.fx-own-cursor \*\{cursor:none!important\}/);
        assert.match(css, /textarea\)\{cursor:text!important\}/);
    }
});

test('each cursor has a resting and a link image with a hotspot; the link image takes the accent', () => {
    const sticker = fx.cursorShapes('sticker', '#14806b');
    assert.ok(sticker.base[0].includes('#fff') && sticker.link[0].includes('#14806b'));
    assert.deepStrictEqual([sticker.base[1], sticker.base[2]], [4, 3]);
    assert.ok(fx.cursorShapes('sticker', null).link[0].toLowerCase().includes('#ffd23f'), 'no accent: links use the yellow');
    const dot = fx.cursorShapes('dot', '#14806b');
    assert.ok(dot.base[0].includes('#14806b') && dot.link[0].includes('#fff'));
    assert.deepStrictEqual([dot.base[1], dot.base[2]], [16, 16]);
    assert.strictEqual(fx.cursorShapes('normal', null), null);
});

test('colours: with an accent most picks are the accent; without one it is always the palette', () => {
    assert.strictEqual(fx.pickColour('#14806b', () => 0.1), '#14806b');
    assert.ok(fx.POP.includes(fx.pickColour('#14806b', () => 0.9)));
    for (const r of [0, 0.3, 0.99]) assert.ok(fx.POP.includes(fx.pickColour(null, () => r)));
});
