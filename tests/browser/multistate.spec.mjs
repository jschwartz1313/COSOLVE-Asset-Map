import { expect, test } from "@playwright/test";

test.skip(!process.env.COSOLVE_MULTISTATE_QA_USERNAME || !process.env.COSOLVE_MULTISTATE_QA_PASSWORD,
  "State previews need a dedicated staff QA account in an isolated database.");

async function fits(page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth))
    .toBeLessThanOrEqual(page.viewportSize().width);
  const overflow = await page.locator(".site-header select, main h1, main h2, main p, main button")
    .evaluateAll(elements => elements.filter(element => element.getClientRects().length
      && !element.closest(".visually-hidden")
      && getComputedStyle(element).textOverflow !== "ellipsis"
      && element.scrollWidth > element.clientWidth + 1).map(element => element.textContent));
  expect(overflow).toEqual([]);
}

test.beforeEach(async ({ page }) => {
  await page.goto("/login/");
  await page.locator('input[name="login"]').fill(process.env.COSOLVE_MULTISTATE_QA_USERNAME);
  await page.locator('input[name="password"]').fill(process.env.COSOLVE_MULTISTATE_QA_PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.locator("[data-state-switcher]")).toBeVisible();
});

test("switch states, search the map, inspect layers and keep directory scope", async ({ page }, info) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.getByLabel("State inventory").selectOption("ohio");
  await expect(page).toHaveURL(/\/states\/ohio\/map\//);
  const response = await page.request.get("/states/ohio/api/assets.geojson");
  const data = await response.json();
  expect(data.features.length).toBeGreaterThan(0);
  expect(data.features.every(feature => feature.properties.location.state === "OH")).toBe(true);
  await expect(page.locator("#result-count")).toHaveText(String(data.result_count));
  await expect(page.locator(".leaflet-tile-loaded").first()).toBeVisible();
  await expect(page.locator(".map-legend")).toHaveAttribute("open", "");
  await page.locator('.map-layers > summary').click();
  await expect(page.getByLabel("County boundaries", { exact: true })).toBeVisible();
  await page.getByLabel("County boundaries", { exact: true }).check();
  await expect(page.locator("#county-layer-toggle")).toBeChecked();
  await expect(page.getByLabel("MAAP flight-area outlines", { exact: false })).toBeHidden();
  await page.locator('.map-layers > summary').click();
  const radio = page.locator('input[name="map-basemap"][value="topo"]');
  await radio.check();
  await expect(page.locator("[data-map-app]")).toHaveAttribute("data-basemap", "topo");
  await expect(page.locator(".leaflet-tile-loaded").first()).toBeVisible();
  if (await page.locator(".filter-open").isVisible()) await page.locator(".filter-open").click();
  await page.locator('#asset-filters input[name="q"]').fill(data.features[0].properties.name);
  await page.locator('#asset-filters button[type="submit"]').click();
  await expect(page.locator("#map-status")).toBeHidden();
  await expect(page.locator("#result-list")).toContainText(data.features[0].properties.name);
  await fits(page);
  await page.screenshot({ path: info.outputPath("state-map.png"), fullPage: true });
  await page.getByRole("link", { name: "Directory", exact: true }).click();
  await expect(page).toHaveURL(/\/states\/ohio\/directory\//);
  await expect(page.locator(".directory-results")).toContainText(data.features[0].properties.name);
  await fits(page);
  expect(errors).toEqual([]);
});

test("comparison, profile links, export and saved views retain the chosen state", async ({ page }, info) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/states/ohio/directory/");
  const controls = page.locator("[data-compare-asset]");
  await controls.nth(0).check();
  await controls.nth(1).check();
  await expect(page.locator("[data-comparison-assets] li")).toHaveCount(2);
  await page.getByRole("link", { name: "Compare selected assets", exact: true }).click();
  await expect(page).toHaveURL(/\/states\/ohio\/compare\//);
  await expect(page.locator(".asset-comparison")).toBeVisible();
  await page.getByRole("button", { name: "Add assets", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Add assets", exact: true });
  await expect(dialog.getByRole("checkbox").first()).toBeVisible();
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await fits(page);
  await page.screenshot({ path: info.outputPath("state-comparison.png"), fullPage: true });
  const csv = await page.request.get("/states/ohio/admin/imports/export/");
  expect(csv.status()).toBe(200);
  expect(await csv.text()).not.toContain("Allocortech");
  await page.goto("/states/ohio/directory/");
  await page.locator(".directory-row h3 a").first().click();
  await expect(page).toHaveURL(/\/states\/ohio\/assets\//);
  await fits(page);
  await page.goto("/states/ohio/saved-views/?view_type=map&query=q%3Dautonomy");
  await page.getByLabel("Name", { exact: true }).fill(`Ohio UI view ${info.project.name} ${Date.now()}`);
  await page.getByRole("button", { name: "Save view", exact: true }).click();
  await page.locator(".saved-view-row").first().getByRole("link", { name: "Open map", exact: true }).click();
  await expect(page).toHaveURL(/\/states\/ohio\/map\/\?q=autonomy/);
  await page.getByLabel("State inventory").selectOption("virginia");
  await expect(page).toHaveURL(/\/map\/$/);
  await page.goto("/directory/");
  await expect(page.locator("[data-comparison-count]")).toHaveText("0 selected");
  expect(errors).toEqual([]);
});

test("every benchmark state renders its own real starter inventory", async ({ page }, info) => {
  test.skip(process.env.COSOLVE_QA_ALL_STATES !== "1", "Requires the complete researched starter catalog.");
  test.setTimeout(180000);
  const states = [
    ["arizona", "AZ"], ["california", "CA"], ["colorado", "CO"], ["florida", "FL"],
    ["michigan", "MI"], ["new-york", "NY"], ["north-carolina", "NC"],
    ["north-dakota", "ND"], ["ohio", "OH"], ["oklahoma", "OK"],
    ["pennsylvania", "PA"], ["texas", "TX"], ["utah", "UT"],
  ];
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  for (const [slug, code] of states) {
    const prefix = `/states/${slug}`;
    const response = await page.request.get(prefix + "/api/assets.geojson");
    expect(response.ok()).toBe(true);
    const data = await response.json();
    expect(data.result_count).toBeGreaterThanOrEqual(50);
    expect(data.features.every(feature => feature.properties.location.state === code)).toBe(true);
    await page.goto(prefix + "/directory/");
    await expect(page.getByLabel("State inventory")).toHaveValue(slug);
    await expect(page.locator("[data-compare-asset]").first()).toBeEnabled();
    expect(await page.locator(".directory-row h3 a").first().getAttribute("href"))
      .toMatch(new RegExp(`^${prefix}/assets/`));
    await fits(page);
    await page.goto(prefix + "/map/");
    await expect(page.locator("#result-count")).toHaveText(String(data.result_count));
    await expect(page.locator("#map-status")).toBeHidden();
    await expect(page.locator(".leaflet-marker-icon").first()).toBeVisible();
    await expect(page.locator(".leaflet-tile-loaded").first()).toBeVisible();
    await fits(page);
    await page.screenshot({ path: info.outputPath(`${slug}-map.png`), fullPage: true });
  }
  expect(errors).toEqual([]);
});
