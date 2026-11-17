const menus = [...document.querySelectorAll("[data-header-menu]")];
const stateSwitcher = document.querySelector("[data-state-switcher]");
if (stateSwitcher) {
  stateSwitcher.querySelector("select").addEventListener("change", () => stateSwitcher.requestSubmit());
  stateSwitcher.querySelector("button").hidden = true;
}

for (const menu of menus) {
  menu.addEventListener("toggle", () => {
    if (!menu.open) return;
    for (const other of menus) {
      if (other !== menu) other.open = false;
    }
  });
}

document.addEventListener("click", (event) => {
  for (const menu of menus) {
    if (!menu.contains(event.target)) menu.open = false;
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  const menu = menus.find((item) => item.open);
  if (menu) {
    event.preventDefault();
    menu.open = false;
    menu.querySelector("summary")?.focus();
  }
});
