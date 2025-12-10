const containerFluidEl = document.getElementById('containerFluid');
const enableDevMenu = containerFluidEl.dataset.enableDevMenu === 'true';

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
  // showModalNextToElement2(helpModalEl, anchorEl);
});


// Msg modal

function showMsgModal(title, msg)
{
  const msgModalEl = document.getElementById('msgModal');
  const msgModalTitleEl = document.getElementById('msgModalTitle');
  const msgModalBodyEl = document.getElementById('msgModalBody');
  msgModalTitleEl.textContent = title;
  msgModalBodyEl.innerHTML = msg;
  new bootstrap.Modal(msgModalEl).show();
}

// Confirm modal

function showConfirmModal(title, msg)
{
  const confirmModalEl = document.getElementById('confirmModal');
  const confirmModalTitleEl = document.getElementById('confirmModalTitle');
  const confirmModalBodyEl = document.getElementById('confirmModalBody');
  confirmModalTitleEl.textContent = title;
  confirmModalBodyEl.innerHTML = msg;
  new bootstrap.Modal(confirmModalEl).show();
}

// Returns a Promise that resolves to the clicked button's value (or data-action) for non-form
// modals. Modal buttons should have `data-action` or a `value` attribute.
function showModalValue(modalId, title, msg)
{
  return new Promise((resolve) => {
    const modalEl = document.getElementById(modalId);
    if (!modalEl) {
      resolve(null);
      return;
    }

    const confirmModalTitleEl = document.getElementById('confirmModalTitle');
    const confirmModalBodyEl = document.getElementById('confirmModalBody');
    confirmModalTitleEl.textContent = title;
    confirmModalBodyEl.innerHTML = msg;

    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    const buttons = Array.from(
        modalEl.querySelectorAll('button, input[type="button"], input[type="submit"]'));
    const onHidden = () => {
      cleanup();
      resolve(null);
    };
    const onClick = (e) => {
      e.preventDefault();
      const btn = e.currentTarget;
      // const val = btn.getAttribute('data-action') ?? btn.value ?? null;
      const val = btn.value;
      cleanup();
      modal.hide();
      resolve(val);
    };
    const cleanup = () => {
      modalEl.removeEventListener('hidden.bs.modal', onHidden);
      buttons.forEach((b) => b.removeEventListener('click', onClick));
    };
    modalEl.addEventListener('hidden.bs.modal', onHidden, {once: true});
    buttons.forEach((b) => b.addEventListener('click', onClick, {once: true}));
    modal.show();
  });
}

//

function showModalNextToElement1(modalEl, targetEl)
{
  const rect = targetEl.getBoundingClientRect();
  modalEl.style.position = 'absolute';
  // modalEl.style.top = `${rect.bottom + window.scrollY}px`;
  // modalEl.style.left = `${rect.left + window.scrollX}px`;
  modalEl.style.top = `0px`;
  modalEl.style.left = `0px`;
  modalEl.style.display = 'block';
  modalEl.classList.add('show');
  // helpModal.show();
}

function showModalNextToElement2(modalEl, targetEl)
{
  const dialog = modalEl.querySelector('.modal-dialog') || modalEl;

  // Ensure modal is a direct child of body for absolute positioning
  if (modalEl.parentElement !== document.body) {
    document.body.appendChild(modalEl);
  }
  // Save original inline styles so we can restore on hide
  modalEl._origStyle = {
    position: modalEl.style.position || '',
    top: modalEl.style.top || '',
    left: modalEl.style.left || '',
    display: modalEl.style.display || '',
    visibility: modalEl.style.visibility || '',
    transform: modalEl.style.transform || '',
    zIndex: modalEl.style.zIndex || '',
    margin: modalEl.style.margin || ''
  };
  // Prepare for measurement: remove centering, make visible but hidden for measurement
  modalEl.style.position = 'absolute';
  modalEl.style.margin = '0';
  modalEl.style.transform = 'none';
  modalEl.style.visibility = 'hidden';
  modalEl.style.display = 'block';
  modalEl.classList.add('show');
  modalEl.style.zIndex = 1055;
  // Force reflow to ensure measurements are correct
  dialog.offsetWidth;
  // Measure
  const targetRect = targetEl.getBoundingClientRect();
  const modalRect = dialog.getBoundingClientRect();
  // Default position: below left of target
  let top = targetRect.bottom + window.scrollY;
  let left = targetRect.left + window.scrollX;
  // Adjust to keep inside viewport
  if (left + modalRect.width > window.scrollX + window.innerWidth) {
    left = window.scrollX + window.innerWidth - modalRect.width - 10;
  }
  if (top + modalRect.height > window.scrollY + window.innerHeight) {
    top = targetRect.top + window.scrollY - modalRect.height;
  }
  top = Math.max(top, 10);
  left = Math.max(left, 10);
  // Apply and reveal
  modalEl.style.top = `${top}px`;
  modalEl.style.left = `${left}px`;
  modalEl.style.visibility = 'visible';
  // Backdrop (avoid duplicates)
  if (!document.body.querySelector('.modal-backdrop.custom-show')) {
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop fade show custom-show';
    backdrop.style.zIndex = 1050;
    backdrop.addEventListener('click', hide);
    document.body.appendChild(backdrop);
  }

  // Cleanup/hide
  function hide()
  {
    modalEl.classList.remove('show');
    modalEl.style.display = 'none';
    Object.assign(modalEl.style, modalEl._origStyle || {});
    const bd = document.body.querySelector('.modal-backdrop.custom-show');
    if (bd) {
      bd.remove();
    }
    const closeEls = modalEl.querySelectorAll('[data-bs-dismiss="modal"], .btn-close');
    closeEls.forEach(el => el.removeEventListener('click', hide));
  }

  // Wire dismiss buttons
  const closeEls = modalEl.querySelectorAll('[data-bs-dismiss="modal"], .btn-close');
  closeEls.forEach(el => el.addEventListener('click', hide));

  return hide;
}

// Ctrl-drag rectangle drawing
// This draws a rectangle on the screen while holding Ctrl and dragging the mouse. For use when
// creating tutorials.

let box = null;
let startX = 0;
let startY = 0;
let lastMouseX = 0;
let lastMouseY = 0;

if (enableDevMenu) {
  // Start rectangle on Ctrl keydown (guard against key repeat)
  document.addEventListener('keydown', ev => {
    if (ev.key === 'Control' && !box) {
      if (document.activeElement && document.activeElement.closest('input,textarea,select')) {
        return;
      }
      startX = lastMouseX;
      startY = lastMouseY;
      box = document.createElement('div');
      box.style.position = 'absolute';
      box.style.border = '2px solid red';
      box.style.left = `${startX}px`;
      box.style.top = `${startY}px`;
      box.style.width = '1px';
      box.style.height = '1px';
      box.style.pointerEvents = 'none';
      box.style.zIndex = 9999;
      document.body.appendChild(box);
    }
  });

  // Track mouse position and resize while box exists
  document.addEventListener('mousemove', ev => {
    lastMouseX = ev.pageX;
    lastMouseY = ev.pageY;
    if (box) {
      updateBox(ev.pageX, ev.pageY);
    }
  });

  // Remove rectangle on Ctrl release
  document.addEventListener('keyup', ev => {
    if (ev.key === 'Control' && box) {
      box.remove();
      box = null;
    }
  });

  // Safety: clean up on window blur
  window.addEventListener('blur', () => {
    if (box) {
      box.remove();
      box = null;
    }
  });
}

function updateBox(x, y)
{
  if (!box) {
    return;
  }
  box.style.width = `${Math.abs(x - startX)}px`;
  box.style.height = `${Math.abs(y - startY)}px`;
  box.style.left = `${Math.min(x, startX)}px`;
  box.style.top = `${Math.min(y, startY)}px`;
}
