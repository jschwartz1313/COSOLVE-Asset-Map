import { expect, test } from "@playwright/test";

test.skip(!process.env.COSOLVE_MULTISTATE_QA_USERNAME || !process.env.COSOLVE_MULTISTATE_QA_PASSWORD,
  "Needs isolated staff QA accounts.");

async function login(page, username) {
  await page.context().clearCookies();
  await page.goto("/login/");
  await page.locator('input[name="login"]').fill(username);
  await page.locator('input[name="password"]').fill(process.env.COSOLVE_MULTISTATE_QA_PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}

async function openFilters(page) {
  if (await page.locator(".filter-open").isVisible()) await page.locator(".filter-open").click();
}

test("approved selector sits above filters and starts new states on Street", async ({ page }, info) => {
  await login(page, process.env.COSOLVE_MULTISTATE_QA_USERNAME);
  await openFilters(page);
  const picker = page.getByLabel("State inventory");
  await expect(page.locator(".site-header [data-state-switcher]")).toHaveCount(0);
  await expect(page.locator(".filters-panel > [data-state-switcher]")).toBeVisible();
  const before = await picker.boundingBox();
  const search = await page.locator('#asset-filters input[name="q"]').boundingBox();
  expect(before.y + before.height).toBeLessThan(search.y);
  await picker.selectOption("ohio");
  await expect(page).toHaveURL(/\/states\/ohio\/map\//);
  await expect(page.locator('input[name="map-basemap"][value="street"]')).toBeChecked();
  await expect(page.locator("[data-map-app]")).toHaveAttribute("data-basemap", "street");
  await openFilters(page);
  await expect(page.getByLabel("State inventory")).toHaveValue("ohio");
  await expect(page.locator(".state-switcher")).toContainText("Internal preview");
  await page.screenshot({ path: info.outputPath("state-picker-map.png"), animations: "disabled" });
  await page.goto("/states/ohio/directory/");
  await expect(page.locator(".directory-filters > [data-state-switcher]")).toBeVisible();
  await expect(page.locator("#directory-filters .filter-select.is-enhanced")).not.toHaveCount(0);
  await expect(page.locator(".site-header [data-state-switcher]")).toHaveCount(0);
  await page.getByLabel("State inventory").selectOption("california");
  await expect(page).toHaveURL(/\/states\/california\/directory\//);
  await expect(page.locator('.directory-row').first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("state-picker-directory.png"), animations: "disabled" });
  await page.goto("/states/ohio/map/?map_basemap=topo");
  await expect(page.locator('input[name="map-basemap"][value="topo"]')).toBeChecked();
});

test("other staff and guests have no state switcher and cannot open peer links", async ({ page }, info) => {
  for (const username of ["ui-denied", "ui-guest"]) {
    await login(page, username);
    await page.goto("/map/");
    await expect(page.locator("[data-state-switcher]")).toHaveCount(0);
    const data = await (await page.request.get("/api/assets.geojson")).json();
    expect(data.features.every(feature => feature.properties.location.state === "VA")).toBe(true);
    for (const path of ["map/", "directory/", "api/assets.geojson", "compare/options/", "admin/imports/export/"]) {
      const response = await page.request.get("/states/ohio/" + path);
      expect(response.status()).toBe(404);
      expect(response.headers()["cache-control"]).toBe("private, no-store");
    }
    await page.goto("/directory/");
    await expect(page.locator("[data-state-switcher]")).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`${username}-virginia-only.png`), animations: "disabled" });
  }
});

test("state selection remains available from More on profiles without a filter column", async ({ page }) => {
  await login(page, process.env.COSOLVE_MULTISTATE_QA_USERNAME);
  await page.goto("/states/ohio/directory/");
  await page.locator(".directory-row h3 a").first().click();
  await page.locator(".navigation-menu > summary").click();
  await expect(page.locator(".header-menu-panel [data-state-switcher]")).toBeVisible();
  await page.getByLabel("State inventory").selectOption("virginia");
  await expect(page).toHaveURL(/\/map\/$/);
});
