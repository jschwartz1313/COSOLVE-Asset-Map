import { expect, test } from "@playwright/test";

test("directory navigation does not turn paging or sorting into map filters", async ({ page }) => {
  await page.goto("/directory/?q=airport&sort=type&page=2");
  await page.getByRole("link", { name: "View on map", exact: true }).click();
  await expect(page.locator(".result-row").first()).toBeVisible();
  await expect(page.locator(".active-filter-chip")).toHaveCount(1);
  await expect(page.locator("[data-active-filter-bar]")).toContainText("Search: airport");
});

test("failed searches clear stale pins and prevent analysis until recovery", async ({ page }, testInfo) => {
  await page.goto("/map/?q=Adaptive%20Aerospace%20Group");
  await expect(page.locator(".result-row").first()).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("single-result.png") });
  await expect(page.locator(".asset-marker")).toHaveCount(1);
  await expect(page.locator("#asset-results-title")).toHaveText("1 asset");
  await expect(page.locator(".active-filter-summary")).toHaveText("1 active filter");
  let release;
  const pending = new Promise((resolve) => { release = resolve; });
  await page.route("**/api/assets.geojson?*", async (route) => {
    if (!new URL(route.request().url()).searchParams.has("region")) return route.continue();
    await pending;
    await route.fulfill({ status: 503, body: "Unavailable" });
  });
  if (await page.locator(".filter-open").isVisible()) await page.locator(".filter-open").click();
  await page.locator('select[name="region"]').selectOption("hampton-roads");
  await page.locator("#asset-filters button[type=submit]").click();
  await expect(page.locator("[data-map-app]")).toHaveAttribute("aria-busy", "true");
  await expect(page.locator("#print-view")).toBeDisabled();
  await expect(page.locator("#nearby-search")).toBeDisabled();
  release();
  await expect(page.locator("#map-status")).toContainText("could not be loaded");
  await expect(page.locator("#result-list .empty-state")).toContainText("temporarily unavailable");
  await expect(page.locator(".asset-marker, .marker-cluster")).toHaveCount(0);
  await expect(page.locator("#result-count")).toHaveText("0");
  await expect(page.locator("#directory-link")).toHaveAttribute("href", /region=hampton-roads/);
  await expect(page.locator("#select-polygon")).toBeDisabled();
  await page.unroute("**/api/assets.geojson?*");
  await page.locator("#asset-filters button[type=submit]").click();
  await expect(page.locator(".asset-marker")).toHaveCount(1);
  await expect(page.locator("#print-view")).toBeEnabled();
  await expect(page.locator("#nearby-search")).toBeEnabled();
});

test("shared nearby view preserves the circle and selected results", async ({ context, page }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/map/?region=hampton-roads");
  await expect(page.locator(".result-row").first()).toBeVisible();
  await page.locator(".map-analysis > summary").click();
  await page.locator("#nearby-radius").selectOption("25");
  await page.locator("#nearby-search").click();
  await expect(page.locator("#analysis-status")).toContainText("within 25 miles");
  const count = await page.locator("#result-count").textContent();
  expect(Number(count)).toBeGreaterThan(0);
  await page.locator(".map-actions > summary").click();
  await page.locator("#copy-view-link").click();
  const url = await page.evaluate(() => navigator.clipboard.readText());
  expect(new URL(url).searchParams.get("map_analysis")).toMatch(/^radius\|/);
  await page.goto(url);
  await expect(page.locator("#analysis-status")).toContainText("within 25 miles");
  await expect(page.locator("#result-count")).toHaveText(count);
  await expect(page.locator(".leaflet-analysis-selection-pane path")).toHaveCount(1);
});

test("airspace popups use the published base when the facility label is blank", async ({ page }) => {
  await page.route("**/virginia-flight-constraints.geojson?*", (route) => route.fulfill({
    contentType: "application/json",
    json: { type: "FeatureCollection", features: [{ type: "Feature", properties: {
      name: " ", base: "Published base name", category: "National-security UAS flight restriction",
      constraint_type: "national-security-uas", type_code: "UAS NSFR", floor: "Surface",
    }, geometry: { type: "Polygon", coordinates: [[[-77.1, 36.9], [-76.9, 36.9],
      [-76.9, 37.1], [-77.1, 37.1], [-77.1, 36.9]]] } }] },
  }));
  await page.goto("/map/?map_lat=37&map_lon=-77&map_zoom=8");
  await expect(page.locator(".result-row").first()).toBeVisible();
  await page.locator(".map-layers > summary").click();
  await page.locator("#flight-constraints-toggle").check();
  await expect(page.locator("#flight-constraints-toggle")).toBeEnabled();
  await page.locator("#asset-layer-toggle").uncheck();
  await page.locator(".map-layers > summary").click();
  await page.locator(".leaflet-flight-constraints-pane path").click({ force: true });
  await expect(page.locator(".drone-reference-popup h3")).toHaveText("Published base name");
});
