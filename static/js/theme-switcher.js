export const THEMES = ["classic", "dark", "color", "showcase"];

export const THEME_LABELS = {
  classic: "Current",
  dark: "Dark",
  color: "Color",
  showcase: "Showcase",
};

export function normalizeTheme(value) {
  return THEMES.includes(value) ? value : "classic";
}

function storageValue(storage, key) {
  try {
    return storage?.getItem(key);
  } catch (error) {
    return null;
  }
}

function saveValue(storage, key, value) {
  try {
    storage?.setItem(key, value);
  } catch (error) {
    // Theme selection still works when storage is unavailable.
  }
}

export function initializeThemeSwitcher(doc = document, win = window) {
  const root = doc.documentElement;
  const buttons = [...doc.querySelectorAll("[data-theme-choice]")];
  const cover = doc.querySelector("[data-showcase-cover]");
  const enterButton = doc.querySelector("[data-showcase-enter]");
  const status = doc.querySelector("[data-theme-status]");
  const themeMeta = doc.querySelector("#theme-color-meta");
  const themeColors = {
    classic: "#ffffff",
    dark: "#11171a",
    color: "#ffffff",
    showcase: "#071823",
  };

  function hideCover({ remember = true } = {}) {
    if (!cover) return;
    cover.hidden = true;
    doc.body.classList.remove("showcase-cover-open");
    if (remember) saveValue(win.sessionStorage, "cosolve-showcase-cover-seen", "true");
  }

  function showCover({ focus = false } = {}) {
    if (!cover) return;
    cover.hidden = false;
    doc.body.classList.add("showcase-cover-open");
    if (focus) enterButton?.focus();
  }

  function applyTheme(value, { announce = false, showIntro = false } = {}) {
    const theme = normalizeTheme(value);
    root.dataset.theme = theme;
    saveValue(win.localStorage, "cosolve-display-mode", theme);
    for (const button of buttons) {
      button.setAttribute("aria-pressed", String(button.dataset.themeChoice === theme));
    }
    if (themeMeta) themeMeta.content = themeColors[theme];

    if (theme === "showcase") {
      const seen = storageValue(win.sessionStorage, "cosolve-showcase-cover-seen") === "true";
      if (showIntro || !seen) showCover({ focus: showIntro });
    } else {
      hideCover({ remember: false });
    }

    if (announce && status) status.textContent = `${THEME_LABELS[theme]} view selected`;
    win.dispatchEvent(new CustomEvent("cosolve:themechange", { detail: { theme } }));
    return theme;
  }

  for (const button of buttons) {
    button.addEventListener("click", () => {
      applyTheme(button.dataset.themeChoice, { announce: true, showIntro: true });
    });
    button.addEventListener("keydown", (event) => {
      if (!new Set(["ArrowLeft", "ArrowRight", "Home", "End"]).has(event.key)) return;
      event.preventDefault();
      const currentIndex = THEMES.indexOf(normalizeTheme(root.dataset.theme));
      const nextIndex = event.key === "Home"
        ? 0
        : event.key === "End"
          ? THEMES.length - 1
          : (currentIndex + (event.key === "ArrowRight" ? 1 : -1) + THEMES.length)
            % THEMES.length;
      const nextButton = buttons.find((item) => item.dataset.themeChoice === THEMES[nextIndex]);
      nextButton?.focus();
      applyTheme(THEMES[nextIndex], { announce: true, showIntro: true });
    });
  }

  enterButton?.addEventListener("click", () => {
    hideCover();
    if (!doc.body.classList.contains("map-page")) {
      const mapUrl = doc.querySelector(".brand")?.href;
      if (mapUrl) win.location.assign(mapUrl);
      return;
    }
    doc.querySelector("#main-content")?.focus({ preventScroll: true });
  });

  doc.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && cover && !cover.hidden) hideCover();
  });

  return applyTheme(root.dataset.theme);
}

if (typeof document !== "undefined" && typeof window !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => initializeThemeSwitcher(), { once: true });
  } else {
    initializeThemeSwitcher();
  }
}
