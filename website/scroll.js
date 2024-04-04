// JavaScript to handle the scrolling behavior
window.addEventListener('scroll', () => {
    const tableHeader = document.querySelector('thead');
    const offset = window.scrollY;

    if (offset > 0) {
        tableHeader.classList.add('sticky');
    } else {
        tableHeader.classList.remove('sticky');
    }
});

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
            event.sortPriority = 4; 
            event.venue = venue;

            // Determine sortPriority based on specific tags ('current', 'future', 'past')
            if (event.tags.includes('current')) {
                event.sortPriority = 1;
            } else if (event.tags.includes('future')) {
                event.sortPriority = 2;
            } else if (event.tags.includes('past')) {
                event.sortPriority = 3;
            }
            
            eventsArray.push(event);
        });
    });

    // Sort by sortPriority, then by 'sortDate'
    eventsArray.sort((a, b) => {
        const priorityComparison = a.sortPriority - b.sortPriority;
        if (priorityComparison !== 0) return priorityComparison;

        // For dates, ensure comparison handles string dates correctly
        return a.sortDate.localeCompare(b.sortDate);
    });

    return eventsArray;
}

// Load data
window.addEventListener('DOMContentLoaded', () => {
    fetch("events_db.json")
        .then(response => response.json())
        .then(unsortedData => {
            // Assuming `sortEvents` expects and returns the whole dataset
            const sortedEvents = sortEvents(unsortedData); // Sort the data

            const tableBody = document.getElementById('event-list');

            // Since sortedEvents is an array, iterate directly over it
            sortedEvents.forEach(event => {
                const row = tableBody.insertRow();

                // Date column
                const dateCell = row.insertCell();
                const options = { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC'};
                let dateText = 'Dates TBA'; // Default text for events without specific dates
            
                const startDate = event.dates.start !== 'null' ? new Date(event.dates.start) : null;
                const endDate = event.dates.end !== 'null' ? new Date(event.dates.end) : null;
                const today = new Date();
                today.setHours(0, 0, 0, 0); // Normalize today's date for comparison

                console.log(event)
                console.log(endDate)
            
                const isPastEvent = event.tags.includes('past');
                const isOngoingEvent = (startDate === null || startDate <= today) && (endDate === null || endDate >= today);
            
                if (isPastEvent && endDate) {
                    // For past events with a known end date
                    dateText = `Closed ${new Intl.DateTimeFormat('en-US', options).format(endDate)}`;
                } else if (isOngoingEvent) {
                    // For ongoing events
                    if (startDate && endDate) {
                        // If both start and end dates are known
                        dateText = `${new Intl.DateTimeFormat('en-US', options).format(startDate)} to ${new Intl.DateTimeFormat('en-US', options).format(endDate)}`;
                    } else if (startDate) {
                        // If only the start date is known
                        dateText = `Started on ${new Intl.DateTimeFormat('en-US', options).format(startDate)}`;
                    } else if (endDate) {
                        // If only the end date is known
                        dateText = `Through ${new Intl.DateTimeFormat('en-US', options).format(endDate)}`;
                    } else {
                        // If neither date is known, it remains "Dates TBA"
                    }
                }
            
                dateCell.textContent = dateText;

                // Event Title @ Venue column
                const titleVenueCell = row.insertCell();
                titleVenueCell.textContent = `${event.name} @ ${event.venue}`;

                // Tags column
                const tagsCell = row.insertCell();
                tagsCell.textContent = event.tags.join(', ');

                // Links column
                const linksCell = row.insertCell();
                event.links.forEach((link, index) => {
                    const linkElement = document.createElement('a');
                    linkElement.href = link.link;
                    linkElement.textContent = link.description || 'Link';
                    linkElement.target = '_blank'; // Open in new tab/window
                    linksCell.appendChild(linkElement);

                    // Add a line break if there are multiple links, but not after the last one
                    if (index < event.links.length - 1) {
                        linksCell.appendChild(document.createElement('br'));
                    }
                });
            });
        })
        .catch(error => {
            console.error('Error loading events:', error);
        });
});
