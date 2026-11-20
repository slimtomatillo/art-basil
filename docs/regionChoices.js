// The Add Event page's regions: the "We cover" chips and the two Region menus (the event form and the
// venue-suggestion form), drawn from docs/data/region_info.json so a new region appears with no edit to
// the page. The page keeps plain, hand-written copies of them for when the data cannot load; they are
// replaced as soon as it does.
//
//   <span data-region-chips>...</span>     gets one coloured chip per region
//   <select data-region-menu>...</select>  gets one option per region, after its first "Choose a region"
//   <input type="hidden" data-region-code="ev-region">  holds the code ("pdx") of the region picked in the menu
//                                                       with that id, so the submission email carries it too
//
// The chosen option's text is what the form sends (siteForms.js), so it carries the place:
// "Portland, Oregon, USA". The code is a convenience for whoever adds the show, not a checked fact: the
// visitor picked the region themselves, and a hidden field can be wrong or changed, so the code is
// always checked against the venue (SUBMISSIONS.md).
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
            option.setAttribute('data-code', code);
            return option;
        });
        select.replaceChildren(...(first ? [first] : []), ...options);
        select.value = options.some(option => option.textContent === chosen) ? chosen : '';
    }

    // The code of the region picked in a menu: '' for "Choose a region", or for a plain option with no code
    function chosenCode(select) {
        const option = Array.from(select.children).find(child => child.textContent === select.value);
        return (option && option.getAttribute('data-code')) || '';
    }

    // Put each menu's chosen code into the hidden field that names it
    function syncCodes(doc) {
        const fields = Array.from(doc.querySelectorAll('[data-region-code]'));
        doc.querySelectorAll('select[data-region-menu]').forEach(select => {
            const code = chosenCode(select);
            fields.filter(field => field.getAttribute('data-region-code') === select.getAttribute('id'))
                .forEach(field => { field.value = code; });
        });
    }

    // Keep the codes in step with the menus. Done as soon as the page loads, so it works with the plain
    // options too if the data cannot load.
    function wire(doc) {
        doc.querySelectorAll('select[data-region-menu]').forEach(select => select.addEventListener('change', () => syncCodes(doc)));
        // After a send the form is reset (siteForms.js). The menu goes back to "Choose a region" but a hidden
        // field that was set from script keeps its value through a reset, so clear the code to match. The
        // reset happens just after this event, hence the timer.
        if (doc.addEventListener) doc.addEventListener('reset', () => setTimeout(() => syncCodes(doc), 0), true);
        syncCodes(doc);
    }

    function fill(doc, info) {
        doc.querySelectorAll('[data-region-chips]').forEach(container => fillChips(container, info));
        doc.querySelectorAll('select[data-region-menu]').forEach(select => fillMenu(select, info));
        syncCodes(doc);
    }

    // On the page: fetch the data, then replace the plain copies. If it cannot load they stay.
    function boot() {
        wire(document);
        return RegionInfo.load('data/region_info.json')
            .then(info => fill(document, info))
            .catch(error => { console.error('The region list could not load; the plain one stays.', error); });
    }

    return { fillChips, fillMenu, chosenCode, syncCodes, wire, fill, boot };
}));
