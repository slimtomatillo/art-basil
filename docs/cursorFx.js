// Cursor & effects (WEBSITE-61): the visitor can pick a mouse effect (Kid Pix
// stamps, marker line, pixel squares or none) and a cursor (normal, sticker
// arrow or blob dot) from a small panel on every page. The choice is kept in
// localStorage. Effects are small elements animated with the Web Animations
// API (no full-page canvas); they never run for touch input, and default to off for
// visitors who prefer reduced motion. The pure parts (validating a saved choice,
// building the cursor CSS) are testable in Node: `node --test tests/`.

(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.cursorFx = factory();
        if (typeof document !== 'undefined') {
            if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', root.cursorFx.init);
            else root.cursorFx.init();
        }
    }
}(typeof self !== 'undefined' ? self : this, function () {

    const EFFECTS = [['stamps', 'Kid Pix stamps'], ['marker', 'Marker line'], ['pixels', 'Pixel squares'], ['off', 'Off']];
    const CURSORS = [['normal', 'Normal'], ['sticker', 'Sticker'], ['dot', 'Blob dot']];
    const DEFAULTS = { effect: 'pixels', cursor: 'sticker' };
    const STORAGE_KEY = 'artbasil.fx';
    const POP = ['#14806b', '#c4520f', '#3358d6', '#8f3fc0', '#c93631', '#b8227a', '#00748f', '#ffc61a', '#5f7a0a', '#1c78c0'];
    const YELLOW = '#ffd23f';

    // A saved choice is only trusted if it is one of the known options
    function sanitize(raw) {
        const out = { ...DEFAULTS };
        let explicit = false;
        if (raw && typeof raw === 'object') {
            if (EFFECTS.some(([v]) => v === raw.effect)) { out.effect = raw.effect; explicit = true; }
            if (CURSORS.some(([v]) => v === raw.cursor)) out.cursor = raw.cursor;
        }
        return { settings: out, explicitEffect: explicit };
    }

    const svgUri = (svg) => `url("data:image/svg+xml;utf8,${encodeURIComponent(svg)}")`;
    const arrowSvg = (fill) => `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32"><path d="M6 5 L6 26 L11.5 21 L15.5 30 L19.5 28.3 L15.5 19.5 L23 19.5 Z" fill="#111" stroke="#111" stroke-width="3" stroke-linejoin="round"/><path d="M4 3 L4 24 L9.5 19 L13.5 28 L17.5 26.3 L13.5 17.5 L21 17.5 Z" fill="${fill}" stroke="#111" stroke-width="2.4" stroke-linejoin="round"/></svg>`;
    const dotSvg = (fill) => `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32"><circle cx="18" cy="18" r="9" fill="#111"/><circle cx="16" cy="16" r="9" fill="${fill}" stroke="#111" stroke-width="2.4"/><circle cx="12.5" cy="12.5" r="2.4" fill="#fff" opacity=".75"/></svg>`;

    // Things that should show the "clickable" version of the cursor
    const CLICKABLE = 'a[href], button, label, select, summary, [role="button"], input[type="checkbox"], input[type="radio"], input[type="submit"], .tag-chip, .region-blob, .filter-dropdown-toggle, .notify-button, .filter-option';
    // Fields where the real text cursor is kept
    const TEXT_FIELDS = 'input:not([type="checkbox"]):not([type="radio"]):not([type="submit"]), textarea';

    // The two images (resting and over-a-link) and their hotspots for a cursor choice
    function cursorShapes(cursor, accent) {
        if (cursor === 'sticker') return { base: [arrowSvg('#fff'), 4, 3], link: [arrowSvg(accent || YELLOW), 4, 3] };
        if (cursor === 'dot') return { base: [dotSvg(accent || YELLOW), 16, 16], link: [dotSvg('#fff'), 16, 16] };
        return null;
    }

    // The sticker and dot cursors are not browser cursors: browsers flash a custom
    // cursor image as the pointer moves (it is re-set on every move), so the real
    // cursor is hidden and a small element follows the pointer instead (see init).
    // The text cursor is kept inside text fields.
    // `cursor: none` is not used: on macOS some browsers only hide the cursor until
    // the next mouse move, so the arrow reappears for a moment on every move (a ghost
    // flickering behind the drawn cursor). A 1x1 transparent image stays hidden.
    const INVISIBLE = 'url("data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7") 0 0,none';
    function cursorCss(cursor) {
        if (!cursorShapes(cursor)) return '';
        return `html.fx-own-cursor,html.fx-own-cursor *{cursor:${INVISIBLE}!important}` +
            `html.fx-own-cursor :is(${TEXT_FIELDS}){cursor:text!important}`;
    }

    // On a region page most of the colour is the region's accent, with some of the
    // pop palette mixed in; elsewhere it is the full palette.
    function pickColour(accent, rand = Math.random) {
        if (accent && rand() < 0.65) return accent;
        return POP[Math.floor(rand() * POP.length)];
    }

    // ------------------------------------------------------------------ browser
    function init() {
        let saved = null;
        try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY)); } catch (e) { /* storage blocked or bad JSON */ }
        const { settings, explicitEffect } = sanitize(saved);
        const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (reduced && !explicitEffect) settings.effect = 'off';

        const cssVar = getComputedStyle(document.body).getPropertyValue('--region-c').trim();
        const accent = /^#[0-9a-f]{6}$/i.test(cssVar) && cssVar.toLowerCase() !== '#111111' && cssVar !== '#111' ? cssVar : null;

        const style = document.createElement('style');
        document.head.append(style);
        // ---- sticker / dot cursor: an element that follows the pointer
        const root = document.documentElement;
        const canOwnCursor = matchMedia('(hover: hover) and (pointer: fine)').matches;
        const own = document.createElement('div');
        own.className = 'fx-own-cursor-img';
        own.setAttribute('aria-hidden', 'true');
        own.hidden = true;
        document.body.append(own);
        let hotspot = null;
        const applyCursor = () => {
            const shapes = canOwnCursor ? cursorShapes(settings.cursor, accent) : null;
            hotspot = shapes ? [shapes.base[1], shapes.base[2]] : null;
            style.textContent = shapes ? cursorCss(settings.cursor) : '';
            root.classList.toggle('fx-own-cursor', Boolean(shapes));
            own.hidden = true;                                   // shown again on the next move
            own.innerHTML = shapes ? `<span class="rest">${shapes.base[0]}</span><span class="link">${shapes.link[0]}</span>` : '';
        };
        applyCursor();
        addEventListener('pointermove', (e) => {
            if (!hotspot || e.pointerType === 'touch') return;
            const target = e.target instanceof Element ? e.target : null;
            if (target && target.closest(TEXT_FIELDS)) { own.hidden = true; return; }
            const link = target && target.closest(CLICKABLE);
            own.hidden = false;
            own.classList.toggle('is-link', Boolean(link) && !link.matches(':disabled'));
            own.style.transform = `translate3d(${e.clientX - hotspot[0]}px,${e.clientY - hotspot[1]}px,0)`;
        }, { passive: true });
        root.addEventListener('mouseleave', () => { own.hidden = true; });

        // ---- effects
        // Each effect is a handful of small, short-lived elements animated with the Web
        // Animations API (no timers, no per-frame work). They used to be drawn on one
        // full-viewport canvas, which repainted the whole page on every pointer move and
        // made Chrome on macOS flash the system cursor.
        const live = new Set();
        const rnd = (a, b) => a + Math.random() * (b - a);
        const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
        let last = null;

        // Adds `el` to the page, plays `keyframes` on it, and removes it when they finish
        function play(el, keyframes, duration, onDone) {
            if (!el.isConnected) document.body.append(el);
            const anim = el.animate(keyframes, { duration, easing: 'linear' });
            live.add(anim);
            anim.onfinish = () => { live.delete(anim); el.remove(); if (onDone) onDone(); };
            return anim;
        }
        const bit = (css) => { const el = document.createElement('div'); el.className = 'fx-bit'; el.style.cssText = css; return el; };
        const far = (x, y, min) => { if (!last) { last = { x, y }; return true; } if (Math.hypot(x - last.x, y - last.y) < min) return false; last = { x, y }; return true; };

        // Glyphs are drawn in a box from -1.6 to 1.6, so one SVG shape serves any size
        const STAR = Array.from({ length: 10 }, (_, i) => { const r = i % 2 ? 0.45 : 1, a = (i / 10) * 6.283 - 1.57; return `${(Math.cos(a) * r).toFixed(3)},${(Math.sin(a) * r).toFixed(3)}`; }).join(' ');
        const GLYPHS = {
            star: (c) => `<polygon points="${STAR}" fill="${c}"/>`,
            heart: (c) => `<path d="M0 .8C-1.4 -.2 -.5 -1.1 0 -.3C.5 -1.1 1.4 -.2 0 .8Z" fill="${c}"/>`,
            zig: (c) => `<path d="M-1 0L-.5 -.5L0 .5L.5 -.5L1 0" fill="none" stroke="${c}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`,
            plus: (c) => `<path d="M-1 0L1 0M0 -1L0 1" fill="none" stroke="${c}" stroke-width="3" stroke-linecap="round" vector-effect="non-scaling-stroke"/>`,
            dot: (c) => `<circle r=".55" fill="${c}"/>`,
        };

        function stamp(x, y, vx, vy) {
            const kind = pick(Object.keys(GLYPHS)), size = rnd(7, 13) * 3.2, c = pickColour(accent);
            const el = bit(`width:${size}px;height:${size}px;margin:${-size / 2}px 0 0 ${-size / 2}px`);
            el.innerHTML = `<svg viewBox="-1.6 -1.6 3.2 3.2" width="${size}" height="${size}">${GLYPHS[kind](c)}</svg>`;
            // Work out the flight (it drifts, falls and spins over 1.5 s) as keyframes
            const spin = rnd(-0.06, 0.06);
            let px = x, py = y, rot = rnd(0, 6.28);
            const frames = [];
            for (let f = 0; f <= 90; f += 6) {
                frames.push({ transform: `translate3d(${px.toFixed(1)}px,${py.toFixed(1)}px,0) rotate(${rot.toFixed(2)}rad)`, opacity: Math.min(1, (1 - f / 90) * 2) });
                for (let k = 0; k < 6; k++) { px += vx; py += vy; vy += 0.03; vx *= 0.985; rot += spin; }
            }
            play(el, frames, 1500);
        }

        // Pixel squares: one per 14px grid cell, visiting a cell again keeps it lit
        const cells = new Map();
        const PIXEL_FADE = [{ opacity: 1 }, { opacity: 1, offset: 0.44 }, { opacity: 0 }];
        function lightCell(x, y) {
            const g = 14, cx = Math.floor(x / g) * g, cy = Math.floor(y / g) * g, key = `${cx},${cy}`;
            const cell = cells.get(key);
            if (cell) { live.delete(cell.anim); cell.anim.cancel(); cell.anim = play(cell.el, PIXEL_FADE, 900, () => cells.delete(key)); return; }
            const el = bit(`width:14px;height:14px;background:${pickColour(accent)};box-shadow:2px 2px 0 #111;transform:translate3d(${cx}px,${cy}px,0)`);
            cells.set(key, { el, anim: play(el, PIXEL_FADE, 900, () => cells.delete(key)) });
        }

        // Marker line: a thick rounded segment between each pair of nearby points, thinning as it fades
        function markerSegment(a, b) {
            const len = Math.hypot(b.x - a.x, b.y - a.y);
            const colour = accent || POP[Math.floor(performance.now() / 600) % POP.length];
            const el = bit(`width:${(len + 10).toFixed(1)}px;height:10px;margin:-5px 0 0 -5px;border-radius:5px;background:${colour};transform-origin:5px 50%`);   // 5px past each end = round caps
            const place = `translate3d(${a.x}px,${a.y}px,0) rotate(${Math.atan2(b.y - a.y, b.x - a.x).toFixed(3)}rad)`;
            play(el, [{ transform: `${place} scaleY(1)`, opacity: 0.85 }, { transform: `${place} scaleY(0.4)`, opacity: 0 }], 1100);
        }

        const FX = {
            stamps: {
                move(x, y) { if (far(x, y, 28)) stamp(x, y, rnd(-0.3, 0.3), rnd(0.1, 0.6)); },
                click(x, y) { for (let k = 0; k < 16; k++) { const a = (k / 16) * 6.283, s = rnd(1.5, 4); stamp(x, y, Math.cos(a) * s, Math.sin(a) * s); } },
            },
            marker: {
                move(x, y) {
                    const from = last, d = from ? Math.hypot(x - from.x, y - from.y) : 0;
                    if (from && d < 4) return;                  // too small to be worth an element
                    last = { x, y };
                    if (from && d <= 120) markerSegment(from, last);
                },
            },
            pixels: { move: lightCell },
        };

        function reset() {
            for (const anim of live) { if (anim.effect && anim.effect.target) anim.effect.target.remove(); anim.cancel(); }
            live.clear();
            cells.clear();
            last = null;
        }

        addEventListener('pointermove', (e) => { if (e.pointerType !== 'touch' && FX[settings.effect]) FX[settings.effect].move(e.clientX, e.clientY); });
        addEventListener('pointerdown', (e) => { if (e.pointerType !== 'touch' && FX[settings.effect] && FX[settings.effect].click) FX[settings.effect].click(e.clientX, e.clientY); });

        // ---- settings panel
        const wrap = document.createElement('div');
        wrap.className = 'fx-settings';
        const group = (name, legend, options) => `<fieldset class="fx-group"><legend>${legend}</legend>` +
            options.map(([v, l]) => `<label class="fx-pill"><input type="radio" name="fx-${name}" value="${v}"${settings[name] === v ? ' checked' : ''}><span>${l}</span></label>`).join('') + '</fieldset>';
        wrap.innerHTML =
            '<button class="fx-toggle" type="button" aria-haspopup="true" aria-expanded="false" aria-controls="fxPanel" title="Cursor and effects">' +
            '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3.5 L5 18 L9 14.6 L11.6 20.5 L14 19.4 L11.4 13.6 L16.5 13.6 Z" fill="#fff" stroke="#111" stroke-width="2" stroke-linejoin="round"/><path d="M18.5 3 L19.3 5.2 L21.5 6 L19.3 6.8 L18.5 9 L17.7 6.8 L15.5 6 L17.7 5.2 Z" fill="#ffd23f" stroke="#111" stroke-width="1.2" stroke-linejoin="round"/></svg>' +
            '<span class="visually-hidden">Cursor and effects</span></button>' +
            `<div class="fx-panel" id="fxPanel" role="group" aria-label="Cursor and effects" hidden>${group('effect', 'Effect', EFFECTS)}${group('cursor', 'Cursor', CURSORS)}</div>`;
        document.body.append(wrap);

        const toggle = wrap.querySelector('.fx-toggle'), panel = wrap.querySelector('.fx-panel');
        const setOpen = (open) => { panel.hidden = !open; toggle.setAttribute('aria-expanded', String(open)); };
        toggle.addEventListener('click', () => setOpen(panel.hidden));
        document.addEventListener('click', (e) => { if (!panel.hidden && !wrap.contains(e.target)) setOpen(false); });
        document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !panel.hidden) { setOpen(false); toggle.focus(); } });
        wrap.addEventListener('change', (e) => {
            const input = e.target;
            if (input.name === 'fx-effect') { settings.effect = input.value; reset(); }
            if (input.name === 'fx-cursor') { settings.cursor = input.value; applyCursor(); }
            try { localStorage.setItem(STORAGE_KEY, JSON.stringify(settings)); } catch (err) { /* not saved */ }
        });
    }

    return { EFFECTS, CURSORS, DEFAULTS, STORAGE_KEY, POP, sanitize, cursorShapes, cursorCss, pickColour, init };
}));
