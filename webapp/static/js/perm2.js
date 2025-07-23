// Constants passed from the server
const headerContainerEl = document.getElementById('header-container'); // for data-root-path, data-root-count
const BASE_PATH = headerContainerEl.dataset.rootPath;
const ROOT_COUNT = parseInt(headerContainerEl.dataset.rootCount);

const rowHeight = 30;      // pixels
const blockSize = 100;     // rows per fetch
const bufferRows = 50;     // above & below viewport
const totalRows = ROOT_COUNT; // static total count

const container = document.getElementById('scroll-container');          // scrollable container
const spacer = document.getElementById('spacer');                       // the scroll spacer div
const visibleRows = document.getElementById('visible-rows');            // container for row elements

const loadedBlocks = new Map(); // blockIndex -> row data array


const blockPromises = new Map(); // blockIndex -> Promise

let fetchVersion = 0;                 // incremented on each new render

let ccc = 0;

const blockControllers = new Map(); // blockIndex -> AbortController

render();


let debounceTimer = null;

container.addEventListener('scroll', () => {
  if (debounceTimer) {
    clearTimeout(debounceTimer);
  }
  debounceTimer = setTimeout(() => {
    scheduleRender();
  }, 250); // Wait for scroll to settle
});


function fetchBlock(blockIndex, version)
{
  if (loadedBlocks.has(blockIndex)) {
    return Promise.resolve();
  }

  // Cancel any prior fetch for this block
  if (blockControllers.has(blockIndex)) {
    blockControllers.get(blockIndex).abort();
    blockControllers.delete(blockIndex);
    blockPromises.delete(blockIndex);
  }

  const controller = new AbortController();
  const signal = controller.signal;
  blockControllers.set(blockIndex, controller);

  const promise = fetch(
      `${BASE_PATH}/perm2/fetch?start=${blockIndex * blockSize}&limit=${blockSize}`,
      {signal}
  )
      .then(res => res.json())
      .then(rows => {
        loadedBlocks.set(blockIndex, rows);
      })
      .catch(err => {
        if (err.name !== 'AbortError') {
          console.error('Fetch error:', err);
        }
      })
      .finally(() => {
        blockPromises.delete(blockIndex);
        blockControllers.delete(blockIndex);
      });

  const wrapped = {promise, version};
  blockPromises.set(blockIndex, wrapped);
  return promise;
}


let isRenderScheduled = false;

function scheduleRender()
{
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
  fetchVersion++; // bump version to mark this render as current

  const version = fetchVersion;

  const scrollTop = container.scrollTop;
  const firstVisibleRow = Math.floor(scrollTop / rowHeight);
  const lastVisibleRow = Math.ceil((scrollTop + container.clientHeight) / rowHeight);
  const startRow = Math.max(0, firstVisibleRow - bufferRows);
  const endRow = Math.min(totalRows, lastVisibleRow + bufferRows);

  const neededBlocks = [];
  for (let i = Math.floor(startRow / blockSize); i <= Math.floor((endRow - 1) / blockSize); i++) {
    neededBlocks.push(i);
  }

  const promises = neededBlocks.map(b => fetchBlock(b, version));

  Promise.all(promises).then(() => {
    // Only render if this version is still current
    if (version === fetchVersion) {
      renderRows(startRow, endRow);
    }
  });
}


function renderRows(startRow, endRow)
{
  visibleRows.innerHTML = '';

  for (let i = startRow; i < endRow; i++) {
    const blockIndex = Math.floor(i / blockSize);
    const block = loadedBlocks.get(blockIndex);

    if (!block) {
      console.warn(`Missing block ${blockIndex} at row ${i}`);
      continue;
    }

    const row = block[i % blockSize];
    const div = document.createElement('div');
    div.innerHTML = `<ul class='tree'>
          <li>
            <details class='tree-details'>
              <summary>
                <span>
                  <input type='checkbox' class='tree-checkbox'/>
                  <span class='tree-resource-title'>PackageID-${i}</span>
                  <span class='tree-resource-type'>Package</span>
                </span>
              </summary>
              <ul>
                <li class='tree-indent'>
                </li>
              </ul>
            </details>
          </li>
        </ul>
    `;

    div.className = 'scroll-row';
    // div.textContent = `Row ${i}: ${row}`;
    div.style.top = `${i * rowHeight}px`;
    visibleRows.appendChild(div);
  }

  spacer.style.height = `${totalRows * rowHeight}px`;
}


function log(...args)
{
  if (typeof console !== 'undefined' && console.log) {
    ccc += 1;
    console.log(ccc, ...args);

  }
}
