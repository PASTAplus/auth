// Fetch all the forms we want to apply custom Bootstrap validation styles to
let forms = document.getElementsByClassName('needs-validation');
// Loop over them and prevent submission
Array.prototype.filter.call(forms, function (form) {
  form.addEventListener('submit', function (event) {
    if (form.checkValidity() === false) {
      event.preventDefault();
      event.stopPropagation();
    }
    form.classList.add('was-validated');
  }, false);
});

// Handle new/edit group buttons and update modal before displaying
let groupModal = document.getElementById('groupModal');
groupModal.addEventListener('show.bs.modal', function (event) {
  let button = event.relatedTarget;

  let formTarget = button.getAttribute('data-form-target');
  let groupTitle = button.getAttribute('data-title');
  let groupId = button.getAttribute('data-group-id');
  let groupName = button.getAttribute('data-group-name');
  let groupDescription = button.getAttribute('data-group-description');
  let submitText = button.getAttribute('data-submit-text');

  let formEl = groupModal.querySelector('#groupForm');
  let titleEl = groupModal.querySelector('#groupTitle');
  let IdEl = groupModal.querySelector('#groupId');
  let nameEl = groupModal.querySelector('#groupName');
  let descriptionEl = groupModal.querySelector('#groupDescription');
  let submitEl = groupModal.querySelector('#groupButton');

  formEl.action = formTarget;
  titleEl.textContent = groupTitle;
  IdEl.value = groupId;
  nameEl.value = groupName;
  descriptionEl.value = groupDescription;
  submitEl.textContent = submitText;
});


// Handle group delete buttons and update modal before displaying
let deleteGroupModal = document.getElementById('deleteGroupModal');
deleteGroupModal.addEventListener('show.bs.modal', function (event) {
  let button = event.relatedTarget;
  let groupId = button.getAttribute('data-group-id');
  let groupName = button.getAttribute('data-group-name');

  let modalGroupIdInput = deleteGroupModal.querySelector('#deleteGroupId');
  let modalGroupNameInput = deleteGroupModal.querySelector('#deleteGroupName');

  modalGroupIdInput.value = groupId;
  modalGroupNameInput.textContent = groupName;
});
