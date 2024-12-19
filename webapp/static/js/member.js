// const memberListMsgEl = document.getElementById('memberListMsg');
const searchMemberEl = document.getElementById('searchMember');
const memberListEl = document.getElementById('memberList');
const candidateListEl = document.getElementById('candidateList');

let headerContainerEl = document.getElementsByClassName('header-container')[0];
const GROUP_ID = parseInt(headerContainerEl.dataset.groupId);
const ROOT_PATH = headerContainerEl.dataset.rootPath;

let fetchDelay = null;
// const memberProfileIdSet = new Set();
const memberProfileMap = new Map();
const candidateProfileMap = new Map();

/*
  Initial setup
*/

fetchMembers();

/*
  Events
*/

searchMemberEl.addEventListener('input', function (e) {
  clearTimeout(fetchDelay);
  if (searchMemberEl.value.length < 2) {
    candidateListEl.innerHTML = '';
    return;
  }
  fetchDelay = setTimeout(fetchSearch, 300);
});


// We can't add an event handler directly to a dynamically generated element, so we use event
// delegation to listen for clicks on the parent element.
candidateListEl.addEventListener('click', function (event) {
  if (!event.target.closest('.icon-text-button')) { return; }
  const candidateEl = event.target.closest('.profile-root');
  const profileId = parseInt(candidateEl.dataset.profileId);
  const profileMap = candidateProfileMap.get(profileId);
  if (memberProfileMap.has(profileId)) {
    removeMember(profileId);
  }
  else {
    addMember(profileId, profileMap);
  }
});

memberListEl.addEventListener('click', function (event) {
  if (!event.target.closest('.icon-text-button')) { return; }
  const memberEl = event.target.closest('.profile-root');
  removeMember(parseInt(memberEl.dataset.profileId));
});

function addMember(profileId, profileMap)
{
  memberProfileMap.set(profileMap.profile_id, profileMap);
  refreshMembers();
  refreshCandidates();
  fetchAddRemoveMember(profileId, true);
}

function removeMember(profileId)
{
  memberProfileMap.delete(profileId);
  refreshMembers();
  refreshCandidates();
  fetchAddRemoveMember(profileId, false);
}

function refreshMembers()
{
  if (memberProfileMap.size === 0) {
    memberListEl.innerHTML = `<div class='grid-msg'>No members have been added to this group yet.</div>`;
    return;
  }
  // We use a document fragment to avoid multiple reflows.
  const fragment = document.createDocumentFragment();
  for (const [_profileId, profileMap] of memberProfileMap) {
    addProfile(fragment, profileMap, false);
  }
  memberListEl.replaceChildren(fragment);
}


function refreshCandidates()
{
  if (candidateProfileMap.size === 0 && searchMemberEl.value.length > 1) {
    candidateListEl.innerHTML = `<div class='grid-msg'>No candidates found.</div>`;
    return;
  }
  const fragment = document.createDocumentFragment();
  for (const [_profileId, profileMap] of candidateProfileMap) {
    addProfile(fragment, profileMap, !memberProfileMap.has(profileMap.profile_id));
  }
  candidateListEl.replaceChildren(fragment);
}


function addProfile(parentEl, profileMap, isAdd)
{
  const profileEl = document.createElement('div');
  profileEl.classList.add('profile-flex');
  profileEl.classList.add('profile-root');
  profileEl.dataset.profileId = profileMap.profile_id;
  profileEl.innerHTML = createProfileHtml(profileMap, isAdd);
  parentEl.appendChild(profileEl);
}


// Create the HTML for either a member or a candidate.
function createProfileHtml(profileMap, isAdd)
{
  const p = profileMap;
  let buttonHtml = isAdd ? `
      <button type='submit' class='icon-text-button' id='addButton'>
          <span><img src='${ROOT_PATH}/static/svg/arrow-up-from-line.svg' alt='Add'></span>
          <span>Add</span>
        </button>
    ` : `
      <button type='submit' class='icon-text-button' id='removeButton'>
          <span><img src='${ROOT_PATH}/static/svg/arrow-down-from-line.svg' alt='Remove'></span>
          <span>Remove</span>
        </button>
    `;
  return `
    <div class='profile-flex-row'>
      <div class='profile-flex-child profile-flex-avatar'>
        <img src='${p.avatar_url}' alt='Avatar' class='avatar avatar-small'>
      </div>
      <div class='profile-flex-child profile-flex-name'>${p.full_name}</div>
      <div class='profile-flex-child'>${p.email}</div>
      <div class='profile-flex-child'>${p.organization || ''}</div>
      <div class='profile-flex-child'>${p.association || ''}</div>
      <div class='profile-flex-child profile-flex-button'>
        ${buttonHtml}      
      </div>
    </div>
  `;
}

function fetchMembers()
{
  const searchStr = searchMemberEl.value;
  console.log('searchStr:', searchStr);

  fetch(`/group/member/list/${GROUP_ID}`, {
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
          memberProfileMap.clear();
          for (const profileMap of resultObj.member_list) {
            memberProfileMap.set(profileMap.profile_id, profileMap);
          }
          refreshMembers();
        }
      })
      .catch((error) => {
        console.error('Error:', error);
      });
}

function fetchSearch()
{
  const searchStr = searchMemberEl.value;
  console.log('searchStr:', searchStr);

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
          candidateProfileMap.clear();
          for (const profileMap of resultObj.candidate_list) {
            candidateProfileMap.set(profileMap.profile_id, profileMap);
          }
          refreshCandidates();
        }
      })
      .catch((error) => {
        console.error('Error:', error);
      });
}

function fetchAddRemoveMember(memberProfileId, isAdd)
{
  fetch(`${ROOT_PATH}/group/member/add-remove`, {
    method: 'POST', headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({group_id: GROUP_ID, member_profile_id: memberProfileId, is_add: isAdd}),
  })
      .then((response) => response.json())
      .then((resultObj) => {
        console.log('Status:', resultObj.status);
        if (resultObj.error) {
          alert(resultObj.error);
        }
      })
      .catch((error) => {
        console.error('Error:', error);
      });
}
