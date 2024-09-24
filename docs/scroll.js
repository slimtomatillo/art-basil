// Search bar
document.addEventListener('DOMContentLoaded', function() {
    const searchBar = document.getElementById('searchBar');

    searchBar.addEventListener('keyup', function(e) {
        const term = e.target.value.toLowerCase();
        const rows = document.getElementById('eventTable').getElementsByTagName('tbody')[0].getElementsByTagName('tr');

        Array.from(rows).forEach(function(row) {
            const title = row.getElementsByTagName('td')[0].textContent;
            const date = row.getElementsByTagName('td')[1].textContent;
            const location = row.getElementsByTagName('td')[2].textContent;
            const tags = row.getElementsByTagName('td')[3].textContent;

            if (title.toLowerCase().indexOf(term) !== -1 || date.toLowerCase().indexOf(term) !== -1 || location.toLowerCase().indexOf(term) !== -1 || tags.toLowerCase().indexOf(term) !== -1) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    });
});

// Show search bar and table header when user scrolls down the page
window.addEventListener('scroll', () => {
    const searchBarContainer = document.getElementById('searchBarContainer');
    const tableHeader = document.querySelector('thead');
    const offset = window.scrollY;

    if (offset > 0) {
        searchBarContainer.classList.add('sticky');
        tableHeader.classList.add('sticky');

        // Dynamically adjust the top value for the table header
        const searchBarHeight = searchBarContainer.offsetHeight; // Height of the search bar container
        tableHeader.style.top = `${searchBarHeight - 1}px`; // Apply this height as the top value for the table header
    } else {
        searchBarContainer.classList.remove('sticky');
        tableHeader.classList.remove('sticky');
        tableHeader.style.top = '0px'; // Reset the top value when not sticky
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
            event.sortPriority = 5; 
            event.venue = venue;

            // Determine sortPriority based on specific tags ('current', 'future', 'past')
            if (event.tags.includes('current')) {
                // Check if the event is ongoing
                if (event.ongoing === false) {
                    event.sortPriority = 1;  // Non-ongoing current events
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

    // Sort by sortPriority, then by 'sortDate'
    eventsArray.sort((a, b) => {
        const priorityComparison = a.sortPriority - b.sortPriority;
        if (priorityComparison !== 0) return priorityComparison;

        // For 'past' events (sortPriority === 3), sort by 'sortDate' descending
        if(a.sortPriority === 3 && b.sortPriority === 3) {
            return b.sortDate.localeCompare(a.sortDate); // Descending for 'past' events
        }

        // For other events, sort by 'sortDate' ascending
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

                // Image column
                const imageCell = row.insertCell();

                // Find the image link with the description "Image"
                const imageLinkObj = event.links.find(link => link.description === 'Image');

                if (imageLinkObj && imageLinkObj.link) {
                    const imgElement = document.createElement('img');
                    imgElement.src = imageLinkObj.link;
                    imgElement.alt = `${event.name} @ ${event.venue}`; // Make the alt attribute Event Name @ Venue
                    imgElement.className = 'event-image'; // Initial class for hover effect
                    imgElement.style.maxWidth = '150px'; // Set a max width to ensure the image fits nicely in the table cell
                    imgElement.style.maxHeight = '130px'; // Set a max width to ensure the image fits nicely in the table cell
                    imgElement.style.height = 'auto'; // Maintain aspect ratio
                    imgElement.style.justifySelf = 'center';
                    imageCell.appendChild(imgElement);

                    // Add click event listener to toggle enlarged class
                    imgElement.addEventListener('click', () => {
                        imgElement.classList.toggle('event-image-enlarged');
                    });
                } else {
                    // Handle the case where there is no image link
                    imageCell.textContent = '';
                }

                // Date column
                const dateCell = row.insertCell();
                const options = { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC'};
                let dateText = 'Dates TBA'; // Default text for events without specific dates
            
                const startDate = event.dates.start !== 'null' ? new Date(event.dates.start) : null;
                const endDate = event.dates.end !== 'null' ? new Date(event.dates.end) : null;
                const today = new Date();
                today.setHours(0, 0, 0, 0); // Normalize today's date for comparison
            
                const isPastEvent = event.tags.includes('past');
                const isCurrentEvent = event.tags.includes('current');
                const isFutureEvent = event.tags.includes('future');
            
                if (event.ongoing === true) {
                    // If the event is marked as ongoing
                    dateText = "Ongoing";
                } else if (isPastEvent && endDate) {
                    // For past events with a known end date
                    dateText = `Closed ${new Intl.DateTimeFormat('en-US', options).format(endDate)}`;
                } else if (isCurrentEvent) {
                    // For current events
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
                } else if (isFutureEvent) {
                    // For future events
                    dateText = `Opens on ${new Intl.DateTimeFormat('en-US', options).format(startDate)}`;
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
