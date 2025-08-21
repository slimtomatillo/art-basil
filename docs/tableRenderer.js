// Table Renderer - Handles table creation and event row rendering

class TableRenderer {
    constructor(tableBodyId) {
        this.tableBody = document.getElementById(tableBodyId);
        this.venues = null;
    }

    setVenues(venues) {
        this.venues = venues;
    }

    renderEventRow(event) {
        const row = this.tableBody.insertRow();

        // Add data attribute to row for filtering
        row.setAttribute('data-phase', event.phase);

        // Image column
        const imageCell = row.insertCell();
        this.renderImageCell(imageCell, event);

        // Date column
        const dateCell = row.insertCell();
        dateCell.textContent = this.formatEventDate(event);

        // Event Title @ Venue column
        const titleVenueCell = row.insertCell();
        titleVenueCell.textContent = `${event.name} @ ${event.venue}`;

        // Tags column
        const tagsCell = row.insertCell();
        tagsCell.textContent = event.tags.join(', ');

        // Links column
        const linksCell = row.insertCell();
        this.renderLinksCell(linksCell, event);
    }

    renderImageCell(cell, event) {
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
            cell.appendChild(imgElement);

            // Add click event for opening modal
            imgElement.addEventListener('click', (e) => {
                e.stopPropagation();
                this.openImageModal(imageLinkObj.link);
            });
        } else {
            // Handle the case where there is no image link
            cell.textContent = '';
        }
    }

    renderLinksCell(cell, event) {
        // Find the link with the description 'Event Page'
        const eventPageLink = event.links.find(link => link.description === 'Event Page');

        if (eventPageLink) {
            const linkElement = document.createElement('a');
            linkElement.href = eventPageLink.link;
            linkElement.textContent = eventPageLink.description || 'Link';
            linkElement.target = '_blank'; // Open in new tab/window
            cell.appendChild(linkElement);
        }
       
        // Add maps link
        const venueName = event.venue;

        if (venueName && this.venues[venueName]) {
            cell.appendChild(document.createElement('br'));
            const address = this.venues[venueName];
            const venueLink = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address)}`;
            const mapLinkElement = document.createElement('a');
            mapLinkElement.href = venueLink;
            mapLinkElement.textContent = 'Map';
            mapLinkElement.target = '_blank'; // Open in new tab/window
            cell.appendChild(mapLinkElement);
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
            cell.appendChild(notifyButton);
        }
    }

    formatEventDate(event) {
        const options = { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC'};
        let dateText = 'Dates TBA'; // Default text for events without specific dates
    
        // Helper function to safely create Date objects
        const createSafeDate = (dateString) => {
            if (!dateString || dateString === 'null' || dateString === '') {
                return null;
            }
            
            try {
                const date = new Date(dateString);
                // Check if the date is valid
                if (isNaN(date.getTime())) {
                    console.warn(`Invalid date string: ${dateString}`);
                    return null;
                }
                return date;
            } catch (error) {
                console.warn(`Error parsing date: ${dateString}`, error);
                return null;
            }
        };
    
        const startDate = createSafeDate(event.dates.start);
        const endDate = createSafeDate(event.dates.end);
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
            try {
                dateText = `Closed ${new Intl.DateTimeFormat('en-US', options).format(endDate)}`;
            } catch (error) {
                console.warn(`Error formatting end date:`, error);
                dateText = "Closed (date unavailable)";
            }
        } else if (isCurrentEvent) {
            // For current events
            if (endDate) {
                // If end date is known
                try {
                    dateText = `Through ${new Intl.DateTimeFormat('en-US', options).format(endDate)}`;
                } catch (error) {
                    console.warn(`Error formatting end date:`, error);
                    dateText = "Through (date unavailable)";
                }
            } else if (startDate) {
                // If start date is known
                try {
                    dateText = `Started on ${new Intl.DateTimeFormat('en-US', options).format(startDate)}`;
                } catch (error) {
                    console.warn(`Error formatting start date:`, error);
                    dateText = "Started on (date unavailable)";
                }
            } else {
                // If neither date is known, it remains "Dates TBA"
                dateText = "Dates TBA";
            }
        } else if (isFutureEvent && startDate) {
            // For future events
            try {
                dateText = `Opens ${new Intl.DateTimeFormat('en-US', options).format(startDate)}`;
            } catch (error) {
                console.warn(`Error formatting start date:`, error);
                dateText = "Opens (date unavailable)";
            }
        }
    
        return dateText;
    }

    openImageModal(imageSrc) {
        if (window.modalManager) {
            window.modalManager.openImageModal(imageSrc);
        }
    }

    clearTable() {
        if (this.tableBody) {
            this.tableBody.innerHTML = '';
        }
    }
}

// Export class for use in other modules
window.TableRenderer = TableRenderer;
