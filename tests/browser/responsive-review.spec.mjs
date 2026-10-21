import { expect, test } from "@playwright/test";

test("directory titles have room at tablet widths", async ({ page }) => {
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

test("expanded legend does not cover toolbar controls", async ({ page }) => {

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
    expect(covered, `at ${width}px`).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth))
      .toBeLessThanOrEqual(width);
  }
});
