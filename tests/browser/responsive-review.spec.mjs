import { THEMES } from "../../static/js/theme-switcher.js";
import { expect, test } from "@playwright/test";

for (const theme of THEMES) {
  test(`directory titles have room at tablet widths in ${theme}`, async ({ page }) => {
    await page.addInitScript((selectedTheme) => {
      localStorage.setItem("cosolve-display-mode", selectedTheme);
      sessionStorage.setItem("cosolve-showcase-cover-seen", "true");
      sessionStorage.setItem("cosolve-showcase-light-cover-seen", "true");
    }, theme);
    for (const width of [768, 820, 880]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/directory/");
      const names = await page.locator(".directory-row-main h3").evaluateAll((elements) =>
        elements.map((element) => ({ width: element.clientWidth, scroll: element.scrollWidth })),
      );
      expect(names.length).toBeGreaterThan(0);
      for (const name of names) {
        expect(name.width).toBeGreaterThan(300);
        expect(name.scroll).toBeLessThanOrEqual(name.width + 1);
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth))
        .toBeLessThanOrEqual(width);
    }
  });

  test(`expanded legend does not cover toolbar controls in ${theme}`, async ({ page }) => {
    await page.addInitScript((selectedTheme) => {
      localStorage.setItem("cosolve-display-mode", selectedTheme);
      sessionStorage.setItem("cosolve-showcase-cover-seen", "true");
      sessionStorage.setItem("cosolve-showcase-light-cover-seen", "true");
    }, theme);

    for (const width of [320, 390, 651, 768, 881, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/map/");
      await expect(page.locator(".result-row").first()).toBeVisible();
      await page.locator(".map-legend > summary").click();
      const covered = await page.locator(".map-toolbar").evaluate((toolbar) => {
        const legend = toolbar.querySelector(".map-legend").getBoundingClientRect();
        return [...toolbar.querySelectorAll(
          ".map-tools > button, .map-tools > details:not([open]) > summary",
        )].filter((control) => {
          const bounds = control.getBoundingClientRect();
          return bounds.width && bounds.height
            && Math.min(bounds.right, legend.right) > Math.max(bounds.left, legend.left)
            && Math.min(bounds.bottom, legend.bottom) > Math.max(bounds.top, legend.top);
        }).map((control) => control.textContent.trim());
      });
      expect(covered, `${theme} at ${width}px`).toEqual([]);
      expect(await page.evaluate(() => document.documentElement.scrollWidth))
        .toBeLessThanOrEqual(width);
    }
  });
}

for (const theme of ["showcase", "showcase-light"]) {
  test(`a saved ${theme} appearance returns to Current without an introduction`, async ({ page }) => {
    await page.addInitScript((selectedTheme) => {
      localStorage.setItem("cosolve-display-mode", selectedTheme);
    }, theme);
    await page.goto("/map/");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "classic");
    await expect(page.locator(".result-row").first()).toBeVisible();
    await expect(page.locator("[data-showcase-cover]")).toHaveCount(0);
    await expect(page.locator(".site-header")).toHaveJSProperty("inert", false);
    await expect(page.locator("#main-content")).toHaveJSProperty("inert", false);

    await expect.poll(() => page.evaluate(() =>
      localStorage.getItem("cosolve-display-mode"),
    )).toBe("classic");
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "classic");
  });
}
