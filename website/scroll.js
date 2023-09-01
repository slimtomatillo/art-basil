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
    const eventList = document.getElementById('event-list');

    // Fetch the JSON data
    fetch("data.json")  // Replace with the path to your JSON data file
        .then((response) => response.json())
        .then((data) => {
            // Populate the table rows with event data
            data.forEach((event) => {
                const row = document.createElement("tr");
                row.innerHTML = `
                    <td>${event.Date}</td>
                    <td>${event.Title} @ ${event.Venue}</td>
                    <td>${event.Tags}</td>
                    <td><a href="${event.Link}">${"Link"}</a></td>
                `;
                eventList.appendChild(row);
            });
        })
        .catch((error) => console.error("Error fetching data:", error));
});