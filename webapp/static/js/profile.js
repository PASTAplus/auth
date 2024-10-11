const editButton = document.getElementById('editProfile');
const saveButton = document.getElementById('saveProfileButton');

editButton.addEventListener('click', function () {
  const profileMap = getProfileFields();
  console.log(profileMap);
  setModalFields(profileMap);
  // Show the modal using Bootstrap's JavaScript API
  const modal = new bootstrap.Modal(document.getElementById('editProfileModal'));
  modal.show();
});

saveButton.addEventListener('click', function () {
  const profileMap = getProfileFields();
  const modalMap = getModalFields();

  console.log(modalMap);
  setProfileFields(modalMap);

  // Close the modal using Bootstrap's JavaScript API
  const modal = bootstrap.Modal.getInstance(document.getElementById('editProfileModal'));
  modal.hide();

  // Post the data to the server
  fetch('/profile/update', {
    method: 'POST', headers: {
      'Content-Type': 'application/json',
    }, body: JSON.stringify(modalMap),
  }).then(response => {
    if (response.ok) {
      console.log('Profile updated successfully');
    }
    else {
      console.error('Profile update failed');
    }
  }).then(() => {
    // Reload the page if the name changed, as the avatar may then need to be updated
    if (profileMap.full_name !== modalMap.full_name) {
      location.reload();
    }
  });
});

function getProfileFields()
{
  return {
    full_name: document.getElementById('profileName').textContent,
    email: document.getElementById('profileEmail').textContent,
    organization: document.getElementById('profileOrganization').textContent,
    association: document.getElementById('profileAssociation').textContent,
    email_notifications: document.getElementById('profileNotifications').dataset.notifications,
  };
}

function setProfileFields(profileMap)
{
  document.getElementById('profileName').textContent = profileMap.full_name;
  document.getElementById('profileEmail').textContent = profileMap.email;
  document.getElementById('profileOrganization').textContent = profileMap.organization;
  document.getElementById('profileAssociation').textContent = profileMap.association;
  let notificationsEl = document.getElementById('profileNotifications');
  notificationsEl.dataset.notifications = profileMap.email_notifications;
  notificationsEl.textContent = profileMap.email_notifications ? 'Yes' : 'No';
}

function getModalFields()
{
  return {
    full_name: document.getElementById('modalName').value,
    email: document.getElementById('modalEmail').value,
    organization: document.getElementById('modalOrganization').value,
    association: document.getElementById('modalAssociation').value,
    email_notifications: document.getElementById('modalNotifications').checked,
  };
}

function setModalFields(profileMap)
{
  document.getElementById('modalName').value = profileMap.full_name;
  document.getElementById('modalEmail').value = profileMap.email;
  document.getElementById('modalOrganization').value = profileMap.organization;
  document.getElementById('modalAssociation').value = profileMap.association;
  let notificationsEl = document.getElementById('profileNotifications');
  document.getElementById('modalNotifications').checked =
      notificationsEl.dataset.notifications === 'true';
}

// Form validation

const VALID_NAME_RX = /^.{3,}$/;
const VALID_EMAIL_RX = /^[\w.%+-]+@[\w.-]+\.[a-zA-Z]{2,}$/;

document.getElementById('editProfileModal').addEventListener('show.bs.modal', function () {
  console.debug('show.bs.modal');
  validateForm();
});

document.querySelectorAll('.form-control').forEach(function (element) {
  element.addEventListener('input', function (_event) {
    validateForm();
  });
});

function validateForm()
{
  const isNameValid = updateValidationClasses(
      document.getElementById('modalName'), VALID_NAME_RX, false
  );
  const isEmailValid = updateValidationClasses(
      document.getElementById('modalEmail'), VALID_EMAIL_RX, false
  );
  let isFormValid = isNameValid && isEmailValid;
  document.getElementById('saveProfileButton').disabled = !isFormValid;
}

function updateValidationClasses(inputEl, validationRx, emptyIsValid = true)
{
  let el = inputEl.closest('.form-group');
  const val = inputEl.value;

  if (val === '' && emptyIsValid) {
    el.classList.remove('success', 'error');
    return true;
  }

  const isValid = validationRx.test(val);

  if (isValid) {
    inputEl.classList.remove('is-invalid');
    inputEl.classList.add('is-valid');
  }
  else {
    inputEl.classList.remove('is-valid');
    inputEl.classList.add('is-invalid');
  }

  return isValid;
}
