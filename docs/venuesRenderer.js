// Venues Renderer - Renders the venue directory for the current region.
// Region detection and data fetching are handled by dataManager.js, which
// this page also loads.

window.addEventListener('DOMContentLoaded', async () => {
    const tbody = document.getElementById('venue-list');
    if (!tbody) return;

    let venues;
    try {
        venues = await window.dataManager.fetchVenues();
    } catch (error) {
        console.error('Failed to load venues:', error);
        venues = {};
    }

    const names = Object.keys(venues).sort((a, b) => a.localeCompare(b));

    if (names.length === 0) {
        const row = tbody.insertRow();
        const cell = row.insertCell();
        cell.colSpan = 3;
        cell.className = 'text-center text-muted py-4';
        cell.textContent = 'No venues listed yet.';
        return;
    }

    names.forEach(name => {
        // A plain address, or a list of spaces (see venueAddresses.js)
        const entries = window.venueAddresses.normalize(venues[name]);
        const row = tbody.insertRow();

        // Venue name links back to the region's exhibitions, pre-filtered
        // to that venue via the search bar (see searchManager.js's ?search=
        // handling).
        const nameCell = row.insertCell();
        const nameLink = document.createElement('a');
        nameLink.href = `index.html?search=${encodeURIComponent(name)}`;
        nameLink.textContent = name;
        nameLink.className = 'fw-semibold text-decoration-none';
        nameCell.appendChild(nameLink);

        // One line per space: "Hart House: 7 Hart House Circle, ..." (just the address for a single space)
        const addressCell = row.insertCell();
        entries.forEach((entry, i) => {
            if (i) addressCell.appendChild(document.createElement('br'));
            addressCell.appendChild(document.createTextNode(
                entries.length > 1 && entry.label ? `${entry.label}: ${entry.address}` : entry.address));
        });

        const linksCell = row.insertCell();
        window.venueAddresses.mapLinks(venues[name]).forEach((map, i) => {
            if (i) linksCell.appendChild(document.createTextNode(' · '));
            const mapLink = document.createElement('a');
            mapLink.href = map.href;
            mapLink.textContent = map.text;
            mapLink.target = '_blank';
            if (window.mapChoice) window.mapChoice.attach(mapLink, map); // Apple devices: Apple or Google Maps
            linksCell.appendChild(mapLink);
        });
    });
});
