import { expect, test } from "@playwright/test";

test("map layers toggle without moving the reset control", async ({ page }) => {
  await page.goto("/map/");
  await expect(page.locator(".result-row").first()).toBeVisible();

  const reset = page.locator("#reset-view");
  const initialTop = (await reset.boundingBox()).y;
  await page.locator(".map-legend summary").click();
  expect((await reset.boundingBox()).y).toBe(initialTop);
  await page.locator(".map-legend summary").click();
  await page.locator(".map-layers summary").click();

  const stateToggle = page.locator("#state-boundary-toggle");
  await expect(page.locator(".leaflet-state-boundary-pane path")).not.toHaveCount(0);
  await stateToggle.uncheck();
  await expect(page.locator(".leaflet-state-boundary-pane path")).toHaveCount(0);
  await stateToggle.check();
  await expect(page.locator(".leaflet-state-boundary-pane path")).not.toHaveCount(0);

  await page.locator("#county-layer-toggle").check();
  await expect(page.locator(".leaflet-county-boundaries-pane path")).not.toHaveCount(0);
});

test("empty filters preserve the complete map result set", async ({ page }) => {
  await page.goto("/map/");
  const count = page.locator("#result-count");
  const initialCount = await count.textContent();
  expect(Number(initialCount)).toBeGreaterThan(0);
  if (await page.locator(".filter-open").isVisible()) {
    await page.locator(".filter-open").click();
  }
  await page.locator("#asset-filters button[type=submit]").click();
  await expect(count).toHaveText(initialCount);
});

test("directory remains within the viewport", async ({ page }) => {
  await page.goto("/directory/");
  await expect(page.locator(".directory-row").first()).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true);
});
