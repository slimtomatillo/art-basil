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

                // Check if event.Links is defined
                if (event.Links && Array.isArray(event.Links)) {
                    // Create an array of anchor elements from the list of links
                    const linksHTML = event.Links.map(linkObj => `<a href="${linkObj.Link}">${linkObj.Text}</a>`).join('<br>');

                    // Use linksHTML to display all the links in the table cell
                    row.innerHTML = `
                        <td>${event.Date}</td>
                        <td>${event.Title} @ ${event.Venue}</td>
                        <td>${event.Tags.join(', ')}</td>
                        <td>${linksHTML}</td>
                    `;
                } else {
                    // If event.Link is undefined or not an array, display an empty cell
                    row.innerHTML = `
                        <td>${event.Date}</td>
                        <td>${event.Title} @ ${event.Venue}</td>
                        <td>${event.Tags.join(', ')}</td>
                        <td></td>
                    `;
                }

                eventList.appendChild(row);
            });
        })
        .catch((error) => console.error("Error fetching data:", error));
});
