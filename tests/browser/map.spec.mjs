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
  if (page.viewportSize().width <= 650) {
    expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeLessThan(1800);
    expect(
      await page.locator("#result-list").evaluate((element) => getComputedStyle(element).overflowY),
    ).toBe("auto");
  }
});

test("directory remains within the viewport", async ({ page }) => {
  await page.goto("/directory/");
  await expect(page.locator(".directory-row").first()).toBeVisible();
  await expect(page.locator(".directory-filters .category-filter")).not.toHaveAttribute("open", "");
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true);
});

test("asset detail pages stay compact and within the viewport", async ({ page }) => {
  await page.goto("/assets/ata-aviation/");
  await expect(page.getByRole("heading", { name: "ATA Aviation" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Documented relevance" })).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true);
  expect(await page.locator(".detail-main section").first().evaluate((element) => element.getBoundingClientRect().height)).toBeLessThan(140);
});

test("about page reports review status without an empty date range", async ({ page }) => {
  await page.goto("/about-data/");
  await expect(page.getByText("Editorial review", { exact: true })).toBeVisible();
  await expect(page.getByText("Verification range", { exact: true })).toHaveCount(0);
});

test("update workflow and institutional footer remain within the viewport", async ({ page }) => {
  await page.goto("/suggest-update/");
  await expect(page.getByRole("heading", { name: "Suggest an update" })).toBeVisible();
  await expect(page.getByLabel("Request type")).toBeVisible();
  await expect(page.getByRole("contentinfo")).toContainText("Catalog updated");
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true);
});

test("mobile filter drawer exposes an accessible open and close state", async ({ page }) => {
  test.skip(page.viewportSize().width > 880, "Compact drawer behavior only applies below 880px.");
  await page.goto("/map/");
  const openButton = page.getByRole("button", { name: "Open filters" });
  const panel = page.locator("#asset-filters-panel");
  await expect(openButton).toHaveAttribute("aria-expanded", "false");
  await expect(panel).toHaveAttribute("aria-hidden", "true");
  await expect(panel).toHaveAttribute("inert", "");
  await openButton.click();
  await expect(openButton).toHaveAttribute("aria-expanded", "true");
  await expect(panel).toHaveAttribute("aria-hidden", "false");
  await expect(panel).not.toHaveAttribute("inert", "");
  await page.keyboard.press("Escape");
  await expect(openButton).toHaveAttribute("aria-expanded", "false");
  await expect(openButton).toBeFocused();
});
