// Event Sorter - Handles event sorting and priority assignment

function sortEvents(events) {
    let eventsArray = [];
    // Today's date at the venues ('YYYY-MM-DD' in the region's time zone), not the viewer's
    const today = window.dataManager.regionToday(window.dataManager.getRegion());

    Object.entries(events).forEach(([venue, venueEvents]) => {
        Object.values(venueEvents).forEach(event => {
            // The event's own dates are left as they are: the table shows "Started on ..." for an open
            // show with no end date, and Notify Me offers a started show's real opening day and full
            // run. The sort keys below are separate fields.

            // Handle 'null' or missing end dates
            event.sortDate = event.dates.end && event.dates.end !== 'null' ? event.dates.end : '9999-12-31';
            // For sorting upcoming shows by opening date: a show that has already started (by the
            // venue's date) sorts after the ones that really are upcoming, as it always has
            // (ISO date strings compare chronologically as plain strings)
            const hasStarted = event.dates.start && event.dates.start !== 'null' && event.dates.start.slice(0, 10) <= today;
            event.sortStart = hasStarted ? 'null' : (event.dates.start || '9999-12-31');
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
            return a.sortStart.localeCompare(b.sortStart); // Ascending for future events
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
