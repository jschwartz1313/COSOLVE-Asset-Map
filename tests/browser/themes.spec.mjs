import { expect, test } from "@playwright/test";
import { publicAssetCount } from "./helpers.mjs";

async function selectTheme(page, theme) {
  await page.locator(".appearance-menu > summary").click();
  await page.locator(`[data-theme-choice="${theme}"]`).click();
}

async function expectContiguousMapPanels(page) {
  if (page.viewportSize().width <= 650) {
    await expect(page.locator('[data-panel-resizer="left"]')).toBeHidden();
    await expect(page.locator('[data-panel-resizer="right"]')).toBeHidden();
    return;
  }
  const bounds = await page.locator(".map-workspace").evaluate((workspace) => {
    const selectors = [".filters-panel", '[data-panel-resizer="left"]', ".map-stage",
      '[data-panel-resizer="right"]', ".results-panel"];
    return selectors.map((selector) => {
      const { left, right } = workspace.querySelector(selector).getBoundingClientRect();
      return { left, right };
    });
  });
  for (let index = 1; index < bounds.length; index += 1) {
    expect(bounds[index].left).toBeCloseTo(bounds[index - 1].right, 0);
  }
}

test("Current and Dark preserve map data, layout and saved appearance", async ({ page }, testInfo) => {
  const total = await publicAssetCount(page);
  const showcaseRequests = [];
  page.on("request", (request) => {
    if (request.url().includes("/img/themes/")) showcaseRequests.push(request.url());
  });
  await page.goto("/map/");
  await expect(page.locator(".result-row").first()).toBeVisible();
  const originalWorkspace = await page.locator(".map-workspace").boundingBox();
  const originalFilters = await page.locator(".filters-panel").boundingBox();
  for (const theme of ["dark", "classic"]) {
    await selectTheme(page, theme);
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    await expect(page.locator(`[data-theme-choice="${theme}"]`))
      .toHaveAttribute("aria-pressed", "true");
    await expect(page.locator("#result-count")).toHaveText(String(total));
    await expectContiguousMapPanels(page);
    expect(await page.locator(".map-workspace").boundingBox()).toEqual(originalWorkspace);
    expect(await page.locator(".filters-panel").boundingBox()).toEqual(originalFilters);
    await expect(page.locator("[data-showcase-cover]")).toHaveCount(0);
    await expect.poll(() => page.locator(".result-row").evaluateAll((rows) =>
      [...new Set(rows.slice(0, 6).map((row) => getComputedStyle(row).borderLeftWidth))],
    )).toEqual(["0px"]);
    await page.screenshot({path: testInfo.outputPath(`map-${theme}.png`), animations: "disabled"});
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
  }
  expect(showcaseRequests).toEqual([]);
});

test("the compact appearance menu offers only Current and Dark", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/map/");
  const switcher = page.locator(".appearance-switcher");
  await expect(switcher).toBeHidden();
  expect((await page.locator(".site-header").boundingBox()).height).toBeLessThanOrEqual(100);
  await page.locator(".appearance-menu > summary").click();
  await expect(switcher).toBeVisible();
  await expect(switcher.locator("button")).toHaveText(["Current", "Dark"]);
  const box = await switcher.boundingBox();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(390);
  expect(box.y + box.height).toBeLessThanOrEqual(844);
  await page.screenshot({path: testInfo.outputPath("appearance-menu.png"), animations: "disabled"});
  await page.locator('[data-theme-choice="dark"]').click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(switcher).toBeHidden();
});

test("keyboard selection cycles only through active appearances", async ({ page }) => {
  await page.goto("/map/");
  await page.locator(".appearance-menu > summary").click();
  const classic = page.locator('[data-theme-choice="classic"]');
  const dark = page.locator('[data-theme-choice="dark"]');
  await classic.focus();
  await page.keyboard.press("ArrowRight");
  await expect(dark).toBeFocused();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.keyboard.press("ArrowRight");
  await expect(classic).toBeFocused();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "classic");
  await page.keyboard.press("End");
  await expect(dark).toBeFocused();
  await page.keyboard.press("Home");
  await expect(classic).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.locator(".appearance-menu > summary")).toBeFocused();
});

test("Dark persists between the directory and asset profiles", async ({ page }) => {
  await page.goto("/directory/?q=reactor");
  await selectTheme(page, "dark");
  await page.locator(".directory-row-main h3 a").first().click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.locator("[data-showcase-cover]")).toHaveCount(0);
  await expect(page.locator("[data-theme-choice]")).toHaveCount(2);
});
