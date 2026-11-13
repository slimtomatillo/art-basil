// Run with: node --test tests/
// Receptions stay in the data (tagged 'reception' by processing.py) but the site does not list them for now.
const test = require('node:test');
const assert = require('node:assert');

global.window = { location: { pathname: '/la/' } };
require('../docs/dataManager.js');
const { hideReceptions } = window.dataManager;

const events = () => ({
    'Venue A': {
        show: { name: 'A Show', tags: ['exhibition', 'current'] },
        reception: { name: 'A Show – Opening Reception', tags: ['event', 'future', 'reception'] },
        untagged: { name: 'No tags at all' },
    },
    'Venue B': { onlyReception: { name: 'Opening Reception', tags: ['reception'] } },
});

test('receptions are taken out of the events, and nothing else is', () => {
    const shown = hideReceptions(events());
    assert.deepStrictEqual(Object.keys(shown['Venue A']), ['show', 'untagged']);
    assert.deepStrictEqual(Object.keys(shown['Venue B']), []);
});

test('with SHOW_RECEPTIONS on they are all still there', () => {
    const shown = hideReceptions(events(), true);
    assert.deepStrictEqual(Object.keys(shown['Venue A']), ['show', 'reception', 'untagged']);
    assert.deepStrictEqual(Object.keys(shown['Venue B']), ['onlyReception']);
});

test('the site hides receptions unless the switch in dataManager.js is turned on', () => {
    // hideReceptions() with no second argument follows the file's SHOW_RECEPTIONS, which ships as false
    assert.deepStrictEqual(Object.keys(hideReceptions(events())['Venue A']), ['show', 'untagged']);
});
