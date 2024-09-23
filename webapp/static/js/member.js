const memberListMsgEl = document.getElementById('memberListMsg');
const searchMemberEl = document.getElementById('searchMember');
const memberListEl = document.getElementById('memberList');
const candidateListEl = document.getElementById('candidateList');

const GROUP_ID = parseInt(
    document.getElementsByClassName('header-container')[0].getAttribute('data-group-id'));

let fetchDelay = null;
const memberProfileIdSet = new Set();
const candidateProfileMap = new Map();

/*
  Initial setup
*/
// find all profile-root under memberListEl
const memberElArr = memberListEl.querySelectorAll('.profile-root');
for (const memberEl of memberElArr) {
  memberProfileIdSet.add(parseInt(memberEl.getAttribute('data-profile-id')));
}
refreshMemberListMsg();

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
  candidateEl = event.target.closest('.profile-root');
  let profileId = parseInt(candidateEl.getAttribute('data-profile-id'));
  const candidateMap = candidateProfileMap.get(profileId);
  memberProfileIdSet.add(profileId);
  addProfile(memberListEl, candidateMap, false);
  refreshCandidates();
  refreshMemberListMsg();
  fetchAddRemoveMember(profileId, true);
});

memberListEl.addEventListener('click', function (event) {
  if (!event.target.closest('.icon-text-button')) { return; }
  memberEl = event.target.closest('.profile-root');
  let profileId = parseInt(memberEl.getAttribute('data-profile-id'));
  memberProfileIdSet.delete(profileId);
  memberEl.remove();
  refreshCandidates();
  refreshMemberListMsg();
  fetchAddRemoveMember(profileId, false);
});

function refreshMemberListMsg() {
  if (memberProfileIdSet.size === 0) {
    memberListMsgEl.innerHTML = `<p>No members have been added to this group yet.</p>`;
  } else {
    memberListMsgEl.innerHTML = ``;
  }
}

/**/

function fetchSearch()
{
  const searchStr = searchMemberEl.value;
  console.log('searchStr:', searchStr);

  fetch('/group/member/search', {
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
  fetch('/group/member/add-remove', {
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


function refreshCandidates()
{
  if (candidateProfileMap.size === 0) {
    candidateListEl.innerHTML = `<p>No candidates found.</p>`;
    return;
  }
  // We use a document fragment to avoid multiple reflows.
  const fragment = document.createDocumentFragment();
  for (const [_profileId, profileMap] of candidateProfileMap) {
    addProfile(fragment, profileMap, true);
  }
  candidateListEl.replaceChildren(fragment);
}

function addProfile(parentEl, profileMap, remove)
{
  const profileEl = document.createElement('div');
  profileEl.classList.add('profile-flex');
  profileEl.classList.add('profile-root');
  profileEl.setAttribute('data-profile-id', profileMap.profile_id);
  profileEl.innerHTML = createProfileHtml(profileMap, remove);
  parentEl.appendChild(profileEl);
}

// Create the HTML for either a member or a candidate.
function createProfileHtml(profileMap, is_add)
{
  const p = profileMap;
  // noinspection JSUnresolvedReference
  let buttonHtml;
  if (is_add && !memberProfileIdSet.has(p.profile_id)) {
    buttonHtml = `
      <button type='submit' class='icon-text-button' id='addButton'>
          <span><img src='/static/svg/arrow-up-from-line.svg' alt='Add'></span>
          <span>Add</span>
        </button>
    `;
  }
  else if (is_add) {
    buttonHtml = `
      <span>(Group Member)</span>
    `;
  }
  else {
    buttonHtml = `
      <button type='submit' class='icon-text-button' id='removeButton'>
          <span><img src='/static/svg/arrow-down-from-line.svg' alt='Remove'></span>
          <span>Remove</span>
        </button>
    `;
  }
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


// Set test string and trigger event
// searchMemberEl.value = 'Roger';
// searchMemberEl.dispatchEvent(new Event('input'));
