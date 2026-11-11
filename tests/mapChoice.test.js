// Run with: node --test tests/
// The Apple Maps / Google Maps choice (docs/mapChoice.js) driven through a tiny fake DOM: it only
// appears on Apple devices, a plain click opens the choice instead of Google Maps, a modified click
// is left alone, Escape and an outside click close it, and each item points at the right app.
const test = require('node:test');
const assert = require('node:assert');
const va = require('../docs/venueAddresses.js');
const mapChoice = require('../docs/mapChoice.js');

const IPHONE = { userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1' };
const ANDROID = { userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/120 Mobile Safari/537.36' };

function makeElement(tag) {
    const el = {
        tag, className: '', textContent: '', href: '', target: '', rel: '', attributes: {}, children: [], listeners: {},
        style: {}, offsetWidth: 150, removed: false, focused: false,
        setAttribute(name, value) { el.attributes[name] = String(value); },
        getAttribute(name) { return el.attributes[name] ?? null; },
        append(...nodes) { el.children.push(...nodes); },
        contains(node) { return node === el || el.children.some(c => c === node || (c.contains && c.contains(node))); },
        addEventListener(name, fn) { (el.listeners[name] ||= []).push(fn); },
        getBoundingClientRect() { return { left: 40, bottom: 100, top: 80, right: 100 }; },
        focus() { el.focused = true; env.document.activeElement = el; },
        remove() { el.removed = true; el.parentBody && (el.parentBody.children = el.parentBody.children.filter(c => c !== el)); },
    };
    return el;
}

let env;
function setup(navigator) {
    const listeners = {};
    const body = makeElement('body');
    const doc = {
        body, activeElement: null, createElement: makeElement,
        addEventListener(name, fn) { (listeners['d' + name] ||= []).push(fn); },
        removeEventListener(name, fn) { listeners['d' + name] = (listeners['d' + name] || []).filter(f => f !== fn); },
    };
    const originalAppend = body.append;
    body.append = (...nodes) => { nodes.forEach(n => { n.parentBody = body; }); originalAppend(...nodes); };
    const win = {
        venueAddresses: va, innerWidth: 390,
        addEventListener(name, fn) { (listeners['w' + name] ||= []).push(fn); },
        removeEventListener(name, fn) { listeners['w' + name] = (listeners['w' + name] || []).filter(f => f !== fn); },
    };
    env = { window: win, document: doc, navigator, listeners };
    return env;
}

const LINK = va.mapLinks('1 Main St, San Francisco, CA')[0];
const click = (anchor, extra = {}) => {
    const event = { button: 0, prevented: false, preventDefault() { event.prevented = true; }, ...extra };
    (anchor.listeners.click || []).forEach(fn => fn(event));
    return event;
};
const menus = e => e.document.body.children.filter(c => c.className === 'map-choice');

test('on an Android or desktop browser the link is left alone', () => {
    const e = setup(ANDROID);
    const anchor = makeElement('a');
    assert.strictEqual(mapChoice.attach(anchor, LINK, e), false);
    assert.deepStrictEqual(anchor.listeners, {});
});

test('on an iPhone a click opens a choice of Apple Maps and Google Maps instead of going to Google', () => {
    const e = setup(IPHONE);
    const anchor = makeElement('a');
    assert.strictEqual(mapChoice.attach(anchor, LINK, e), true);
    const event = click(anchor);
    assert.ok(event.prevented, 'the link is not followed');
    const [menu] = menus(e);
    assert.ok(menu);
    const [apple, google] = menu.children;
    assert.deepStrictEqual([apple.textContent, apple.href], ['Apple Maps', 'https://maps.apple.com/?q=1%20Main%20St%2C%20San%20Francisco%2C%20CA']);
    assert.deepStrictEqual([google.textContent, google.href], ['Google Maps', LINK.href]);
    assert.ok([apple, google].every(a => a.target === '_blank' && a.rel.includes('noopener')));
    assert.ok(apple.focused, 'focus moves into the choice');
    assert.strictEqual(menu.style.top, '104px');
});

test('a modified click (new tab) goes straight to the link', () => {
    const e = setup(IPHONE);
    const anchor = makeElement('a');
    mapChoice.attach(anchor, LINK, e);
    for (const extra of [{ metaKey: true }, { ctrlKey: true }, { shiftKey: true }, { button: 1 }]) {
        assert.ok(!click(anchor, extra).prevented, JSON.stringify(extra));
    }
    assert.strictEqual(menus(e).length, 0);
});

test('Escape closes the choice and returns focus to the link; so does a click elsewhere', () => {
    const e = setup(IPHONE);
    const anchor = makeElement('a');
    mapChoice.attach(anchor, LINK, e);
    click(anchor);
    anchor.focused = false;
    e.listeners.dkeydown.forEach(fn => fn({ key: 'Escape' }));
    assert.strictEqual(menus(e).length, 0);
    assert.ok(anchor.focused);

    click(anchor);
    assert.strictEqual(menus(e).length, 1);
    e.listeners.dclick.forEach(fn => fn({ target: makeElement('p') }));
    assert.strictEqual(menus(e).length, 0);
    assert.deepStrictEqual(e.listeners.dkeydown, [], 'listeners are removed when it closes');
});

test('choosing an app closes the choice, and only one is open at a time', () => {
    const e = setup(IPHONE);
    const a = makeElement('a');
    const b = makeElement('a');
    mapChoice.attach(a, LINK, e);
    mapChoice.attach(b, LINK, e);
    click(a);
    click(b);
    assert.strictEqual(menus(e).length, 1);
    menus(e)[0].children[1].listeners.click[0]();
    assert.strictEqual(menus(e).length, 0);
});

test('the choice stays on screen near the right edge', () => {
    const e = setup(IPHONE);
    const anchor = makeElement('a');
    anchor.getBoundingClientRect = () => ({ left: 380, bottom: 50, top: 30, right: 400 });
    mapChoice.attach(anchor, LINK, e);
    click(anchor);
    assert.strictEqual(menus(e)[0].style.left, '232px'); // 390 - 150 - 8
});
