document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("#registerForm");
    form.addEventListener("submit", (event) => {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
      }
      form.classList.add("was-validated");
    });
  });
  