// toggleFields.js

function toggleIDFields() {
  const citizenship = document.getElementById('citizenship').value;
  const saIdField = document.getElementById('saId');
  const passportField = document.getElementById('passportNo');

  if (citizenship === 'South Africa') {
    saIdField.disabled = false;
    saIdField.required = true;
    passportField.disabled = true;
    passportField.required = false;
    passportField.value = ''; // Clear passport field
  } else {
    saIdField.disabled = true;
    saIdField.required = false;
    saIdField.value = ''; // Clear SA ID field
    passportField.disabled = false;
    passportField.required = true;
  }
}

// Attach the event listener to the citizenship dropdown on DOM content load
document.addEventListener('DOMContentLoaded', () => {
  const citizenshipField = document.getElementById('citizenship');
  const saIdField = document.getElementById('saId');
  const passportField = document.getElementById('passportNo');

  // Initialize the state on page load
  toggleIDFields();

  // Listen for changes on the citizenship dropdown
  citizenshipField.addEventListener('change', toggleIDFields);
});

  