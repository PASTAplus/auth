let headerContainerEl = document.getElementsByClassName('header-container')[0];
const BASE_PATH = headerContainerEl.dataset.basePath;

// The search input for new member principals
const principalSearchEl = document.getElementById('principalSearch');
// The list of principal search results
const principalListEl = document.getElementById('principalList');
// Fetching search results when the user stops typing
let principalFetchDelay = null;

// The list of members in the group
const memberListEl = document.getElementById('memberList');

let memberProfileArray = [];
let searchProfileArray = [];

// Init

// refreshSearchInput();

//
// Events
//

// Group list (left side)

// Global click handler
document.addEventListener('click', function (ev) {
  // Propagate click on any child of group-details class to the previous group-select radio button
  const detailsEl = ev.target.closest('.group-details');
  if (detailsEl) {
    // Ignore elements that can receive click without changing the selected group
    if (ev.target.tagName === 'BUTTON' || ev.target.tagName === 'IMG') {
      return;
    }
    // Find previous group-select radio button
    const radioEl = detailsEl.previousElementSibling.querySelector('input[name="group-select"]');
    radioEl.click();
  }
});

// Show new members on click on all group-select radio buttons
let groupSelectEls = document.querySelectorAll('input[name="group-select"]');
for (const selectEl of groupSelectEls) {
  selectEl.addEventListener('click', function (_ev) {
    fetchMembers(selectEl.value);
  });
}

// Member list (right side)

// Search for new members
principalSearchEl.addEventListener('input', function (_ev) {
  clearTimeout(principalFetchDelay);
  if (principalSearchEl.value.length < 2) {
    principalListEl.classList.remove('visible');
    return;
  }
  principalFetchDelay = setTimeout(fetchPrincipalSearch, 300);
});

// Hide the principal list when the search input loses focus
principalSearchEl.addEventListener('blur', function (_ev) {
  principalListEl.classList.remove('visible');
});

// Add a principal to the group
// We use mousedown instead of click to prevent the blur event on principalSearchEl from firing
// before the click event.
principalListEl.addEventListener('mousedown', function (ev) {
  const divEl = ev.target.closest('.principal-flex');
  const profileId = parseInt(divEl.dataset.profileId);
  const groupId = getGroupId();
  fetchAddRemoveMember(groupId, profileId, true);
  principalSearchEl.value = '';
});

// Get value of selected group-select radio button
function getGroupId()
{
  return document.querySelector('input[name="group-select"]:checked').value;
}

// Remove a profile from the group
// Global click handler
document.addEventListener('click', function (ev) {
  const buttonEl = ev.target.closest('.remove-button');
  if (!buttonEl) {return;}
  const profileId = parseInt(buttonEl.parentElement.dataset.profileId);
  const groupId = getGroupId();
  fetchAddRemoveMember(groupId, profileId, false);
});


//
// Fetch
//


function fetchPrincipalSearch()
{
  const searchStr = principalSearchEl.value;
  fetch(`${BASE_PATH}/int/api/group/member/search`, {
    method: 'POST', headers: {
      'Content-Type': 'application/json',
    }, body: JSON.stringify({query: searchStr}),
  })
      .then((response) => {
        if (response.status === 401) {
          window.location = `${BASE_PATH}/ui/signin?info=expired`;
          return Promise.reject('Unauthorized');
        }
        return response.json();
      })
      .then((resultObj) => {
        if (resultObj.error) {
          errorDialog(resultObj.error);
        }
        else {
          searchProfileArray = resultObj;
          refreshPrincipals();
        }
      })
      .catch((error) => {
        errorDialog(error);
      });
}


function fetchMembers(groupId)
{
  fetch(`/int/api/group/member/list/${groupId}`, {
    method: 'GET', headers: {
      'Content-Type': 'application/json',
    },
  })
      .then((response) => {
        if (response.status === 401) {
          window.location = `${BASE_PATH}/ui/signin?info=expired`;
          return Promise.reject('Unauthorized');
        }
        return response.json();
      })
      .then((resultObj) => {
        if (resultObj.error) {
          errorDialog(resultObj.error);
        }
        else {
          memberProfileArray = resultObj;
          refreshMembers();
          setMemberCount(groupId, memberProfileArray.length);
          principalSearchEl.placeholder = 'Add Users and Groups';
          principalSearchEl.disabled = false;
        }
      })
      .catch((error) => {
        errorDialog(error);
      });
}


function fetchAddRemoveMember(groupId, memberProfileId, isAdd)
{
  if (hasMember(memberProfileId) && isAdd) {
    return;
  }
  fetch(`${BASE_PATH}/int/api/group/member/add-remove`, {
    method: 'POST', headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({group_id: groupId, member_profile_id: memberProfileId, is_add: isAdd}),
  })
      .then((response) => {
        if (response.status === 401) {
          window.location = `${BASE_PATH}/ui/signin?info=expired`;
          return Promise.reject('Unauthorized');
        }
        return response.json();
      })
      .then((resultObj) => {
        if (resultObj.error) {
          errorDialog(resultObj.error);
        }
        else {
          fetchMembers(getGroupId());
          // refreshMembers();
        }
      })
      .catch((error) => {
        errorDialog(error);
      });
}


function setMemberCount(groupId, count)
{
  const radioEl = document.querySelector(`input[name="group-select"][value='${groupId}']`);
  const detailsEl = radioEl.parentElement.nextElementSibling;
  const countEl = detailsEl.querySelector('.member-count');
  countEl.textContent = `${count} member${count === 1 ? '' : 's'}`;
}


//
// Forms
//

// Fetch all the forms we want to apply custom Bootstrap validation styles to
let forms = document.getElementsByClassName('needs-validation');
// Loop over them and prevent submission
Array.prototype.filter.call(forms, function (form) {
  form.addEventListener('submit', function (ev) {
    if (form.checkValidity() === false) {
      ev.prevDefault();
      ev.stopPropagation();
    }
    form.classList.add('was-validated');
  }, false);
});

// Handle new/edit group buttons and update modal before displaying
let groupModal = document.getElementById('groupModal');
groupModal.addEventListener('show.bs.modal', function (ev) {
  let button = ev.relatedTarget;

  let formTarget = button.getAttribute('data-form-target');
  let groupTitle = button.getAttribute('data-title');
  let groupId = button.getAttribute('data-group-id');
  let groupName = button.getAttribute('data-group-name');
  let groupDescription = button.getAttribute('data-group-description');
  let submitText = button.getAttribute('data-submit-text');

  let formEl = groupModal.querySelector('#groupForm');
  let titleEl = groupModal.querySelector('#groupTitle');
  let IdEl = groupModal.querySelector('#groupId');
  let nameEl = groupModal.querySelector('#groupName');
  let descriptionEl = groupModal.querySelector('#groupDescription');
  let submitEl = groupModal.querySelector('#groupButton');

  formEl.action = formTarget;
  titleEl.textContent = groupTitle;
  IdEl.value = groupId;
  nameEl.value = groupName;
  descriptionEl.value = groupDescription;
  submitEl.textContent = submitText;
});


// Handle group delete buttons and update modal before displaying
let deleteGroupModal = document.getElementById('deleteGroupModal');
deleteGroupModal.addEventListener('show.bs.modal', function (ev) {
  let button = ev.relatedTarget;
  let groupId = button.getAttribute('data-group-id');
  let groupName = button.getAttribute('data-group-name');

  let modalGroupIdInput = deleteGroupModal.querySelector('#deleteGroupId');
  let modalGroupNameInput = deleteGroupModal.querySelector('#deleteGroupName');

  modalGroupIdInput.value = groupId;
  modalGroupNameInput.textContent = groupName;
});

//
// Util
//

function hasMember(profileId)
{
  return memberProfileArray.some((profileObj) => profileObj.profile_id === profileId);
}


function removeMember(profileId)
{
  // memberProfileMap.delete(profileId);
  // refreshMembers();
  // refreshPrincipals();
  // fetchAddRemoveMember(profileId, false);
}

function refreshMembers()
{
  if (!memberProfileArray.length) {
    memberListEl.innerHTML =
        `<div class='grid-msg'>No members have been added to this group yet.</div>`;
    return;
  }
  const fragment = document.createDocumentFragment();
  for (const profileObj of memberProfileArray) {
    addPrincipalDiv(fragment, profileObj);
    addRemoveButtonDiv(fragment, profileObj);
  }
  memberListEl.replaceChildren(fragment);
}


function refreshPrincipals()
{
  principalListEl.classList.add('visible');

  if (!searchProfileArray.length && principalSearchEl.value.length > 1) {
    principalListEl.innerHTML = `<div class='grid-msg'>No principals found.</div>`;
    return;
  }
  const fragment = document.createDocumentFragment();
  for (const profileObj of searchProfileArray) {
    addPrincipalDiv(fragment, profileObj);
  }
  principalListEl.replaceChildren(fragment);
}


// Create the HTML for either a member or a principal.
function addPrincipalDiv(parentEl, principalObj)
{
  const p = principalObj;
  const principalEl = document.createElement('div');
  principalEl.classList.add('principal-flex');
  principalEl.dataset.profileId = p.profile_id;
  principalEl.innerHTML = `
    <div class='principal-child principal-avatar'>
      <img src='${p.avatar_url}' alt='Avatar' class='avatar avatar-smaller'>
    </div>
    <div class='principal-child principal-info'>
      <div class='principal-title'>${p.title || ''}</div>
      <div class='principal-description'>${p.description || ''}</div>
      <div class='edi-id-parent'>
        <div class='edi-id-child-text'>
          ${p.edi_id}
        </div>
        <div class='edi-id-child-icon'>
          <img class='edi-id-copy-button'
            src='${BASE_PATH}/static/svg/copy.svg'
            alt='Copy User Identifier'
          >
        </div>
      </div>
    </div>
  `;
  parentEl.appendChild(principalEl);
}


function addRemoveButtonDiv(parentEl, principalObj)
{
  const removeEl = document.createElement('div');
  removeEl.dataset.profileId = principalObj.profile_id;
  removeEl.innerHTML = `
    <button class='remove-button icon-text-button'>
      <span><img src='${BASE_PATH}/static/svg/leave-group.svg' alt='Remove'></span>
      <span>Remove</span>
    </button>
  `;
  parentEl.appendChild(removeEl);
}
