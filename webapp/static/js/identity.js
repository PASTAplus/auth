// Handle identity unlink buttons
let unlinkProfileModal = document.getElementById('unlinkProfileModal');
unlinkProfileModal.addEventListener('show.bs.modal', function (ev) {
  let button = ev.relatedTarget;
  let modalGroupIdInput = unlinkProfileModal.querySelector('#unlinkProfileId');
  modalGroupIdInput.value = button.dataset.profileId;
});
