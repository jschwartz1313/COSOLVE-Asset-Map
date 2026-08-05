export const THEMES = ["classic", "dark", "color", "showcase", "showcase-light"];

export const THEME_LABELS = {
  classic: "Current",
  dark: "Dark",
  color: "Color",
  showcase: "Showcase",
  "showcase-light": "Showcase Light",
};

const SHOWCASE_THEMES = new Set(["showcase", "showcase-light"]);

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
  const coverScroll = doc.querySelector("[data-showcase-scroll]");
  const enterButtons = [...doc.querySelectorAll("[data-showcase-enter]")];
  const storyButton = doc.querySelector("[data-showcase-scroll-story]");
  const revealItems = [...doc.querySelectorAll("[data-showcase-reveal]")];
  const status = doc.querySelector("[data-theme-status]");
  const themeMeta = doc.querySelector("#theme-color-meta");
  const themeColors = {
    classic: "#ffffff",
    dark: "#11171a",
    color: "#ffffff",
    showcase: "#071823",
    "showcase-light": "#ffffff",
  };
  const reducedMotion = win.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  let revealObserver;
  let leaveTimer;
  let activeCoverTheme = "showcase";

  function coverSeenKey(theme) {
    return theme === "showcase-light"
      ? "cosolve-showcase-light-cover-seen"
      : "cosolve-showcase-cover-seen";
  }

  function updateShowcaseProgress() {
    if (!cover || !coverScroll) return;
    const available = coverScroll.scrollHeight - coverScroll.clientHeight;
    const progress = available > 0 ? coverScroll.scrollTop / available : 0;
    cover.style.setProperty("--showcase-progress", String(progress));
    cover.style.setProperty(
      "--showcase-shift",
      `${Math.min(coverScroll.scrollTop * 0.08, 72)}px`,
    );
  }

  function prepareRevealItems() {
    revealObserver?.disconnect();
    if (reducedMotion || !("IntersectionObserver" in win)) {
      revealItems.forEach((item) => item.classList.add("is-visible"));
      return;
    }
    revealItems.forEach((item) => item.classList.remove("is-visible"));
    revealObserver = new win.IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          entry.target.classList.add("is-visible");
          revealObserver.unobserve(entry.target);
        }
      },
      { root: coverScroll, rootMargin: "0px 0px -12%", threshold: 0.16 },
    );
    revealItems.forEach((item) => revealObserver.observe(item));
  }

  function hideCover({ remember = true } = {}) {
    if (!cover) return;
    win.clearTimeout(leaveTimer);
    cover.hidden = true;
    cover.classList.remove("is-ready", "is-leaving");
    doc.body.classList.remove("showcase-cover-open");
    if (remember) saveValue(win.sessionStorage, coverSeenKey(activeCoverTheme), "true");
  }

  function showCover({ focus = false, theme = "showcase" } = {}) {
    if (!cover) return;
    activeCoverTheme = theme;
    win.clearTimeout(leaveTimer);
    cover.hidden = false;
    cover.classList.remove("is-leaving");
    doc.body.classList.add("showcase-cover-open");
    if (coverScroll) coverScroll.scrollTop = 0;
    updateShowcaseProgress();
    prepareRevealItems();
    win.requestAnimationFrame(() => cover.classList.add("is-ready"));
    if (focus) enterButtons[0]?.focus();
  }

  function enterSite() {
    if (!cover || cover.hidden) return;
    cover.classList.add("is-leaving");
    const delay = reducedMotion ? 0 : 440;
    leaveTimer = win.setTimeout(() => {
      hideCover();
      if (!doc.body.classList.contains("map-page")) {
        const mapUrl = doc.querySelector(".brand")?.href;
        if (mapUrl) win.location.assign(mapUrl);
        return;
      }
      doc.body.classList.add("showcase-arrival");
      win.setTimeout(() => doc.body.classList.remove("showcase-arrival"), 900);
      doc.querySelector("#main-content")?.focus({ preventScroll: true });
    }, delay);
  }

  function applyTheme(value, { announce = false, showIntro = false } = {}) {
    const theme = normalizeTheme(value);
    root.dataset.theme = theme;
    saveValue(win.localStorage, "cosolve-display-mode", theme);
    for (const button of buttons) {
      button.setAttribute("aria-pressed", String(button.dataset.themeChoice === theme));
    }
    if (themeMeta) themeMeta.content = themeColors[theme];

    if (SHOWCASE_THEMES.has(theme)) {
      const seen = storageValue(win.sessionStorage, coverSeenKey(theme)) === "true";
      if (showIntro || !seen) showCover({ focus: showIntro, theme });
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

  enterButtons.forEach((button) => button.addEventListener("click", enterSite));
  storyButton?.addEventListener("click", () => {
    coverScroll?.querySelector(".showcase-statement")?.scrollIntoView({
      behavior: reducedMotion ? "auto" : "smooth",
      block: "start",
    });
  });
  coverScroll?.addEventListener("scroll", updateShowcaseProgress, { passive: true });

  doc.addEventListener("keydown", (event) => {
    if (!cover || cover.hidden) return;
    if (event.key === "Escape") {
      hideCover();
      buttons.find((button) => button.dataset.themeChoice === activeCoverTheme)?.focus();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = [...cover.querySelectorAll("button, summary, a[href]")]
      .filter((element) => !element.hasAttribute("disabled"));
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable.at(-1);
    if (event.shiftKey && doc.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && doc.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
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
