// Highlight the current page in the navigation bar
const headerEl = document.querySelectorAll('div.header-container[data-highlight-menu]');
if (!headerEl) {
  throw new Error('Missing data-highlight-menu attribute on header-container div');
}
const navEl = document.getElementById(headerEl[0].dataset.highlightMenu);
if (!navEl) {
  throw new Error(`No nav element with id ${headerEl.dataset.highlightMenu}`);
}
navEl.classList.add('active');
// ARIA is an accessibility standard. It helps with screen readers.
navEl.setAttribute('aria-current', 'page');

// Handle EDI-ID copy buttons
// This is a global event listener in order to handle dynamically created elements.
document.addEventListener('click', function (ev) {
  if (ev.target.matches('.edi-id-copy-button')) {
    const idEl = ev.target.closest('.edi-id-parent');
    const textEl = idEl.querySelector('.edi-id-child-text');
    const pastaIdStr = textEl.textContent.trim();
    navigator.clipboard.writeText(pastaIdStr).catch(function (error) {
      errorDialog(error);
    });
    // Create a floating div that says "Copied"
    const copiedDiv = document.createElement('div');
    copiedDiv.textContent = 'Copied';
    copiedDiv.className = 'edi-id-copied-box';
    const parentContainer = ev.target.parentElement;
    parentContainer.appendChild(copiedDiv);
    // Remove the floating div after 2 seconds
    setTimeout(() => {
      copiedDiv.remove();
    }, 2000);
  }
});

// Keep track of the height of the navbar, for use in CSS that limits the height of the main content
// area.

function updateNavbarHeight()
{
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
if (privacyPolicyModal.dataset.profileId !== undefined &&
    privacyPolicyModal.dataset.policyAccepted !== 'true') {
  new bootstrap.Modal(privacyPolicyModal).show();
}

// Error dialog

function errorDialog(error)
{
  // If the error is a string, convert it to an object.
  const errorMsg = typeof error === 'string' ? `Error: ${error}` :
      error.stack || error || JSON.stringify(error, null, 2);
  document.getElementById('errorMsg').innerText = errorMsg;
  new bootstrap.Modal(document.getElementById('errorModal')).show();
  throw error;
}

document.getElementById('copyErrorButton').addEventListener('click', function () {
  const errorMsg = document.getElementById('errorMsg').innerText;
  navigator.clipboard.writeText(errorMsg).then(function () {
    const copyErrorButton = document.getElementById('copyErrorButton');
    copyErrorButton.value = 'Copied';
  }).catch(function (error) {
    alert(error);
  });
});
