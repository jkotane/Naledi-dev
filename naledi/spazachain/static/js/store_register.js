function updateLesseeFields(status) {
    const leseefnameField = document.getElementById('leseefname');
    const leseelnameField = document.getElementById('leseelname');
    const lesee_IDField = document.getElementById('lesee_id');
    const lesseeDetailsSection = document.getElementById('lesee-details');

    if (status === 'Rented') {
        lesseeDetailsSection.classList.remove('d-none'); // Show lessee details
        leseefnameField.disabled = false;
        leseefnameField.required = true;

        leseelnameField.disabled = false;
        leseelnameField.required = true;

        lesee_IDField.disabled = false;
        lesee_IDField.required = true;
    } else {
        lesseeDetailsSection.classList.add('d-none'); // Hide lessee details
        leseefnameField.value = '';
        leseefnameField.disabled = true;
        leseefnameField.required = false;

        leseelnameField.value = '';
        leseelnameField.disabled = true;
        leseelnameField.required = false;

        lesee_IDField.value = '';
        lesee_IDField.disabled = true;
        lesee_IDField.required = false;
    }
}

// Event listener for ownership status change
document.addEventListener('DOMContentLoaded', function () {
    const ownershipStatusInputs = document.querySelectorAll('input[name="ownershipstatus"]');
    const selectedStatus = document.querySelector('input[name="ownershipstatus"]:checked');

    if (selectedStatus) {
        updateLesseeFields(selectedStatus.value);
    }

    ownershipStatusInputs.forEach(input => {
        input.addEventListener('change', function () {
            updateLesseeFields(this.value);
        });
    });
});



