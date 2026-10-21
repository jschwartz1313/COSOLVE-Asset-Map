import { bindFilterSelects } from "./filters.js?v=20261021-2";

const form = document.querySelector(".directory-filters form");
if (form) bindFilterSelects(form);
