// Web3Forms (WEBSITE-70): sends form submissions (add an event, suggest a venue,
// site feedback) to info.artbasil@gmail.com through https://web3forms.com, so the
// site stays static with no backend. Web3Forms emails every field it receives, so
// each field is sent under a human-readable label.
//
// The access key below is not a secret: Web3Forms designs it to be public, and it
// can only send mail to the inbox it was created for. Until it is filled in, every
// submission fails with the "email us instead" message, so nothing looks like it
// worked when it did not.
//
// The pure parts (building the payload, reading the response, the spam checks, the
// email fallback) are testable in Node: `node --test tests/`.

(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.web3forms = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {

    const WEB3FORMS_ACCESS_KEY = '';   // paste the key from web3forms.com here (see WEBSITE-70)
    const ENDPOINT = 'https://api.web3forms.com/submit';
    const FALLBACK_EMAIL = 'info.artbasil@gmail.com';
    const MIN_FILL_MS = 2500;          // a person cannot read and fill a form faster than this

    // Fields as { 'Label shown in the email': value }. Empty ones are left out; the
    // submitter's address goes under `email`, which Web3Forms uses as the reply-to.
    function buildPayload(fields, { accessKey, subject, fromName = 'Art Basil website' }) {
        const payload = { access_key: accessKey, subject, from_name: fromName };
        for (const [label, value] of Object.entries(fields)) {
            const text = value === undefined || value === null ? '' : String(value).trim();
            if (text) payload[label] = text;
        }
        return payload;
    }

    // Web3Forms answers 200 with a JSON message on success. Anything else, or an
    // explicit success: false, is a failure.
    function interpretResponse(status, json) {
        const ok = status === 200 && !(json && json.success === false);
        return { ok, message: (json && json.message) || '' };
    }

    // Bots fill every input, including a hidden checkbox, and submit instantly.
    function looksLikeBot({ botcheck, elapsedMs }) {
        return Boolean(botcheck) || elapsedMs < MIN_FILL_MS;
    }

    // If sending fails, give the visitor their own message back as an email to send by hand
    function mailtoFallback(fields, subject, email = FALLBACK_EMAIL) {
        const body = Object.entries(fields)
            .filter(([, v]) => v !== undefined && v !== null && String(v).trim())
            .map(([k, v]) => `${k}: ${String(v).trim()}`)
            .join('\n');
        return `mailto:${email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    }

    // Sends one submission. `fetchImpl` is injectable so tests can fake the network.
    // Resolves to { ok, message, spam }; never rejects.
    async function submit(fields, { subject, honeypot = false, elapsedMs = Infinity, accessKey = WEB3FORMS_ACCESS_KEY, fetchImpl } = {}) {
        if (looksLikeBot({ botcheck: honeypot, elapsedMs })) {
            return { ok: true, message: '', spam: true };          // look successful, send nothing
        }
        if (!accessKey) {
            return { ok: false, message: 'The form is not set up yet.', spam: false };
        }
        const doFetch = fetchImpl || (typeof fetch === 'function' ? fetch : null);
        if (!doFetch) return { ok: false, message: 'This browser cannot send the form.', spam: false };
        try {
            const response = await doFetch(ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
                body: JSON.stringify(buildPayload(fields, { accessKey, subject })),
            });
            let json = null;
            try { json = await response.json(); } catch (e) { /* not JSON */ }
            return { ...interpretResponse(response.status, json), spam: false };
        } catch (e) {
            return { ok: false, message: 'Could not reach the form service.', spam: false };
        }
    }

    return { ENDPOINT, FALLBACK_EMAIL, MIN_FILL_MS, buildPayload, interpretResponse, looksLikeBot, mailtoFallback, submit };
}));
