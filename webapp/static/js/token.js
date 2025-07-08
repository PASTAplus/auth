let headerContainerEl = document.getElementsByClassName('header-container')[0];

// Add click hander for copyTokenButton
const ROOT_PATH = headerContainerEl.dataset.rootPath;

const copyTokenButton = document.getElementById('copyTokenButton');

copyTokenButton.addEventListener('click', function () {
  fetch(`${ROOT_PATH}/token/download`)
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

