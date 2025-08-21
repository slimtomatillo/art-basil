// Data Manager - Handles data fetching and region detection

// Get the region from the URL path
const getRegion = () => {
    const path = window.location.pathname;
    
    if (path.includes('/sf/')) {
        return 'sf';
    }
    if (path.includes('/la/')) {
        return 'la';
    }
    
    return 'sf'; // default to SF
};

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

// Load event data
async function fetchEvents() {
    const region = getRegion();
    
    try {
        const response = await fetch(`../data/${region}_events.json`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const events = await response.json();
        return events;
    } catch (error) {
        console.error('Failed to fetch events:', error);
        return {};
    }
}

// Export functions for use in other modules
window.dataManager = {
    getRegion,
    fetchVenues,
    fetchEvents
};
