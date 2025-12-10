const hash = window.location.hash;
if (hash) {
  const header = document.getElementById(hash.substring(1));
  if (header) {
    header.classList.add('flash-highlight');
    document.getElementById('close-btn').classList.remove('d-none');

  }
}
