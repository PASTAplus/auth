let headerContainerEl = document.getElementsByClassName('header-container')[0];

// Add click hander for copyTokenButton
const BASE_PATH = headerContainerEl.dataset.basePath;

const copyTokenButton = document.getElementById('copyTokenButton');

copyTokenButton.addEventListener('click', function () {
  fetch(`${BASE_PATH}/ui/api/token/download`)
      .then((response) => response.text())
      .then((token) => {
        navigator.clipboard.writeText(token);
      })
      .catch((error) => {
        errorDialog(error);
      });

  const copyStatus = document.getElementById('copyStatus');
  copyStatus.textContent = 'Copied';
});

