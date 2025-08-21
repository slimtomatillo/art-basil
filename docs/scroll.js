// Main Event Loader - Coordinates data loading, sorting, and rendering
// This file now serves as the main orchestrator using separated modules

// Load data and render events
window.addEventListener('DOMContentLoaded', async () => {
    try {
        // Wait for all modules to be loaded
        await waitForModules();
        
        // Fetch venue data
        const venues = await window.dataManager.fetchVenues();
        
        // Fetch and sort event data
        const unsortedData = await window.dataManager.fetchEvents();
        
        if (!unsortedData || Object.keys(unsortedData).length === 0) {
            console.error('No events data received!');
            return;
        }
        
        const sortedEvents = window.eventSorter.sortEvents(unsortedData);
        
        if (!sortedEvents || sortedEvents.length === 0) {
            console.error('No events after sorting!');
            return;
        }
        
        // Initialize table renderer
        const tableRenderer = new window.TableRenderer('event-list');
        tableRenderer.setVenues(venues);
        
        // Clear existing table content
        tableRenderer.clearTable();
        
        // Render all events
        sortedEvents.forEach((event, index) => {
            try {
                tableRenderer.renderEventRow(event);
            } catch (error) {
                console.error(`Error rendering event ${index + 1} (${event.name || 'Unknown'}):`, error);
                // Continue rendering other events instead of stopping completely
            }
        });
        
        // Initialize search manager after events are rendered
        if (window.searchManager) {
            window.searchManager = new SearchManager();
        } else {
            window.searchManager = new SearchManager();
        }
        
    } catch (error) {
        console.error('Error loading events:', error);
    }
});

// Helper function to wait for all required modules to be loaded
function waitForModules() {
    return new Promise((resolve) => {
        const checkModules = () => {
            if (window.dataManager && 
                window.eventSorter && 
                window.TableRenderer && 
                window.modalManager) {
                resolve();
            } else {
                setTimeout(checkModules, 100);
            }
        };
        checkModules();
    });
}

