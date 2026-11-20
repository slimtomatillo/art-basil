// Google Analytics, loaded on the live site only. Every page includes this one file instead of its own
// copy of Google's snippet. On any other host (localhost while developing, a github.io preview, a file
// opened from disk) Google's script is never fetched, so testing the site doesn't count as visits.
//
// `gtag` and `dataLayer` are defined everywhere, so code that calls gtag() keeps working off the live
// site; there the calls just go nowhere.

(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.artBasilAnalytics = factory();
        root.artBasilAnalytics.start(root, root.document);
    }
}(typeof self !== 'undefined' ? self : this, function () {
    const MEASUREMENT_ID = 'G-G06G4L1YGN';
    const LIVE_HOSTS = ['artbasil.info', 'www.artbasil.info'];

    function isLiveHost(hostname) {
        return LIVE_HOSTS.includes(String(hostname || '').toLowerCase());
    }

    // Sets up gtag on `win`; on the live site, also adds Google's script to `doc`. Returns true if it did.
    function start(win, doc) {
        win.dataLayer = win.dataLayer || [];
        win.gtag = win.gtag || function () { win.dataLayer.push(arguments); };
        if (!isLiveHost(win.location && win.location.hostname)) return false;

        const script = doc.createElement('script');
        script.async = true;
        script.src = 'https://www.googletagmanager.com/gtag/js?id=' + MEASUREMENT_ID;
        doc.head.appendChild(script);
        win.gtag('js', new Date());
        win.gtag('config', MEASUREMENT_ID);
        return true;
    }

    return { MEASUREMENT_ID, LIVE_HOSTS, isLiveHost, start };
}));
