import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

const catalog = JSON.parse(
  readFileSync(new URL("../../data/virginia_real_assets.json", import.meta.url), "utf8"),
);

test("four presentation modes preserve the same map data and controls", async ({ page }) => {
  await page.goto("/map/");
  await expect(page.locator("#result-count")).toHaveText(String(catalog.record_count));

  const originalWorkspace = await page.locator(".map-workspace").boundingBox();
  const originalFilters = await page.locator(".filters-panel").boundingBox();

  await page.locator('[data-theme-choice="dark"]').click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.locator('[data-theme-choice="dark"]')).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.locator("#result-count")).toHaveText(String(catalog.record_count));
  expect(await page.locator(".map-workspace").boundingBox()).toEqual(originalWorkspace);
  expect(await page.locator(".filters-panel").boundingBox()).toEqual(originalFilters);

  await page.locator('[data-theme-choice="color"]').click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "color");
  await expect(page.locator("#result-count")).toHaveText(String(catalog.record_count));
  await expect(page.locator(".theme-page-visual")).toBeHidden();

  await page.locator('[data-theme-choice="showcase"]').click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "showcase");
  await expect(page.locator("[data-showcase-cover]")).toBeVisible();
  await page.locator("[data-showcase-enter]").click();
  await expect(page.locator("[data-showcase-cover]")).toBeHidden();
  await expect(page.locator("#result-count")).toHaveText(String(catalog.record_count));

  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "showcase");
  await expect(page.locator("[data-showcase-cover]")).toBeHidden();

  await page.locator('[data-theme-choice="classic"]').click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "classic");
});

test("color and showcase imagery appears on supporting pages", async ({ page }) => {
  await page.goto("/directory/");
  await page.locator('[data-theme-choice="color"]').click();
  await expect(page.locator(".theme-page-visual")).toBeVisible();
  await expect(page.locator(".directory-list")).toBeVisible();

  await page.locator('[data-theme-choice="showcase"]').click();
  await expect(page.locator("[data-showcase-cover]")).toBeVisible();
  await page.locator("[data-showcase-enter]").click();
  await expect(page).toHaveURL(/\/map\/$/);
  await expect(page.locator("#result-count")).toHaveText(String(catalog.record_count));
});

test("the four-mode switch remains usable on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/map/");
  const switcher = page.locator(".appearance-switcher");
  await expect(switcher).toBeVisible();
  await expect(switcher.locator("button")).toHaveCount(4);

  const switchBox = await switcher.boundingBox();
  expect(switchBox.x).toBeGreaterThanOrEqual(0);
  expect(switchBox.x + switchBox.width).toBeLessThanOrEqual(390);
  expect(switchBox.y + switchBox.height).toBeLessThanOrEqual(844);

  await page.locator('[data-theme-choice="showcase"]').click();
  await expect(page.locator("[data-showcase-cover]")).toBeVisible();
  const coverBox = await page.locator("[data-showcase-cover]").boundingBox();
  expect(coverBox.width).toBe(390);
  expect(coverBox.height).toBeGreaterThanOrEqual(844);
});
