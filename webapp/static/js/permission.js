let headerContainerEl = document.getElementsByClassName('header-container')[0];
const ROOT_PATH = headerContainerEl.dataset.rootPath;
const PUBLIC_PASTA_ID = headerContainerEl.dataset.publicPastaId;
const RESOURCE_TYPE = headerContainerEl.dataset.resourceType;
const PERMISSION_LEVEL_LIST = ['None', 'Reader', 'Editor', 'Owner'];

// The filter input for resources
const resourceFilterEl = document.getElementById('resourceFilter');
const resourceTreeEl = document.getElementById('resourceTree');
let resourceFetchDelay = null;

selectAllCheckboxEl = document.getElementById('selectAllCheckbox');
showPermissionsCheckboxEl = document.getElementById('showPermissionsCheckbox');

const permissionListEl = document.getElementById('permissionList');

// The search input for principals
const principalSearchEl = document.getElementById('principalSearch');
// The list of principal search results
const principalListEl = document.getElementById('principalList');
let principalFetchDelay = null;

// The list of collection/resource/permission items in the resource tree
let treeArray = [];
// Map for looking up resource Ids for selected resources in the tree
const resourceMap = new Map();

let permissionArray = [];
let principalArray = [];

//
//  Initial setup
//

fetchResourceFilter();

//
//  Events
//

// Resource tree (left side)

resourceFilterEl.addEventListener('input', function (_ev) {
  clearTimeout(resourceFetchDelay);
  clearCheckboxStates();
  permissionArray = [];
  refreshPermissions();
  resourceFetchDelay = setTimeout(fetchResourceFilter, 300);
});

selectAllCheckboxEl.addEventListener('change', function (ev) {
  const checkboxEls = document.querySelectorAll('.tree-checkbox');
  for (const checkboxEl of checkboxEls) {
    checkboxEl.checked = ev.target.checked;
  }
  fetchSelectedResourcePermissions();
});

resourceTreeEl.addEventListener('change', function (ev) {
  // Propagate click on collection checkbox to resource checkboxes.
  if (ev.target.classList.contains('tree-collection-checkbox')) {
    const collectionItem = ev.target.closest('.tree-collection-item');
    const checkboxEls = collectionItem.querySelectorAll('.tree-resource-type-checkbox');
    for (const checkboxEl of checkboxEls) {
      checkboxEl.checked = ev.target.checked;
    }
    refreshSelectAllCheckbox();
    fetchSelectedResourcePermissions();
  }
  // Propagate click on resource type checkbox to collection checkbox.
  if (ev.target.classList.contains('tree-resource-type-checkbox')) {
    const collectionItemEl = ev.target.closest('.tree-collection-item');
    const collectionCheckboxEl = collectionItemEl.querySelector('.tree-collection-checkbox');
    // If collectionCheckboxEl is null, this is a top level resource, so there is no collection
    // item.
    if (collectionCheckboxEl !== null) {
      const resourceTypesEl = collectionItemEl.querySelector('.tree-resource-type-list');
      collectionCheckboxEl.checked = isAllChecked(resourceTypesEl);
      // return;
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
  const principalType = divEl.dataset.principalType;
  const resources = getSelectedResourceIds();
  fetchSetPermission(resources, principalId, principalType, 1);
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
    const principalType = divEl.dataset.principalType;
    const permissionLevel = parseInt(ev.target.value);
    const resources = getSelectedResourceIds();
    fetchSetPermission(resources, principalId, principalType, permissionLevel);
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

function fetchResourceFilter()
{
  const checkboxStates = saveCheckboxStates();

  // Display a "loading..." message if fetch is slow. This avoids the message flickering on in brief
  // moments when the fetch is fast.
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
          resourceMap.clear();
          let mapIdx = 0;
          for (const resourceObj of resultObj.resources) {
            for (const [_resourceType, resourceTypeDict] of
                Object.entries(resourceObj.resource_dict)) {
              resourceTypeDict.resource_map_idx = mapIdx;
              const resourceIds = Object.keys(resourceTypeDict.resource_id_dict).map(Number);
              resourceMap.set(mapIdx++, resourceIds);
            }
          }
          clearTimeout(msgDelay);
          refreshResourceTree();
          restoreCheckboxStates(checkboxStates);
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

function fetchSetPermission(resources, principalId, principalType, permissionLevel)
{
  fetch(`${ROOT_PATH}/permission/update`, {
    method: 'POST', headers: {
      'Content-Type': 'application/json',
    }, body: JSON.stringify({
      resources: resources, principalId: principalId, principalType: principalType,
      permissionLevel: permissionLevel,
    }),
  })
      .then((response) => response.json())
      .then((resultObj) => {
        if (resultObj.error) {
          errorDialog(resultObj.error);
        }
        else {
          fetchResourceFilter();
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
          principalArray = resultObj.principal_list;
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

function refreshResourceTree()
{
  if (!treeArray.length) {
    resourceTreeEl.innerHTML = `<div class='grid-msg'>No resources found</div>`;
    return;
  }
  // We use a document fragment to avoid multiple reflows.
  const fragment = document.createDocumentFragment();
  for (const resourceObj of treeArray) {
    if (resourceObj.collection_label === null && resourceObj.collection_type === null) {
      addTreeNullCollectionDiv(fragment, resourceObj);
    }
    else {
      addTreeCollectionDiv(fragment, resourceObj);
    }
  }
  resourceTreeEl.replaceChildren(fragment);
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

// Add section of the tree for a resource that is in a collection.

function addTreeCollectionDiv(parentEl, collectionObj)
{
  const collectionEl = document.createElement('div');
  collectionEl.classList.add('tree-collection-item');
  collectionEl.innerHTML = `
    <div class=''>
      <label>
        <span>
          <input type='checkbox' class='tree-checkbox tree-collection-checkbox'/>
          <span class='tree-title'>${collectionObj.collection_label}</span>
          <span class='tree-collection-type tree-type-label'>${collectionObj.collection_type}</span>
        </span>
      </label>
    </div>
    <div class='tree-resource-type-list'>
      ${formatTreeResourceTypeDiv(collectionObj.resource_dict)}
   </div>
  `;
  parentEl.appendChild(collectionEl);
}


function formatTreeResourceTypeDiv(resourceDict)
{
  let htmlList = [];
  for (const [resourceType, resourceObj] of Object.entries(resourceDict)) {
    let hideTypeClass;
    let indentClass;
    // if (resourceType.startsWith('single-')) {
    //   hideTypeClass = 'tree-resource-hidden';
    //   indentClass = '';
    // }
    // else {
    hideTypeClass = '';
    indentClass = 'tree-indent';
    // }
    // data-resource-type='${resourceType}'
    htmlList.push(`
      <div class='${indentClass}'>
          <label class='tree-resource-type ${hideTypeClass}'>
            <input type='checkbox' class='tree-checkbox tree-resource-type-checkbox'
              data-resource-map-idx='${resourceObj.resource_map_idx}'
            />
            ${resourceType}
          </label>
        <div class=''>
          ${formatTreePrincipalDiv(resourceObj.principal_list)}
        </div>
      </div>
    `);
  }
  return htmlList.join('');
}

// Add section of the tree for a resource that is not in a collection.

function addTreeNullCollectionDiv(parentEl, collectionObj)
{
  const collectionEl = document.createElement('div');
  collectionEl.classList.add('tree-collection-item');
  collectionEl.innerHTML = `
    <div class='tree-resource-type-list'>
      ${formatTreeNullResourceTypeDiv(collectionObj.resource_dict)}
   </div>
  `;
  parentEl.appendChild(collectionEl);
}

function formatTreeNullResourceTypeDiv(resourceDict)
{
  let htmlList = [];
  for (const [resourceType, resourceObj] of Object.entries(resourceDict)) {
    htmlList.push(`
      <div class=''>
          <label class=''
            data-resource-type='${resourceType}'
          >
            <input type='checkbox' class='tree-checkbox tree-resource-type-checkbox'
              data-resource-map-idx='${resourceObj.resource_map_idx}'
            />
            <span class='tree-title'>${Object.values(resourceObj.resource_id_dict)[0]}</span>
            <span class='tree-type-label'>${resourceType}</span>
          </label>
        <div class=''>
          ${formatTreePrincipalDiv(resourceObj.principal_list)}
        </div>
      </div>
    `);
  }
  return htmlList.join('');
}

// Add section of the tree for a principal in a resource type.
// This is used resources both in and not in collections.
function formatTreePrincipalDiv(principalList)
{
  let htmlList = [];
  for (const principalObj of principalList) {
    htmlList.push(`
      <div class='tree-indent tree-principal'>
        <div class='tree-principal-name'>${principalObj.title}</div> 
        <div class='tree-principal-pasta-id'>${principalObj.pasta_id}</div>
        <div class='tree-principal-permission-level'>
          ${formatTreePermissionLevelDiv(principalObj.permission_level)}
        </div>
      </div>
    `);
  }
  return htmlList.join('');
}


function formatTreePermissionLevelDiv(level)
{
  return PERMISSION_LEVEL_LIST[level] || 'Unknown';
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

function addPermissionLevelDropdownDiv(parentEl, permissionObj)
{
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

//
//  Util
//

// Return a list of resourceIds for selected resource types and resources in resource tree.
function getSelectedResourceIds()
{
  const selectedResourceIds = [];
  // Since resource checkboxes are updated when collection checkboxes are clicked, we only need to
  // iterate over the resource checkboxes.
  const checkboxEls = document.querySelectorAll('.tree-resource-type-checkbox:checked');
  for (const checkboxEl of checkboxEls) {
    const mapIdx = parseInt(checkboxEl.dataset.resourceMapIdx);
    selectedResourceIds.push(...resourceMap.get(mapIdx));
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
  for (const checkboxEl of document.querySelectorAll('.tree-checkbox')) {
    states.push(checkboxEl.checked);
  }
  return states;
}

function restoreCheckboxStates(checkboxStates)
{
  selectAllCheckboxEl.checked = checkboxStates.shift();
  for (const checkboxEl of document.querySelectorAll('.tree-checkbox')) {
    checkboxEl.checked = checkboxStates.shift();
  }
}

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
