// Run with: node --test tests/
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const siteFooter = require('../docs/siteFooter.js');

const DOCS = path.join(__dirname, '../docs');

// Every page under docs/ (the pages, not the data)
function pages(dir = DOCS) {
    return fs.readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) return entry.name === 'data' || entry.name === 'images' ? [] : pages(full);
        return entry.name.endsWith('.html') ? [full] : [];
    });
}

// A page with just enough of a document to add a footer to
function fakeDocument(existing = false) {
    const made = [];
    const element = tag => ({ tag, className: '', textContent: '', children: [], append(...kids) { this.children.push(...kids); } });
    const body = element('body');
    return {
        body, made,
        createElement: tag => { const el = element(tag); made.push(el); return el; },
        querySelector: selector => (existing && selector === 'footer.site-footer' ? {} : null),
    };
}

test('the footer says we are independent of Art Basel and of the venues, and to check with the venue', () => {
    assert.match(siteFooter.TEXT, /independent/);
    assert.match(siteFooter.TEXT, /isn't affiliated with Art Basel\b/);
    assert.match(siteFooter.TEXT, /endorsed by any of the venues/);
    assert.match(siteFooter.TEXT, /check with them before you visit/);
});

test('mount adds one footer with the wording at the end of the page, and only once', () => {
    const doc = fakeDocument();
    const footer = siteFooter.mount(doc);
    assert.strictEqual(footer.tag, 'footer');
    assert.strictEqual(footer.className, 'site-footer');
    assert.strictEqual(footer.children[0].textContent, siteFooter.TEXT);
    assert.deepStrictEqual(doc.body.children, [footer]);
    // a page that already has the footer is left alone, and so is a page with no body
    const again = fakeDocument(true);
    assert.strictEqual(siteFooter.mount(again), null);
    assert.deepStrictEqual(again.body.children, []);
    assert.strictEqual(siteFooter.mount({ body: null }), null);
    assert.strictEqual(siteFooter.mount(null), null);
});

test('every page loads the footer script from the right place, so a new page cannot go without it', () => {
    const found = pages();
    assert.ok(found.length >= 19, `only ${found.length} pages found`);
    const missing = [];
    for (const page of found) {
        const rel = path.relative(DOCS, page);
        // the 404 page is served from any depth, so it uses an absolute path
        const expected = rel === '404.html' ? '/siteFooter.js' : path.relative(path.dirname(page), path.join(DOCS, 'siteFooter.js'));
        const html = fs.readFileSync(page, 'utf8');
        if (!html.includes(`<script src="${expected}"></script>`)) missing.push(`${rel} (needs ${expected})`);
    }
    assert.deepStrictEqual(missing, [], 'add <script src="..."></script> for siteFooter.js before </body>');
});
