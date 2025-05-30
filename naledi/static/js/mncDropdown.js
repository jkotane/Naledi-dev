const municipalitiesByProvince = {
  "Eastern Cape": ["Buffalo City", "Nelson Mandela Bay", "Sarah Baartman District"],
  "Free State": ["Mangaung", "Lejweleputswa District", "Thabo Mofutsanyana District"],
  "Gauteng": ["City of Johannesburg", "City of Tshwane", "Ekurhuleni"],
  "KwaZulu-Natal": ["eThekwini", "uMgungundlovu District", "uThukela District"],
  "Limpopo": ["Capricorn District", "Mopani District", "Sekhukhune District"],
  "Mpumalanga": ["Ehlanzeni District", "Gert Sibande District", "Nkangala District"],
  "Northern Cape": ["Frances Baard District", "Namakwa District", "Pixley ka Seme District"],
  "North West": ["Bojanala Platinum District", "Dr Kenneth Kaunda District","Ngaka Modiri Molema District"],
  "Western Cape": ["City of Cape Town", "Garden Route District", "Overberg District"],
};

document.getElementById("province").addEventListener("change", function () {
  const province = this.value;
  const municipalityDropdown = document.getElementById("municipality");

  // Clear existing options
  municipalityDropdown.innerHTML = '<option value="" disabled selected>Select your municipality</option>';

  // Add new options based on selected province
  if (municipalitiesByProvince[province]) {
    municipalitiesByProvince[province].forEach((municipality) => {
      const option = document.createElement("option");
      option.value = municipality;
      option.textContent = municipality;
      municipalityDropdown.appendChild(option);
    });
  }
});
