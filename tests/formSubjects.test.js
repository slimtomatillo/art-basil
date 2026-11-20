// Run with: node --test tests/
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const DOCS = path.join(__dirname, '../docs');

// A form that adds one of its fields to the email subject (data-subject-field="Label", see siteForms.js)
// finds that field by its data-label. If someone renames one and not the other, the subject quietly
// loses the value, so check that they still match.
test('every form that puts a field in its email subject has a field with that label', () => {
    let checked = 0;
    for (const page of ['index.html', 'add_event.html']) {
        const html = fs.readFileSync(path.join(DOCS, page), 'utf8');
        for (const form of html.matchAll(/<form\b[^>]*data-subject-field="([^"]+)"[^>]*>([\s\S]*?)<\/form>/g)) {
            const label = form[1];
            const labels = [...form[2].matchAll(/data-label="([^"]*)"/g)].map(m => m[1]);
            assert.ok(labels.includes(label), `${page}: the subject uses "${label}", but no field has that data-label (found: ${labels.join(', ')})`);
            checked += 1;
        }
    }
    assert.strictEqual(checked, 3, 'expected the "Add my area", "Add an event" and "suggest a venue" forms to be checked');
});

test('the "Add my area" form asks for the state or country along with the city', () => {
    const html = fs.readFileSync(path.join(DOCS, 'index.html'), 'utf8');
    const form = (html.match(/<form[^>]*id="areaForm"[\s\S]*?<\/form>/) || [''])[0];
    assert.match(form, /<label for="area-name">City and state or country/);
    assert.match(form, /placeholder="Like Chicago, Illinois"/);
});
