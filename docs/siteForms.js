// Page behaviour for the Add Event page's forms (WEBSITE-70). Any
// <form data-web3form> gets: validation (the browser's required/url/email/date
// checks, plus end date not before start date), a "Sending..." state, and a
// success or error message. On failure the message offers the visitor's own text
// back as an email to send by hand. Sending itself is web3forms.js.
//
// Markup contract, per form:
//   data-subject="..."          email subject (adds " - <value of data-subject-field>" if set)
//   data-subject-field="Label"  the field whose value is appended to the subject
//   data-success="..."          message shown after a successful send
//   a control per field with name= and data-label="Label in the email"
//   an element with class form-status for messages
//   an input name="botcheck" (hidden checkbox, the honeypot)

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('form[data-web3form]').forEach(setUp);
});

function setUp(form) {
    const loadedAt = performance.now();
    const status = form.querySelector('.form-status');
    const button = form.querySelector('button[type="submit"]');
    const idleLabel = button.textContent;

    const show = (kind, html) => {
        status.className = `form-status is-${kind}`;
        status.setAttribute('role', kind === 'error' ? 'alert' : 'status');
        status.innerHTML = html;
        status.hidden = false;
    };

    // Clear a date-order complaint as soon as either date changes
    const start = form.querySelector('[data-start]'), end = form.querySelector('[data-end]');
    if (start && end) {
        const check = () => end.setCustomValidity(start.value && end.value && end.value < start.value ? 'The end date is before the start date.' : '');
        start.addEventListener('change', check);
        end.addEventListener('change', check);
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!form.reportValidity()) return;

        const fields = {};
        for (const control of form.elements) {
            if (!control.name || control.name === 'botcheck' || control.type === 'submit') continue;
            fields[control.dataset.label || control.name] = control.value;
        }
        const subject = form.dataset.subject + (form.dataset.subjectField && fields[form.dataset.subjectField] ? ` - ${fields[form.dataset.subjectField]}` : '');

        button.disabled = true;
        button.textContent = 'Sending...';
        status.hidden = true;

        const result = await web3forms.submit(fields, {
            subject,
            honeypot: form.elements.botcheck ? form.elements.botcheck.checked : false,
            elapsedMs: performance.now() - loadedAt,
        });

        button.disabled = false;
        button.textContent = idleLabel;

        if (result.ok) {
            show('success', form.dataset.success);
            form.reset();
            status.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        } else {
            const mailto = web3forms.mailtoFallback(fields, subject);
            show('error', `Sorry, that did not send. Please <a href="${mailto}">email it to ${web3forms.FALLBACK_EMAIL}</a> instead (your details are filled in).`);
        }
    });
}
