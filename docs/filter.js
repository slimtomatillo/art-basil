// Variables to store the current search term and phase filter
let currentSearchTerm = '';
let currentPhaseFilter = 'all';

// Function to update the active button styling
function setActiveButton(activeButton) {
    const buttons = document.querySelectorAll('.filter-button');
    buttons.forEach(button => {
        if (button === activeButton) {
            button.classList.add('active');
        } else {
            button.classList.remove('active');
        }
    });
}

// Function to filter events based on search term and phase
function filterEvents() {
    const rows = document.querySelectorAll('#eventTable tbody tr');

    rows.forEach(row => {
        const eventPhase = row.getAttribute('data-phase');
        const title = row.getElementsByTagName('td')[2].textContent.toLowerCase(); // Column index for Title @ Venue
        const date = row.getElementsByTagName('td')[1].textContent.toLowerCase();
        const tags = row.getElementsByTagName('td')[3].textContent.toLowerCase();

        // Check if row matches the search term
        const matchesSearch =
            title.includes(currentSearchTerm) ||
            date.includes(currentSearchTerm) ||
            tags.includes(currentSearchTerm);

        // Check if row matches the phase filter
        const matchesPhase = currentPhaseFilter === 'all' || eventPhase === currentPhaseFilter;

        // Show row if it matches both search and phase
        if (matchesSearch && matchesPhase) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

// Add event listeners after the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Your existing code, including fetching data and initializing the page

    // Get references to the buttons
    const currentButton = document.getElementById('currentButton');
    const futureButton = document.getElementById('futureButton');
    const pastButton = document.getElementById('pastButton');
    const allButton = document.getElementById('allButton');

    // Search bar event listener
    const searchBar = document.getElementById('searchBar');
    searchBar.addEventListener('keyup', function(e) {
        currentSearchTerm = e.target.value.toLowerCase();
        filterEvents();
    });

    // Button event listeners
    currentButton.addEventListener('click', () => {
        currentPhaseFilter = 'current';
        filterEvents();
        setActiveButton(currentButton);
    });

    futureButton.addEventListener('click', () => {
        currentPhaseFilter = 'future';
        filterEvents();
        setActiveButton(futureButton);
    });

    pastButton.addEventListener('click', () => {
        currentPhaseFilter = 'past';
        filterEvents();
        setActiveButton(pastButton);
    });

    allButton.addEventListener('click', () => {
        currentPhaseFilter = 'all';
        filterEvents();
        setActiveButton(allButton);
    });

    // Optionally, set the initial active button
    setActiveButton(allButton);
});
