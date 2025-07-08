let headerContainerEl = document.getElementsByClassName('header-container')[0];

// Constants passed from the server
const ROOT_PATH = headerContainerEl.dataset.rootPath;
const PUBLIC_EDI_ID = headerContainerEl.dataset.publicEdiId;
const AUTHENTICATED_EDI_ID = headerContainerEl.dataset.authenticatedEdiId;
const RESOURCE_TYPE = headerContainerEl.dataset.resourceType;

const PERMISSION_LEVEL_LIST = ['None', 'Reader', 'Editor', 'Owner'];

// The filter input for resources
const resourceFilterEl = document.getElementById('resourceFilter');
const resourceTreeEl = document.getElementById('resourceTree');
let resourceFetchDelay = null;

// Resource tree head checkboxes
selectAllCheckboxEl = document.getElementById('selectAllCheckbox');
showPermissionsCheckboxEl = document.getElementById('showPermissionsCheckbox');

// List of permissions for the selected resources
const permissionListEl = document.getElementById('permissionList');

// Search input for principals
const principalSearchEl = document.getElementById('principalSearch');
// List of principal search results
const principalListEl = document.getElementById('principalList');
let principalFetchDelay = null;

// List of resource/permission items in the resource tree
let treeArray = [];

let permissionArray = [];
let principalArray = [];

//
//  Initial setup
//

fetchResources();

//
//  Events
//

// Resource tree (left side)

resourceFilterEl.addEventListener('input', function (_ev) {
  clearTimeout(resourceFetchDelay);
  clearCheckboxStates();
  permissionArray = [];
  refreshPermissions();
  resourceFetchDelay = setTimeout(fetchResources, 300);
});

selectAllCheckboxEl.addEventListener('change', function (ev) {
  const checkboxEls = document.querySelectorAll('.tree-checkbox');
  for (const checkboxEl of checkboxEls) {
    checkboxEl.checked = ev.target.checked;
  }
  fetchSelectedResourcePermissions();
});

resourceTreeEl.addEventListener('change', function (ev) {
  // Propagate click on resource checkbox to child checkboxes.
  if (ev.target.classList.contains('tree-checkbox')) {
    const detailsEl = ev.target.closest('.tree-details');
    const checkboxEls = detailsEl.querySelectorAll('.tree-checkbox');
    for (const checkboxEl of checkboxEls) {
      checkboxEl.checked = ev.target.checked;
    }
    refreshSelectAllCheckbox();
    fetchSelectedResourcePermissions();
  }
});

// Principal search (right side, top)

principalSearchEl.addEventListener('input', function (ev) {
  clearTimeout(principalFetchDelay);
  if (principalSearchEl.value.length < 2) {
    principalListEl.classList.remove('visible');
    return;
  }
  principalFetchDelay = setTimeout(fetchPrincipalSearch, 300);
});

principalSearchEl.addEventListener('blur', function (ev) {
  principalListEl.classList.remove('visible');
});

// Add a permission to the selected resources for the new principal selected in the search results.
// The new principal is added with READ permission, which the user can then update if needed.
// We use mousedown instead of click to prevent the blur event on principalSearchEl from firing
// before the click event.
principalListEl.addEventListener('mousedown', function (ev) {
  const divEl = ev.target.closest('.principal-flex');
  const principalId = parseInt(divEl.dataset.principalId);
  // const principalType = divEl.dataset.principalType;
  const resources = getSelectedResourceIds();
  fetchSetPermission(resources, principalId, 1);
});


//
// Permissions (right side, bottom)
//

permissionListEl.addEventListener('change', function (ev) {
  // Handle new permission level selected in permission level dropdown
  if (ev.target.classList.contains('level-dropdown')) {
    const divEl = ev.target.closest('div');
    // dataset values are HTML attributes, which are always strings
    const principalId = parseInt(divEl.dataset.principalId);
    // const principalType = divEl.dataset.principalType;
    const permissionLevel = parseInt(ev.target.value);
    const resources = getSelectedResourceIds();
    fetchSetPermission(resources, principalId, permissionLevel);
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


// Show and hide individual permissions in the resource tree
showPermissionsCheckboxEl.addEventListener('change', function (_ev) {
  const permissionList = document.querySelectorAll('.tree-principal');
  for (const permission of permissionList) {
    permission.classList.toggle('tree-principal-hidden', !showPermissionsCheckboxEl.checked);
  }
});


//
//  Fetch
//

function fetchResources()
{
  // const checkboxStates = saveCheckboxStates();
  const treeState = saveTreeState();

  // Display a "loading..." message if fetch is slow. This avoids the message flickering on in brief
  // moments when the fetch is fast, but the message can still flicker on briefly if the fetch takes
  // just slightly longer than the timeout set here.
  const msgDelay = setTimeout(function () {
    resourceTreeEl.innerHTML = `<div class='grid-msg'>Loading resources...</div>`;
  }, 2000);

  fetch(`${ROOT_PATH}/permission/resource/filter`, {
    method: 'POST', headers: {
      'Content-Type': 'application/json',
    }, body: JSON.stringify({query: resourceFilterEl.value, type: RESOURCE_TYPE}),
  })
      .then((response) => response.json())
      .then((resultObj) => {
        if (resultObj.error) {
          errorDialog(resultObj.error);
        }
        else {
          treeArray = resultObj.resources;
          clearTimeout(msgDelay);
          refreshResourceTree(treeArray);
          restoreTreeState(treeState);
          fetchSelectedResourcePermissions();
        }
      })
      .catch((error) => {
        errorDialog(error);
      });
}


function fetchSelectedResourcePermissions()
{
  const resources = getSelectedResourceIds();

  // Skip server round-trip if no resources are selected.
  if (!resources.length) {
    permissionArray = [];
    refreshPermissions();
    return;
  }

  const msgDelay = setTimeout(function () {
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
          errorDialog(resultObj.error);
        }
        else {
          permissionArray = resultObj.permissionArray;
          clearTimeout(msgDelay);
          refreshPermissions();
        }
      })
      .catch((error) => {
        errorDialog(error);
      });
}


function fetchSetPermission(resources, principalId, permissionLevel)
{
  fetch(`${ROOT_PATH}/permission/update`, {
    method: 'POST', headers: {
      'Content-Type': 'application/json',
    }, body: JSON.stringify({
      resources: resources, principalId: principalId, permissionLevel: permissionLevel,
    }),
  })
      .then((response) => response.json())
      .then((resultObj) => {
        if (resultObj.error) {
          errorDialog(resultObj.error);
        }
        else {
          fetchResources();
          principalSearchEl.value = '';
        }
      })
      .catch((error) => {
        errorDialog(error);
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
          errorDialog(resultObj.error);
        }
        else {
          principalArray = resultObj.principals;
          refreshPrincipals();
        }
      })
      .catch((error) => {
        errorDialog(error);
      });
}

//
//  Refresh
//

function refreshResourceTree(resourceArray)
{
  if (!resourceArray.length) {
    resourceTreeEl.innerHTML = `<div class='grid-msg'>No resources found</div>`;
    return;
  }
  resourceTreeEl.innerHTML = refreshResourceTreeRecursive(resourceArray);
}

function refreshResourceTreeRecursive(resourceArray)
{
  const htmlArr = [];
  for (const resourceObj of resourceArray) {
    htmlArr.push(
        `<ul class='tree'>
          <li>
            <details class='tree-details'>
              <summary>
                <span>
                  <input type='checkbox' class='tree-checkbox'
                    data-resource-id='${resourceObj.resource_id}'
                  />
                  <span class='tree-resource-title'>${resourceObj.label}</span>
                  <!--<span class='tree-resource-title'>${resourceObj.key}</span>-->
                  <span class='tree-resource-type'>${resourceObj.type}</span>
                </span>
              </summary>
              <ul>
                <li class='tree-indent'>
                  ${formatTreePrincipalDiv(resourceObj.principals)}
                  ${refreshResourceTreeRecursive(resourceObj.children)}
                </li>
              </ul>
            </details>
          </li>
        </ul>
    `);
  }
  return htmlArr.join('');
}

// Add section of the tree for a principal in a resource type.
function formatTreePrincipalDiv(principalList)
{
  let htmlArray = [];
  for (const principalObj of principalList) {
    htmlArray.push(`
      <div class='tree-principal'>
        <div class='tree-principal-name'>${principalObj.title || ''}</div>
        <div class='tree-principal-edi-id'>${principalObj.edi_id}</div>
        <div class='tree-principal-permission-level'>
          ${formatTreePermissionLevelDiv(principalObj.permission_level)}
        </div>
      </div>
    `);
  }
  return htmlArray.join('');
}


function formatTreePermissionLevelDiv(level)
{
  return PERMISSION_LEVEL_LIST[level] || 'Unknown';
}

function refreshSelectAllCheckbox()
{
  selectAllCheckboxEl.checked = isAllChecked(resourceTreeEl);
}

function refreshPermissions()
{
  if (!permissionArray.length) {
    let emptyMsg;
    if (isSomeChecked(resourceTreeEl)) {
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


//
// Permissions (right side, bottom)
//

function addPrincipalDiv(parentEl, principalObj)
{
  const c = principalObj;
  const principalEl = document.createElement('div');
  principalEl.classList.add('principal-flex');
  principalEl.dataset.principalId = c.principal_id;
  principalEl.innerHTML = `
    <div class='principal-child principal-avatar'>
      <img src='${c.avatar_url}' alt='Avatar' class='avatar avatar-smaller'>
    </div>
    <div class='principal-child principal-info'>
      <div class='principal-title'>${c.title || ''}</div>
      <div class='principal-description'>${c.description || ''}</div>
      <div class='edi-id-parent'>
        <div class='edi-id-child-text'>
          ${c.edi_id}
        </div>
        <div class='edi-id-child-icon'>
          <img class='edi-id-copy-button'
            src='${ROOT_PATH}/static/svg/copy.svg'
            alt='Copy User Identifier'
          >
        </div>
      </div>
    </div>
  `;
  parentEl.appendChild(principalEl);
}

function addPermissionLevelDropdownDiv(parentEl, permissionObj)
{
  const levelEl = document.createElement('div');
  levelEl.dataset.principalId = permissionObj.principal_id;
  // levelEl.dataset.principalType = permissionObj.principal_type;
  const permission_level = permissionObj.permission_level;
  let optionsHtml = `
    <option value='0' ${permission_level === 0 ? 'selected' : ''}>None</option>
    <option value='1' ${permission_level === 1 ? 'selected' : ''}>Reader</option>
  `;
  if (permissionObj.edi_id !== PUBLIC_EDI_ID) {
    optionsHtml += `
      <option value='2' ${permission_level === 2 ? 'selected' : ''}>Editor</option>
      <option value='3' ${permission_level === 3 ? 'selected' : ''}>Owner</option>
    `;
  }
  levelEl.innerHTML = `<select class='level-dropdown'>${optionsHtml}</select>`;
  parentEl.appendChild(levelEl);
}

//
//  Util
//

// Return a list of resourceIds for selected resource types and resources in resource tree.
// function getSelectedResourceIds()
// {
//   const selectedResourceIds = [];
//   const checkboxEls = document.querySelectorAll('.tree-checkbox:checked');
//   for (const checkboxEl of checkboxEls) {
//     const resourceId = parseInt(checkboxEl.dataset.resourceId);
//     selectedResourceIds.push(resourceId);
//   }
//   return selectedResourceIds;
// }

function getSelectedResourceIds()
{
  return Array.from(document.querySelectorAll('.tree-checkbox:checked'))
      .map(checkboxEl => parseInt(checkboxEl.dataset.resourceId));
}

//
// Checkboxes
//

function clearCheckboxStates()
{
  selectAllCheckboxEl.checked = false;
  for (const checkboxEl of document.querySelectorAll('.tree-checkbox')) {
    checkboxEl.checked = false;
  }
}

function isAllChecked(rootEl)
{
  return Array.from(rootEl.querySelectorAll('.tree-checkbox')).every(el => el.checked);
}

function isSomeChecked(rootEl)
{
  return Array.from(rootEl.querySelectorAll('.tree-checkbox')).some(el => el.checked);
}

//
// Tree
//

// Capture the open/closed and checked state of each node
function saveTreeState() {
  const state = {};
  const detailsEls = document.querySelectorAll('.tree-details');
  detailsEls.forEach(detailsEl => {
    const checkboxEl = detailsEl.querySelector('.tree-checkbox');
    const resourceId = checkboxEl.dataset.resourceId;
    state[resourceId] = {open: detailsEl.open, checked: checkboxEl.checked};
  });
  return state;
}

// Apply the saved state to the tree
function restoreTreeState(state) {
  const detailsEls = document.querySelectorAll('.tree-details');
  detailsEls.forEach(detailsEl => {
    const checkboxEl = detailsEl.querySelector('.tree-checkbox');
    const resourceId = checkboxEl.dataset.resourceId;
    if (state[resourceId] !== undefined) {
      detailsEl.open = state[resourceId].open;
      checkboxEl.checked = state[resourceId].checked;
    }
  });
}
