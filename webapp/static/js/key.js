let headerContainerEl = document.getElementById('headerContainer');
// Constants passed from the server
const NEW_SECRET = headerContainerEl.dataset.newSecret;

const fromInputEl = document.getElementById('keyValidFrom');
const toInputEl = document.getElementById('keyValidTo');
const durationEl = document.getElementById('keyDuration');

// Fetch all the forms we want to apply custom Bootstrap validation styles to
let forms = document.getElementsByClassName('needs-validation');
// Loop over them and prevent submission
Array.prototype.filter.call(forms, function (form) {
  form.addEventListener('submit', ev => {
    let isValidDateRange = true;
    const fromDate = new Date(fromInputEl.value);
    const toDate = new Date(toInputEl.value);
    let invalidMsg = 'Invalid date.';
    if (!isNaN(fromDate.getTime()) && !isNaN(toDate.getTime()) && fromDate >= toDate) {
      fromInputEl.classList.add('is-invalid');
      invalidMsg = 'From-date must be before to-date';
      isValidDateRange = false;
    }
    document.getElementById('fromDateFeedback').textContent = invalidMsg;
    if (!isValidDateRange || form.checkValidity() === false) {
      ev.preventDefault();
      ev.stopPropagation();
    }
    form.classList.add('was-validated');
  }, false);
});

// Key new/edit modal
let editKeyModalEl = document.getElementById('editKeyModal');
editKeyModalEl.addEventListener('show.bs.modal', ev => {
  let button = ev.relatedTarget;
  document.getElementById('keyForm').action = button.dataset.formTarget;
  document.getElementById('keyTitle').textContent = button.dataset.title;
  document.getElementById('keySubmitButton').textContent = button.dataset.submitText;
  document.getElementById('keyName').value = button.dataset.keyName;
  document.getElementById('keyGroupId').value = button.dataset.keyGroupId;
  fromInputEl.value = button.dataset.keyValidFrom;
  toInputEl.value = button.dataset.keyValidTo;

  document.getElementById('keyCreated').textContent = button.dataset.keyCreated;
  document.getElementById('keyUpdated').textContent = button.dataset.keyUpdated;
  document.getElementById('keyLastUsed').textContent = button.dataset.keyLastUsed;
  document.getElementById('keyUseCount').textContent = button.dataset.keyUseCount;
  updateDurationDisplay();
});

// Clear the form if the modal is canceled/closed
editKeyModalEl.addEventListener('hidden.bs.modal', () => {
  // Reset the form
  document.getElementById('keyForm').reset();
  // Clear validation styles
  const formInputs = document.getElementById('keyForm').querySelectorAll('input');
  formInputs.forEach(input => {
    input.classList.remove('is-invalid');
    input.classList.remove('is-valid');
  });
  // Reset the duration display
  durationEl.textContent = '--';
});

// Key delete modal
let deleteKeyModalEl = document.getElementById('deleteKeyModal');
deleteKeyModalEl.addEventListener('show.bs.modal', function (ev) {
  let button = ev.relatedTarget;
  document.getElementById('deleteKey').value = button.dataset.keyToken;
  document.getElementById('deleteKeyName').textContent = button.dataset.keyName;
});

// newSecretMsgModal
if (NEW_SECRET !== '') {
  let newSecretMsgModalEl = document.getElementById('newSecretMsgModal');
  newSecretMsgModal = new bootstrap.Modal(newSecretMsgModalEl);
  newSecretMsgModal.show();
}

//
// Events
//

fromInputEl.addEventListener('change', updateDurationDisplay);
toInputEl.addEventListener('change', updateDurationDisplay);

function updateDurationDisplay()
{
  const fromDate = new Date(fromInputEl.value);
  const toDate = new Date(toInputEl.value);
  if (!isNaN(fromDate.getTime()) && !isNaN(toDate.getTime()) && fromDate < toDate) {
    durationEl.textContent = formatDuration(fromDate, toDate);
  }
  else {
    durationEl.textContent = '--';
  }
}

// Format the exact time between dates as a string
function formatDuration(startDate, endDate)
{
  const {years, months, days} = getDuration(startDate, endDate);
  const parts = [];
  if (years > 0) {
    parts.push(`${years} year${years !== 1 ? 's' : ''}`);
  }
  if (months > 0) {
    parts.push(`${months} month${months !== 1 ? 's' : ''}`);
  }
  if (days > 0) {
    parts.push(`${days} day${days !== 1 ? 's' : ''}`);
  }
  return parts.join(', ');
}

// Calculate exact years, months, and days between two real dates
function getDuration(startDate, endDate)
{
  let start = new Date(startDate);
  let end = new Date(endDate);
  let years = end.getFullYear() - start.getFullYear();
  let months = end.getMonth() - start.getMonth();
  // If months is negative, adjust years and months
  if (months < 0) {
    years--;
    months += 12;
  }
  let days = end.getDate() - start.getDate();
  // If days is negative, adjust months and days
  if (days < 0) {
    months--;
    // Get the number of days in the previous month relative to end date
    const lastMonth = new Date(end.getFullYear(), end.getMonth(), 0);
    days += lastMonth.getDate();
  }
  // If months became negative after day adjustment, readjust years and months
  if (months < 0) {
    years--;
    months += 12;
  }
  return {years, months, days};
}

