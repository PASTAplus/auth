/* jshint esversion: 11, browser: true */

let headerContainerEl = document.getElementsByClassName('header-container')[0];

// Constants passed from the server
const BASE_PATH = headerContainerEl.dataset.basePath;
const PUBLIC_EDI_ID = headerContainerEl.dataset.publicEdiId;
const TOTAL_TREE_COUNT = parseInt(headerContainerEl.dataset.rootCount);
const SEARCH_UUID = headerContainerEl.dataset.searchUuid;
const ENABLE_PUBLIC_ACCESS_WARNING = headerContainerEl.dataset.enablePublicAccessWarning === 'true';

// const AUTHENTICATED_EDI_ID = headerContainerEl.dataset.authenticatedEdiId;
// const RESOURCE_TYPE = headerContainerEl.dataset.resourceType;

const PERMISSION_LEVEL_ARRAY = ['None', 'Reader', 'Editor', 'Owner'];

// Resource tree head checkboxes
// selectAllCheckboxEl = document.getElementById('selectAllCheckbox');
// showPermissionsCheckboxEl = document.getElementById('showPermissionsCheckbox');
// Resource tree

// List of permissions for the selected resources
const permissionListEl = document.getElementById('permissionList');

// Search input for principals
const principalSearchEl = document.getElementById('principalSearch');
// List of principal search results
const principalListEl = document.getElementById('principalList');
let principalFetchDelay = null;

let permissionArray = [];
let principalArray = [];

// Infinite scroll resource tree variables
const collapsedTreeHeight = 35; // pixels
const blockSize = 100; // trees per fetch
const bufferTrees = 100; // above & below viewport

const resourceTreeEl = document.getElementById('resourceTree');
const spacerEl = document.getElementById('spacer');
const visibleTrees = document.getElementById('visible-trees');

const loadedBlocks = new Map(); // blockIdx -> tree data array
const blockPromises = new Map(); // blockIdx -> Promise

// Incremented on each new render
let fetchVersion = 0;

// logging
let logIdx = 0;
let logSpacerTimeout = null;
const ENABLE_LOGGING = true;

// To prevent flooding the server with requests while the user is scrolling, we debounce scroll
// events to a maximum of one every SCROLL_DEBOUNCE_MS milliseconds.
const SCROLL_DEBOUNCE_MS = 50;
let debounceTimer = null;
let isRenderScheduled = false;

// Track the properties of expanded trees
let expandedTreeOffset;
const expandedTreeHtml = new Map(); // treeIdx -> HTML string
const expandedTreeState = new Map(); // treeIdx -> tree state Map (resourceId -> {checked, open})
const expandedTreeRootId = new Map(); // treeIdx -> rootId

//
//  Initial setup
//

// Set the path for the expand/collapse SVG icon used in the resource tree
document.documentElement.style.setProperty('--expand-collapse-path',
    `url('${BASE_PATH}/static/svg/expand-collapse.svg')`);

scheduleRender();


//
//  Scroll event handling
//

resourceTreeEl.addEventListener('scroll', () => {
  if (debounceTimer) {
    clearTimeout(debounceTimer);
  }
  debounceTimer = setTimeout(() => {
    scheduleRender();
  }, SCROLL_DEBOUNCE_MS);
});


// Handle click on the summary expand/collapse button on a placeholder root.
// TODO: We should use the toggle event on the details element, but that event does not bubble,
// so we would need to attach a listener to each details element.
resourceTreeEl.addEventListener('click', (ev) => {
  // On the first expand on a placeholder root, we fetch the real tree from the server and render
  // it. The new tree also replaces the placeholder root and does not have the 'placeholder-root'
  // class, so this event listener won't be triggered again for the same tree.
  if (ev.target.classList.contains('placeholder-root')) {
    log('Click on placeholder root', ev);

    const detailsEl = ev.target;
    const treeContainerEl = detailsEl.closest('.tree-container');
    const rootId = parseInt(treeContainerEl.dataset.rootId);
    const treeIdx = parseInt(treeContainerEl.dataset.treeIdx);
    fetchTree(rootId).then(tree => {
      log('Placeholder expand click - Fetched first real tree for root_id:', {rootId});
      if (tree) {
        updateValidTree(treeContainerEl, tree, treeIdx, rootId);
        scheduleRender();
      }
      else {
        // As we are just now expanding the placeholder root into a real tree, the user has had no
        // opportunity to modify the tree. But it's remotely possible that it has been updated by
        // another user.
        alert('Failed to load resource tree. Has the resource been deleted, ' +
            'or have your permissions changed?');
      }
    });
    ev.stopPropagation();
  }
});

function updateValidTree(treeContainerEl, tree, treeIdx, rootId)
{
  log('updateValidTree()', {treeContainerEl, tree, treeIdx});
  // Remove fixed height
  treeContainerEl.style.height = 'auto';
  const treeHtml = formatResourceTreeRecursive(tree, true);
  treeContainerEl.innerHTML = treeHtml;
  const newDetailsEl = treeContainerEl.querySelector('.tree-details');
  newDetailsEl.open = true;
  expandedTreeHtml.set(treeIdx, treeHtml);
  expandedTreeState.set(treeIdx, getTreeState(treeContainerEl));
  expandedTreeRootId.set(treeIdx, rootId);
  measureTreeHeight(treeIdx).then(fullHeight => {
    expandedTreeOffset.set(treeIdx, fullHeight);
    scheduleRender();
  });
}

// Measure the full height of an expanded tree and save it.
function measureTreeHeight(treeIdx)
{
  log('measureTreeHeight()', {treeIdx});
  // These must be set before calling this function
  const treeHtml = expandedTreeHtml.get(treeIdx);
  const treeState = expandedTreeState.get(treeIdx);
  // Create temporary container for measurement
  const tempMeasureEl = document.createElement('div');
  tempMeasureEl.className = 'tree-container hide-container';
  tempMeasureEl.innerHTML = treeHtml;
  // Add to DOM temporarily for measurement
  document.body.appendChild(tempMeasureEl);
  return new Promise(resolve => {
    setTreeState(tempMeasureEl, treeState);
    // Allow the DOM to update before measuring height
    requestAnimationFrame(() => {
      const fullHeight = tempMeasureEl.offsetHeight;
      // Remove temporary container
      document.body.removeChild(tempMeasureEl);
      resolve(fullHeight);
    });
  });
}

// Handle click on the summary expand/collapse button on any node in a real tree (not a
// placeholder).
resourceTreeEl.addEventListener('pointerdown', (ev) => {
  log('Pointer down on summary', ev);
  const immediateCheckbox = ev.target.closest('.tree-details')?.querySelector('.tree-checkbox');
  if (immediateCheckbox && immediateCheckbox.contains(ev.target)) {
    return;
  }
  if (ev.target.closest('.tree-checkbox')) {
    // Ignore clicks on checkboxes, which are handled in a separate event listener.
    return;
  }
  const summaryEl = ev.target.closest("summary");
  if (!summaryEl) {
    return;
  }
  if (summaryEl.classList.contains('placeholder-root')) {
    return;
  }
  const detailsEl = summaryEl?.parentNode;
  if (summaryEl && detailsEl instanceof HTMLDetailsElement) {
    // Stop default toggle behavior
    ev.preventDefault();
  }
  const treeContainerEl = detailsEl.closest('.tree-container');
  const treeIdx = parseInt(treeContainerEl.dataset.treeIdx);
  detailsEl.open = !detailsEl.open;
  expandedTreeState.set(treeIdx, getTreeState(treeContainerEl));
  measureTreeHeight(treeIdx).then(fullHeight => {
    expandedTreeOffset.set(treeIdx, fullHeight);
    scheduleRender();
  });
  ev.stopPropagation();
});


// Resource tree (left side)

// Handle click on a placeholder checkbox.
resourceTreeEl.addEventListener('change', ev => {
  if (ev.target.classList.contains('placeholder-checkbox')) {
    log('Click on placeholder checkbox', ev);
    const checkboxEl = ev.target;
    const treeContainerEl = checkboxEl.closest('.tree-container');
    const rootId = parseInt(treeContainerEl.dataset.rootId);
    const treeIdx = parseInt(treeContainerEl.dataset.treeIdx);

    fetchTree(rootId).then(tree => {
      log('Placeholder checkbox click - Fetched first real tree for root_id:', {rootId});
      // Remove fixed height
      treeContainerEl.style.height = 'auto';
      const treeHtml = formatResourceTreeRecursive(tree, false);
      treeContainerEl.innerHTML = treeHtml;
      // Propagate click on resource checkbox to child checkboxes.
      const checkboxEls = treeContainerEl.querySelectorAll('.tree-checkbox');
      for (const el of checkboxEls) {
        el.checked = true;
      }
      requestAnimationFrame(() => {
        const fullHeight = treeContainerEl.offsetHeight;
        expandedTreeHtml.set(treeIdx, treeHtml);
        expandedTreeState.set(treeIdx, getTreeState(treeContainerEl));
        expandedTreeOffset.set(treeIdx, fullHeight);
        expandedTreeRootId.set(treeIdx, rootId);
        fetchSelectedResourcePermissions();
        scheduleRender();
      });
    });
  }
});

// Handle click on a real checkbox.
resourceTreeEl.addEventListener('change', ev => {
  if (ev.target.classList.contains('tree-checkbox')) {
    log('Click on real checkbox', ev);
    const checkboxEl = ev.target;
    const treeContainerEl = checkboxEl.closest('.tree-container');
    const treeIdx = parseInt(treeContainerEl.dataset.treeIdx);
    // Propagate click on resource checkbox to child checkboxes.
    const detailsEl = checkboxEl.closest('.tree-details');
    const checkboxEls = detailsEl.querySelectorAll('.tree-checkbox');
    for (const el of checkboxEls) {
      el.checked = checkboxEl.checked;
    }
    requestAnimationFrame(() => {
      expandedTreeState.set(treeIdx, getTreeState(treeContainerEl));
      fetchSelectedResourcePermissions();
    });
  }
});

// Principal search (right side, top)

principalSearchEl.addEventListener('input', _ev => {
  clearTimeout(principalFetchDelay);
  if (principalSearchEl.value.length < 2) {
    principalListEl.classList.remove('visible');
    return;
  }
  principalFetchDelay = setTimeout(fetchPrincipalSearch, 300);
});

principalSearchEl.addEventListener('blur', _ev => {
  principalListEl.classList.remove('visible');
});

// Add a permission to the selected resources for the new principal selected in the search results.
// The new principal is added with READ permission, which the user can then update if needed.
// We use mousedown instead of click to prevent the blur event on principalSearchEl from firing
// before the click event.
principalListEl.addEventListener('mousedown', ev => {
  const divEl = ev.target.closest('.principal-flex');
  const principalId = parseInt(divEl.dataset.principalId);
  const resources = getSelectedResourceIds();
  fetchSetPermission(resources, principalId, 1);
});


//
// Permissions (right side, bottom)
//

permissionListEl.addEventListener('change', ev => {
  // Handle new permission level selected in permission level dropdown
  if (ev.target.classList.contains('level-dropdown')) {
    const divEl = ev.target.closest('div');
    // dataset values are HTML attributes, which are always strings
    const principalId = parseInt(divEl.dataset.principalId);
    const permissionLevel = parseInt(ev.target.value);

    if (ENABLE_PUBLIC_ACCESS_WARNING) {
      if (divEl.dataset.ediId === PUBLIC_EDI_ID && permissionLevel === 0) {
        (async () => {
          const action = await showModalValue('confirmModal',
              'Revoking public access', `
              <p>
                Public access on Package and Metadata resources may only be removed when pre-approved by
                EDI.
              </p>
              <p>
                If your selection includes Package and Metadata resources in published packages, please
                cancel this operation and contact EDI for additional guidance.
              </p>`
          );
          if (action === 'accept') {
            const resources = getSelectedResourceIds();
            fetchSetPermission(resources, principalId, permissionLevel);
          }
          else {
            // Revert the dropdown to the previous value
            const previousPermission = permissionArray.find(p => p.principal_id === principalId);
            ev.target.value = previousPermission ? previousPermission.permission_level : 0;
          }
        })();
      }
    }
    else {
      const resources = getSelectedResourceIds();
      fetchSetPermission(resources, principalId, permissionLevel);
    }
  }
});

// **
// The goal with this was to enable re-selecting the same permission level in the dropdown to apply
// that permission to all selected resources, even if some of those resources already had that
// permission. However, could not get this to work reliably. Leaving this in, in case we want to
// give it another try later.
// **.
// permissionListEl.addEventListener('click', function (ev) {
//   // Trigger change event on level-dropdown, even if the same level is selected again. This allows a
//   // permission that only exists for some of the selected resources, to be applied to all the
//   // selected resources without changing the permission level.
//   if (ev.target.classList.contains('level-dropdown')) {
//     ev.target.dispatchEvent(new Event('change', {bubbles: true}));
//   }
// });


// Fetch a block of tree roots, if not already loaded.
function fetchBlock(blockIdx, version)
{
  log('fetchBlock()', {blockIdx, version});
  if (loadedBlocks.has(blockIdx)) {
    return Promise.resolve();
  }
  // Only start a new fetch if there isn't one already in progress
  if (blockPromises.has(blockIdx)) {
    return blockPromises.get(blockIdx).promise;
  }
  const url = new URL(`${BASE_PATH}/int/api/permission/slice`, window.location.origin);
  url.search = new URLSearchParams({
    uuid: SEARCH_UUID, start: (blockIdx * blockSize).toString(), limit: blockSize.toString(),
  }).toString();
  // Use  to get the final URL
  // Start a new fetch and return a promise we'll wait on later
  const promise = fetch(url.toString(), {cache: 'no-store'})
      .then(res => res.json())
      .then(trees => {
        loadedBlocks.set(blockIdx, trees);
      })
      .catch(err => {
        console.error('Fetch error:', err);
      })
      .finally(() => {
        blockPromises.delete(blockIdx);
      });

  const wrapped = {promise, version};
  blockPromises.set(blockIdx, wrapped);
  return promise;
}

function fetchTree(rootId)
{
  log('fetchTree()', {rootId});
  const url = new URL(`${BASE_PATH}/int/api/permission/tree/${rootId}`, window.location.origin);
  return fetch(url.toString(), {cache: 'no-store'})
      .then(res => res.json())
      .then(tree => {
        // log('Fetched tree for root_id:', rootId, tree);
        return tree;
      })
      .catch(err => {
        console.error('Fetch tree error:', err);
        throw err;
      });
}

//
// Infinite scroll rendering
//


function scheduleRender()
{
  log('scheduleRender()');
  if (!isRenderScheduled) {
    isRenderScheduled = true;
    requestAnimationFrame(() => {
      render();
      isRenderScheduled = false;
    });
  }
}


function render()
{
  log('render()');
  // Bump version to mark this render as current
  fetchVersion++;
  const version = fetchVersion;
  // Position calculations
  const scrollTop = resourceTree.scrollTop;
  const startTree = Math.max(0, expandedTreeOffset.getTreeAtOffset(
      Math.max(0, scrollTop - bufferTrees * collapsedTreeHeight)));
  const endTree = Math.min(TOTAL_TREE_COUNT, expandedTreeOffset.getTreeAtOffset(
      scrollTop + resourceTree.clientHeight + bufferTrees * collapsedTreeHeight) + 1);
  const neededBlocks = [];
  for (let i = Math.floor(startTree / blockSize); i <= Math.floor((endTree - 1) / blockSize); i++) {
    neededBlocks.push(i);
  }
  const promises = neededBlocks.map(b => fetchBlock(b, version));
  Promise.all(promises).then(() => {
    // Only render if this version is still current
    if (version === fetchVersion) {
      updateSpacerHeight();
      renderTrees(startTree, endTree);
    }
  });
}

// render = timerLog(render, 'render');

function updateSpacerHeight()
{
  log('updateSpacerHeight()');
  // Calculate total height considering expanded trees
  const totalHeight = expandedTreeOffset.getOffset(TOTAL_TREE_COUNT);
  spacerEl.style.height = `${totalHeight}px`;
}

function renderTrees(startTree, endTree)
{
  log('renderTrees()', {startTree, endTree});
  visibleTrees.innerHTML = '';

  for (let treeIdx = startTree; treeIdx < endTree; treeIdx++) {
    // // This tree was expanded, but is no longer valid (e.g. resource deleted or permissions
    // // changed). We display nothing for this tree.
    // if (expandedTreeHtml.has(treeIdx) && expandedTreeHtml == null) {
    //   const div = document.createElement('div');
    //   div.className = 'tree-container';
    //   div.dataset.treeIdx = treeIdx;
    //   div.style.top = `${expandedTreeOffset.getOffset(treeIdx)}px`;
    //   div.style.height = '0px';
    //   visibleTrees.appendChild(div);
    //   continue;
    // }
    const blockIdx = Math.floor(treeIdx / blockSize);
    const block = loadedBlocks.get(blockIdx);

    if (!block) {
      console.warn(`Missing block ${blockIdx} at tree ${treeIdx}`);
      continue;
    }

    const tree = block[treeIdx % blockSize];
    const div = document.createElement('div');
    div.className = 'tree-container';
    div.dataset.treeIdx = treeIdx;
    div.dataset.rootId = tree.resource_id;

    if (expandedTreeHtml.has(treeIdx)) {
      // If the tree is already expanded, use the cached HTML
      div.innerHTML = expandedTreeHtml.get(treeIdx);
      const state = expandedTreeState.get(treeIdx);
      setTreeState(div, state);
      // Switch this tree from fixed height to height based on content. This height is the one that
      // was measured when the tree was first expanded.
      div.style.height = 'auto';
    }
    else {
      div.innerHTML = `<ul class='tree'>
            <li>
              <details class='tree-details' >
                <summary class='tree-summary placeholder-root'>
                  <span>
                    <input type='checkbox' class='tree-checkbox placeholder-checkbox'/>
                    <span class='tree-resource-title'>${tree.label}</span>
                    <span class='tree-resource-type'>${tree.type}</span>
                  </span>
                </summary>
              </details>
            </li>
          </ul>
      `;
    }

    const topOffset = expandedTreeOffset.getOffset(treeIdx);
    div.style.top = `${topOffset}px`;
    visibleTrees.appendChild(div);
  }
}

function refreshExpandedTrees()
{
  log('refreshExpandedTrees()');
  for (const treeIdx of expandedTreeHtml.keys()) {
    const rootId = expandedTreeRootId.get(treeIdx);
    fetchTree(rootId).then(tree => {
      if (tree) {
        refreshExpandedValidTree(treeIdx, tree);
      }
      else {
        // Tree is no longer valid (e.g. resource deleted or permissions changed)
        refreshExpandedNullTree(treeIdx);
      }
    });
  }
}

function refreshExpandedValidTree(treeIdx, tree)
{
  log('refreshExpandedValidTree()', {treeIdx, tree});
  const treeHtml = formatResourceTreeRecursive(tree, false);
  expandedTreeHtml.set(treeIdx, treeHtml);
  // expandedTreeState.set(treeIdx, getTreeState(treeContainerEl));
  measureTreeHeight(treeIdx).then(fullHeight => {
    expandedTreeOffset.set(treeIdx, fullHeight);
    scheduleRender();
  });
}


function refreshExpandedNullTree(treeIdx)
{
  log('refreshExpandedNullTree()', {treeIdx});
  const treeContainerEl = document.querySelector(`[data-tree-idx='${treeIdx}']`);
  if (treeContainerEl) {
    treeContainerEl.style.display = 'none';
  }
  expandedTreeOffset.set(treeIdx, 0);
  // Setting to null marks this tree as invalid (no longer has permissions for the current user), so
  // we don't try to render it again. We use null instead of deleting the key, so we can distinguish
  // between trees that have not been expanded yet and trees that were expanded but are now invalid.
  expandedTreeHtml.set(treeIdx, null);
  requestAnimationFrame(() => {
    scheduleRender();
  });
}


//
//  Fetch
//


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

  fetch(`${BASE_PATH}/int/api/permission/aggregate/get`, {
    method: 'POST', headers: {
      'Content-Type': 'application/json',
    }, body: JSON.stringify(resources), cache: 'no-store',
  })
      .then((response) => {
        if (response.status === 401) {
          redirectToLogin();
          return Promise.reject('Unauthorized');
        }
        return response.json();
      })
      .then((result) => {
        permissionArray = result;
        clearTimeout(msgDelay);
        refreshPermissions();
      })
      .catch((error) => {
        if (error !== 'Unauthorized') {
          errorDialog(error);
        }
      });
}

// Called when the user selects a new principal from the search results (which gives that principal
// 'read'), or changes a permission level on one of the existing principals.
function fetchSetPermission(resources, principalId, permissionLevel)
{
  log('fetchSetPermission() START', {resources, principalId, permissionLevel});
  fetch(`${BASE_PATH}/int/api/permission/update`, {
    method: 'POST', headers: {
      'Content-Type': 'application/json',
    }, body: JSON.stringify({
      resources: resources, principalId: principalId, permissionLevel: permissionLevel,
    }), cache: 'no-store',
  })
      .then((response) => {
        if (response.status === 401) {
          redirectToLogin();
          return Promise.reject('Unauthorized');
        }
        return response.json();
      })
      .then((result) => {
        principalSearchEl.value = '';
        refreshExpandedTrees();
        fetchSelectedResourcePermissions();
        if (result.skip_count) {
          showMsgModal(
              'Permissions not updated', `${result.skip_count} of ${result.total_count} 
              resources could not be updated because removing the last owner is not permitted.`);
        }
      })
      .catch((error) => {
        if (error !== 'Unauthorized') {
          errorDialog(error);
        }
      });
  log('fetchSetPermission() END');
}

function fetchPrincipalSearch()
{
  const searchStr = principalSearchEl.value;
  fetch(`${BASE_PATH}/int/api/permission/principal/search`, {
    method: 'POST', headers: {
      'Content-Type': 'application/json',
    }, body: JSON.stringify({query: searchStr}), cache: 'no-store',
  })
      .then((response) => {
        if (response.status === 401) {
          redirectToLogin();
          return Promise.reject('Unauthorized');
        }
        return response.json();
      })
      .then((result) => {
        principalArray = result;
        refreshPrincipals();
      })
      .catch((error) => {
        if (error !== 'Unauthorized') {
          errorDialog(error);
        }
      });
}

//
//  Refresh
//


function formatResourceTreeRecursive(tree, open = true)
{
  return `<ul class='tree'>
    <li>
      <details class='tree-details${open ? ' open' : ''}'>
        <summary class='tree-summary'>
          <span>
            <input type='checkbox' class='tree-checkbox'
              data-resource-id='${tree.resource_id}'
            />
            <span class='tree-resource-title'>${tree.label}</span>
            <span class='tree-resource-type'>${tree.type}</span>
          </span>
        </summary>
        <ul>
          <li class='tree-indent'>
            ${formatTreePrincipalDiv(tree.principals)}
            ${tree.children ?
      tree.children.map(child => formatResourceTreeRecursive(child, false)).join('') : ''}
          </li>
        </ul>
      </details>
    </li>
  </ul>`;
}

// Add section of the tree for a principal in a resource type.
function formatTreePrincipalDiv(principalList)
{
  let htmlArray = [];
  for (const principal of principalList) {
    htmlArray.push(`
      <div class='tree-principal'>
        <div class='tree-principal-name'>${principal.title || ''}</div>
        <div class='tree-principal-edi-id'>${principal.edi_id}</div>
        <div class='tree-principal-permission-level'>
          ${formatTreePermissionLevelDiv(principal.permission_level)}
        </div>
      </div>
    `);
  }
  return htmlArray.join('');
}

function formatTreePermissionLevelDiv(level)
{
  return PERMISSION_LEVEL_ARRAY[level] || 'Unknown';
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
  for (const permission of permissionArray) {
    addPrincipalDiv(fragment, permission);
    addPermissionLevelDropdownDiv(fragment, permission, false);
  }
  permissionListEl.replaceChildren(fragment);
}

//
// Aggregated principal permissions (right side, bottom)
//

function refreshPrincipals()
{
  if (!principalArray.length) {
    principalListEl.innerHTML = `<div class='grid-msg'>No user profiles or groups found</div>`;
    principalListEl.classList.add('visible');
    return;
  }
  const fragment = document.createDocumentFragment();
  for (const principal of principalArray) {
    addPrincipalDiv(fragment, principal);
    // classList holds only unique values, so no need to check if it already exists
    principalListEl.classList.add('visible');
  }
  principalListEl.replaceChildren(fragment);
}

// refreshPrincipals = timerLog(refreshPrincipals, 'refreshPrincipals');


function addPrincipalDiv(parentEl, principal)
{
  const c = principal;
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
        <div class='copy-text-parent'>
          <div class='copy-text-text'>
              ${c.edi_id}
          </div>
          <div class='copy-text-icon'>
            <i class='bi bi-copy'></i>
          </div>
        </div>
      </div>
    </div>
  `;
  parentEl.appendChild(principalEl);
}

function addPermissionLevelDropdownDiv(parentEl, permission)
{
  const levelEl = document.createElement('div');
  levelEl.dataset.principalId = permission.principal_id;
  levelEl.dataset.ediId = permission.edi_id;
  const permission_level = permission.permission_level;
  let optionsHtml = `
    <option value='0' ${permission_level === 0 ? 'selected' : ''}>None</option>
    <option value='1' ${permission_level === 1 ? 'selected' : ''}>Reader</option>
  `;
  if (permission.edi_id !== PUBLIC_EDI_ID) {
    optionsHtml += `
      <option value='2' ${permission_level === 2 ? 'selected' : ''}>Editor</option>
      <option value='3' ${permission_level === 3 ? 'selected' : ''}>Owner</option>
    `;
  }
  levelEl.innerHTML = `<select class='level-dropdown'>${optionsHtml}</select>`;
  parentEl.appendChild(levelEl);
}

//
// Infinite scroll offset calculations
//

// Track the heights of expanded trees.
//
// This provides 3 fast operations:
// - Add the index and height of newly expanded tree.
// - Get the absolute position of a tree (expanded or not), given the tree index.
// - Get the index of the first tree that is visible, or partially visible, given a scroll offset.
//
// Note: This can be optimized further with a second binary search, but linear search is probably
// all we need, as the user is unlikely to expand a large number of trees.
class ExpandedTreeOffsets
{
  constructor()
  {
    // [{treeIdx, height}, ...] sorted by treeIdx
    this.trees = [];
  }

  // Set the height of a tree at the given index.
  // This may be called multiple times for the same treeIdx, as the user expands and collapses
  // branches of the tree.
  set(treeIdx, height)
  {
    log('ExpandedTreeOffsets.set()', {treeIdx, height});
    // Remove existing exception for this row
    const existingIdx = this.trees.findIndex(e => e.treeIdx === treeIdx);
    if (existingIdx !== -1) {
      this.trees.splice(existingIdx, 1);
    }
    let insertIdx = 0;
    while (insertIdx < this.trees.length && this.trees[insertIdx].treeIdx < treeIdx) {
      insertIdx++;
    }
    this.trees.splice(insertIdx, 0, {treeIdx, height});
  }

  // Binary search to find the last tree that starts at or before the given offset
  getTreeAtOffset(targetOffset)
  {
    // log('ExpandedTreeOffsets.getTreeAtOffset()', {targetOffset});
    let low = 0;
    let high = TOTAL_TREE_COUNT - 1;

    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      const midOffset = this.getOffset(mid);
      const nextOffset = this.getOffset(mid + 1);
      // Found the tree
      if (midOffset <= targetOffset &&
          (mid === TOTAL_TREE_COUNT - 1 || nextOffset > targetOffset)) {
        return mid;
      }
      // If the midOffset is greater than the target, search in the lower half
      if (midOffset > targetOffset) {
        high = mid - 1;
      }
      // If the midOffset is less than or equal to the target, search in the upper half
      else {
        low = mid + 1;
      }
    }
    // Default to first tree if not found
    return 0;
  }

  // Calculate the absolute position for a tree in the container.
  // The position is the standard tree height multiplied by the tree index, plus adjustments for any
  // expanded trees that are before the treeIdx.
  getOffset(treeIdx)
  {
    // log('ExpandedTreeOffsets.getOffset()', {treeIdx});
    let offset = treeIdx * collapsedTreeHeight;
    // Add the heights of all expanded trees before this treeIdx
    const trees = this.trees.filter(tree => tree.treeIdx < treeIdx);
    for (const {height} of trees) {
      offset += height - collapsedTreeHeight;
    }
    return offset;
  }
}

// Initializing the ExpandedTreeOffsets instance here allows us to move the class definition away
// from the top of the file.
expandedTreeOffset = new ExpandedTreeOffsets();

//
//  Util
//

// Return a list of resourceIds for selected resource types and resources in resource tree.
function getSelectedResourceIds()
{
  const resourceIdList = [];
  for (const state of expandedTreeState.values()) {
    for (const [resourceId, nodeState] of state.entries()) {
      if (nodeState.checked) {
        resourceIdList.push(resourceId);
      }
    }
  }
  return resourceIdList;
}

//
// Checkboxes
//

function clearCheckboxStates()
{
  // selectAllCheckboxEl.checked = false;
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
// Tree state (expanded/collapsed and checked/unchecked state of each node)
//

// Capture the state.
function getTreeState(treeRootEl)
{
  log('getTreeState()', {treeRootEl});
  const state = new Map();
  const detailsEls = treeRootEl.querySelectorAll('.tree-details');
  detailsEls.forEach(detailsEl => {
    const checkboxEl = detailsEl.querySelector('.tree-checkbox');
    const resourceId = parseInt(checkboxEl.dataset.resourceId);
    state.set(resourceId, {open: detailsEl.open, checked: checkboxEl.checked});
  });
  log('getTreeState() - state:', state);
  return state;
}

// Apply the saved state to the tree
function setTreeState(treeRootEl, state)
{
  log('setTreeState()', {treeRootEl});
  const detailsEls = treeRootEl.querySelectorAll('.tree-details');
  detailsEls.forEach(detailsEl => {
    const checkboxEl = detailsEl.querySelector('.tree-checkbox');
    const resourceId = parseInt(checkboxEl.dataset.resourceId);
    if (state.has(resourceId)) {
      const nodeState = state.get(resourceId);
      detailsEl.open = nodeState.open;
      checkboxEl.checked = nodeState.checked;
    }
  });
}

//
// Misc utils
//

function redirectToLogin()
{
  window.location.href =
      `${BASE_PATH}/ui/signin?next=${encodeURIComponent(window.location.pathname)}`;
}

// Logging

// Add a log index to each log message.
// To separate bursts of log messages that result from user actions, we add a spacer line after a
// few seconds of inactivity.

function log(...args)
{
  if (!ENABLE_LOGGING || typeof console === 'undefined' || !console.log) {
    return;
  }
  logIdx += 1;
  console.log(logIdx, ...args);
  if (logSpacerTimeout) {
    clearTimeout(logSpacerTimeout);
  }
  logSpacerTimeout = setTimeout(() => {
    console.log('-'.repeat(100));
  }, 3000);
}

function timerLog(fn, name)
{
  return function (...args) {
    log(`${name} - START`);
    const start = performance.now();
    const result = fn.apply(this, args);
    const end = performance.now();
    log(`${name} - END (${(end - start).toFixed(2)} ms)`);
    countDomElements();
    return result;
  };
}

function countDomElements()
{
  log('NUMBER OF DOM ELEMENTS: ' + document.getElementsByTagName('*').length);
}
