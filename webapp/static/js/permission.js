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

// The search input for principals
const principalSearchEl = document.getElementById('principalSearch');
// The list of principal search results
const principalListEl = document.getElementById('principalList');
let principalFetchDelay = null;

const collectionMap = new Map();
let permissionArray = [];
let principalArray = [];

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
    permissionArray.length = 0;
    refreshPermissions();
    return;
  }
  resourceFetchDelay = setTimeout(fetchCollectionSearch, 300);
});


principalSearchEl.addEventListener('input', function (e) {
  clearTimeout(principalFetchDelay);
  if (principalSearchEl.value.length < 2) {
    principalListEl.classList.remove('visible');
    return;
  }
  principalFetchDelay = setTimeout(fetchPrincipalSearch, 300);
});

principalSearchEl.addEventListener('blur', function (e) {
  principalListEl.classList.remove('visible');
});

// We can't add an event handler directly to dynamically generated elements, so we use event
// delegation to listen for clicks on the parent element.
permissionListEl.addEventListener('change', function (event) {
  // Handle new permission level selected in permission level dropdown
  if (event.target.classList.contains('level-dropdown')) {
    // dataset is an HTML attribute, and all attributes are stored as strings
    const divEl = event.target.closest('div');
    const principalId = parseInt(divEl.dataset.principalId);
    const principalType = divEl.dataset.principalType;
    const permissionLevel = parseInt(event.target.value);
    const resources = getAllSelectedResources();
    fetchSetPermission(resources, principalId, principalType, permissionLevel);
    // TODO: Test for race condition
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

// We use mousedown instead of click to prevent the blur event on principalSearchEl from firing
// before the click event.
principalListEl.addEventListener('mousedown', function (event) {
  const divEl = event.target.closest('.principal-flex');
  const principalId = parseInt(divEl.dataset.principalId);
  const principalType = divEl.dataset.principalType;
  const resources = getAllSelectedResources();
  fetchSetPermission(resources, principalId, principalType, 1);
});


selectAllCheckboxEl.addEventListener('change', function (event) {
  const checkboxes = document.querySelectorAll('.collection-checkbox');
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
  if (resources.length > 0) {
    fetchGetPermissions(resources);
  }
  else {
    permissionArray.length = 0;
    refreshPermissions();
  }
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
            permissionArray.length = 0;
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
  fetch(`${ROOT_PATH}/permission/aggregate/get`, {
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
          permissionArray = resultObj.permission_list;
          refreshPermissions();
        }
      })
      .catch((error) => {
        console.error('Error:', error);
      });
}

function fetchSetPermission(resources, principalId, principalType, permissionLevel)
{
  fetch(`${ROOT_PATH}/permission/update`, {
    method: 'POST', headers: {
      'Content-Type': 'application/json',
    }, body: JSON.stringify({
      resources: resources,
      principalId: principalId,
      principalType: principalType,
      permissionLevel: permissionLevel,
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
          principalSearchEl.value = '';
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
//         // a new permission, so we need to update the permissionArray.
//         if (resultObj.permissionId) {
//           const v = permissionArray.get(o.permissionId);
//           permissionArray.delete(o.permissionId);
//           permissionArray.set(resultObj.permissionId, v);
//         }
//         if (resultObj.error) {
//           alert(resultObj.error);
//         }
//       })
//       .catch((error) => {
//         console.error('fetchPermissionCrud() Error:', error);
//       });
// }

function fetchPrincipalSearch()
{
  const searchStr = principalSearchEl.value;
  fetch(`${ROOT_PATH}/permission/principal/search`, {
    method: 'POST', headers: {
      'Content-Type': 'application/json',
    }, body: JSON.stringify({query: searchStr}),
  })
      .then((response) => response.json())
      .then((resultObj) => {
        if (resultObj.error) {
          alert(resultObj.error);
        }
        else {
          principalArray = resultObj.principal_list;
          refreshPrincipals();
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
  if (!collectionMap.size) {
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
  if (!permissionArray.length) {
    let emptyMsg;
    if (isSomeChecked()) {
      principalSearchEl.placeholder = 'Add Users and Groups';
      emptyMsg = 'No permissions have been added yet';
      principalSearchEl.disabled = false;
    }
    else {
      principalSearchEl.placeholder = 'Select resources to set permissions';
      emptyMsg = '';
      principalSearchEl.disabled = true;
    }
    permissionListEl.innerHTML = `<div class='grid-msg'>${emptyMsg}</div>`;
    return;
  }
  else {
    principalSearchEl.placeholder = 'Add Users and Groups';
    principalSearchEl.disabled = false;
  }

  // We use a document fragment to avoid multiple reflows.
  const fragment = document.createDocumentFragment();
  for (const permissionObj of permissionArray) {
    if (permissionObj.principal_type === 'public') {
      addPublicPrincipalDiv(fragment, permissionObj);
      addPermissionLevelDropdownDiv(fragment, permissionObj, true);
    }
    else {
      addPrincipalDiv(fragment, permissionObj);
      addPermissionLevelDropdownDiv(fragment, permissionObj, false);
    }
  }
  permissionListEl.replaceChildren(fragment);
}


function refreshPrincipals()
{
  if (!principalArray.length) {
    principalListEl.innerHTML = `<div class='grid-msg'>No user profiles or groups found</div>`;
    principalListEl.classList.add('visible');
    return;
  }
  // We use a document fragment to avoid multiple reflows.
  const fragment = document.createDocumentFragment();
  for (const principalObj of principalArray) {
    addPrincipalDiv(fragment, principalObj);
    // classList holds only unique values, so no need to check if it already exists
    principalListEl.classList.add('visible');
  }
  principalListEl.replaceChildren(fragment);
}


function addCollectionDiv(parentEl, collectionId, collectionObj)
{
  const collectionEl = document.createElement('div');
  collectionEl.classList.add('collection-item');
  collectionEl.dataset.collectionId = collectionId;
  collectionEl.innerHTML = `
    <div class=''>
      <label>
      <span>
        <input type='checkbox' class='collection-checkbox collection-checkbox-collection'/>
        ${collectionObj.collection_label}
        <span class='collection-type'>${collectionObj.collection_type}</span>
        </span>     
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
          ${formatCollectionPrincipalDict(resourceObj.principal_list)}
        </div>
      </div>
    `);
  }
  return htmlList.join('');
}


function formatCollectionPrincipalDict(principalList)
{
  let htmlList = [];
  for (const principalObj of principalList) {
    htmlList.push(`
      <div class='collection-indent collection-principal-row'>
        <div class='collection-name'>${principalObj.title}</div> 
        <div class='collection-pasta-id'>${principalObj.pasta_id}</div>
        <div class='collection-perm-level'>${formatPermissionLevel(principalObj.permission_level)}</div>
      </div>
    `);
  }
  return htmlList.join('');
}


function formatPermissionLevel(level)
{
  return PERMISSION_LEVEL_LIST[level] || 'Unknown';
}

function addPrincipalDiv(parentEl, principalObj)
{
  const c = principalObj;
  const principalEl = document.createElement('div');
  principalEl.classList.add('principal-flex');
  principalEl.dataset.principalId = c.principal_id;
  principalEl.dataset.principalType = c.principal_type;
  principalEl.innerHTML = `
    <div class='principal-child principal-avatar'>
      <img src='${c.avatar_url}' alt='Avatar' class='avatar avatar-smaller'>
    </div>
    <div class='principal-child principal-info'>
      <div class='principal-info-child'>${c.title}</div>
      <div class='principal-info-child'>${c.description}</div>

      <div class='principal-info-child'>
        <div class='pasta-id-parent'>
          <div class='pasta-id-child-text'>
            ${c.pasta_id}
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


function addPublicPrincipalDiv(parentEl, principalObj)
{
  const c = principalObj;
  const principalEl = document.createElement('div');
  principalEl.classList.add('principal-flex');
  principalEl.classList.add('principal-public');
  principalEl.dataset.principalId = c.principal_id;
  principalEl.dataset.principalType = c.principal_type;
  principalEl.innerHTML = `
    <div class='principal-child principal-avatar'>
      <img src='${c.avatar_url}' alt='Avatar' class='avatar avatar-smaller'>
    </div>
    <div class='principal-child principal-info'>
      <div class='principal-info-child'>Public Access</div>
    </div>
  `;
  parentEl.appendChild(principalEl);
}


function addPermissionLevelDropdownDiv(parentEl, permissionObj, isPublic) {
  const levelEl = document.createElement('div');
  levelEl.dataset.principalId = permissionObj.principal_id;
  levelEl.dataset.principalType = permissionObj.principal_type;
  const permission_level = permissionObj.permission_level;
  let optionsHtml = `
    <option value='0' ${permission_level === 0 ? 'selected' : ''}>None</option>
    <option value='1' ${permission_level === 1 ? 'selected' : ''}>Reader</option>
  `;
  if (!isPublic) {
    optionsHtml += `
      <option value='2' ${permission_level === 2 ? 'selected' : ''}>Editor</option>
      <option value='3' ${permission_level === 3 ? 'selected' : ''}>Owner</option>
    `;
  }
  levelEl.innerHTML = `<select class='level-dropdown'>${optionsHtml}</select>`;
  parentEl.appendChild(levelEl);
}

function refreshShowPermissions()
{
  const permissionList = document.querySelectorAll('.collection-principal-row');
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
