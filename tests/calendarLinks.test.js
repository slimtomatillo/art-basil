// Run with: node --test tests/
const test = require('node:test');
const assert = require('node:assert');
const cl = require('../docs/calendarLinks.js');

const show = (extra = {}) => ({
    name: 'Ana Mendieta: Earth Bodies',
    venue: 'Hammer Museum',
    dates: { start: '2026-10-01', end: '2026-11-12' },
    links: [{ description: 'Event Page', link: 'https://hammer.ucla.edu/exhibitions/ana' }],
    ...extra,
});
const NOW = new Date('2026-11-13T16:41:00Z');

// The Google link as notify.js built it before WEBSITE-114, kept here so the refactor cannot change it
function legacyGoogleUrl(event, calendarType) {
    const startDateObj = event.dates.start && event.dates.start !== 'null' ? new Date(event.dates.start) : null;
    const endDateObj = event.dates.end && event.dates.end !== 'null' ? new Date(event.dates.end) : null;
    let startDate, endDate, eventTitle, eventDescription;
    switch (calendarType) {
        case 'opening': startDate = endDate = startDateObj; eventTitle = `${event.name} - Opening Day`;
            eventDescription = `Opening day of ${event.name} at ${event.venue}`; break;
        case 'closing': startDate = endDate = endDateObj; eventTitle = `${event.name} - Closing Day`;
            eventDescription = `Last day to see ${event.name} at ${event.venue}`; break;
        case 'full': startDate = startDateObj; endDate = endDateObj; eventTitle = event.name;
            eventDescription = `${event.name} at ${event.venue}`; break;
    }
    const eventPageLink = event.links.find(link => link.description === 'Event Page');
    if (eventPageLink) eventDescription += `\n\n<a href="${eventPageLink.link}">Event Page</a>`;
    const fmt = date => `${date.getUTCFullYear()}${String(date.getUTCMonth() + 1).padStart(2, '0')}${String(date.getUTCDate()).padStart(2, '0')}`;
    const startDateStr = fmt(startDate);
    const endDateStr = fmt(new Date(endDate.getTime() + 24 * 60 * 60 * 1000));
    const fullDescription = eventDescription + '\n\n💡 Tip: Set a reminder for 1 week before this event!'
        + '\n\nCreated by <a href="https://artbasil.info">Art Basil</a>';
    return `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${encodeURIComponent(eventTitle)}&dates=${startDateStr}/${endDateStr}&details=${encodeURIComponent(fullDescription)}&location=${encodeURIComponent(event.venue)}`;
}

test('the Google link is exactly what it was before the other calendars were added', () => {
    for (const event of [show(), show({ links: [] }), show({ name: 'A & B, "C"', venue: 'Café Ñ' }),
        show({ dates: { start: '2026-12-31', end: '2027-01-03' } })]) {
        for (const type of ['opening', 'closing', 'full']) {
            assert.strictEqual(cl.googleUrl(cl.resolve(event, type)), legacyGoogleUrl(event, type), `${event.name} ${type}`);
        }
    }
});

test('an all-day entry ends on the day after the last day, across a month and a year', () => {
    const google = cl.googleUrl(cl.resolve(show({ dates: { start: '2026-12-20', end: '2026-12-31' } }), 'full'));
    assert.ok(google.includes('dates=20261220/20270101'));
    const outlook = new URL(cl.outlookUrl(cl.resolve(show({ dates: { start: '2026-02-20', end: '2026-02-28' } }), 'full')));
    assert.strictEqual(outlook.searchParams.get('startdt'), '2026-02-20');
    assert.strictEqual(outlook.searchParams.get('enddt'), '2026-03-01');
    assert.strictEqual(outlook.searchParams.get('allday'), 'true');
    const yahoo = new URL(cl.yahooUrl(cl.resolve(show(), 'closing')));
    assert.strictEqual(yahoo.searchParams.get('st'), '20261112');
    assert.strictEqual(yahoo.searchParams.get('et'), '20261113');
    assert.strictEqual(yahoo.searchParams.get('dur'), 'allday');
});

test('missing or bad dates are refused with the same messages as before', () => {
    assert.deepStrictEqual(cl.resolve(show({ dates: { start: null, end: '2026-11-12' } }), 'opening'),
        { ok: false, message: 'Opening date not available for this event' });
    assert.deepStrictEqual(cl.resolve(show({ dates: { start: '2026-10-01', end: 'null' } }), 'closing'),
        { ok: false, message: 'Closing date not available for this event' });
    assert.deepStrictEqual(cl.resolve(show({ dates: { start: '2026-10-01', end: null } }), 'full'),
        { ok: false, message: 'Full event dates not available for this event' });
    assert.deepStrictEqual(cl.resolve(show(), 'weekly'), { ok: false, message: 'Invalid calendar type selected' });
    assert.strictEqual(cl.resolve(show({ dates: { start: '2026-02-31', end: '2026-11-12' } }), 'opening').ok, false);
    assert.strictEqual(cl.resolve(show({ dates: { start: '2026-10-01T00:00:00.000Z', end: '2026-11-12' } }), 'opening').ok, true);
});

test('the .ics is a valid all-day entry with CRLF lines, an exclusive end and a stable id', () => {
    const r = cl.resolve(show(), 'full');
    const ics = cl.icsText(r, 'full', NOW);
    assert.ok(ics.endsWith('END:VCALENDAR\r\n'));
    assert.ok(!/[^\r]\n/.test(ics), 'every line break is CRLF');
    for (const line of ['BEGIN:VCALENDAR', 'VERSION:2.0', 'BEGIN:VEVENT', 'DTSTAMP:20261113T164100Z',
        'DTSTART;VALUE=DATE:20261001', 'DTEND;VALUE=DATE:20261113', 'LOCATION:Hammer Museum', 'TRANSP:TRANSPARENT',
        'URL:https://hammer.ucla.edu/exhibitions/ana', 'END:VEVENT']) {
        assert.ok(ics.split('\r\n').includes(line), line);
    }
    assert.strictEqual(cl.icsText(r, 'full', new Date('2030-01-01T00:00:00Z')).match(/UID:.*/)[0], ics.match(/UID:.*/)[0]);
    assert.notStrictEqual(cl.icsText(cl.resolve(show(), 'closing'), 'closing', NOW).match(/UID:.*/)[0], ics.match(/UID:.*/)[0]);
});

test('text is escaped, and long lines are folded between characters, never inside one', () => {
    assert.strictEqual(cl.icsEscape('a,b;c\\d\ne'), 'a\\,b\\;c\\\\d\\ne');
    const ics = cl.icsText(cl.resolve(show({ name: 'Hello, World; "Ünïcode" 🎨' }), 'opening'), 'opening', NOW);
    assert.ok(ics.includes('SUMMARY:Hello\\, World\\; "Ünïcode" 🎨 - Opening Day'));
    const long = cl.icsText(cl.resolve(show({ name: 'É'.repeat(80) }), 'opening'), 'opening', NOW);
    for (const line of long.split('\r\n')) assert.ok(Buffer.byteLength(line) <= 75, `${Buffer.byteLength(line)} octets: ${line}`);
    // unfolding (remove CRLF + one space) gives back the whole text, with no character split
    const unfolded = long.replace(/\r\n /g, '');
    assert.ok(unfolded.includes('SUMMARY:' + 'É'.repeat(80) + ' - Opening Day'));
    assert.ok(!unfolded.includes('�'));
});

test('alerts: opening the day before, closing a week before and on the day, a run a week before it closes', () => {
    const alarms = (event, type) => cl.alarms(cl.resolve(event, type), type).map(a => a.trigger);
    assert.deepStrictEqual(alarms(show(), 'opening'), ['-PT15H']);                        // 9:00 the day before
    assert.deepStrictEqual(alarms(show(), 'closing'), ['-P6DT15H', 'PT9H']);              // 9:00 seven days before; 9:00 that day
    // Oct 1 - Nov 12: Nov 5 is a week before the 12th, 35 days after Oct 1; the 12th is 42 days after
    assert.deepStrictEqual(alarms(show(), 'full'), ['P35DT9H', 'P42DT9H']);
    // a run that closes within a week of opening has no "a week before" alert
    assert.deepStrictEqual(alarms(show({ dates: { start: '2026-11-10', end: '2026-11-12' } }), 'full'), ['P2DT9H']);
    // a one-day run: the closing alert is on the day
    assert.deepStrictEqual(alarms(show({ dates: { start: '2026-11-12', end: '2026-11-12' } }), 'full'), ['PT9H']);
    const ics = cl.icsText(cl.resolve(show(), 'closing'), 'closing', NOW).split('\r\n');
    assert.strictEqual(ics.filter(l => l === 'BEGIN:VALARM').length, 2);
    assert.ok(ics.includes('TRIGGER:-P6DT15H') && ics.includes('TRIGGER:PT9H') && ics.includes('ACTION:DISPLAY'));
});

test('without an event page link there is no URL line or link text', () => {
    const ics = cl.icsText(cl.resolve(show({ links: [] }), 'closing'), 'closing', NOW);
    assert.ok(!ics.includes('URL:') && !ics.includes('Event page:'));
    assert.ok(!cl.outlookUrl(cl.resolve(show({ links: [] }), 'closing')).includes('Event%20page'));
});

test('the file name is a plain slug with the type', () => {
    assert.strictEqual(cl.icsFileName(cl.resolve(show({ name: 'Ünïcode & Café: the Show!' }), 'closing'), 'closing'), 'unicode-cafe-the-show-closing.ics');
    assert.strictEqual(cl.icsFileName(cl.resolve(show({ name: '!!!' }), 'full'), 'full'), 'event-full.ics');
});

test('the Outlook link is for work, school and Microsoft 365 accounts (outlook.office.com): the personal host sends them to a login page', () => {
    const url = new URL(cl.outlookUrl(cl.resolve(show(), 'closing')));
    assert.strictEqual(url.host, 'outlook.office.com');
    assert.strictEqual(url.pathname, '/calendar/0/deeplink/compose');
    assert.strictEqual(url.searchParams.get('startdt'), '2026-11-12');
    assert.strictEqual(url.searchParams.get('enddt'), '2026-11-13');
});

test('the Outlook body is HTML: line breaks are <br> and the text is escaped', () => {
    const body = new URL(cl.outlookUrl(cl.resolve(show({ name: 'Tom & Jerry <live>' }), 'full'))).searchParams.get('body');
    assert.ok(!body.includes('\n'), 'no plain newlines, Outlook turns them into spaces');
    assert.ok(body.includes('Tom &amp; Jerry &lt;live&gt; at Hammer Museum<br><br>Event page: https://hammer.ucla.edu/exhibitions/ana<br><br>Added from Art Basil'));
    // the other targets still take plain text
    assert.ok(new URL(cl.yahooUrl(cl.resolve(show(), 'full'))).searchParams.get('desc').includes('\n\n'));
});

test('the providers offered are the four the modal lists', () => {
    assert.deepStrictEqual(cl.PROVIDERS, ['google', 'ics', 'outlook', 'yahoo']);
});
