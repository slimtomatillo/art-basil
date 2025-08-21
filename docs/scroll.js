// Main Event Loader - Coordinates data loading, sorting, and rendering
// This file now serves as the main orchestrator using separated modules

// Load data and render events
window.addEventListener('DOMContentLoaded', async () => {
    console.log('DOM Content Loaded - Starting event loading...');
    
    try {
        // Wait for all modules to be loaded
        console.log('Waiting for modules to load...');
        await waitForModules();
        console.log('All modules loaded successfully');
        
        // Fetch venue data
        console.log('Fetching venues...');
        const venues = await window.dataManager.fetchVenues();
        console.log('Venues fetched:', venues);
        
        // Fetch and sort event data
        console.log('Fetching events...');
        const unsortedData = await window.dataManager.fetchEvents();
        console.log('Raw events data:', unsortedData);
        
        const sortedEvents = window.eventSorter.sortEvents(unsortedData);
        console.log('Events sorted:', sortedEvents);
        
        // Initialize table renderer
        console.log('Initializing table renderer...');
        const tableRenderer = new window.TableRenderer('event-list');
        tableRenderer.setVenues(venues);
        
        // Clear existing table content
        tableRenderer.clearTable();
        
        // Render all events
        console.log('Rendering events...');
        sortedEvents.forEach((event, index) => {
            console.log(`Rendering event ${index + 1}:`, event.name);
            tableRenderer.renderEventRow(event);
        });
        
        console.log('Events loaded successfully:', sortedEvents.length);
        
    } catch (error) {
        console.error('Error loading events:', error);
        console.error('Error stack:', error.stack);
    }
});

// Helper function to wait for all required modules to be loaded
function waitForModules() {
    return new Promise((resolve) => {
        const checkModules = () => {
            console.log('Checking modules...', {
                dataManager: !!window.dataManager,
                eventSorter: !!window.eventSorter,
                TableRenderer: !!window.TableRenderer,
                searchManager: !!window.searchManager,
                modalManager: !!window.modalManager
            });
            
            if (window.dataManager && 
                window.eventSorter && 
                window.TableRenderer && 
                window.searchManager && 
                window.modalManager) {
                console.log('All modules are loaded!');
                resolve();
            } else {
                console.log('Some modules not loaded yet, waiting...');
                setTimeout(checkModules, 100);
            }
        };
        checkModules();
    });
}

