// Cursor & effects (WEBSITE-61): the visitor can pick a mouse effect (Kid Pix
// stamps, marker line, pixel squares or none) and a cursor (normal, sticker
// arrow or blob dot) from a small panel on every page. The choice is kept in
// localStorage. Effects are drawn on one fixed canvas and only run while there is
// something to draw; they never run for touch input, and default to off for
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

    function cursorCss(cursor, accent) {
        if (cursor === 'sticker') {
            const link = svgUri(arrowSvg(accent || YELLOW));
            return `html{cursor:${svgUri(arrowSvg('#fff'))} 4 3,auto}` +
                `:is(${CLICKABLE}):not(:disabled){cursor:${link} 4 3,pointer!important}` +
                `input:not([type="checkbox"]):not([type="radio"]):not([type="submit"]),textarea{cursor:text!important}`;
        }
        if (cursor === 'dot') {
            return `html{cursor:${svgUri(dotSvg(accent || YELLOW))} 16 16,auto}` +
                `:is(${CLICKABLE}):not(:disabled){cursor:${svgUri(dotSvg('#fff'))} 16 16,pointer!important}` +
                `input:not([type="checkbox"]):not([type="radio"]):not([type="submit"]),textarea{cursor:text!important}`;
        }
        return '';
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
        const applyCursor = () => { style.textContent = cursorCss(settings.cursor, accent); };
        applyCursor();

        // ---- canvas effects
        const canvas = document.createElement('canvas');
        canvas.setAttribute('aria-hidden', 'true');
        canvas.style.cssText = 'position:fixed;inset:0;width:100vw;height:100vh;pointer-events:none;z-index:9999';
        document.body.append(canvas);
        const ctx = canvas.getContext('2d');
        let W = 0, H = 0;
        const resize = () => { const dpr = window.devicePixelRatio || 1; W = innerWidth; H = innerHeight; canvas.width = W * dpr; canvas.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); };
        resize();
        addEventListener('resize', resize);

        const rnd = (a, b) => a + Math.random() * (b - a);
        const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
        let items = [], pts = [], last = null, running = false, t0 = 0;

        const far = (x, y, min) => { if (!last) { last = { x, y }; return true; } if (Math.hypot(x - last.x, y - last.y) < min) return false; last = { x, y }; return true; };
        const stamp = (x, y, vx, vy) => ({ x, y, vx, vy, rot: rnd(0, 6.28), spin: rnd(-0.06, 0.06), life: 1, kind: pick(['star', 'heart', 'zig', 'dot', 'plus']), s: rnd(7, 13), c: pickColour(accent) });
        function glyph(kind, s) {
            ctx.lineWidth = 3; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.beginPath();
            if (kind === 'star') { for (let i = 0; i < 10; i++) { const r = i % 2 ? s * 0.45 : s, a = (i / 10) * 6.283 - 1.57; ctx.lineTo(Math.cos(a) * r, Math.sin(a) * r); } ctx.closePath(); ctx.fill(); }
            else if (kind === 'heart') { ctx.moveTo(0, s * 0.8); ctx.bezierCurveTo(-s * 1.4, -s * 0.2, -s * 0.5, -s * 1.1, 0, -s * 0.3); ctx.bezierCurveTo(s * 0.5, -s * 1.1, s * 1.4, -s * 0.2, 0, s * 0.8); ctx.fill(); }
            else if (kind === 'zig') { ctx.moveTo(-s, 0); ctx.lineTo(-s / 2, -s / 2); ctx.lineTo(0, s / 2); ctx.lineTo(s / 2, -s / 2); ctx.lineTo(s, 0); ctx.stroke(); }
            else if (kind === 'plus') { ctx.moveTo(-s, 0); ctx.lineTo(s, 0); ctx.moveTo(0, -s); ctx.lineTo(0, s); ctx.stroke(); }
            else { ctx.arc(0, 0, s * 0.55, 0, 7); ctx.fill(); }
        }

        const FX = {
            stamps: {
                move(x, y) { if (far(x, y, 28)) items.push(stamp(x, y, rnd(-0.3, 0.3), rnd(0.1, 0.6))); },
                click(x, y) { for (let k = 0; k < 16; k++) { const a = (k / 16) * 6.283, s = rnd(1.5, 4); items.push(stamp(x, y, Math.cos(a) * s, Math.sin(a) * s)); } },
                draw(dt) { items = items.filter((i) => (i.life -= dt / 1.5) > 0); for (const i of items) { i.x += i.vx; i.y += i.vy; i.vy += 0.03; i.vx *= 0.985; i.rot += i.spin; ctx.save(); ctx.translate(i.x, i.y); ctx.rotate(i.rot); ctx.globalAlpha = Math.min(1, i.life * 2); ctx.fillStyle = ctx.strokeStyle = i.c; glyph(i.kind, i.s); ctx.restore(); } ctx.globalAlpha = 1; },
                busy: () => items.length > 0,
            },
            marker: {
                move(x, y) { pts.push({ x, y, t: performance.now(), c: accent || POP[Math.floor(performance.now() / 600) % POP.length] }); },
                draw() { const now = performance.now(); pts = pts.filter((p) => now - p.t < 1100); ctx.lineCap = ctx.lineJoin = 'round'; for (let i = 1; i < pts.length; i++) { const a = pts[i - 1], b = pts[i], age = (now - b.t) / 1100; if (Math.hypot(b.x - a.x, b.y - a.y) > 120) continue; ctx.strokeStyle = b.c; ctx.globalAlpha = 0.85 * (1 - age); ctx.lineWidth = 10 * (1 - age * 0.6); ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); } ctx.globalAlpha = 1; },
                busy: () => pts.length > 0,
            },
            pixels: {
                move(x, y) { const g = 14, cx = Math.floor(x / g) * g, cy = Math.floor(y / g) * g; const hit = items.find((i) => i.x === cx && i.y === cy); if (hit) hit.life = 1; else items.push({ x: cx, y: cy, life: 1, c: pickColour(accent) }); },
                draw(dt) { items = items.filter((i) => (i.life -= dt / 0.9) > 0); for (const i of items) { ctx.globalAlpha = Math.min(1, i.life * 1.8); ctx.fillStyle = i.c; ctx.fillRect(i.x, i.y, 14, 14); ctx.fillStyle = '#111'; ctx.fillRect(i.x + 14, i.y + 2, 2, 14); ctx.fillRect(i.x + 2, i.y + 14, 14, 2); } ctx.globalAlpha = 1; },
                busy: () => items.length > 0,
            },
        };

        function loop(now) {
            const dt = Math.min(0.05, (now - t0) / 1000); t0 = now;
            ctx.clearRect(0, 0, W, H);
            const fx = FX[settings.effect];
            if (!fx) { running = false; return; }
            fx.draw(dt);
            if (fx.busy()) requestAnimationFrame(loop); else running = false;   // stop when nothing is left to draw
        }
        function wake() { if (!running) { running = true; t0 = performance.now(); requestAnimationFrame(loop); } }
        function reset() { items = []; pts = []; last = null; ctx.clearRect(0, 0, W, H); }

        addEventListener('pointermove', (e) => { if (e.pointerType === 'touch') return; const fx = FX[settings.effect]; if (fx) { fx.move(e.clientX, e.clientY); wake(); } });
        addEventListener('pointerdown', (e) => { if (e.pointerType === 'touch') return; const fx = FX[settings.effect]; if (fx && fx.click) { fx.click(e.clientX, e.clientY); wake(); } });

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

    return { EFFECTS, CURSORS, DEFAULTS, STORAGE_KEY, POP, sanitize, cursorCss, pickColour, init };
}));
