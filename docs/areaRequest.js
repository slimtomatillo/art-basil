// "Add my area" on the home page: opens the request dialog and closes it again.
// The form itself (validation, sending, success and error messages) is the shared
// siteForms.js, which picks up any <form data-web3form>. Dialog style is the
// feedback dialog's (.feedback-modal).
document.addEventListener('DOMContentLoaded', function () {
    const openButton = document.getElementById('requestAreaButton');
    const modal = document.getElementById('areaModal');
    const closeButton = document.getElementById('areaClose');
    if (!openButton || !modal) return;

    const field = document.getElementById('area-name');
    const status = modal.querySelector('.form-status');

    function open() {
        modal.style.display = 'block';
        status.hidden = true;
        field.focus();
    }

    function close() {
        modal.style.display = 'none';
        openButton.focus();
    }

    openButton.addEventListener('click', open);
    closeButton.addEventListener('click', close);
    // A click on the dimmed backdrop (not on the dialog itself) closes it
    modal.addEventListener('click', function (e) {
        if (e.target === modal) close();
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && modal.style.display === 'block') close();
    });
});
