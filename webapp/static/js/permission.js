let headerContainerEl = document.getElementsByClassName('header-container')[0];
const ROOT_PATH = headerContainerEl.dataset.rootPath;
const PUBLIC_PASTA_ID = headerContainerEl.dataset.publicPastaId;
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

//
//  Initial setup
//

fetchCollectionSearch();

//
//  Events
//

collectionSearchEl.addEventListener('input', function (e) {
  clearTimeout(resourceFetchDelay);
  clearCheckboxStates();
  permissionArray.length = 0;
  refreshPermissions();
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
permissionListEl.addEventListener('change', function (ev) {
  // Handle new permission level selected in permission level dropdown
  if (ev.target.classList.contains('level-dropdown')) {
    const divEl = ev.target.closest('div');
    // dataset values are HTML attributes, which are always strings
    const principalId = parseInt(divEl.dataset.principalId);
    const principalType = divEl.dataset.principalType;
    const permissionLevel = parseInt(ev.target.value);
    const resources = getSelectedResources();
    fetchSetPermission(resources, principalId, principalType, permissionLevel);
    // TODO: Test for race condition
    ev.target.disabled = true;
  }
});

// permissionListEl.addEventListener('click', function (ev) {
//   // Trigger change event on level-dropdown, even if the same level is selected again. This allows a
//   // permission that only exists for some of the selected resources, to be applied to all the
//   // selected resources without changing the permission level.
//   if (ev.target.classList.contains('level-dropdown')) {
//     ev.target.dispatchEvent(new Event('change', {bubbles: true}));
//   }
// });

// We use mousedown instead of click to prevent the blur event on principalSearchEl from firing
// before the click event.
principalListEl.addEventListener('mousedown', function (ev) {
  const divEl = ev.target.closest('.principal-flex');
  const principalId = parseInt(divEl.dataset.principalId);
  const principalType = divEl.dataset.principalType;
  const resources = getSelectedResources();
  fetchSetPermission(resources, principalId, principalType, 1);
});


selectAllCheckboxEl.addEventListener('change', function (ev) {
  const checkboxes = document.querySelectorAll('.collection-checkbox');
  for (const checkbox of checkboxes) {
    checkbox.checked = ev.target.checked;
  }
});

document.addEventListener('change', function (ev) {
  // Propagate click on collection checkbox to resource checkboxes.
  if (ev.target.classList.contains('collection-checkbox-collection')) {
    const collectionItem = ev.target.closest('.collection-item');
    const resourceCheckboxes = collectionItem.querySelectorAll('.collection-checkbox-resource');
    for (const checkbox of resourceCheckboxes) {
      checkbox.checked = ev.target.checked;
      // If any checkbox is unchecked, uncheck the selectAllCheckbox.
      selectAllCheckboxEl.checked = false;
    }
  }
  // If a resource checkbox is unchecked, uncheck the collection checkbox.
  if (ev.target.classList.contains('collection-checkbox-resource')) {
    const collectionItem = ev.target.closest('.collection-item');
    if (!ev.target.checked) {
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
  const resources = getSelectedResources();
  if (resources.length > 0) {
    fetchGetPermissions(resources);
  }
  else {
    permissionArray.length = 0;
    refreshPermissions();
  }
});

// Show and hide individual permissions in the Resources list
showPermissionsCheckboxEl.addEventListener('change', function (_ev) {
  refreshShowPermissions();
});


//
//  Fetch
//

function fetchCollectionSearch()
{
  const checkboxStates = saveCheckboxStates();

  // Display a "loading..." message if fetch is slow. This avoids the message flickering on in brief
  // moments when the fetch is fast.
  const msgDelay = setTimeout(function() {
    collectionListEl.innerHTML = `<div class='grid-msg'>Loading resources...</div>`;
  }, 2000);

  fetch(`${ROOT_PATH}/permission/resource/search`, {
    method: 'POST', headers: {
      'Content-Type': 'application/json',
    }, body: JSON.stringify({query: collectionSearchEl.value}),
  })
      .then((response) => response.json())
      .then((resultObj) => {
        if (resultObj.error) {
          errorDialog('fetchCollectionSearch()', resultObj.error);
        }
        else {
          collectionMap.clear();
          for (const [collectionId, collectionObj] of Object.entries(resultObj.collection_dict)) {
            collectionMap.set(parseInt(collectionId), collectionObj);
          }
          clearTimeout(msgDelay);
          refreshCollections();
          restoreCheckboxStates(checkboxStates);
          //   selectAllCheckboxEl.checked = false;
          //   permissionArray.length = 0;
          //   refreshPermissions();
          //   refreshShowPermissions();
        }
      })
      .catch((error) => {
        errorDialog('fetchCollectionSearch()', error);
      });
}


function fetchGetPermissions(resources)
{
  const msgDelay = setTimeout(function() {
    permissionListEl.innerHTML = `<div class='grid-msg'>Loading permissions...</div>`;
  }, 2000);

  fetch(`${ROOT_PATH}/permission/aggregate/get`, {
    method: 'POST', headers: {
      'Content-Type': 'application/json',
    }, body: JSON.stringify(resources),
  })
      .then((response) => response.json())
      .then((resultObj) => {
        if (resultObj.error) {
          errorDialog('fetchGetPermissions()', resultObj.error);
        }
        else {
          permissionArray = resultObj.permission_list;
          clearTimeout(msgDelay);
          refreshPermissions();
        }
      })
      .catch((error) => {
        errorDialog('fetchGetPermissions()', error);
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
        if (resultObj.error) {
          errorDialog('fetchSetPermission()', resultObj.error);
        }
        else {
          fetchCollectionSearch();
          principalSearchEl.value = '';
        }
      })
      .catch((error) => {
        errorDialog('fetchSetPermission()', error);
      });
}


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
          errorDialog('fetchPrincipalSearch()', resultObj.error);
        }
        else {
          principalArray = resultObj.principal_list;
          refreshPrincipals();
        }
      })
      .catch((error) => {
        errorDialog('fetchPrincipalSearch()', error);
      });
}

//
//  Refresh
//

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

  const fragment = document.createDocumentFragment();
  for (const permissionObj of permissionArray) {
      addPrincipalDiv(fragment, permissionObj);
      addPermissionLevelDropdownDiv(fragment, permissionObj, false);
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
      <div class='principal-info-child'>${c.description || ''}</div>
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

function addPermissionLevelDropdownDiv(parentEl, permissionObj) {
  const levelEl = document.createElement('div');
  levelEl.dataset.principalId = permissionObj.principal_id;
  levelEl.dataset.principalType = permissionObj.principal_type;
  const permission_level = permissionObj.permission_level;
  let optionsHtml = `
    <option value='0' ${permission_level === 0 ? 'selected' : ''}>None</option>
    <option value='1' ${permission_level === 1 ? 'selected' : ''}>Reader</option>
  `;
  if (permissionObj.pasta_id !== PUBLIC_PASTA_ID) {
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

//
//  Util
//

// Return a list of [collectionId, resourceType] for each checked resource checkbox.
function getSelectedResources()
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
  return selectedResourceIds;
}



//
// Checkboxes
//

function saveCheckboxStates()
{
  const states = [];
  states.push(selectAllCheckboxEl.checked);
  const checkboxes = document.querySelectorAll('.collection-checkbox');
  for (const checkbox of checkboxes) {
    states.push(checkbox.checked);
  }
  return states;
}

function restoreCheckboxStates(checkboxStates)
{
  selectAllCheckboxEl.checked = checkboxStates.shift();
  const checkboxes = document.querySelectorAll('.collection-checkbox');
  for (const checkbox of checkboxes) {
    checkbox.checked = checkboxStates.shift();
  }
}

function clearCheckboxStates()
{
  selectAllCheckboxEl.checked = false;
  const checkboxes = document.querySelectorAll('.collection-checkbox');
  for (const checkbox of checkboxes) {
    checkbox.checked = false;
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
