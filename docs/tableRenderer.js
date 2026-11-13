// Table Renderer - Handles table creation and event row rendering

// Tags that exist in the data but shouldn't render as a chip right now.
// "opening" currently just means the description mentions an opening
// reception somewhere, not that this listing IS the opening event, and
// as a prominent chip that reads as a misleading claim. Revisit once we
// have real opening-event data to back it up.
const HIDDEN_TAGS = new Set(['opening']);

// Different scrapers build each event's tags array in a different order
// (e.g. `[exhibition, past, museum]` vs `[exhibition, museum, past]`), so
// the raw data order isn't consistent from one event to the next. This is
// the canonical display order every event's chips get sorted into,
// regardless of how the scraper that produced it ordered them. Anything
// not listed here (a tag added later) sorts after everything that is,
// alphabetically among itself.
const TAG_DISPLAY_ORDER = [
    'exhibition',
    'current', 'future', 'past',
    'museum', 'gallery',
    'free',
    'opening',
    'queer', 'immigrant', 'refugee', 'south-asian',
];

function sortTagsForDisplay(tags) {
    return [...tags].sort((a, b) => {
        const ia = TAG_DISPLAY_ORDER.indexOf(a);
        const ib = TAG_DISPLAY_ORDER.indexOf(b);
        const ra = ia === -1 ? TAG_DISPLAY_ORDER.length : ia;
        const rb = ib === -1 ? TAG_DISPLAY_ORDER.length : ib;
        return ra !== rb ? ra - rb : a.localeCompare(b);
    });
}

// Curated colors for tags we know about today. Two things drove this pass
// specifically (exhibition/current/museum used to look like near-identical
// greens): `exhibition` and `past` - by far the two most common tags, and
// almost always paired with each other and with every other tag - are now
// flat greys instead of competing for a hue at all, and the 4 tags that
// most often appear together on one row (current, future, museum, gallery)
// are placed 64-168deg apart from each other, not as neighbors on the
// wheel. The 5 rare identity/theme tags (each under 1% of all tag uses)
// fill the remaining gaps; a tighter gap there is a low-risk tradeoff since
// they almost never co-occur with each other in the real data. Every color
// keeps at least a 4.5:1 contrast ratio against the chip's white text, and
// none sit in the ~30-110deg range (yellow/amber/lime/olive), which read as
// a muddy brown no matter how it was tuned.
const TAG_COLOR_MAP = {
    current: '#2a8618',
    future: '#3c41dd',
    past: '#334155',
    exhibition: '#78716c',
    museum: '#c723c2',
    gallery: '#178277',
    free: '#188640',
    queer: '#2178ba',
    immigrant: '#8c3cdd',
    refugee: '#d92674',
    'south-asian': '#d93826',
};

// Any tag not in the map above (i.e. one added to the data later) gets a
// color from this function instead of a code change. Hues are placed with
// the golden angle (~137.5deg) rather than an even 360/N split, which is
// the standard trick for spacing out an open-ended, growing set of
// categories - each new tag stays well separated from every tag before it,
// not just from its immediate neighbors in a fixed-size wheel. The hue is
// then remapped out of the same muddy 35-115deg range the curated colors
// above avoid, and lightness is fixed low enough (30%) that every hue
// clears 4.5:1 contrast against white.
function getTagColor(tag) {
    if (TAG_COLOR_MAP[tag]) return TAG_COLOR_MAP[tag];

    let hash = 0;
    for (let i = 0; i < tag.length; i++) {
        hash = (hash * 31 + tag.charCodeAt(i)) >>> 0;
    }
    const GOLDEN_ANGLE = 137.508;
    const rawHue = (hash * GOLDEN_ANGLE) % 360;
    const hue = (118 + (rawHue / 360) * 280) % 360; // remapped into the 280deg usable arc
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
        this.venueImages = {};

        // On phones the CSS shows each row as a card (display: grid), and changing a
        // table's display makes some screen readers stop treating it as a table. Naming
        // the roles keeps it one, whatever the layout.
        const table = this.tableBody && this.tableBody.closest('table');
        if (table) {
            table.setAttribute('role', 'table');
            table.querySelectorAll('thead, tbody').forEach(el => el.setAttribute('role', 'rowgroup'));
            table.querySelectorAll('tr').forEach(el => el.setAttribute('role', 'row'));
            table.querySelectorAll('th').forEach(el => el.setAttribute('role', 'columnheader'));
        }
    }

    setVenues(venues) {
        this.venues = venues;
    }

    // The day part of a stored date ("2026-11-13" or "2026-11-13 00:00:00"), or '' for none (or 'null')
    isoDay(value) {
        return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value) ? value.slice(0, 10) : '';
    }

    // The area ids of a venue (see AREAS in filterState.js), from the cities, ZIP codes or districts in its addresses
    areasOf(venueName) {
        if (!venueName || !this.venues || !window.filterState || !window.venueAddresses || !window.dataManager) return [];
        const addresses = window.venueAddresses.normalize(this.venues[venueName]).map(entry => entry.address);
        return window.filterState.areasOfAddresses(window.dataManager.getRegion(), addresses);
    }

    // {venue name: picture URL}: a logo or banner shown for events with no picture of their own
    setVenueImages(venueImages) {
        this.venueImages = venueImages || {};
    }

    renderEventRow(event) {
        const row = this.tableBody.insertRow();
        row.setAttribute('role', 'row');

        // The event itself, for Map view's popups (a property, not an attribute: it is not text)
        row.eventData = event;

        // Add data attributes to row for filtering
        row.setAttribute('data-phase', event.phase);
        row.setAttribute('data-ongoing', event.ongoing === true);
        row.setAttribute('data-tags', event.tags.join('|'));
        // Which venue the row is for, so "Use my location" can look its distance up (nearMeControl.js)
        row.setAttribute('data-venue', event.venue || '');
        // When the show runs ('YYYY-MM-DD', empty if unknown) and which area(s) its venue is in, for the
        // dates and Area filters (filterState.js)
        const dates = event.dates || {};
        row.setAttribute('data-start', this.isoDay(dates.start));
        row.setAttribute('data-end', this.isoDay(dates.end));
        row.setAttribute('data-areas', this.areasOf(event.venue).join('|'));

        // Image column
        const imageCell = row.insertCell();
        this.renderImageCell(imageCell, event);

        // Date column
        const dateCell = row.insertCell();
        dateCell.textContent = this.formatEventDate(event);

        // Event Title @ Venue column
        const titleVenueCell = row.insertCell();
        titleVenueCell.append(`${event.name} @ `);
        titleVenueCell.append(this.venueLink(event.venue));

        // Tags column
        const tagsCell = row.insertCell();
        this.renderTagsCell(tagsCell, event);

        // Links column
        const linksCell = row.insertCell();
        this.renderLinksCell(linksCell, event);

        Array.from(row.cells).forEach(cell => cell.setAttribute('role', 'cell'));
    }

    // The venue's name in the "title @ venue" cell: a link to that venue's shows. A click filters the page to the
    // venue (SearchManager.setVenue); the href is the same view as a link, so a middle or Ctrl/Cmd-click opens it
    // in a new tab. Its text is the plain venue name, so the text search reads the cell as before.
    venueLink(venue) {
        const link = document.createElement('a');
        link.className = 'venue-link';
        link.textContent = venue || '';
        if (!venue) return link;
        link.href = `?venue=${encodeURIComponent(venue)}`;
        link.title = `Show only ${venue}`;
        link.addEventListener('click', (e) => {
            // Leave a new-tab click alone, and fall back to the link if the filters aren't ready
            if (e.button > 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey || !window.searchManager) return;
            e.preventDefault();
            window.searchManager.setVenue(venue);
        });
        return link;
    }

    renderTagsCell(cell, event) {
        sortTagsForDisplay(event.tags)
            .filter(tag => !HIDDEN_TAGS.has(tag))
            .forEach(tag => {
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
        // No picture of its own: fall back to the venue's logo, if we have one
        const venueImage = this.venueImages[event.venue];
        const imageSrc = imageLinkObj && imageLinkObj.link ? imageLinkObj.link : venueImage;

        if (imageSrc) {
            const imgElement = document.createElement('img');
            imgElement.src = imageSrc;
            imgElement.alt = imageLinkObj && imageLinkObj.link
                ? `${event.name} @ ${event.venue}`
                : `${event.venue} logo`;
            imgElement.className = imageLinkObj && imageLinkObj.link ? 'event-image' : 'event-image venue-logo';
            imgElement.loading = 'lazy';   // rows below the fold load their pictures as they are scrolled to
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
                this.openImageModal(imageSrc);
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
            linkElement.className = 'event-link';
            cell.appendChild(linkElement);
        }
       
        // Add maps link
        const venueName = event.venue;

        // One link per address; a venue with several spaces gets "Map: <space>" for each, or only for the spaces the show names (WEBSITE-122)
        const mapLinks = venueName ? window.venueAddresses.mapLinks((this.venues || {})[venueName], event.locations) : [];
        if (mapLinks.length) {
            cell.appendChild(document.createElement('br'));
            mapLinks.forEach((map, i) => {
                // The Links column is narrow, so each space's link sits on its own line
                if (i) cell.appendChild(document.createElement('br'));
                const mapLinkElement = document.createElement('a');
                mapLinkElement.href = map.href;
                mapLinkElement.textContent = map.text;
                if (mapLinks.length > 1) mapLinkElement.title = map.title;
                mapLinkElement.target = '_blank'; // Open in new tab/window
                mapLinkElement.className = 'event-link';
                if (window.mapChoice) window.mapChoice.attach(mapLinkElement, map); // Apple devices: Apple or Google Maps
                cell.appendChild(mapLinkElement);
            });
        }

        // "1.4 mi away": empty and hidden until the visitor shares their location (nearMeControl.js).
        // It sits in this column, not the title or date ones, so the text search never matches it.
        const distanceElement = document.createElement('span');
        distanceElement.className = 'event-distance';
        distanceElement.hidden = true;
        cell.appendChild(distanceElement);

        // Add notify button
        if ((event.dates.start && event.dates.start !== 'null') || (event.dates.end && event.dates.end !== 'null')) {
            const notifyButton = document.createElement('button');
            notifyButton.className = 'notify-button';
            // Bell icon + label. Constant markup only; nothing from the event goes in here.
            notifyButton.innerHTML =
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" ' +
                'stroke-linejoin="round" aria-hidden="true"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/>' +
                '<path d="M10.3 21a1.9 1.9 0 0 0 3.4 0"/></svg><span>Notify Me</span>';
            // The "Notify Me" label is hidden on narrow screens (see styles.css), so the
            // button needs its own name; it still starts with the visible words.
            notifyButton.setAttribute('aria-label', 'Notify me about this event');
            notifyButton.title = 'Notify me';
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
