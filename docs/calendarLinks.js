// Calendar Links - the pure logic behind Notify Me's "Add to calendar" (no DOM access, so it can be unit
// tested in Node: `node --test tests/`). notify.js shows the modal and opens or downloads what this builds.
//
// An event is added as an all-day entry: its opening day, its closing day, or the whole run. Four targets:
// a Google Calendar link, an Outlook (outlook.live.com) link, a Yahoo link, and an .ics file (Apple
// Calendar, Outlook desktop, Thunderbird, most others) that carries its own alerts, so the person's
// own calendar app does the reminding and the site needs no backend, storage or sender (WEBSITE-114).
//
// Event dates are calendar days at the venue ("YYYY-MM-DD"), never moments in time. They are handled as
// strings and as UTC midnight, so the day cannot shift for a viewer west of UTC (see WEBSITE-66's
// neighbours), and an all-day entry ends on the EXCLUSIVE next day, as Google and iCalendar both want.

(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.calendarLinks = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {
    const ATTRIBUTION_URL = 'https://artbasil.info';
    const ALERT_HOUR = 9;                       // alerts in the .ics go off at 9:00 in the person's own time zone
    const WEEK_BEFORE = 7;

    // "2026-11-12" (or a longer ISO string that starts with it) -> "2026-11-12"; anything else -> null
    function dayOf(value) {
        if (value === null || value === undefined || value === 'null') return null;
        const m = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);
        if (!m) return null;
        const t = Date.UTC(+m[1], +m[2] - 1, +m[3]);
        const back = new Date(t).toISOString().slice(0, 10);
        return back === `${m[1]}-${m[2]}-${m[3]}` ? back : null;       // rejects 2026-02-31
    }

    function addDays(day, n) {
        const [y, m, d] = day.split('-').map(Number);
        return new Date(Date.UTC(y, m - 1, d + n)).toISOString().slice(0, 10);
    }

    function daysBetween(from, to) {
        const t = day => { const [y, m, d] = day.split('-').map(Number); return Date.UTC(y, m - 1, d); };
        return Math.round((t(to) - t(from)) / 86400000);
    }

    const compact = day => day.replace(/-/g, '');                       // "2026-11-12" -> "20261112"

    function eventPageLink(event) {
        const link = ((event && event.links) || []).find(l => l.description === 'Event Page');
        return link ? link.link : null;
    }

    // What to add for an event and a type ('opening' | 'closing' | 'full'):
    // { ok: true, name, venue, title, summary, startDay, lastDay, link } or { ok: false, message }
    function resolve(event, type) {
        const name = event.name, venue = event.venue;
        const start = dayOf(event.dates && event.dates.start);
        const end = dayOf(event.dates && event.dates.end);
        const base = { ok: true, name, venue, link: eventPageLink(event) };
        switch (type) {
            case 'opening':
                if (!start) return { ok: false, message: 'Opening date not available for this event' };
                return { ...base, title: `${name} - Opening Day`, summary: `Opening day of ${name} at ${venue}`, startDay: start, lastDay: start };
            case 'closing':
                if (!end) return { ok: false, message: 'Closing date not available for this event' };
                return { ...base, title: `${name} - Closing Day`, summary: `Last day to see ${name} at ${venue}`, startDay: end, lastDay: end };
            case 'full':
                if (!start || !end) return { ok: false, message: 'Full event dates not available for this event' };
                return { ...base, title: name, summary: `${name} at ${venue}`, startDay: start, lastDay: end };
            default:
                return { ok: false, message: 'Invalid calendar type selected' };
        }
    }

    // Plain text for the targets that take no HTML (Outlook, Yahoo, the .ics)
    function plainDescription(r) {
        let text = r.summary;
        if (r.link) text += `\n\nEvent page: ${r.link}`;
        return `${text}\n\nAdded from Art Basil (${ATTRIBUTION_URL})`;
    }

    const query = params => params.map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&');

    // Google Calendar's description takes a little HTML, which is how the link and attribution were always added
    function googleUrl(r) {
        let description = r.summary;
        if (r.link) description += `\n\n<a href="${r.link}">Event Page</a>`;
        description += '\n\n💡 Tip: Set a reminder for 1 week before this event!';
        description += `\n\nCreated by <a href="${ATTRIBUTION_URL}">Art Basil</a>`;
        // the dates value keeps its "/" as it always has (Google reads it either way)
        const dates = `${compact(r.startDay)}/${compact(addDays(r.lastDay, 1))}`;
        return `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${encodeURIComponent(r.title)}`
            + `&dates=${dates}&details=${encodeURIComponent(description)}&location=${encodeURIComponent(r.venue)}`;
    }

    // Outlook on the web (personal accounts); an all-day entry ends on the next day
    function outlookUrl(r) {
        return 'https://outlook.live.com/calendar/0/deeplink/compose?' + query([
            ['path', '/calendar/action/compose'], ['rru', 'addevent'], ['subject', r.title],
            ['startdt', r.startDay], ['enddt', addDays(r.lastDay, 1)], ['allday', 'true'],
            ['body', plainDescription(r)], ['location', r.venue]]);
    }

    function yahooUrl(r) {
        return 'https://calendar.yahoo.com/?' + query([
            ['v', '60'], ['title', r.title], ['st', compact(r.startDay)], ['et', compact(addDays(r.lastDay, 1))],
            ['dur', 'allday'], ['desc', plainDescription(r)], ['in_loc', r.venue]]);
    }

    // --- .ics (RFC 5545) -------------------------------------------------------------------------------

    // Backslash, semicolon, comma and line breaks are special in iCalendar text
    function icsEscape(text) {
        return String(text).replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\r\n|\r|\n/g, '\\n');
    }

    // Lines are at most 75 octets; a longer one continues on the next line after a space. Cut between
    // characters, never inside one (an accent or an emoji is several octets).
    function fold(line) {
        const out = [];
        let current = '', bytes = 0;
        const limit = 75;
        for (const ch of line) {
            const size = utf8Length(ch);
            const room = out.length === 0 ? limit : limit - 1;           // continuation lines start with a space
            if (bytes + size > room) { out.push(current); current = ''; bytes = 0; }
            current += ch;
            bytes += size;
        }
        out.push(current);
        return out.map((part, i) => (i === 0 ? part : ' ' + part)).join('\r\n');
    }

    function utf8Length(ch) {
        const c = ch.codePointAt(0);
        return c < 0x80 ? 1 : c < 0x800 ? 2 : c < 0x10000 ? 3 : 4;
    }

    // A stable id, so adding the same show twice updates the entry instead of duplicating it
    function uid(r, type) {
        const text = `${r.name}|${r.venue}|${r.startDay}|${r.lastDay}|${type}`;
        let a = 0x811c9dc5, b = 0x01000193;
        for (let i = 0; i < text.length; i++) {
            a = Math.imul(a ^ text.charCodeAt(i), 0x01000193) >>> 0;
            b = Math.imul(b + text.charCodeAt(i), 0x85ebca6b) >>> 0;
        }
        return `${a.toString(16).padStart(8, '0')}${b.toString(16).padStart(8, '0')}@artbasil.info`;
    }

    const stamp = date => date.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '');   // 20261113T164100Z

    // "PT9H", "P3DT9H", "-P6DT15H": a duration from the start of the all-day entry (00:00 on its first day)
    function duration(days, hours, before) {
        return `${before ? '-' : ''}P${days ? days + 'D' : ''}${hours ? 'T' + hours + 'H' : ''}`;
    }

    // Alerts, each relative to the start of the entry so every calendar app understands them:
    //  - opening day: the day before, at 9:00
    //  - closing day: a week before, and on the day, at 9:00
    //  - the full run: a week before it closes, and on the closing day (an alert that would already have
    //    gone off before the entry starts is left out)
    function alarms(r, type) {
        const hoursBeforeMidnight = 24 - ALERT_HOUR;                    // 9:00 the day before = 15h before 00:00
        const list = [];
        if (type === 'opening') {
            list.push({ trigger: duration(0, hoursBeforeMidnight, true), text: `Opens tomorrow: ${r.name} at ${r.venue}` });
        } else if (type === 'closing') {
            list.push({ trigger: duration(WEEK_BEFORE - 1, hoursBeforeMidnight, true), text: `Closes in a week: ${r.name} at ${r.venue}` });
            list.push({ trigger: duration(0, ALERT_HOUR, false), text: `Last day: ${r.name} at ${r.venue}` });
        } else if (type === 'full') {
            const weekBefore = daysBetween(r.startDay, addDays(r.lastDay, -WEEK_BEFORE));
            if (weekBefore >= 0) list.push({ trigger: duration(weekBefore, ALERT_HOUR, false), text: `Closes in a week: ${r.name} at ${r.venue}` });
            list.push({ trigger: duration(daysBetween(r.startDay, r.lastDay), ALERT_HOUR, false), text: `Last day: ${r.name} at ${r.venue}` });
        }
        return list;
    }

    // The .ics file as text, CRLF line endings, `now` is the time stamp (a Date, passed in so tests are exact)
    function icsText(r, type, now = new Date()) {
        const lines = [
            'BEGIN:VCALENDAR',
            'VERSION:2.0',
            'PRODID:-//Art Basil//artbasil.info//EN',
            'CALSCALE:GREGORIAN',
            'METHOD:PUBLISH',
            'BEGIN:VEVENT',
            `UID:${uid(r, type)}`,
            `DTSTAMP:${stamp(now)}`,
            `DTSTART;VALUE=DATE:${compact(r.startDay)}`,
            `DTEND;VALUE=DATE:${compact(addDays(r.lastDay, 1))}`,
            `SUMMARY:${icsEscape(r.title)}`,
            `LOCATION:${icsEscape(r.venue)}`,
            `DESCRIPTION:${icsEscape(plainDescription(r))}`,
            'TRANSP:TRANSPARENT',                                       // an all-day show does not make the person "busy"
        ];
        if (r.link) lines.push(`URL:${r.link}`);
        for (const alarm of alarms(r, type)) {
            lines.push('BEGIN:VALARM', 'ACTION:DISPLAY', `DESCRIPTION:${icsEscape(alarm.text)}`, `TRIGGER:${alarm.trigger}`, 'END:VALARM');
        }
        lines.push('END:VEVENT', 'END:VCALENDAR');
        return lines.map(fold).join('\r\n') + '\r\n';
    }

    // A file name for the download: "the-show-name-closing.ics"
    function icsFileName(r, type) {
        const slug = String(r.name).normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
            .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60) || 'event';
        return `${slug}-${type}.ics`;
    }

    const PROVIDERS = ['google', 'ics', 'outlook', 'yahoo'];

    return { PROVIDERS, dayOf, addDays, daysBetween, resolve, googleUrl, outlookUrl, yahooUrl, icsText, icsFileName, icsEscape, fold, alarms };
}));
