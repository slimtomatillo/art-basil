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

// Load data
window.addEventListener('DOMContentLoaded', () => {
    fetch("events_db.json")
        .then(response => response.json())
        .then(data => {
            const tableBody = document.getElementById('event-list');

            // Iterate over the data to create table rows for each event
            Object.entries(data).forEach(([venue, events]) => {
                Object.values(events).forEach(event => {
                    const row = tableBody.insertRow();

                    // Date column
                    const dateCell = row.insertCell();
                    dateCell.textContent = event.dates.start ? `${event.dates.start} to ${event.dates.end}` : 'Dates TBA';

                    // Event Title @ Venue column
                    const titleVenueCell = row.insertCell();
                    titleVenueCell.textContent = `${event.name} @ ${venue}`;

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
            });
        })
        .catch(error => {
            console.error('Error loading events:', error);
        });
});
