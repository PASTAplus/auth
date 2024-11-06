// Highlight the current page in the navigation bar
let pageName = getPageName();
let el_arr = document.querySelectorAll('a.nav-link');
for (let el of el_arr) {
  if (el.getAttribute('href').endsWith(`/${pageName}`)) {
    el.classList.add('active');
    // ARIA is an accessibility standard. It helps with screen readers.
    el.setAttribute('aria-current', 'page');
  } else {
    el.classList.remove('active');
    el.setAttribute('aria-current', 'false');
  }
}

function getPageName() {
  let url = window.location.pathname;
  let split_list = url.split('/');
  return split_list[split_list.length - 1];
}

// Handle PASTA ID copy buttons
let copyButtons = document.querySelectorAll('.pasta-id-child-icon');
for (let button of copyButtons) {
  button.addEventListener('click', function(e) {
    let currentEl = e.target;
    let pastaIdStr = currentEl.parentElement.previousElementSibling.textContent.trim();
    copyTextToClipboard(pastaIdStr);
  });
}

function copyTextToClipboard(text)
{
  navigator.clipboard.writeText(text).then(function () {
    console.log('Text copied to clipboard');
  }).catch(function (err) {
    console.error('Could not copy text: ', err);
  });
}

// Privacy Policy Modal

let privacyPolicyModal = document.getElementById('privacyPolicyModal');
if (privacyPolicyModal.dataset.profileId !== undefined && privacyPolicyModal.dataset.policyAccepted !== 'true') {
  let modal = new bootstrap.Modal(privacyPolicyModal);
  modal.show();
  // privacyPolicyModal.addEventListener('hidden.bs.modal', function() {
  //   let profileId = privacyPolicyModal.dataset.profileId;
  //   let url = `/profile/${profileId}/privacy_policy`;
  //   window.location.href = url;
  // });
}

