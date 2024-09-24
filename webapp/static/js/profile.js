const editButton = document.getElementById('editProfile');
const saveButton = document.getElementById('saveProfileButton');

editButton.addEventListener('click', function () {
  const profileMap = getProfileFields();
  console.log(profileMap);
  setModalFields(profileMap);
  // Show the modal
  $('#editProfileModal').modal('show');
});

saveButton.addEventListener('click', function () {
  const profileMap = getProfileFields();
  const modalMap = getModalFields();

  // // Handle form submission
  // const formData = new FormData(profileForm);
  // const profileData = {};
  // formData.forEach((value, key) => {
  //   profileData[key] = value;
  // });
  // profileData['send-notifications'] = false;
  // // Example: Log the profile data to the console
  console.log(modalMap);
  setProfileFields(modalMap);

  // Close the modal
  $('#editProfileModal').modal('hide');

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


// closeButton.addEventListener('click', function () {
//   // Close the modal
//   $('#editProfileModal').modal('hide');
// });

function getProfileFields()
{
  return {
    full_name: document.getElementById('profileName').textContent,
    email: document.getElementById('profileEmail').textContent,
    organization: document.getElementById('profileOrganization').textContent,
    association: document.getElementById('profileAssociation').textContent,
    email_notifications: document.getElementById('profileNotifications').checked,
  };
}

function setProfileFields(profileMap)
{
  document.getElementById('profileName').textContent = profileMap.full_name;
  document.getElementById('profileEmail').textContent = profileMap.email;
  document.getElementById('profileOrganization').textContent = profileMap.organization;
  document.getElementById('profileAssociation').textContent = profileMap.association;
  document.getElementById('profileNotifications').checked = profileMap.email_notifications;
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
  document.getElementById('modalNotifications').checked = profileMap.email_notifications;
}

// Form validation

const VALID_NAME_RX = /^.{3,}$/;
const VALID_EMAIL_RX = /^[\w.%+-]+@[\w.-]+\.[a-zA-Z]{2,}$/;

$(document).on('show.bs.modal', '.modal', function () {
  console.debug('show.bs.modal');
  validateForm();
});

$('.form-control').on('keyup', function (_event) {
  validateForm();
});

function validateForm()
{
  const isNameValid = updateValidationClasses($('#modalName'), VALID_NAME_RX);
  const isEmailValid = updateValidationClasses($('#modalEmail'), VALID_EMAIL_RX, false);
  let isFormValid = isNameValid && isEmailValid;
  $('#saveProfileButton').prop('disabled', !isFormValid);
}

function updateValidationClasses(inputEl, validationRx, emptyIsValid = true)
{
  // let el = $(inputEl).closest('.form-group');
  const val = inputEl.val();

  if (val === '' && emptyIsValid) {
    el.removeClass('success error');
    return true;
  }

  const isValid = validationRx.test(val);

  if (isValid) {
    inputEl.removeClass('is-invalid');
    inputEl.addClass('is-valid');
  }
  else {
    inputEl.removeClass('is-valid');
    inputEl.addClass('is-invalid');
  }

  return isValid;
}
