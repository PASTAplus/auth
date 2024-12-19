const saveButton = document.getElementById('saveProfileButton');

saveButton.addEventListener('click', function (event) {
  const formEl = document.getElementById('editProfileForm');
  formEl.classList.remove('needs-validation');
  formEl.classList.add('was-validated');
  if (!formEl.checkValidity()) {
    event.preventDefault();
  }
});
