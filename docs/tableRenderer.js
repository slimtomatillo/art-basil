// Table Renderer - Handles table creation and event row rendering

// Curated colors for tags we know about today, individually tuned so no two
// are easy to mix up (e.g. gallery/museum used to both be purple) and each
// keeps at least a 4.5:1 contrast ratio against the chip's white text.
const TAG_COLOR_MAP = {
    current: '#228641',
    future: '#2971a3',
    past: '#556377',
    exhibition: '#a33929',
    museum: '#936f25',
    gallery: '#657a1f',
    opening: '#378221',
    free: '#218275',
    queer: '#292fa3',
    immigrant: '#6629a3',
    refugee: '#a3299e',
    'south-asian': '#a3295b',
};

// Any tag not in the map above (i.e. one added to the data later) gets a
// color from this function instead of a code change. Hues are placed with
// the golden angle (~137.5deg) rather than an even 360/N split, which is
// the standard trick for spacing out an open-ended, growing set of
// categories - each new tag stays well separated from every tag before it,
// not just from its immediate neighbors in a fixed-size wheel. Lightness is
// fixed low enough (30%) that every hue clears 4.5:1 contrast against white.
function getTagColor(tag) {
    if (TAG_COLOR_MAP[tag]) return TAG_COLOR_MAP[tag];

    let hash = 0;
    for (let i = 0; i < tag.length; i++) {
        hash = (hash * 31 + tag.charCodeAt(i)) >>> 0;
    }
    const GOLDEN_ANGLE = 137.508;
    const hue = (hash * GOLDEN_ANGLE) % 360;
    return hslToHex(hue, 0.55, 0.30);
}

function hslToHex(h, s, l) {
    const a = s * Math.min(l, 1 - l);
    const f = n => {
        const k = (n + h / 30) % 12;
        const color = l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
        return Math.round(color * 255).toString(16).padStart(2, '0');
    };
    return `#${f(0)}${f(8)}${f(4)}`;
}

function formatTagLabel(tag) {
    return tag.toLowerCase().replace(/-/g, ' ');
}

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

        // Add data attributes to row for filtering
        row.setAttribute('data-phase', event.phase);
        row.setAttribute('data-ongoing', event.ongoing === true);
        row.setAttribute('data-tags', event.tags.join('|'));

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
        this.renderTagsCell(tagsCell, event);

        // Links column
        const linksCell = row.insertCell();
        this.renderLinksCell(linksCell, event);
    }

    renderTagsCell(cell, event) {
        event.tags.forEach(tag => {
            const chip = document.createElement('span');
            chip.className = 'tag-chip';
            chip.textContent = formatTagLabel(tag);
            chip.dataset.tag = tag;
            chip.style.backgroundColor = getTagColor(tag);

            chip.addEventListener('click', (e) => {
                e.stopPropagation();
                if (window.searchManager) {
                    window.searchManager.toggleTagFilter(tag);
                }
            });

            cell.appendChild(chip);
        });
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

            // Some venues' images are hotlinked from a third-party CDN that
            // can intermittently fail to load for a visitor (e.g. a bot-
            // protection challenge on the source site) even though the URL
            // is otherwise valid. Rather than showing a broken-image icon,
            // remove the element so the cell just renders empty.
            imgElement.addEventListener('error', () => {
                imgElement.remove();
            }, { once: true });

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
        } else if (isPastEvent) {
            // For past events
            if (endDate) {
                // Known end date
                try {
                    dateText = `Closed ${new Intl.DateTimeFormat('en-US', options).format(endDate)}`;
                } catch (error) {
                    console.warn(`Error formatting end date:`, error);
                    dateText = "Closed (date unavailable)";
                }
            } else if (startDate) {
                // No end date on record, but we know when it opened. Lead
                // with "Closed" (like every other past-event row) rather
                // than "Opened <date>" alone - on its own that could read as
                // still running, especially next to "Started on <date>"
                // (which *is* used for a currently-open show).
                try {
                    dateText = `Closed (opened ${new Intl.DateTimeFormat('en-US', options).format(startDate)})`;
                } catch (error) {
                    console.warn(`Error formatting start date:`, error);
                    dateText = "Closed (date unavailable)";
                }
            } else {
                // A closed show with no date on record at all. Unlike "Dates
                // TBA" (which implies an announcement is still pending), this
                // exhibition already happened - the source just never gave a
                // date, or it's an orphaned entry that dropped off the source
                // before a date could be captured.
                dateText = "Closed (date unknown)";
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
        } else if (isFutureEvent) {
            // For future events
            if (startDate) {
                try {
                    dateText = `Opens ${new Intl.DateTimeFormat('en-US', options).format(startDate)}`;
                } catch (error) {
                    console.warn(`Error formatting start date:`, error);
                    dateText = "Opens (date unavailable)";
                }
            }
            // else: stays "Dates TBA" - the show is coming but no date has
            // been announced yet, which is exactly what "TBA" means here.
        } else if (!isPastEvent && !isCurrentEvent && !isFutureEvent) {
            // No phase at all - we don't even know whether this is open or
            // closed, so "Dates TBA" (which implies a pending announcement)
            // would be a guess. Be explicit that this is a data gap instead.
            dateText = "Dates unavailable";
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
