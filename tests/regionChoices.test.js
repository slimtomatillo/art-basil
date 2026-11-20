// Run with: node --test tests/
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const RegionInfo = require('../docs/regionInfo.js');
const RegionChoices = require('../docs/regionChoices.js');
const { fakePage } = require('./fakeDom.js');

const DOCS = path.join(__dirname, '../docs');
const info = JSON.parse(fs.readFileSync(path.join(DOCS, 'data/region_info.json'), 'utf8'));
const labels = Object.values(info).map(region => RegionInfo.menuLabel(region));
const names = Object.values(info).map(region => region.name);

// A menu that starts as the page's plain copy: "Choose a region" and two old options
function plainMenu(doc) {
    const select = doc.createElement('select');
    select.setAttribute('data-region-menu', '');
    ['Choose a region', 'Old A', 'Old B'].forEach((text, i) => {
        const option = doc.createElement('option');
        option.textContent = text;
        if (!i) option.setAttribute('value', '');
        select.appendChild(option);
    });
    return select;
}

const texts = element => element.children.map(child => child.textContent);

// ---- the label ----

test('a menu label is the name with its place, or with just the country when there is no state', () => {
    assert.strictEqual(RegionInfo.menuLabel(info.pdx), 'Portland, Oregon, USA');
    assert.strictEqual(RegionInfo.menuLabel(info.mtl), 'Montreal, Québec, Canada');
    assert.strictEqual(RegionInfo.menuLabel(info.ist), 'Istanbul, Türkiye');
    assert.strictEqual(RegionInfo.menuLabel(info.nyc), 'New York, New York, USA');
});

// ---- the menus ----

test('a menu keeps "Choose a region" first and gets one option per region, in the file order', () => {
    const { doc } = fakePage();
    const select = plainMenu(doc);
    const choose = select.children[0];
    RegionChoices.fillMenu(select, info);
    assert.strictEqual(select.children[0], choose, 'the first option is the same one');
    assert.deepStrictEqual(texts(select), ['Choose a region', ...labels]);
});

test('the place is in every menu option, so no Portland can be mistaken for another', () => {
    const { doc } = fakePage();
    const select = plainMenu(doc);
    RegionChoices.fillMenu(select, info);
    for (const option of select.children.slice(1)) {
        assert.ok(option.textContent.includes(','), `"${option.textContent}" has no place`);
    }
    assert.ok(texts(select).includes('Portland, Oregon, USA'));
});

test('what the visitor already picked stays picked, if it is still on the list', () => {
    const { doc } = fakePage();
    const select = plainMenu(doc);
    select.value = 'Portland, Oregon, USA';
    RegionChoices.fillMenu(select, info);
    assert.strictEqual(select.value, 'Portland, Oregon, USA');

    const other = plainMenu(doc);
    other.value = 'Old A';
    RegionChoices.fillMenu(other, info);
    assert.notStrictEqual(other.value, 'Old A');
});

// ---- the chips ----

test('the "We cover" line gets one chip per region, in its own colour, with a space between', () => {
    const { doc } = fakePage();
    const container = doc.createElement('span');
    container.setAttribute('data-region-chips', '');
    container.appendChild(doc.createElement('span'));
    RegionChoices.fillChips(container, info);
    const chips = container.children.filter(child => child.nodeType === 1);
    assert.deepStrictEqual(chips.map(chip => chip.textContent), names);
    assert.ok(chips.every(chip => chip.classes.has('region-chip')));
    assert.strictEqual(chips[0].style.props['--c'], info.sf.colour);
    assert.strictEqual(container.children.length, chips.length * 2 - 1, 'a space between each pair');
});

test('fill finds every chip line and every menu on the page', () => {
    const { doc } = fakePage();
    const chips = doc.createElement('span');
    chips.setAttribute('data-region-chips', '');
    const eventMenu = plainMenu(doc);
    const venueMenu = plainMenu(doc);
    [chips, eventMenu, venueMenu].forEach(node => doc.body.appendChild(node));
    RegionChoices.fill(doc, info);
    assert.strictEqual(chips.children.filter(child => child.nodeType === 1).length, names.length);
    assert.deepStrictEqual(texts(eventMenu), ['Choose a region', ...labels]);
    assert.deepStrictEqual(texts(venueMenu), ['Choose a region', ...labels]);
});

test('a region added to the data shows up in the chips and both menus with no other change', () => {
    const { doc } = fakePage();
    const more = { ...info, chi: { name: 'Chicago', label: 'Chicago', place: 'Illinois', country: 'USA', colour: '#336699', lat: 41.88, lng: -87.63 } };
    const chips = doc.createElement('span');
    chips.setAttribute('data-region-chips', '');
    const menu = plainMenu(doc);
    [chips, menu].forEach(node => doc.body.appendChild(node));
    RegionChoices.fill(doc, more);
    assert.ok(chips.children.some(child => child.textContent === 'Chicago'));
    assert.ok(texts(menu).includes('Chicago, Illinois, USA'));
});

// ---- the region code ----

// A menu with an id and the hidden field that names it, both on the page
function formWithCode(doc, id) {
    const select = plainMenu(doc);
    select.setAttribute('id', id);
    const field = doc.createElement('input');
    field.setAttribute('type', 'hidden');
    field.setAttribute('data-region-code', id);
    doc.body.appendChild(select);
    doc.body.appendChild(field);
    return { select, field };
}

test('every option built from the data carries its region code', () => {
    const { doc } = fakePage();
    const select = plainMenu(doc);
    RegionChoices.fillMenu(select, info);
    const codes = select.children.slice(1).map(option => option.getAttribute('data-code'));
    assert.deepStrictEqual(codes, Object.keys(info));
    assert.strictEqual(select.children[0].getAttribute('data-code'), null, '"Choose a region" has no code');
});

test('the hidden field holds the code of the chosen region, and is empty for "Choose a region"', () => {
    const { doc } = fakePage();
    const { select, field } = formWithCode(doc, 'ev-region');
    RegionChoices.fill(doc, info);
    assert.strictEqual(field.value, '');

    select.value = 'Portland, Oregon, USA';
    RegionChoices.syncCodes(doc);
    assert.strictEqual(field.value, 'pdx');

    select.value = '';
    RegionChoices.syncCodes(doc);
    assert.strictEqual(field.value, '');
});

test('changing the menu updates the code, and each form keeps its own', () => {
    const { doc } = fakePage();
    const event = formWithCode(doc, 'ev-region');
    const venue = formWithCode(doc, 'vn-region');
    RegionChoices.fill(doc, info);
    RegionChoices.wire(doc);

    event.select.value = 'New York, New York, USA';
    event.select.fire('change');
    assert.strictEqual(event.field.value, 'nyc');
    assert.strictEqual(venue.field.value, '', 'the other form is untouched');

    venue.select.value = 'Istanbul, Türkiye';
    venue.select.fire('change');
    assert.strictEqual(venue.field.value, 'ist');
    assert.strictEqual(event.field.value, 'nyc');
});

test('the code works with the page\'s plain options too, before or without the data', () => {
    const { doc } = fakePage();
    const { select, field } = formWithCode(doc, 'ev-region');
    const plain = doc.createElement('option');
    plain.textContent = 'Portland, Oregon, USA';
    plain.setAttribute('data-code', 'pdx');
    select.appendChild(plain);
    RegionChoices.wire(doc);
    select.value = 'Portland, Oregon, USA';
    select.fire('change');
    assert.strictEqual(field.value, 'pdx');
});

test('when the form is reset after a send, the code clears with the menu', async () => {
    const { doc } = fakePage();
    const { select, field } = formWithCode(doc, 'ev-region');
    RegionChoices.fill(doc, info);
    RegionChoices.wire(doc);
    select.value = 'Portland, Oregon, USA';
    select.fire('change');
    assert.strictEqual(field.value, 'pdx');

    // a form reset puts the menu back to "Choose a region" but leaves a hidden field as script set it
    select.value = '';
    doc.fire('reset');
    await new Promise(resolve => setTimeout(resolve, 5));
    assert.strictEqual(field.value, '');
});

test('a plain option with no code leaves the field empty rather than guessing', () => {
    const { doc } = fakePage();
    const { select, field } = formWithCode(doc, 'ev-region');
    select.value = 'Old A';
    RegionChoices.wire(doc);
    select.fire('change');
    assert.strictEqual(field.value, '');
});

test('after the menu is rebuilt, the code follows what is still chosen (or clears)', () => {
    const { doc } = fakePage();
    const { select, field } = formWithCode(doc, 'ev-region');
    select.value = 'Portland, Oregon, USA';
    RegionChoices.fill(doc, info);
    assert.strictEqual(field.value, 'pdx');

    select.value = 'Old A';
    RegionChoices.fill(doc, info);
    assert.strictEqual(select.value, '');
    assert.strictEqual(field.value, '');
});

// ---- the page ----

const html = fs.readFileSync(path.join(DOCS, 'add_event.html'), 'utf8');

test('the Add Event page loads the scripts, has the two menus and the chip line, and starts the fill', () => {
    assert.match(html, /<script src="regionInfo\.js"><\/script>/);
    assert.match(html, /<script src="regionChoices\.js"><\/script>/);
    assert.match(html, /RegionChoices\.boot\(\)/);
    assert.strictEqual((html.match(/<select[^>]*data-region-menu/g) || []).length, 2);
    assert.match(html, /<select id="ev-region"[^>]*data-region-menu/);
    assert.match(html, /<select id="vn-region"[^>]*data-region-menu/);
    assert.match(html, /<span data-region-chips>/);
});

test('the plain copies on the Add Event page (shown if the data cannot load) only list regions the data has', () => {
    // Each menu still starts with "Choose a region". A region missing from the plain list does no harm
    // (the data adds it), but one that is out of date or no longer in the data would show wrong text.
    for (const id of ['ev-region', 'vn-region']) {
        const menu = (html.match(new RegExp(`<select id="${id}"[\\s\\S]*?</select>`)) || [''])[0];
        const options = [...menu.matchAll(/<option[^>]*>([^<]*)<\/option>/g)].map(m => m[1]);
        assert.strictEqual(options[0], 'Choose a region');
        for (const option of options.slice(1)) {
            assert.ok(labels.includes(option), `#${id} has "${option}", which is not a region label in region_info.json`);
        }
    }
    const line = (html.match(/<span data-region-chips>([\s\S]*?)<\/span>\s*<\/p>/) || [, ''])[1];
    const chips = [...line.matchAll(/<span class="region-chip" style="--c: (#[0-9a-fA-F]{6})">([^<]*)<\/span>/g)].map(m => [m[2], m[1]]);
    const wanted = Object.values(info).map(region => `${region.name}|${region.colour.toLowerCase()}`);
    for (const [name, colour] of chips) {
        assert.ok(wanted.includes(`${name}|${colour.toLowerCase()}`), `the plain chip "${name}" ${colour} does not match region_info.json`);
    }
});

test('each form on the Add Event page has a hidden region-code field named for its menu, and the plain options carry the right codes', () => {
    for (const id of ['ev-region', 'vn-region']) {
        const form = (html.match(/<form\b[\s\S]*?<\/form>/g) || []).find(f => f.includes(`id="${id}"`)) || '';
        assert.ok(form, `no form holds #${id}`);
        const field = form.match(/<input[^>]*data-region-code="([^"]+)"[^>]*>/);
        assert.ok(field, `the form with #${id} has no data-region-code field`);
        assert.strictEqual(field[1], id);
        assert.match(field[0], /type="hidden"/);
        assert.match(field[0], /name="region_code"/);
        assert.match(field[0], /data-label="Region code"/);

        const menu = (html.match(new RegExp(`<select id="${id}"[\\s\\S]*?</select>`)) || [''])[0];
        for (const [, code, text] of menu.matchAll(/<option data-code="([^"]*)">([^<]*)<\/option>/g)) {
            assert.strictEqual(labels[Object.keys(info).indexOf(code)], text, `#${id}: the plain option "${text}" has the code "${code}", which does not match region_info.json`);
        }
    }
});
