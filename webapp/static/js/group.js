let headerContainerEl = document.getElementsByClassName('header-container')[0];
const ROOT_PATH = headerContainerEl.dataset.rootPath;

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

// let permissionArray = [];
// let principalArray = [];

//
// Initial setup
//

// fetchMembers();

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

principalSearchEl.addEventListener('input', function (_ev) {
  clearTimeout(principalFetchDelay);
  if (principalSearchEl.value.length < 2) {
    principalListEl.classList.remove('visible');
    return;
  }
  principalFetchDelay = setTimeout(fetchPrincipalSearch, 300);
});

principalSearchEl.addEventListener('blur', function (_ev) {
  principalListEl.classList.remove('visible');
});

// We use mousedown instead of click to prevent the blur event on principalSearchEl from firing
// before the click event.
principalListEl.addEventListener('mousedown', function (event) {
  const divEl = event.target.closest('.principal-flex');
  const principalId = parseInt(divEl.dataset.principalId);
  const groupId = getGroupId();
  fetchAddRemoveMember(groupId, principalId, true);
});

// Get value of selected group-select radio button
function getGroupId() {
  return document.querySelector('input[name="group-select"]:checked').value;
}


// principalListEl.addEventListener('click', function (event) {
//   if (!event.target.closest('.icon-text-button')) { return; }
//   const principalEl = event.target.closest('.profile-root');
//   const profileId = parseInt(principalEl.dataset.profileId);
//   const profileArray = searchProfileArray.get(profileId);
//   if (memberProfileArray.has(profileId)) {
//     removeMember(profileId);
//   }
//   else {
//     memberProfileMap.set(profileMap.profile_id, profileMap);
//     refreshMembers();
//     refreshPrincipals();
//     fetchAddRemoveMember(profileId, true);
//   }
// });

// memberListEl.addEventListener('click', function (event) {
//   if (!event.target.closest('.icon-text-button')) { return; }
//   const memberEl = event.target.closest('.profile-root');
//   removeMember(parseInt(memberEl.dataset.profileId));
// });



//
// Fetch
//


function fetchPrincipalSearch()
{
  const searchStr = principalSearchEl.value;
  fetch(`${ROOT_PATH}/group/member/search`, {
    method: 'POST', headers: {
      'Content-Type': 'application/json',
    }, body: JSON.stringify({query: searchStr}),
  })
      .then((response) => response.json())
      .then((resultObj) => {
        console.log('Status:', resultObj.status);
        if (resultObj.error) {
          alert(resultObj.error);
        }
        else {
          searchProfileArray = resultObj.principal_list;
          refreshPrincipals();
        }
      })
      .catch((error) => {
        console.error('Error:', error);
      });
}


function fetchMembers(groupId)
{
  fetch(`/group/member/list/${groupId}`, {
    method: 'GET', headers: {
      'Content-Type': 'application/json',
    },
  })
      .then((response) => response.json())
      .then((resultObj) => {
        console.log('Status:', resultObj.status);
        if (resultObj.error) {
          alert(resultObj.error);
        }
        else {
          memberProfileArray = resultObj.member_list;
          refreshMembers();
        }
      })
      .catch((error) => {
        console.error('Error:', error);
      });
}


function fetchAddRemoveMember(groupId, memberProfileId, isAdd)
{
  if (hasMember(memberProfileId) && isAdd) {
    return;
  }
  fetch(`${ROOT_PATH}/group/member/add-remove`, {
    method: 'POST', headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({group_id: groupId, member_profile_id: memberProfileId, is_add: isAdd}),
  })
      .then((response) => response.json())
      .then((resultObj) => {
        console.log('Status:', resultObj.status);
        if (resultObj.error) {
          alert(resultObj.error);
        }
        else {
          fetchMembers(getGroupId());
          // refreshMembers();
        }
      })
      .catch((error) => {
        console.error('Error:', error);
      });
}


//
// Forms
//

// Fetch all the forms we want to apply custom Bootstrap validation styles to
let forms = document.getElementsByClassName('needs-validation');
// Loop over them and prevent submission
Array.prototype.filter.call(forms, function (form) {
  form.addEventListener('submit', function (event) {
    if (form.checkValidity() === false) {
      event.preventDefault();
      event.stopPropagation();
    }
    form.classList.add('was-validated');
  }, false);
});

// Handle new/edit group buttons and update modal before displaying
let groupModal = document.getElementById('groupModal');
groupModal.addEventListener('show.bs.modal', function (event) {
  let button = event.relatedTarget;

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
deleteGroupModal.addEventListener('show.bs.modal', function (event) {
  let button = event.relatedTarget;
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

function hasMember(profileId) {
  return memberProfileArray.some((profileObj) => profileObj.principal_id === profileId);
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
    memberListEl.innerHTML = `<div class='grid-msg'>No members have been added to this group yet.</div>`;
    return;
  }
  // We use a document fragment to avoid multiple reflows.
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


// function addProfile(parentEl, profileObj, isAdd)
// {
//   const profileEl = document.createElement('div');
//   profileEl.classList.add('profile-flex');
//   profileEl.classList.add('profile-root');
//   profileEl.dataset.profileId = profileObj.profile_id;
//   profileEl.innerHTML = createProfileHtml(profileObj, isAdd);
//   parentEl.appendChild(profileEl);
// }


// function createProfileHtml(profileObj, isAdd)
// {
//   const p = profileObj;
//   let buttonHtml = isAdd ? `
//       <button type='submit' class='icon-text-button' id='addButton'>
//           <span><img src='${ROOT_PATH}/static/svg/arrow-up-from-line.svg' alt='Add'></span>
//           <span>Add</span>
//         </button>
//     ` : `
//       <button type='submit' class='icon-text-button' id='removeButton'>
//           <span><img src='${ROOT_PATH}/static/svg/arrow-down-from-line.svg' alt='Remove'></span>
//           <span>Remove</span>
//         </button>
//     `;
//   return `
//     <div class='profile-flex-row'>
//       <div class='profile-flex-child profile-flex-avatar'>
//         <img src='${p.avatar_url}' alt='Avatar' class='avatar avatar-small'>
//       </div>
//       <div class='profile-flex-child profile-flex-name'>${p.full_name}</div>
//       <div class='profile-flex-child'>${p.email}</div>
//       <div class='profile-flex-child'>${p.organization || ''}</div>
//       <div class='profile-flex-child'>${p.association || ''}</div>
//       <div class='profile-flex-child profile-flex-button'>
//         ${buttonHtml}
//       </div>
//     </div>
//   `;
// }

// Create the HTML for either a member or a principal.
function addPrincipalDiv(parentEl, principalObj)
{
  const p = principalObj;
  const principalEl = document.createElement('div');
  principalEl.classList.add('principal-flex');
  principalEl.dataset.principalId = p.principal_id;
  principalEl.dataset.principalType = p.principal_type;
  principalEl.innerHTML = `
    <div class='principal-child principal-avatar'>
      <img src='${p.avatar_url}' alt='Avatar' class='avatar avatar-smaller'>
    </div>
    <div class='principal-child principal-info'>
      <div class='principal-info-child'>${p.title}</div>
      <div class='principal-info-child'>${p.description}</div>

      <div class='principal-info-child'>
        <div class='pasta-id-parent'>
          <div class='pasta-id-child-text'>
            ${p.pasta_id}
          </div>
          <div class='pasta-id-child-icon'>
            <img class='pasta-id-copy-button' 
              src='${ROOT_PATH}/static/svg/copy.svg' 
              alt='Copy User Identifier'
            >
          </div>
        </div>
      </div>
    </div>
  `;
  parentEl.appendChild(principalEl);
}


function addRemoveButtonDiv(parentEl, principalObj) {
  const removeEl = document.createElement('div');
  removeEl.dataset.principalId = principalObj.principal_id;
  removeEl.innerHTML = `
    <button class='icon-text-button'>
      <span><img src='${ROOT_PATH}/static/svg/arrow-down-from-line.svg' alt='Remove'></span>
      <span>Remove</span>
    </button>
  `;
  parentEl.appendChild(removeEl);
}
