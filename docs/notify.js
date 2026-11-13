// Notify Modal and Google Calendar Functionality
let currentEvent = null;

// Event dates are calendar days at the venue ("YYYY-MM-DD"), not moments in time.
// new Date('YYYY-MM-DD') parses them as midnight UTC, so they must be read back in
// UTC too. Using local-time getters/formatting would shift the day for every viewer
// west of UTC (i.e. the whole US and Canada). Calendar days are never converted
// between time zones: Nov 12 is Nov 12 for everyone.
const CALENDAR_DATE_DISPLAY = { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' };

// Function to open the notify modal - make it globally accessible
window.openNotifyModal = function(event) {
    currentEvent = event;
    const notifyModal = document.getElementById('notifyModal');
    const eventTitle = document.getElementById('eventTitle');
    const eventVenue = document.getElementById('eventVenue');
    const eventDates = document.getElementById('eventDates');
    
    if (!notifyModal || !eventTitle || !eventVenue || !eventDates) {
        return;
    }
    
    // Populate event info
    eventTitle.textContent = event.name;
    eventVenue.textContent = `@ ${event.venue}`;
    
    // Format dates
    let datesText = '';
    let hasStartDate = event.dates.start && event.dates.start !== 'null';
    let hasEndDate = event.dates.end && event.dates.end !== 'null';
    
    if (hasStartDate) {
        const startDate = new Date(event.dates.start);
        // "Opened" for a show that is already open, by the venue's date (ISO dates compare as strings)
        const today = window.dataManager.regionToday(window.dataManager.getRegion());
        const label = String(event.dates.start).slice(0, 10) <= today ? 'Opened' : 'Opens';
        datesText += `${label}: ${startDate.toLocaleDateString('en-US', CALENDAR_DATE_DISPLAY)}`;
    }
    
    if (hasEndDate) {
        const endDate = new Date(event.dates.end);
        if (hasStartDate) {
            datesText += ` | Closes: ${endDate.toLocaleDateString('en-US', CALENDAR_DATE_DISPLAY)}`;
        } else {
            datesText += `Closes: ${endDate.toLocaleDateString('en-US', CALENDAR_DATE_DISPLAY)}`;
        }
    }
    
    if (!datesText) {
        datesText = 'Dates TBA';
    }
    
    eventDates.textContent = datesText;
    
    // Show modal
    notifyModal.style.display = 'block';
    
    // Reset form (the calendar chosen last time stays chosen)
    document.getElementById('calendarType').value = '';
    const provider = document.getElementById('calendarProvider');
    if (provider) provider.value = recalledProvider() || provider.options[0].value;
}

// The calendar a visitor used last, kept in this browser only (a convenience: the modal works without it)
const PROVIDER_KEY = 'artbasil.calendar';
function recalledProvider() {
    try {
        const saved = localStorage.getItem(PROVIDER_KEY);
        return window.calendarLinks.PROVIDERS.includes(saved) ? saved : null;
    } catch (e) {
        return null;
    }
}
function rememberProvider(provider) {
    try { localStorage.setItem(PROVIDER_KEY, provider); } catch (e) { /* private window or blocked storage */ }
}

// Function to close the notify modal - make it globally accessible
window.closeNotifyModal = function() {
    const notifyModal = document.getElementById('notifyModal');
    notifyModal.style.display = 'none';
    currentEvent = null;
}

// Initialize event listeners when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    const notifyModal = document.getElementById('notifyModal');
    const notifyClose = document.getElementById('notifyClose');
    const notifyForm = document.getElementById('notifyForm');

    if (!notifyModal || !notifyClose || !notifyForm) {
        return;
    }

    // Close modal when X is clicked
    notifyClose.addEventListener('click', function() {
        closeNotifyModal();
    });

    // Close modal when clicking outside of it
    notifyModal.addEventListener('click', function(e) {
        if (e.target === notifyModal) {
            closeNotifyModal();
        }
    });

    // Close modal when pressing Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && notifyModal.style.display === 'block') {
            closeNotifyModal();
        }
    });

    // Handle form submission
    notifyForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const calendarType = document.getElementById('calendarType').value;
        const provider = document.getElementById('calendarProvider').value;
        
        if (!calendarType) {
            alert('Please select a calendar event type');
            return;
        }
        
        if (!currentEvent) {
            alert('No event selected');
            return;
        }
        
        rememberProvider(provider);
        window.addToCalendar(currentEvent, calendarType, provider);
    });
});

// Add the event to the chosen calendar - make it globally accessible. The dates, texts and links are built in
// calendarLinks.js (pure, unit tested); this only opens a link or downloads the .ics file.
window.addToCalendar = function(event, calendarType, provider) {
    const links = window.calendarLinks;
    const resolved = links.resolve(event, calendarType);
    if (!resolved.ok) {
        alert(resolved.message);
        return;
    }

    if (provider === 'ics') {
        downloadIcs(links.icsText(resolved, calendarType), links.icsFileName(resolved, calendarType));
    } else {
        const url = { google: links.googleUrl, outlook: links.outlookUrl, yahoo: links.yahooUrl }[provider];
        if (!url) {
            alert('Invalid calendar selected');
            return;
        }
        window.open(url(resolved), '_blank');
    }

    // Close modal after opening the calendar or starting the download
    closeNotifyModal();
}

// Hand the browser a .ics file to save or open (iPhones and Macs offer to add it to Calendar)
function downloadIcs(text, fileName) {
    const url = URL.createObjectURL(new Blob([text], { type: 'text/calendar;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}
