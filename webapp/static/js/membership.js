const leaveGroupModal = document.getElementById('leaveGroupModal');

leaveGroupModal.addEventListener('show.bs.modal', function (ev) {
  const button = ev.relatedTarget;
  const modalGroupId = leaveGroupModal.querySelector('#leaveGroupId');
  modalGroupId.value = button.dataset.groupId;
  const modalGroupName = leaveGroupModal.querySelector('#leaveGroupName');
  modalGroupName.textContent = button.dataset.groupName;
  const modalGroupOwner = leaveGroupModal.querySelector('#leaveGroupOwner');
  modalGroupOwner.textContent = button.dataset.groupOwner;
  const modalGroupOwnerEmail = leaveGroupModal.querySelector('#leaveGroupEmail');
  modalGroupOwnerEmail.textContent = button.dataset.groupOwnerEmail;
});
