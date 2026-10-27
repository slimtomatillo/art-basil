// Feedback form: the "?" button opens a dialog whose message is emailed to the
// site's inbox through Web3Forms (see web3forms.js, WEBSITE-70). The "sent"
// message only appears once the form service has accepted the message. If sending
// fails, the dialog says so and offers the visitor's text back as an email to send
// by hand. Needs web3forms.js loaded first.
document.addEventListener('DOMContentLoaded', function() {
    const feedbackButton = document.getElementById('feedbackButton');
    const feedbackModal = document.getElementById('feedbackModal');
    const feedbackClose = document.getElementById('feedbackClose');
    const feedbackForm = document.getElementById('feedbackForm');
    const feedbackSuccess = document.getElementById('feedbackSuccess');
    const submitButton = feedbackForm.querySelector('button[type="submit"]');
    const idleLabel = submitButton.textContent;
    let openedAt = 0;
    let closeTimer = null;

    // Hidden checkbox for bots (people never see or tick it) and a message area for failures
    const honeypot = document.createElement('input');
    honeypot.type = 'checkbox';
    honeypot.name = 'botcheck';
    honeypot.tabIndex = -1;
    honeypot.autocomplete = 'off';
    honeypot.setAttribute('aria-hidden', 'true');
    honeypot.style.display = 'none';
    const errorBox = document.createElement('div');
    errorBox.className = 'form-status is-error feedback-error';
    errorBox.setAttribute('role', 'alert');
    errorBox.hidden = true;
    feedbackForm.insertBefore(honeypot, submitButton);
    feedbackForm.insertBefore(errorBox, submitButton);

    // Open modal when feedback button is clicked
    feedbackButton.addEventListener('click', function() {
        clearTimeout(closeTimer);
        feedbackModal.style.display = 'block';
        // Reset form when opening
        feedbackForm.reset();
        feedbackForm.style.display = 'block';
        feedbackSuccess.style.display = 'none';
        errorBox.hidden = true;
        openedAt = performance.now();
    });

    // Close modal when X is clicked
    feedbackClose.addEventListener('click', function() {
        closeFeedbackModal();
    });

    // Close modal when clicking outside of it
    feedbackModal.addEventListener('click', function(e) {
        if (e.target === feedbackModal) {
            closeFeedbackModal();
        }
    });

    // Close modal when pressing Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && feedbackModal.style.display === 'block') {
            closeFeedbackModal();
        }
    });

    // Handle form submission
    feedbackForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        const formData = new FormData(feedbackForm);
        const fields = {
            'Feedback type': formData.get('feedbackType'),
            'Name': formData.get('feedbackName') || 'Anonymous',
            'email': formData.get('feedbackEmail'),
            'Message': formData.get('feedbackMessage'),
            'Page': window.location.pathname,
            'Browser': navigator.userAgent,
        };
        const subject = `Art Basil feedback: ${fields['Feedback type']}`;

        submitButton.disabled = true;
        submitButton.textContent = 'Sending...';
        errorBox.hidden = true;

        const result = await web3forms.submit(fields, {
            subject,
            honeypot: honeypot.checked,
            elapsedMs: performance.now() - openedAt,
        });

        submitButton.disabled = false;
        submitButton.textContent = idleLabel;

        if (result.ok) {
            feedbackForm.style.display = 'none';
            feedbackSuccess.style.display = 'block';
            // Auto-close after 5 seconds
            closeTimer = setTimeout(closeFeedbackModal, 5000);
        } else {
            const mailto = web3forms.mailtoFallback(fields, subject);
            errorBox.innerHTML = `Sorry, that did not send. Please <a href="${mailto}">email it to ${web3forms.FALLBACK_EMAIL}</a> instead (your message is filled in).`;
            errorBox.hidden = false;
        }
    });
});

// Function to close the feedback modal
function closeFeedbackModal() {
    const feedbackModal = document.getElementById('feedbackModal');
    const feedbackForm = document.getElementById('feedbackForm');
    const feedbackSuccess = document.getElementById('feedbackSuccess');

    feedbackModal.style.display = 'none';
    feedbackForm.style.display = 'block';
    feedbackSuccess.style.display = 'none';
}
