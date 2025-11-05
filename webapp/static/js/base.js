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
  const idEl = ev.target.closest('.copy-text-parent');
  if (!idEl) {
    return;
  }
  const textEl = idEl.querySelector('.copy-text-text');
  const pastaIdStr = textEl.textContent.trim();
  navigator.clipboard.writeText(pastaIdStr).catch(function (error) {
    errorDialog(error);
  });
  // Create a floating div that says "Copied"
  const copiedDiv = document.createElement('div');
  copiedDiv.textContent = 'Copied';
  copiedDiv.className = 'copy-text-copied-box';
  const parentContainer = ev.target.parentElement;
  parentContainer.appendChild(copiedDiv);
  // Remove the floating div after 2 seconds
  setTimeout(() => {
    copiedDiv.remove();
  }, 2000);
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

// Help dialog

const helpModalEl = document.getElementById('helpModal');
const helpModal = new bootstrap.Modal(helpModalEl);
const helpTitleEl = document.getElementById('helpModalTitle');
const helpBodyEl = document.getElementById('helpModalBody');

document.addEventListener('click', async ev => {
  const anchorEl = ev.target.closest('a[href]');
  if (!anchorEl || !anchorEl.querySelector('.bi-question-circle')) {
    return;
  }
  // It's a help link. We will handle it instead of following it.
  ev.preventDefault();
  // Fetch the help page
  const url = new URL(anchorEl.href, window.location.href);
  const fetchUrl = url.origin + url.pathname;
  const response = await fetch(fetchUrl, {cache: 'no-store'});
  if (!response.ok) {
    throw new Error('Failed to fetch help page');
  }
  const helpHtml = await response.text();
  // Parse the help page
  const helpDoc = new DOMParser().parseFromString(helpHtml, 'text/html');
  // Find the section for the help topic
  const sectionDivEl = helpDoc.getElementById(url.hash.slice(1));
  if (!sectionDivEl) {
    helpTitleEl.textContent = 'Help';
    helpBodyEl.innerHTML = '<p>Help topic not found.</p>';
    helpModal.show();
    return;
  }
  // Clone the help section into a new div
  let newDivEl = helpDoc.createElement('div');
  newDivEl.appendChild(sectionDivEl.cloneNode(true));
  // Move the title from the doc to the modal title
  const heading = newDivEl.querySelector('h1,h2,h3,h4,h5,h6');
  helpTitleEl.textContent = heading ? heading.textContent.trim() : 'Help';
  if (heading) {
    heading.parentElement.removeChild(heading);
  }
  // Set the doc body
  helpBodyEl.innerHTML = '';
  helpBodyEl.appendChild(newDivEl);

  helpModal.show();
  // showModalNextToElement(helpModalEl, anchorEl);
});

// function showModalNextToElement(modalEl, targetEl) {
//   const rect = targetEl.getBoundingClientRect();
//
//   modalEl.style.position = 'absolute';
//   modalEl.style.top = `${rect.bottom + window.scrollY}px`;
//   modalEl.style.left = `${rect.left + window.scrollX}px`;
//   modalEl.style.display = 'block';
//   modalEl.classList.add('show');
// }

function showModalNextToElement(modalEl, targetEl)
{
  const rect = targetEl.getBoundingClientRect();

  // Temporarily show modal to measure its size
  modalEl.style.visibility = 'hidden';
  modalEl.style.display = 'block';
  modalEl.classList.add('show');
  const modalRect = modalEl.getBoundingClientRect();

  // Default position: below and left-aligned with target
  let top = rect.bottom + window.scrollY;
  let left = rect.left + window.scrollX;

  // If modal overflows right, shift left
  if (left + modalRect.width > window.innerWidth) {
    left = window.innerWidth - modalRect.width - 10;
  }
  // If modal overflows bottom, show above target
  if (top + modalRect.height > window.scrollY + window.innerHeight) {
    top = rect.top + window.scrollY - modalRect.height;
  }
  // Prevent negative positions
  top = Math.max(top, 10);
  left = Math.max(left, 10);

  // Set final position and show
  modalEl.style.top = `${top}px`;
  modalEl.style.left = `${left}px`;
  modalEl.style.visibility = 'visible';
}
