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
        const address = venues[name];
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

        const addressCell = row.insertCell();
        addressCell.textContent = address || '';

        const linksCell = row.insertCell();
        if (address) {
            const mapLink = document.createElement('a');
            mapLink.href = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address)}`;
            mapLink.textContent = 'Map';
            mapLink.target = '_blank';
            linksCell.appendChild(mapLink);
        }
    });
});
