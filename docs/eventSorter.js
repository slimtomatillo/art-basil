// Event Sorter - Handles event sorting and priority assignment

function sortEvents(events) {
    let eventsArray = [];
    // Get today's date, reset hours to ensure we're only comparing dates
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    Object.entries(events).forEach(([venue, venueEvents]) => {
        Object.values(venueEvents).forEach(event => {
            // Convert event.start date to Date object for comparison
            // Check if start date is provided and valid
            if (event.dates.start && event.dates.start !== 'null') {
                const startDate = new Date(event.dates.start);
                // Compare start date with today's date
                if (startDate <= today) {
                    // If the event's start date is today or earlier, set it to 'null'
                    event.dates.start = 'null';
                }
            }

            // Handle 'null' or missing end dates
            event.sortDate = event.dates.end && event.dates.end !== 'null' ? event.dates.end : '9999-12-31';
            // Assign a default high sort priority (will sort last)
            event.sortPriority = 5; 
            event.venue = venue;

            // Determine sortPriority based on specific tags ('current', 'future', 'past')
            if (event.tags.includes('current')) {
                // Check if the event is ongoing
                if (event.ongoing !== true) {
                    event.sortPriority = 1;  // Non-ongoing current events (including exhibitions missing 'ongoing' field)
                } else {
                    event.sortPriority = 2;  // Ongoing current events
                }
            } else if (event.tags.includes('future')) {
                event.sortPriority = 3;
            } else if (event.tags.includes('past')) {
                event.sortPriority = 4;
            }
            
            eventsArray.push(event);
        });
    });

    // Sort by sortPriority, then by appropriate date field
    eventsArray.sort((a, b) => {
        const priorityComparison = a.sortPriority - b.sortPriority;
        if (priorityComparison !== 0) return priorityComparison;

        // For future events (sortPriority === 3), sort by start date ascending
        if (a.sortPriority === 3 && b.sortPriority === 3) {
            const aStart = a.dates?.start || '9999-12-31';
            const bStart = b.dates?.start || '9999-12-31';
            return aStart.localeCompare(bStart); // Ascending for future events
        }

        // For past events (sortPriority === 4), sort by end date descending
        if (a.sortPriority === 4 && b.sortPriority === 4) {
            const aEnd = a.dates?.end || '0000-01-01';
            const bEnd = b.dates?.end || '0000-01-01';
            return bEnd.localeCompare(aEnd); // Descending for past events
        }

        // For other events, sort by sortDate ascending
        return a.sortDate.localeCompare(b.sortDate);
    });

    return eventsArray;
}

// Export function for use in other modules
window.eventSorter = {
    sortEvents
};
