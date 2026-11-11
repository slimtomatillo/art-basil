// Map choice - on an iPhone, iPad or Mac, clicking a "Map" link asks which app to open: Apple Maps or
// Google Maps. Everywhere else the link goes straight to Google Maps and this file does nothing.
//
//   window.mapChoice.attach(anchorElement, mapLink)   // mapLink: one entry of venueAddresses.mapLinks()
//
// The link keeps its Google Maps href, so it still works without JavaScript, with a middle or
// Ctrl/Cmd-click, and for anyone not on an Apple device. Used by the event rows (tableRenderer.js), the
// venue directory (venuesRenderer.js) and the map pin popups (mapView.js).

(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.mapChoice = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {

    let openMenu = null; // { menu, anchor, close }

    function closeMenu(returnFocus) {
        if (!openMenu) return;
        const { menu, anchor, close } = openMenu;
        openMenu = null;
        close();
        if (menu.remove) menu.remove();
        if (returnFocus && anchor.focus) anchor.focus();
    }

    function item(doc, text, href) {
        const a = doc.createElement('a');
        a.className = 'map-choice-item';
        a.href = href;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
        a.setAttribute('role', 'menuitem');
        a.textContent = text;
        a.addEventListener('click', () => closeMenu(false));
        return a;
    }

    function show(anchor, link, doc, win) {
        closeMenu(false);
        const menu = doc.createElement('div');
        menu.className = 'map-choice';
        menu.setAttribute('role', 'menu');
        menu.setAttribute('aria-label', 'Open in');
        const apple = item(doc, 'Apple Maps', link.appleHref);
        const google = item(doc, 'Google Maps', link.href);
        menu.append(apple, google);
        doc.body.append(menu);

        // Just under the link, kept on screen
        const rect = anchor.getBoundingClientRect();
        const width = menu.offsetWidth || 150;
        const left = Math.max(8, Math.min(rect.left, (win.innerWidth || 360) - width - 8));
        menu.style.left = left + 'px';
        menu.style.top = (rect.bottom + 4) + 'px';

        const onKey = e => {
            if (e.key === 'Escape') { closeMenu(true); return; }
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                e.preventDefault();
                (doc.activeElement === apple ? google : apple).focus();
            }
        };
        const onOutside = e => { if (!menu.contains(e.target) && e.target !== anchor) closeMenu(false); };
        const onAway = () => closeMenu(false);
        doc.addEventListener('keydown', onKey);
        doc.addEventListener('click', onOutside, true);
        win.addEventListener('scroll', onAway, true);
        win.addEventListener('resize', onAway);
        openMenu = {
            menu, anchor,
            close() {
                doc.removeEventListener('keydown', onKey);
                doc.removeEventListener('click', onOutside, true);
                win.removeEventListener('scroll', onAway, true);
                win.removeEventListener('resize', onAway);
            },
        };
        apple.focus();
    }

    /** Make `anchor` offer Apple Maps and Google Maps on an Apple device; a no-op elsewhere. The
     *  browser objects are parameters so this can be tested without a browser. */
    function attach(anchor, link, env) {
        const win = (env && env.window) || (typeof window !== 'undefined' ? window : null);
        const doc = (env && env.document) || (typeof document !== 'undefined' ? document : null);
        const nav = (env && env.navigator) || (typeof navigator !== 'undefined' ? navigator : null);
        const addresses = win && win.venueAddresses;
        if (!win || !doc || !link || !link.appleHref || !addresses || !addresses.isAppleDevice(nav)) return false;
        anchor.setAttribute('aria-haspopup', 'menu');
        anchor.addEventListener('click', e => {
            // A middle click or Ctrl/Cmd/Shift-click means "open it in a new tab": leave that alone
            if (e.button > 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
            e.preventDefault();
            show(anchor, link, doc, win);
        });
        return true;
    }

    return { attach, closeMenu };
}));
