let headerContainerEl = document.getElementById('headerContainer');
// Constants passed from the server
const NEW_SECRET = headerContainerEl.dataset.newSecret;

const fromInputEl = document.getElementById('keyValidFrom');
const toInputEl = document.getElementById('keyValidTo');
const durationEl = document.getElementById('keyDuration');

const editKeyModalEl = document.getElementById('editKeyModal');
const deleteKeyModalEl = document.getElementById('deleteKeyModal');

// Fetch all the forms we want to apply custom Bootstrap validation styles to
let forms = document.getElementsByClassName('needs-validation');
// Loop over them and prevent submission
Array.prototype.filter.call(forms, form => {
  form.addEventListener('submit', ev => {
    let isValidDateRange = true;
    const fromDate = new Date(fromInputEl.value);
    const toDate = new Date(toInputEl.value);
    let invalidMsg = 'Invalid date.';
    if (!isNaN(fromDate.getTime()) && !isNaN(toDate.getTime()) && fromDate > toDate) {
      fromInputEl.classList.add('is-invalid');
      invalidMsg = "'Valid from' must be before 'Valid to'";
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
editKeyModalEl.addEventListener('show.bs.modal', ev => {
  let button = ev.relatedTarget;
  document.getElementById('editKeyForm').action = button.dataset.formTarget;
  document.getElementById('keyTitle').textContent = button.dataset.title;
  document.getElementById('keyName').value = button.dataset.keyName;
  document.getElementById('keyGroupId').value = button.dataset.keyGroupId;
  document.getElementById('keySubmitButton').textContent = button.dataset.submitText;

  fromInputEl.value = button.dataset.keyValidFrom;
  toInputEl.value = button.dataset.keyValidTo;

  if (button.dataset.isNew === 'false') {
    document.getElementById('keyInfoGroup').style.display = 'block';
    document.getElementById('deleteButton').style.display = 'block';

    document.getElementById('keyId').value = button.dataset.keyId;
    document.getElementById('keyCreated').textContent = button.dataset.keyCreated;
    document.getElementById('keyUpdated').textContent = button.dataset.keyUpdated;
    document.getElementById('keyLastUsed').textContent = button.dataset.keyLastUsed;
    document.getElementById('keyUseCount').textContent = button.dataset.keyUseCount;
  }
  else {
    document.getElementById('keyInfoGroup').style.display = 'none';
    document.getElementById('deleteButton').style.display = 'none';
  }

  updateDurationDisplay();
});

// Clear the form if the modal is canceled/closed
editKeyModalEl.addEventListener('hidden.bs.modal', () => {
  // Reset the form
  document.getElementById('editKeyForm').reset();
  // Clear validation styles
  const formInputs = document.getElementById('editKeyForm').querySelectorAll('input');
  formInputs.forEach(input => {
    input.classList.remove('is-invalid');
    input.classList.remove('is-valid');
  });
  // Reset the duration display
  durationEl.value = '--';
});


// Key delete modal
document.getElementById('deleteButton').addEventListener('click', ev => {
  ev.preventDefault();
  bootstrap.Modal.getInstance(editKeyModalEl).hide();
  document.getElementById('deleteKeyId').value = parseInt(document.getElementById('keyId').value);
  document.getElementById('deleteKeyName').textContent = document.getElementById('keyName').value;
  (new bootstrap.Modal(deleteKeyModalEl)).show();
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
  if (!isNaN(fromDate.getTime()) && !isNaN(toDate.getTime()) && fromDate <= toDate) {
    durationEl.value = formatDuration(fromDate, toDate);
  }
  else {
    durationEl.value = '--';
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
  end.setDate(end.getDate() + 1);
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

