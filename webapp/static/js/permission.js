let headerContainerEl = document.getElementsByClassName('header-container')[0];
const ROOT_PATH = headerContainerEl.dataset.rootPath;
const PERMISSION_LEVEL_LIST = ['None', 'Reader', 'Editor', 'Owner'];

// The search input for resources
const collectionSearchEl = document.getElementById('collectionSearch');
const collectionListEl = document.getElementById('collectionList');
let resourceFetchDelay = null;

selectAllCheckboxEl = document.getElementById('selectAllCheckbox');
showPermissionsCheckboxEl = document.getElementById('showPermissionsCheckbox');

const permissionListEl = document.getElementById('permissionList');

// The search input for candidates
const candidateSearchEl = document.getElementById('candidateSearch');
// The list of candidate search results
const candidateListEl = document.getElementById('candidateList');
let candidateFetchDelay = null;


const collectionMap = new Map();
const permissionProfileMap = new Map();
const candidateProfileMap = new Map();

/*
  Initial setup
*/

// For testing
collectionSearchEl.value = 'knb';
fetchCollectionSearch();
refreshCollections();

/*
  Events
*/

collectionSearchEl.addEventListener('input', function (e) {
  clearTimeout(resourceFetchDelay);
  if (collectionSearchEl.value.length < 3) {
    collectionMap.clear();
    refreshCollections();
    permissionProfileMap.clear();
    refreshPermissions();
    return;
  }
  resourceFetchDelay = setTimeout(fetchCollectionSearch, 300);
});


candidateSearchEl.addEventListener('input', function (e) {
  clearTimeout(candidateFetchDelay);
  if (candidateSearchEl.value.length < 2) {
    // candidateListEl.classList.remove('visible');
    return;
  }
  candidateFetchDelay = setTimeout(fetchCandidateSearch, 300);
});

candidateSearchEl.addEventListener('blur', function (e) {
  // candidateListEl.classList.remove('visible');
});

// We can't add an event handler directly to dynamically generated elements, so we use event
// delegation to listen for clicks on the parent element.
permissionListEl.addEventListener('change', function (event) {
  // Handle new permission level set in dropdown
  if (event.target.classList.contains('level-dropdown')) {
    // dataset is an HTML attribute, and all attributes are stored as strings
    const profileId = parseInt(event.target.closest('div').dataset.profileId);
    const permissionLevel = parseInt(event.target.value);
    const resources = getAllSelectedResources();
    fetchSetPermission(resources, profileId, permissionLevel);

    // Test re the race condition TODO

    event.target.disabled = true;
  }
});

// permissionListEl.addEventListener('click', function (event) {
//   // Trigger change event on level-dropdown, even if the same level is selected again. This allows a
//   // permission that only exists for some of the selected resources, to be applied to all the
//   // selected resources without changing the permission level.
//   if (event.target.classList.contains('level-dropdown')) {
//     event.target.dispatchEvent(new Event('change', {bubbles: true}));
//   }
// });

// We use mousedown instead of click to prevent the blur event on candidateSearchEl from firing
// before the click event.
candidateListEl.addEventListener('mousedown', function (event) {
  const profileId = parseInt(event.target.closest('.profile-flex').dataset.profileId);
  const resources = getAllSelectedResources();
  fetchSetPermission(resources, profileId, 1);
  // candidateSearchEl.value = '';
  // fetchPermissionCrud('create', {
  //   profileId: profileId, resourceId: globResourceId,
  // });
  // fetchGetPermissions(globResourceId);
});


selectAllCheckboxEl.addEventListener('change', function (event) {
  // const checkboxes = document.querySelectorAll('.collection-item input[type="checkbox"]');
  const checkboxes = document.querySelectorAll(
      // '.collection-checkbox-collection,.collection-checkbox-resource');
        '.collection-checkbox');

  for (const checkbox of checkboxes) {
    checkbox.checked = event.target.checked;
  }
});

document.addEventListener('change', function (event) {
  // Propagate click on collection checkbox to resource checkboxes.
  if (event.target.classList.contains('collection-checkbox-collection')) {
    const collectionItem = event.target.closest('.collection-item');
    const resourceCheckboxes = collectionItem.querySelectorAll('.collection-checkbox-resource');
    for (const checkbox of resourceCheckboxes) {
      checkbox.checked = event.target.checked;
      // If any checkbox is unchecked, uncheck the selectAllCheckbox.
      selectAllCheckboxEl.checked = false;
    }
  }
  // If a resource checkbox is unchecked, uncheck the collection checkbox.
  if (event.target.classList.contains('collection-checkbox-resource')) {
    const collectionItem = event.target.closest('.collection-item');
    if (!event.target.checked) {
      const collectionCheckbox = collectionItem.querySelector('.collection-checkbox-collection');
      collectionCheckbox.checked = false;
      // If any checkbox is unchecked, uncheck the selectAllCheckbox.
      selectAllCheckboxEl.checked = false;
    }
  }
  // If all checkboxes are checked, check the selectAllCheckbox.
  if (isAllChecked()) {
    selectAllCheckboxEl.checked = true;
  }
  //
  const resources = getAllSelectedResources();
  fetchGetPermissions(resources);
});

// Show and hide individual permissions in the Resources list
showPermissionsCheckboxEl.addEventListener('change', function (_event) {
  refreshShowPermissions();
});


/*
  Fetch
*/

function fetchCollectionSearch(preserveCheckboxStates = false)
{
  const searchStr = collectionSearchEl.value;
  // console.log('fetchCollectionSearch() searchStr:', searchStr);

  // "Searching" message can go here.
  // collectionListEl.innerHTML = `<div class='grid-msg'>Searching...</div>`;

  fetch(`${ROOT_PATH}/permission/resource/search`, {
    method: 'POST', headers: {
      'Content-Type': 'application/json',
    }, body: JSON.stringify({query: searchStr}),
  })
      .then((response) => response.json())
      .then((resultObj) => {
        // console.log('fetchCollectionSearch() Status:', resultObj.status);
        if (resultObj.error) {
          alert(resultObj.error);
        }
        else {
          collectionMap.clear();
          // TODO: Probably don't need to iterate here. Can just assign the collection_dict to
          // collectionMap.
          for (const [collectionId, collectionObj] of Object.entries(resultObj.collection_dict)) {
            collectionMap.set(parseInt(collectionId), collectionObj);
          }
          const checkboxStates = saveCheckboxStates();
          refreshCollections();
          if (preserveCheckboxStates) {
            restoreCheckboxStates(checkboxStates);
          }
          else {
            selectAllCheckboxEl.checked = false;

            permissionProfileMap.clear();
            refreshPermissions();
            refreshShowPermissions();
          }
          // const resources = getAllSelectedResources();
          // fetchGetPermissions(resources);
          // selectAllCheckboxEl.dispatchEvent(new Event('change'));
        }
      })
      .catch((error) => {
        console.error('Error:', error);
      });
}


function fetchGetPermissions(resources)
{
  fetch(`${ROOT_PATH}/permission/get-list`, {
    method: 'POST', headers: {
      'Content-Type': 'application/json',
    }, body: JSON.stringify(resources),
  })
      .then((response) => response.json())
      .then((resultObj) => {
        // console.log('fetchGetPermissions() Status:', resultObj.status);
        if (resultObj.error) {
          alert(resultObj.error);
        }
        else {
          permissionProfileMap.clear();
          for (const profPermObj of resultObj.profile_permission_list) {
            permissionProfileMap.set(profPermObj.permission_id, profPermObj);
          }
          refreshPermissions();
        }
      })
      .catch((error) => {
        console.error('Error:', error);
      });
}

function fetchSetPermission(resources, profileId, permissionLevel)
{
  fetch(`${ROOT_PATH}/permission/update`, {
    method: 'POST', headers: {
      'Content-Type': 'application/json',
    }, body: JSON.stringify({
      resources: resources, profileId: profileId, permissionLevel: permissionLevel,
    }),
  })
      .then((response) => response.json())
      .then((resultObj) => {
        // console.log('fetchSetPermission() Status:', resultObj.status);
        if (resultObj.error) {
          alert(resultObj.error);
        }
        else {
          fetchCollectionSearch(true);
          // TODO: cleanest?
          candidateSearchEl.value = '';
          // refreshPermissions();
        }
      })
      .catch((error) => {
        console.error('fetchSetPermission() Error:', error);
      });
}


// function fetchPermissionCrud(action, o)
// {
//   o.action = action;
//   // console.log('fetchPermissionCrud() o:', o);
//   fetch(`${ROOT_PATH}/permission/crud`, {
//     method: 'POST', headers: {
//       'Content-Type': 'application/json',
//     }, body: JSON.stringify(o)
//   })
//       .then((response) => response.json())
//       .then((resultObj) => {
//         // console.log('fetchPermissionCrud() Status:', resultObj.status);
//         // Handle situation where a permission was set to None, then to another value. This creates
//         // a new permission, so we need to update the permissionProfileMap.
//         if (resultObj.permissionId) {
//           const v = permissionProfileMap.get(o.permissionId);
//           permissionProfileMap.delete(o.permissionId);
//           permissionProfileMap.set(resultObj.permissionId, v);
//         }
//         if (resultObj.error) {
//           alert(resultObj.error);
//         }
//       })
//       .catch((error) => {
//         console.error('fetchPermissionCrud() Error:', error);
//       });
// }

function fetchCandidateSearch()
{
  const searchStr = candidateSearchEl.value;
  // console.log('searchStr:', searchStr);

  fetch(`${ROOT_PATH}/permission/candidate/search`, {
    method: 'POST', headers: {
      'Content-Type': 'application/json',
    }, body: JSON.stringify({query: searchStr}),
  })
      .then((response) => response.json())
      .then((resultObj) => {
        // console.log('Status:', resultObj.status);
        if (resultObj.error) {
          alert(resultObj.error);
        }
        else {
          candidateProfileMap.clear();
          for (const candidateObj of resultObj.candidate_list) {
            candidateProfileMap.set(candidateObj.profile_id, candidateObj);
          }
          refreshCandidates();
        }
      })
      .catch((error) => {
        console.error('Error:', error);
      });
}

/*
  Refresh
*/

function refreshCollections()
{
  if (collectionMap.size === 0) {
    collectionListEl.innerHTML = `<div class='grid-msg'>No resources found</div>`;
    return;
  }
  // We use a document fragment to avoid multiple reflows.
  const fragment = document.createDocumentFragment();
  for (const [collectionId, collectionObj] of collectionMap) {
    addCollectionDiv(fragment, collectionId, collectionObj);
  }
  collectionListEl.replaceChildren(fragment);
}


function refreshPermissions()
{
  if (permissionProfileMap.size === 0) {
    let emptyMsg;
    if (isSomeChecked()) {
      candidateSearchEl.placeholder = 'Add Users and Groups';
      emptyMsg = 'No permissions have been added yet';
      candidateSearchEl.disabled = false;
    }
    else {
      candidateSearchEl.placeholder = 'Select resources to set permissions';
      emptyMsg = '';
      candidateSearchEl.disabled = true;
    }
    permissionListEl.innerHTML = `<div class='grid-msg'>${emptyMsg}</div>`;
    return;
  }
  else {
    candidateSearchEl.placeholder = 'Add Users and Groups';
    candidateSearchEl.disabled = false;
  }

  // We use a document fragment to avoid multiple reflows.
  const fragment = document.createDocumentFragment();
  for (const [_permissionId, permissionObj] of permissionProfileMap) {
    addCandidateDiv(fragment, permissionObj);
    addPermissionLevelDropdownDiv(fragment, permissionObj);
  }
  permissionListEl.replaceChildren(fragment);
}


function refreshCandidates()
{
  if (candidateProfileMap.size === 0) {
    candidateListEl.innerHTML = `<div class='grid-msg'>No user profiles or groups found</div>`;
    candidateListEl.classList.add('visible');
    return;
  }
  // We use a document fragment to avoid multiple reflows.
  const fragment = document.createDocumentFragment();
  for (const [_profile_id, candidateObj] of candidateProfileMap) {
    addCandidateDiv(fragment, candidateObj);
    // classList holds only unique values, so no need to check if it already exists
    candidateListEl.classList.add('visible');
  }
  candidateListEl.replaceChildren(fragment);
}


function addCollectionDiv(parentEl, collectionId, collectionObj)
{
  const collectionEl = document.createElement('div');
  collectionEl.classList.add('collection-item');
  collectionEl.dataset.collectionId = collectionId;
  collectionEl.innerHTML = `
    <div class=''>
      <label>
        <input type='checkbox' class='collection-checkbox collection-checkbox-collection'/>
        ${collectionObj.collection_label}     
      </label>
    </div>
    <div class=''>
      ${formatCollectionResourceDict(collectionObj.resource_dict)}
   </div>
  `;
  parentEl.appendChild(collectionEl);
}


function formatCollectionResourceDict(resourceDict)
{
  let htmlList = [];
  for (const [resourceType, resourceObj] of Object.entries(resourceDict)) {
    htmlList.push(`
      <div class='collection-indent'>
        <div class=''>
          <label class='collection-resource-type'>
            <input type='checkbox' class='collection-checkbox collection-checkbox-resource'/>
            ${resourceType}
          </label>
        </div>
        <div class=''>
          ${formatCollectionProfileDict(resourceObj.profile_list)}
        </div>
      </div>
    `);
  }
  return htmlList.join('');
}


function formatCollectionProfileDict(profileList)
{
  let htmlList = [];
  for (const profileObj of profileList) {
    htmlList.push(`
      <div class='collection-indent collection-profile-row'>
        <div class='collection-name'>${profileObj.full_name}</div> 
        <div class='collection-pasta-id'>${profileObj.pasta_id}</div>
        <div class='collection-perm-level'>${formatPermissionLevel(profileObj.permission_level)}</div>
      </div>
    `);
  }
  return htmlList.join('');
}


function formatPermissionLevel(level)
{
  return PERMISSION_LEVEL_LIST[level] || 'Unknown';
}

function addCandidateDiv(parentEl, candidateObj):

// Add a div with profile avatar and info to the parent element.
// This is used for both permissions and candidates.
function addProfileDiv(parentEl, profileObj)
{
  const p = profileObj;
  const profEl = document.createElement('div');
  profEl.classList.add('profile-flex');
  profEl.dataset.profileId = p.profile_id;
  profEl.innerHTML = `
    <div class='profile-child profile-avatar'>
      <img src='${p.avatar_url}' alt='Avatar' class='avatar avatar-smaller'>
    </div>
    <div class='profile-child profile-info'>
      <div class='profile-info-child'>${p.full_name}</div>
      <div class='profile-info-child'>${p.email}</div>

      <div class='profile-info-child'>
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
  parentEl.appendChild(profEl);
}


function addPermissionLevelDropdownDiv(parentEl, permissionObj)
{
  const levelEl = document.createElement('div');
  levelEl.dataset.permissionId = permissionObj.permission_id;
  levelEl.dataset.profileId = permissionObj.profile_id;
  permission_level = permissionObj.permission_level;
  levelEl.innerHTML = `
    <select class='level-dropdown'>
      <option value='0' ${permission_level === 0 ? 'selected' : ''}>None</option>
      <option value='1' ${permission_level === 1 ? 'selected' : ''}>Reader</option>
      <option value='2' ${permission_level === 2 ? 'selected' : ''}>Editor</option>
      <option value='3' ${permission_level === 3 ? 'selected' : ''}>Owner</option>
    </select>
  `;
  parentEl.appendChild(levelEl);
}

function refreshShowPermissions()
{
  const permissionList = document.querySelectorAll('.collection-profile-row');
  for (const permission of permissionList) {
    permission.classList.toggle('hidden', !showPermissionsCheckboxEl.checked);
  }
}

/*
  Utility
*/

// Return a list of [collectionId, resourceType] for each checked resource checkbox.
function getAllSelectedResources()
{
  const selectedResourceIds = [];
  // Since resource checkboxes are updated when collection checkboxes are clicked, we only need to
  // iterate over the resource checkboxes.
  const checkboxes = document.querySelectorAll('.collection-checkbox-resource');
  for (const checkbox of checkboxes) {
    if (checkbox.checked) {
      // Get the collection ID from the parent collection-item div.
      const collectionEl = checkbox.closest('.collection-item');
      const collectionId = parseInt(collectionEl.dataset.collectionId);
      // Get the resource type from the resource checkbox's parent div.
      // const checkboxParentDivEl = checkbox.closest('.collection-checkbox');
      // const resourceType = checkboxParentDivEl.querySelector('.collection-resource-type').innerText.toLowerCase().trim();
      // const resourceType = checkbox.innerText.toLowerCase().trim();
      // Strangely, the innerText is capitalized even though we only style it to be capitalized with CSS.
      const resourceType = checkbox.closest('.collection-resource-type').textContent.trim();
      selectedResourceIds.push([collectionId, resourceType]);
    }
  }
  // console.log('selectedResourceIds:', selectedResourceIds);
  return selectedResourceIds;
}

// Checkboxes

function saveCheckboxStates()
{
  const states = [];
  // states.push(selectAllCheckboxEl.checked);
  const checkboxes = document.querySelectorAll(
      // '.collection-checkbox-collection,.collection-checkbox-resource');
      '.collection-checkbox');
  for (const checkbox of checkboxes) {
    states.push(checkbox.checked);
  }
  return states;
}

function restoreCheckboxStates(checkboxStates)
{
  // selectAllCheckboxEl.checked = checkboxStates.shift();
  const checkboxes = document.querySelectorAll(
      // '.collection-checkbox-collection,.collection-checkbox-resource');
      '.collection-checkbox');
  for (const checkbox of checkboxes) {
    checkbox.checked = checkboxStates.shift();
  }
}

function isAllChecked()
{
  const checkboxes = document.querySelectorAll(
      // '.collection-checkbox-collection,.collection-checkbox-resource');
      '.collection-checkbox');
  for (const checkbox of checkboxes) {
    if (!checkbox.checked) {
      return false;
    }
  }
  return true;
}

function isSomeChecked()
{
  const checkboxes = document.querySelectorAll(
      // '.collection-checkbox-collection,.collection-checkbox-resource');
      '.collection-checkbox');
  for (const checkbox of checkboxes) {
    if (checkbox.checked) {
      return true;
    }
  }
  return false;
}
