// Feedback Form Functionality
document.addEventListener('DOMContentLoaded', function() {
    const feedbackButton = document.getElementById('feedbackButton');
    const feedbackModal = document.getElementById('feedbackModal');
    const feedbackClose = document.getElementById('feedbackClose');
    const feedbackForm = document.getElementById('feedbackForm');
    const feedbackSuccess = document.getElementById('feedbackSuccess');

    // Open modal when feedback button is clicked
    feedbackButton.addEventListener('click', function() {
        feedbackModal.style.display = 'block';
        // Reset form when opening
        feedbackForm.reset();
        feedbackForm.style.display = 'block';
        feedbackSuccess.style.display = 'none';
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
    feedbackForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(feedbackForm);
        const feedbackData = {
            type: formData.get('feedbackType'),
            name: formData.get('feedbackName') || 'Anonymous',
            email: formData.get('feedbackEmail') || 'No email provided',
            message: formData.get('feedbackMessage'),
            timestamp: new Date().toISOString(),
            page: window.location.pathname,
            userAgent: navigator.userAgent
        };

        // Send feedback via email (using mailto as a simple solution)
        sendFeedback(feedbackData);
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

// Function to send feedback
function sendFeedback(feedbackData) {
    const feedbackForm = document.getElementById('feedbackForm');
    const feedbackSuccess = document.getElementById('feedbackSuccess');
    
    // Create email body
    const emailSubject = `Art Basil Feedback: ${feedbackData.type}`;
    const emailBody = `
Feedback Type: ${feedbackData.type}
Name: ${feedbackData.name}
Email: ${feedbackData.email}
Message: ${feedbackData.message}
Timestamp: ${feedbackData.timestamp}
Page: ${feedbackData.page}
User Agent: ${feedbackData.userAgent}
    `.trim();

    // Create mailto link
    const mailtoLink = `mailto:info.artbasil@gmail.com?subject=${encodeURIComponent(emailSubject)}&body=${encodeURIComponent(emailBody)}`;
    
    // Open email client
    window.open(mailtoLink);
    
    // Show success message
    feedbackForm.style.display = 'none';
    feedbackSuccess.style.display = 'block';
    
    // Auto-close after 5 seconds
    setTimeout(() => {
        closeFeedbackModal();
    }, 5000);
}

// Alternative: Send feedback to a webhook or API endpoint
// Uncomment and modify this function if you want to send feedback to a server instead of email
/*
async function sendFeedbackToServer(feedbackData) {
    try {
        const response = await fetch('/api/feedback', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(feedbackData)
        });
        
        if (response.ok) {
            return true;
        } else {
            throw new Error('Failed to send feedback');
        }
    } catch (error) {
        console.error('Error sending feedback:', error);
        return false;
    }
}
*/
