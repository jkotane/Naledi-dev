document.addEventListener('DOMContentLoaded', function () {
    const ownershipStatusInputs = document.querySelectorAll('input[name="ownershipstatus"]');
    const leseefnameField = document.getElementById('leseefname');
    const leseelnameField = document.getElementById('leseelname');
    const lesee_IDField = document.getElementById('lesee_ID');
    const lesseeDetailsSection = document.getElementById('lesee-details');

    function updateLesseeFields(status) {
        if (status === 'Rented') {
            lesseeDetailsSection.classList.remove('d-none'); // Show lessee details section
            leseefnameField.disabled = false;
            leseefnameField.required = true;

            leseelnameField.disabled = false;
            leseelnameField.required = true;

            lesee_IDField.disabled = false;
            lesee_IDField.required = true;
        } else {
            lesseeDetailsSection.classList.add('d-none'); // Hide lessee details section
            leseefnameField.value = '';
            leseefnameField.disabled = true;
            leseefnameField.removeAttribute('required');

            leseelnameField.value = '';
            leseelnameField.disabled = true;
            leseelnameField.removeAttribute('required');

            lesee_IDField.value = '';
            lesee_IDField.disabled = true;
            lesee_IDField.removeAttribute('required');
        }
    }

    // Initial setup based on pre-selected ownership status
    const selectedOwnershipStatus = document.querySelector('input[name="ownershipstatus"]:checked');
    if (selectedOwnershipStatus) {
        updateLesseeFields(selectedOwnershipStatus.value);
    }

    // Add event listener for ownership status changes
    ownershipStatusInputs.forEach(input => {
        input.addEventListener('change', function () {
            updateLesseeFields(this.value);
        });
    });
});