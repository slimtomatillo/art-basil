document.addEventListener('DOMContentLoaded', function() {
    const searchBar = document.getElementById('searchBar');

    searchBar.addEventListener('keyup', function(e) {
        const term = e.target.value.toLowerCase();
        const rows = document.getElementById('eventTable').getElementsByTagName('tbody')[0].getElementsByTagName('tr');

        Array.from(rows).forEach(function(row) {
            const title = row.getElementsByTagName('td')[0].textContent;
            const date = row.getElementsByTagName('td')[1].textContent;
            const location = row.getElementsByTagName('td')[2].textContent;

            if (title.toLowerCase().indexOf(term) !== -1 || date.toLowerCase().indexOf(term) !== -1 || location.toLowerCase().indexOf(term) !== -1) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    });
});
