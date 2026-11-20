// A tiny stand-in for a web page, just enough for the region picker and the Add Event page's region
// lists to draw into without a browser. Used by the tests; not part of the site.

class FakeText {
    constructor(text) { this.nodeType = 3; this.textContent = text; this.children = []; }
    all() { return []; }
}

class FakeElement {
    constructor(doc, tag) {
        this.ownerDocument = doc;
        this.nodeType = 1;
        this.tagName = tag.toUpperCase();
        this.children = [];
        this.attributes = {};
        this.listeners = {};
        this.style = { props: {}, setProperty(name, value) { this.props[name] = value; } };
        this.classes = new Set();
        this.hidden = false;
        this.textContent = '';
        this.value = '';
    }
    get firstChild() { return this.children[0] || null; }
    set className(value) { this.classes = new Set(String(value).split(/\s+/).filter(Boolean)); }
    get className() { return [...this.classes].join(' '); }
    get classList() {
        const classes = this.classes;
        return { toggle(name, on) { (on === undefined ? !classes.has(name) : on) ? classes.add(name) : classes.delete(name); }, contains: name => classes.has(name) };
    }
    setAttribute(name, value) { this.attributes[name] = String(value); }
    getAttribute(name) { return name in this.attributes ? this.attributes[name] : null; }
    hasAttribute(name) { return name in this.attributes; }
    appendChild(child) { this.children.push(child); return child; }
    replaceChildren(...kids) { this.children = [...kids]; }
    addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); }
    fire(type) { (this.listeners[type] || []).forEach(fn => fn({ target: this })); }
    // every element below this one, this one first
    all() { return [this, ...this.children.flatMap(child => child.all())]; }
    find(predicate) { return this.all().filter(predicate); }
    // only the simple selectors the pages use here: "[attr]" and "tag[attr]"
    querySelectorAll(selector) {
        const [, tag, attr] = selector.match(/^([a-z]*)\[([a-z-]+)\]$/) || [];
        return this.all().filter(el => el.nodeType === 1 && (!tag || el.tagName === tag.toUpperCase()) && el.hasAttribute(attr));
    }
}

function fakePage() {
    const doc = {
        createElement: tag => new FakeElement(doc, tag),
        createTextNode: text => new FakeText(text),
    };
    doc.listeners = {};
    doc.addEventListener = (type, fn) => { (doc.listeners[type] = doc.listeners[type] || []).push(fn); };
    doc.fire = type => (doc.listeners[type] || []).forEach(fn => fn({ target: doc }));
    doc.body = new FakeElement(doc, 'body');
    doc.querySelectorAll = selector => doc.body.querySelectorAll(selector);
    return { doc, root: new FakeElement(doc, 'div') };
}

module.exports = { FakeElement, FakeText, fakePage };
