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

// Handle PASTA ID copy buttons
// This is a global event listener in order to handle dynamically created elements.
document.addEventListener('click', function(event) {
  const idEl = event.target.closest('.pasta-id-parent');
  if (!idEl) { return; }
  const textEl = idEl.querySelector('.pasta-id-child-text');
  const pastaIdStr = textEl.textContent.trim();
  copyTextToClipboard(pastaIdStr);
});

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
  const modal = new bootstrap.Modal(privacyPolicyModal);
  modal.show();
  // privacyPolicyModal.addEventListener('hidden.bs.modal', function() {
  //   let profileId = privacyPolicyModal.dataset.profileId;
  //   let url = `/profile/${profileId}/privacy_policy`;
  //   window.location.href = url;
  // });
}

// Keep track of the height of the navbar, for use in CSS that limits
// the height of the main content area.

function updateNavbarHeight() {
  const navbar = document.querySelector('.navbar');
  const navbarHeight = navbar.offsetHeight;
  document.documentElement.style.setProperty('--navbar-height', `${navbarHeight}px`);
  const headerHeight = getComputedStyle(document.documentElement).getPropertyValue('--navbar-height');
  console.log('Header Height:', headerHeight);
}

updateNavbarHeight();
window.addEventListener('resize', updateNavbarHeight);
