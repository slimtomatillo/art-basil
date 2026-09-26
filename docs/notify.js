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
        datesText += `Opens: ${startDate.toLocaleDateString('en-US', CALENDAR_DATE_DISPLAY)}`;
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
    
    // Reset form
    document.getElementById('calendarType').value = '';
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
        
        if (!calendarType) {
            alert('Please select a calendar event type');
            return;
        }
        
        if (!currentEvent) {
            alert('No event selected');
            return;
        }
        
        // Create Google Calendar event
        window.createGoogleCalendarEvent(currentEvent, calendarType);
    });
});

// Function to create Google Calendar event - make it globally accessible
window.createGoogleCalendarEvent = function(event, calendarType) {
    let startDate, endDate, eventTitle, eventDescription;
    
    // Parse dates
    const startDateObj = event.dates.start && event.dates.start !== 'null' ? new Date(event.dates.start) : null;
    const endDateObj = event.dates.end && event.dates.end !== 'null' ? new Date(event.dates.end) : null;
    
    // Set event details based on calendar type
    let eventPageLink; // Declare once outside the switch
    
    switch (calendarType) {
        case 'opening':
            if (!startDateObj) {
                alert('Opening date not available for this event');
                return;
            }
            startDate = startDateObj;
            endDate = startDateObj; // Same day for opening
            eventTitle = `${event.name} - Opening Day`;
            eventDescription = `Opening day of ${event.name} at ${event.venue}`;
            break;
            
        case 'closing':
            if (!endDateObj) {
                alert('Closing date not available for this event');
                return;
            }
            startDate = endDateObj; // Same day for closing
            endDate = endDateObj;
            eventTitle = `${event.name} - Closing Day`;
            eventDescription = `Last day to see ${event.name} at ${event.venue}`;
            break;
            
        case 'full':
            if (!startDateObj || !endDateObj) {
                alert('Full event dates not available for this event');
                return;
            }
            startDate = startDateObj;
            endDate = endDateObj;
            eventTitle = event.name;
            eventDescription = `${event.name} at ${event.venue}`;
            break;
            
        default:
            alert('Invalid calendar type selected');
            return;
    }
    
    // Add event link if available (after switch statement)
    eventPageLink = event.links.find(link => link.description === 'Event Page');
    if (eventPageLink) {
        eventDescription += `\n\n<a href="${eventPageLink.link}">Event Page</a>`;
    }
    
    // Format dates for Google Calendar all-day events (YYYYMMDD format)
    const formatDateForGoogleAllDay = (date) => {
        const year = date.getUTCFullYear();
        const month = String(date.getUTCMonth() + 1).padStart(2, '0');
        const day = String(date.getUTCDate()).padStart(2, '0');
        return `${year}${month}${day}`;
    };
    
    const startDateStr = formatDateForGoogleAllDay(startDate);
    const endDateStr = formatDateForGoogleAllDay(endDate);
    
    // Add reminder note to description
    const reminderNote = '\n\n💡 Tip: Set a reminder for 1 week before this event!';
    const artBasilAttribution = '\n\nCreated by <a href="https://artbasil.info">Art Basil</a>';
    const fullDescription = eventDescription + reminderNote + artBasilAttribution;
    
    // Create Google Calendar URL for all-day events
    const googleCalendarUrl = `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${encodeURIComponent(eventTitle)}&dates=${startDateStr}/${endDateStr}&details=${encodeURIComponent(fullDescription)}&location=${encodeURIComponent(event.venue)}`;
    
    // Open Google Calendar in new tab
    window.open(googleCalendarUrl, '_blank');
    
    // Close modal after opening calendar
    closeNotifyModal();
}
