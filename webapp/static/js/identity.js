// Handle identity unlink buttons
let unlinkProfileModal = document.getElementById('unlinkProfileModal');
unlinkProfileModal.addEventListener('show.bs.modal', function (ev) {
  let button = ev.relatedTarget;
  let idpName = button.getAttribute('data-idp-name');
  let idpUid = button.getAttribute('data-idp-uid');

  let modalGroupIdInput = unlinkProfileModal.querySelector('#unlinkProfileIdpName');
  let modalGroupNameInput = unlinkProfileModal.querySelector('#unlinkProfileUid');

  modalGroupIdInput.value = idpName;
  modalGroupNameInput.value = idpUid;
});
