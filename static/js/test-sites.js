import { bindFilterSelects } from "./filters.js?v=20261021-2";

const form = document.querySelector(".test-site-form");
if (form) {
  bindFilterSelects(form);
  form.addEventListener("submit", () => {
    if (window.matchMedia("(max-width: 700px)").matches) {
      form.action = `${window.location.pathname}#test-results-heading`;
    }
  });
  if (window.location.hash === "#test-results-heading") {
    document.querySelector(".test-search-errors")?.focus();
  }
}
