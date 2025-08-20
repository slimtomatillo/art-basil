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

// Get the region from the URL path
const getRegion = () => {
    const path = window.location.pathname;
    if (path.includes('/sf/')) return 'sf';
    if (path.includes('/la/')) return 'la';
    return 'sf'; // default to SF
};

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

// Load venue data
let venuesCache = null; // Cache for storing the venue data
async function fetchVenues() {
    const region = getRegion();
    try {
        const response = await fetch(`../data/${region}_venues.json`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const venues = await response.json();
        return venues;
    } catch (error) {
        console.error('Failed to fetch venues:', error);
        return [];
    }
}

// Load data
window.addEventListener('DOMContentLoaded', async () => {
    // Fetch venue data once and store it in a constant
    const venues = await fetchVenues();
    const region = getRegion();
    
    // Load event data
    fetch(`../data/${region}_events.json`)
        .then(response => response.json())
        .then(unsortedData => {
            // Assuming `sortEvents` expects and returns the whole dataset
            const sortedEvents = sortEvents(unsortedData); // Sort the data

            const tableBody = document.getElementById('event-list');

            // Since sortedEvents is an array, iterate directly over it
            sortedEvents.forEach(event => {
                const row = tableBody.insertRow();

                // Add data attribute to row for filtering
                row.setAttribute('data-phase', event.phase);

                // Image column
                const imageCell = row.insertCell();

                // Find the image link with the description "Image"
                const imageLinkObj = event.links.find(link => link.description === 'Image');

                if (imageLinkObj && imageLinkObj.link) {
                    const imgElement = document.createElement('img');
                    imgElement.src = imageLinkObj.link;
                    imgElement.alt = `${event.name} @ ${event.venue}`;
                    imgElement.className = 'event-image';
                    imgElement.style.maxWidth = '150px';
                    imgElement.style.maxHeight = '130px';
                    imgElement.style.height = 'auto';
                    imgElement.style.justifySelf = 'center';
                    imgElement.style.cursor = 'pointer';
                    imageCell.appendChild(imgElement);

                    // Get modal elements
                    const modal = document.getElementById('imageModal');
                    const modalImg = document.getElementById('modalImage');

                    // Add click event for opening modal
                    imgElement.addEventListener('click', (e) => {
                        e.stopPropagation();
                        modal.style.display = 'block';
                        modalImg.src = imageLinkObj.link;
                    });

                    // Close modal when clicking on it
                    modal.addEventListener('click', () => {
                        modal.style.display = 'none';
                    });

                    // Close modal when pressing Escape key
                    document.addEventListener('keydown', (e) => {
                        if (e.key === 'Escape' && modal.style.display === 'block') {
                            modal.style.display = 'none';
                        }
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
            
                if (event.ongoing === true && isCurrentEvent === true) {
                    // If the event is marked as ongoing
                    dateText = "Ongoing";
                } else if (isPastEvent && endDate) {
                    // For past events with a known end date
                    dateText = `Closed ${new Intl.DateTimeFormat('en-US', options).format(endDate)}`;
                } else if (isCurrentEvent) {
                    // For current events
                    if (endDate) {
                        // If end date is known
                        dateText = `Through ${new Intl.DateTimeFormat('en-US', options).format(endDate)}`;
                    } else if (startDate) {
                        // If start date is known
                        dateText = `Started on ${new Intl.DateTimeFormat('en-US', options).format(startDate)}`;
                    } else {
                        // If neither date is known, it remains "Dates TBA"
                        dateText = "Dates TBA";
                    }
                } else if (isFutureEvent) {
                    // For future events
                    dateText = `Opens ${new Intl.DateTimeFormat('en-US', options).format(startDate)}`;
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

                // Find the link with the description 'Event Page'
                const eventPageLink = event.links.find(link => link.description === 'Event Page');

                if (eventPageLink) {
                    const linkElement = document.createElement('a');
                    linkElement.href = eventPageLink.link;
                    linkElement.textContent = eventPageLink.description || 'Link';
                    linkElement.target = '_blank'; // Open in new tab/window
                    linksCell.appendChild(linkElement);
                }
               
                // Add maps link
                const venueName = event.venue;

                if (venueName && venues[venueName]) {
                    linksCell.appendChild(document.createElement('br'));
                    const address = venues[venueName];
                    const venueLink = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address)}`;
                    const mapLinkElement = document.createElement('a');
                    mapLinkElement.href = venueLink;
                    mapLinkElement.textContent = 'Map';
                    mapLinkElement.target = '_blank'; // Open in new tab/window
                    linksCell.appendChild(mapLinkElement);
                }

                // Add notify button
                if ((event.dates.start && event.dates.start !== 'null') || (event.dates.end && event.dates.end !== 'null')) {
                    const notifyButton = document.createElement('button');
                    notifyButton.className = 'notify-button';
                    notifyButton.textContent = 'Notify Me';
                    notifyButton.disabled = false; // Ensure button is enabled
                    notifyButton.addEventListener('click', function() {
                        console.log('Notify button clicked');
                        if (typeof window.openNotifyModal === 'function') {
                            window.openNotifyModal(event);
                        } else {
                            console.error('openNotifyModal function not found');
                        }
                    });
                    linksCell.appendChild(notifyButton);
                }
            });
        })
        .catch(error => {
            console.error('Error loading events:', error);
        });
});

