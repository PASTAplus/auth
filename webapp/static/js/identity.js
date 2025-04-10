// Handle identity unlink buttons
let unlinkIdentityModal = document.getElementById('unlinkIdentityModal');
unlinkIdentityModal.addEventListener('show.bs.modal', function (ev) {
  let button = ev.relatedTarget;
  let idpName = button.getAttribute('data-idp-name');
  let idpUid = button.getAttribute('data-idp-uid');

  let modalGroupIdInput = unlinkIdentityModal.querySelector('#unlinkIdentityIdpName');
  let modalGroupNameInput = unlinkIdentityModal.querySelector('#unlinkIdentityUid');

  modalGroupIdInput.value = idpName;
  modalGroupNameInput.value = idpUid;
});
