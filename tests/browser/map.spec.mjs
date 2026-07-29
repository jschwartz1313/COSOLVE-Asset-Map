import { expect, test } from "@playwright/test";

test("map layers toggle without moving the reset control", async ({ page }) => {
  await page.goto("/map/");
  await expect(page.locator(".result-row").first()).toBeVisible();

  const reset = page.locator("#reset-view");
  const initialTop = (await reset.boundingBox()).y;
  await page.locator(".map-legend summary").click();
  expect((await reset.boundingBox()).y).toBe(initialTop);
  await expect(page.locator(".legend-line.county-boundary")).toBeVisible();
  await expect(page.locator(".legend-content")).toContainText("County boundary");
  await page.locator(".map-legend summary").click();
  await page.locator(".map-layers summary").click();

  const stateToggle = page.locator("#state-boundary-toggle");
  await expect(page.locator(".leaflet-state-boundary-pane path")).not.toHaveCount(0);
  await stateToggle.uncheck();
  await expect(page.locator(".leaflet-state-boundary-pane path")).toHaveCount(0);
  await stateToggle.check();
  await expect(page.locator(".leaflet-state-boundary-pane path")).not.toHaveCount(0);

  const regionToggle = page.locator("#region-layer-toggle");
  await expect(page.locator(".leaflet-ecosystem-regions-pane path")).toHaveCount(12);
  await expect(page.locator(".region-map-label")).toHaveCount(12);
  await regionToggle.uncheck();
  await expect(page.locator(".leaflet-ecosystem-regions-pane path")).toHaveCount(0);
  await regionToggle.check();
  await expect(page.locator(".leaflet-ecosystem-regions-pane path")).toHaveCount(12);

  const mpzToggle = page.locator("#mpz-layer-toggle");
  await expect(mpzToggle).not.toBeChecked();
  await mpzToggle.check();
  await expect(page.locator(".leaflet-maritime-prosperity-zones-pane path")).toHaveCount(11);
  await page
    .locator(".leaflet-maritime-prosperity-zones-pane path")
    .first()
    .dispatchEvent("click");
  await expect(page.locator(".mpz-popup")).toContainText(
    "Planning candidate only; not federally designated",
  );
  await expect(page.locator(".mpz-popup-sources a").first()).toHaveAttribute("href", /^https:/);

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

test("strategic categories use the same collapsible filter control", async ({ page }) => {
  await page.goto("/map/");
  if (await page.locator(".filter-open").isVisible()) {
    await page.locator(".filter-open").click();
  }

  const categoryFilter = page.locator("#asset-filters .category-filter");
  await expect(categoryFilter).not.toHaveAttribute("open", "");
  await categoryFilter.locator("summary").click();
  await categoryFilter.locator('input[name="category"]').first().check();
  await expect(categoryFilter).toHaveAttribute("open", "");
  await expect(categoryFilter.locator('[data-filter-count-for="category"]')).toHaveText("1");

  await page.goto("/directory/");
  await expect(page.locator(".directory-filters .category-filter")).not.toHaveAttribute("open", "");
});

test("text search labels matching map points by name", async ({ page }) => {
  await page.goto("/map/");
  if (await page.locator(".filter-open").isVisible()) {
    await page.locator(".filter-open").click();
  }

  await page.locator('input[name="q"]').fill("Adaptive Aerospace Group");
  await page.locator("#asset-filters button[type=submit]").click();
  const marker = page.locator(".asset-marker");
  const label = page.locator(".asset-search-label");
  await expect(page.locator("#result-count")).toHaveText("1");
  await expect(marker).toHaveCount(1);
  await expect(label).toHaveText("Adaptive Aerospace Group");

  await expect
    .poll(async () => {
      const markerBox = await marker.boundingBox();
      const labelBox = await label.boundingBox();
      return labelBox.y + labelBox.height <= markerBox.y + 2;
    })
    .toBe(true);

  if (await page.locator(".filter-open").isVisible()) {
    await page.locator(".filter-open").click();
  }
  await page.locator("#asset-filters button[type=reset]").click();
  await expect(page.locator(".asset-search-label")).toHaveCount(0);
});

test("region selector applies across map and directory without a special coverage control", async ({
  page,
}) => {
  await page.goto("/map/");
  const statewideCount = Number(await page.locator("#result-count").textContent());
  if (await page.locator(".filter-open").isVisible()) {
    await page.locator(".filter-open").click();
  }
  await expect(page.locator('[data-region-quick-filter="hampton-roads"]')).toHaveCount(0);
  await page.locator('select[name="region"]').selectOption("hampton-roads");
  await page.locator("#asset-filters button[type=submit]").click();
  await expect(page).toHaveURL(/region=hampton-roads/);

  const regionalCount = Number(await page.locator("#result-count").textContent());
  expect(regionalCount).toBeGreaterThan(0);
  expect(regionalCount).toBeLessThan(statewideCount);
  await expect(page.locator('select[name="region"]')).toHaveValue("hampton-roads");

  await page.locator("#directory-link").click();
  await expect(page).toHaveURL(/\/directory\/\?region=hampton-roads/);
  await expect(page.locator('[data-region-quick-filter="hampton-roads"]')).toHaveCount(0);
  await expect(page.locator('select[name="region"]')).toHaveValue("hampton-roads");
  await expect(page.locator(".directory-heading h2")).toContainText(`${regionalCount} matching`);
});

test("Hampton Roads records expose site-level location quality", async ({ page }) => {
  await page.goto("/map/?region=hampton-roads");
  const adaptive = page.locator(".result-row").filter({ hasText: "Adaptive Aerospace Group" });
  await expect(adaptive.locator(".row-footer")).toContainText("Site or campus");
  await adaptive.click();
  await expect(page.locator(".leaflet-popup-content")).toContainText(
    "22 Enterprise Parkway, Suite 320",
  );

  const response = await page.request.get("/api/assets.geojson?region=hampton-roads");
  const body = await response.json();
  const regionalChapter = body.features.find(
    (feature) => feature.properties.name === "AUVSI Hampton Roads Chapter",
  );
  expect(regionalChapter.geometry).toBeNull();
  expect(regionalChapter.properties.location.precision_label).toBe("Regional; no single site");
});

test("large map results render in responsive batches", async ({ page }) => {
  await page.goto("/map/");
  await expect(page.locator("#result-count")).toHaveText("232");
  await expect(page.locator(".result-row")).toHaveCount(50);
  await expect(page.getByRole("button", { name: "Show 50 more" })).toBeVisible();
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

test("relationship network renders inside a stable canvas", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/relationships/");
  await expect(page.locator(".network-node").first()).toBeVisible();
  expect(await page.locator(".network-node").count()).toBeGreaterThan(1);
  expect(
    await page.locator(".network-canvas").evaluate((element) => element.clientHeight),
  ).toBeLessThanOrEqual(650);
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true);
  expect(errors).toEqual([]);
});

test("account recovery is available from the sign-in page", async ({ page }) => {
  await page.goto("/login/");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.getByRole("link", { name: "Forgot your password?" }).click();
  await expect(page.getByRole("heading", { name: "Reset your password" })).toBeVisible();
  await expect(page.getByLabel("Email address")).toBeVisible();
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
