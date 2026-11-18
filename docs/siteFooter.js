// The footer on every page (WEBSITE-128): who we are not, and where the details come from. One source for
// the wording, so it cannot drift between the pages. A page includes this script at the end of its <body>.
(function (root, factory) {
    if (typeof module === 'object' && module.exports) module.exports = factory();
    else {
        const footer = factory();
        root.siteFooter = footer;
        if (root.document) footer.mount(root.document);
    }
}(typeof self !== 'undefined' ? self : this, function () {
    const TEXT = 'Art Basil is an independent guide and isn\'t affiliated with Art Basel or endorsed by any of the venues listed. ' +
        'Details come from each venue\'s own site, so check with them before you visit.';

    // Add the footer to the end of the page, once (a second call, or a footer already there, changes nothing)
    function mount(doc) {
        if (!doc || !doc.body || doc.querySelector('footer.site-footer')) return null;
        const footer = doc.createElement('footer');
        footer.className = 'site-footer';
        const line = doc.createElement('p');
        line.textContent = TEXT;
        footer.append(line);
        doc.body.append(footer);
        return footer;
    }

    return { TEXT, mount };
}));
