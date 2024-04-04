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
    Object.entries(events).forEach(([venue, venueEvents]) => {
        Object.values(venueEvents).forEach(event => {
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
                const options = { year: 'numeric', month: 'short', day: 'numeric' };
                let dateText = 'Dates TBA'; // Default text if both dates are 'null' or not provided
                
                if (event.dates.start !== 'null' && event.dates.end !== 'null') {
                    // Both start and end dates are provided
                    const startDate = new Date(event.dates.start);
                    const formattedStartDate = new Intl.DateTimeFormat('en-US', options).format(startDate);
                    const endDate = new Date(event.dates.end);
                    const formattedEndDate = new Intl.DateTimeFormat('en-US', options).format(endDate);
                    dateText = `${formattedStartDate} to ${formattedEndDate}`;
                } else if (event.dates.start !== 'null') {
                    // Only start date is provided
                    const startDate = new Date(event.dates.start);
                    const formattedStartDate = new Intl.DateTimeFormat('en-US', options).format(startDate);
                    dateText = `Starts on ${formattedStartDate}`;
                } else if (event.dates.end !== 'null') {
                    // Only end date is provided
                    const endDate = new Date(event.dates.end);
                    const formattedEndDate = new Intl.DateTimeFormat('en-US', options).format(endDate);
                    dateText = `Through ${formattedEndDate}`;
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
