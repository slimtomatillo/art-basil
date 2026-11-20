// The Add Event page's regions: the "We cover" chips and the two Region menus (the event form and the
// venue-suggestion form), drawn from docs/data/region_info.json so a new region appears with no edit to
// the page. The page keeps plain, hand-written copies of them for when the data cannot load; they are
// replaced as soon as it does.
//
//   <span data-region-chips>...</span>     gets one coloured chip per region
//   <select data-region-menu>...</select>  gets one option per region, after its first "Choose a region"
//
// The chosen option's text is what the form sends (siteForms.js), so it carries the place:
// "Portland, Oregon, USA".
(function (root, factory) {
    if (typeof module === 'object' && module.exports) module.exports = factory(require('./regionInfo.js'));
    else root.RegionChoices = factory(root.RegionInfo);
}(typeof self !== 'undefined' ? self : this, function (RegionInfo) {
    // One chip per region, in the file's order, with a space between (the page's chips sit in a line of text)
    function fillChips(container, info) {
        const doc = container.ownerDocument;
        const kids = [];
        Object.keys(info).forEach((code, index) => {
            const chip = doc.createElement('span');
            chip.className = 'region-chip';
            chip.style.setProperty('--c', info[code].colour);
            chip.textContent = info[code].name;
            if (index) kids.push(doc.createTextNode(' '));
            kids.push(chip);
        });
        container.replaceChildren(...kids);
    }

    // The menu's first option ("Choose a region") stays; the rest become one option per region.
    // Whatever the visitor already picked stays picked if it is still there.
    function fillMenu(select, info) {
        const doc = select.ownerDocument;
        const chosen = select.value;
        const first = select.children[0];
        const options = Object.keys(info).map(code => {
            const option = doc.createElement('option');
            option.textContent = RegionInfo.menuLabel(info[code]);
            return option;
        });
        select.replaceChildren(...(first ? [first] : []), ...options);
        select.value = options.some(option => option.textContent === chosen) ? chosen : '';
    }

    function fill(doc, info) {
        doc.querySelectorAll('[data-region-chips]').forEach(container => fillChips(container, info));
        doc.querySelectorAll('select[data-region-menu]').forEach(select => fillMenu(select, info));
    }

    // On the page: fetch the data, then replace the plain copies. If it cannot load they stay.
    function boot() {
        return RegionInfo.load('data/region_info.json')
            .then(info => fill(document, info))
            .catch(error => { console.error('The region list could not load; the plain one stays.', error); });
    }

    return { fillChips, fillMenu, fill, boot };
}));
