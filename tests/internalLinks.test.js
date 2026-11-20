// Run with: node --test tests/
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const DOCS = path.join(__dirname, '../docs');

// Every page under docs/ (the pages, not the data, images or vendored libraries)
function pages(dir = DOCS) {
    return fs.readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) {
            return ['data', 'images', 'vendor'].includes(entry.name) ? [] : pages(full);
        }
        return entry.name.endsWith('.html') ? [full] : [];
    });
}

// A link that starts with two slashes means "same protocol, another host", so
// href="//pdx/index.html" points at a host called "pdx" and goes nowhere.
test('no page has a link or source that starts with two slashes', () => {
    const bad = [];
    for (const file of pages()) {
        const html = fs.readFileSync(file, 'utf8');
        for (const match of html.matchAll(/\b(?:href|src)\s*=\s*["'](\/\/[^"']*)["']/g)) {
            const line = html.slice(0, match.index).split('\n').length;
            bad.push(`${path.relative(DOCS, file)}:${line} ${match[1]}`);
        }
    }
    assert.deepStrictEqual(bad, [], `Links starting with // point at another host:\n${bad.join('\n')}`);
});
