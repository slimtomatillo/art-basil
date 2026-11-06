// Run with: node --test tests/
const test = require('node:test');
const assert = require('node:assert');

// eventSorter.js is a browser script that reads window.dataManager and registers window.eventSorter
global.window = { dataManager: { regionToday: () => '2026-11-05', getRegion: () => 'la' } };
require('../docs/eventSorter.js');
const { sortEvents } = global.window.eventSorter;

const event = (name, phase, start, end, extra = {}) => ({
    name, tags: ['exhibition', phase], dates: { start, end }, ...extra,
});
const names = list => list.map(e => e.name);

test('a show that has started keeps its real start date', () => {
    const events = { 'Venue A': { x: event('Open show', 'current', '2026-09-01', '2026-12-01') } };
    const [shown] = sortEvents(events);
    assert.strictEqual(shown.dates.start, '2026-09-01');
    assert.strictEqual(shown.dates.end, '2026-12-01');
});

test('a show with only a start date keeps it, so the table can say "Started on"', () => {
    const events = { 'Venue A': { x: event('Open-ended', 'current', '2026-10-04', null) } };
    const [shown] = sortEvents(events);
    assert.strictEqual(shown.dates.start, '2026-10-04');
});

test('the order is unchanged: current by closing date, ongoing, upcoming by opening date, then past by closing date, latest first', () => {
    const events = {
        'Venue A': {
            a: event('Past, closed early', 'past', '2026-01-01', '2026-02-01'),
            b: event('Future, later', 'future', '2027-02-01', '2027-04-01'),
            c: event('Current, closes late', 'current', '2026-09-01', '2027-01-15'),
            d: event('Ongoing', 'current', '2020-01-01', null, { ongoing: true }),
            e: event('Current, closes soon', 'current', '2026-10-01', '2026-11-20'),
            f: event('Future, sooner', 'future', '2026-12-01', '2027-01-30'),
            g: event('Past, closed late', 'past', '2026-03-01', '2026-10-15'),
        },
    };
    assert.deepStrictEqual(names(sortEvents(events)), [
        'Current, closes soon', 'Current, closes late', 'Ongoing', 'Future, sooner', 'Future, later',
        'Past, closed late', 'Past, closed early']);
});

test('an event tagged "future" whose start date has passed still sorts after the really upcoming ones', () => {
    // Some stored events carry stale or contradictory tags (both "future" and "past"); keeping their real start
    // date must not float them to the top of the upcoming block
    const events = { 'Venue A': {
        a: { name: 'Stale future tag', tags: ['exhibition', 'future', 'past'], dates: { start: '2021-02-27', end: '2025-01-12' } },
        b: event('Really upcoming', 'future', '2027-02-01', '2027-04-01'),
    } };
    assert.deepStrictEqual(names(sortEvents(events)), ['Really upcoming', 'Stale future tag']);
});

test('sortDate is the closing date, or the far future when there is none', () => {
    const events = { 'Venue A': { a: event('Has end', 'current', '2026-09-01', '2026-12-01'), b: event('No end', 'current', '2026-09-01', null) } };
    const byName = Object.fromEntries(sortEvents(events).map(e => [e.name, e.sortDate]));
    assert.strictEqual(byName['Has end'], '2026-12-01');
    assert.strictEqual(byName['No end'], '9999-12-31');
});
