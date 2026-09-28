import { expect, test } from "@playwright/test";

for (const theme of ["classic", "dark", "showcase", "showcase-light"]) {
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
  test(`the ${theme} introduction contains keyboard focus and restores the map`, async ({ page }) => {
    await page.addInitScript((selectedTheme) => {
      localStorage.setItem("cosolve-display-mode", selectedTheme);
    }, theme);
    await page.goto("/map/");
    const cover = page.locator("[data-showcase-cover]");
    const enter = cover.locator("[data-showcase-enter]").first();
    const credits = cover.locator(".showcase-credits > summary");
    await expect(cover).toBeVisible();
    await expect(enter).toBeFocused();
    await expect(page.locator(".site-header")).toHaveJSProperty("inert", true);
    await expect(page.locator("#main-content")).toHaveJSProperty("inert", true);

    await page.keyboard.press("Shift+Tab");
    await expect(credits).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(enter).toBeFocused();

    await credits.focus();
    await page.keyboard.press("Space");
    const lastCredit = cover.locator(".showcase-credits a").last();
    await expect(lastCredit).toBeVisible();
    await lastCredit.focus();
    await page.keyboard.press("Tab");
    await expect(enter).toBeFocused();

    await page.keyboard.press("Escape");
    await expect(cover).toBeHidden();
    await expect(page.locator(".appearance-menu > summary")).toBeFocused();
    await expect(page.locator(".site-header")).toHaveJSProperty("inert", false);
    await expect(page.locator("#main-content")).toHaveJSProperty("inert", false);

    await page.locator(".appearance-menu > summary").click();
    await page.locator(`[data-theme-choice="${theme}"]`).click();
    await expect(enter).toBeFocused();
    await enter.click();
    await expect(cover).toBeHidden();
    await expect(page.locator("#main-content")).toBeFocused();
    await expect(page.locator(".site-header")).toHaveJSProperty("inert", false);
  });
}
