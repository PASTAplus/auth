// Highlight the current page in the navigation bar
const pageName = getPageName();
const el_arr = document.querySelectorAll('a.nav-link');
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
  const url = window.location.pathname;
  const split_list = url.split('/');
  return split_list[split_list.length - 1];
}

// Handle EDI ID copy buttons
// This is a global event listener in order to handle dynamically created elements.
document.addEventListener('click', function(ev) {
  if (ev.target.matches('.pasta-id-copy-button')) {
    const idEl = ev.target.closest('.pasta-id-parent');
    const textEl = idEl.querySelector('.pasta-id-child-text');
    const pastaIdStr = textEl.textContent.trim();
    navigator.clipboard.writeText(pastaIdStr).catch(function (error) {
      errorDialog(error);
    });
  }
});

// Keep track of the height of the navbar, for use in CSS that limits
// the height of the main content area.

function updateNavbarHeight() {
  const navbar = document.querySelector('.navbar');
  const navbarHeight = navbar.offsetHeight;
  document.documentElement.style.setProperty('--navbar-height', `${navbarHeight}px`);
}

updateNavbarHeight();
window.addEventListener('resize', updateNavbarHeight);

//
// Modals
//

// Privacy Policy
let privacyPolicyModal = document.getElementById('privacyPolicyModal');
if (privacyPolicyModal.dataset.profileId !== undefined && privacyPolicyModal.dataset.policyAccepted !== 'true') {
  new bootstrap.Modal(privacyPolicyModal).show();
}

// Error dialog

function errorDialog(error) {
  // If the error is a string, convert it to an object.
  const errorMsg = typeof error === 'string' ? `Error: ${error}` :
      error.stack || error || JSON.stringify(error, null, 2);
  document.getElementById('errorMsg').innerText = errorMsg;
  new bootstrap.Modal(document.getElementById('errorModal')).show();
  throw error;
}

document.getElementById('copyErrorButton').addEventListener('click', function() {
  const errorMsg = document.getElementById('errorMsg').innerText;
  navigator.clipboard.writeText(errorMsg).then(
    function () {
      const copyErrorButton = document.getElementById('copyErrorButton');
      copyErrorButton.value = 'Copied';
    }
  ).catch(function (error) {
    alert(error);
  });
});
