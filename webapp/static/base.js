// Import this file after building the DOM (just before the closing </body> tag)

let $ = jQuery.noConflict();

// Highlight the current page in the navigation bar
let pageName = getPageName();
let el_arr = document.querySelectorAll('a.nav-link');
for (let el of el_arr) {
    if (el.getAttribute('href').endsWith(`/${pageName}`)) {
        el.classList.add('active');
        // ARIA is an accessibility standard. It helps with screen readers.
        el.setAttribute('aria-current', 'page');
    }
    else {
        el.classList.remove('active');
        el.setAttribute('aria-current', 'false');
    }
}

function getPageName()
{
    let url = window.location.pathname;
    let split_list = url.split('/');
    return split_list[split_list.length - 1];
}

