import { THEMES } from "../../static/js/theme-switcher.js";
import { expect, test } from "@playwright/test";

test("map headings stay concise and the legend follows visible overlays", async ({ page }) => {
  await page.goto("/map/");
  await expect(page.locator(".result-row").first()).toBeVisible();
  await expect(page.locator(".panel-heading .eyebrow, #asset-results-view .eyebrow")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Directory", exact: true })).toHaveCount(1);
  await expect(page.locator("#asset-results-view #directory-link")).toHaveCount(0);

  await page.locator(".map-legend summary").click();
  await expect(page.locator("[data-legend-toggle]:visible")).toHaveCount(7);
  await expect(page.locator('[data-legend-toggle="state-boundary-toggle"]')).toBeVisible();
  await page.locator(".map-layers summary").click();
  for (const id of ["county-layer-toggle", "region-layer-toggle", "mpz-layer-toggle", "heliport-layer-toggle"]) {
    const toggle = page.locator(`#${id}`);
    const entry = page.locator(`[data-legend-toggle="${id}"]`);
    await expect(entry).toBeHidden();
    await toggle.check();
    await expect(toggle).toBeEnabled();
    await expect(entry).toBeVisible();
    await toggle.uncheck();
    await expect(entry).toBeHidden();
  }

  await page.locator("#verification-layer-toggle").check();
  await page.locator("#precision-layer-toggle").check();
  await expect(page.locator("[data-verification-legend]")).toBeVisible();
  await expect(page.locator("[data-precision-legend]")).toBeVisible();
  await page.locator("#asset-layer-toggle").uncheck();
  await expect(page.locator(".legend-dot.university")).toBeHidden();
  await expect(page.locator("[data-verification-legend]")).toBeHidden();
  await expect(page.locator("[data-precision-legend]")).toBeHidden();
  await page.locator("#state-boundary-toggle").uncheck();
  await expect(page.locator("[data-legend-toggle]:visible")).toHaveCount(0);
  await expect(page.locator("[data-legend-empty]")).toBeVisible();
  await page.locator("#asset-layer-toggle").check();
  await expect(page.locator("[data-verification-legend]")).toBeVisible();
  await expect(page.locator("[data-legend-empty]")).toBeHidden();
});

const referenceLayers = [
  ["county-layer-toggle", "virginia-counties", "county-boundaries", "County boundaries"],
  ["region-layer-toggle", "virginia-regions", "ecosystem-regions", "Ecosystem region shading"],
  ["mpz-layer-toggle", "virginia-maritime-prosperity-candidates", "maritime-prosperity-zones", "Potential Maritime Prosperity Zone tracts"],
  ["heliport-layer-toggle", "virginia-heliports", "heliports", "FAA heliport reference points"],
  ["controlled-airspace-toggle", "virginia-surface-controlled-airspace", "controlled-airspace", "FAA surface controlled airspace"],
  ["uas-facility-map-toggle", "virginia-uas-facility-map", "uas-facility-map", "FAA authorization-ceiling data"],
  ["flight-constraints-toggle", "virginia-flight-constraints", "flight-constraints", "FAA flight-constraint data"],
  ["uas-test-sites-toggle", "virginia-uas-test-sites", "uas-test-sites", "UAS test-facility data"],
  ["maap-flight-areas-toggle", "maap-flight-areas", "maap-flight-areas", "MAAP supplied flight-area outlines"],
];

for (const [id, file, pane, label] of referenceLayers) {
  test(`${label} clear their failure after a successful retry`, async ({ page }) => {
    const pattern = `**/${file}.geojson*`;
    await page.route(pattern, (route) => route.fulfill({ status: 503, body: "Unavailable" }));
    await page.goto("/map/");
    await expect(page.locator("[data-map-app]")).toHaveAttribute("aria-busy", "false");
    await page.locator(".map-legend summary").click();
    await page.locator(".map-layers summary").click();
    const toggle = page.locator(`#${id}`);
    const legend = page.locator(`[data-legend-toggle="${id}"]`);
    const geometry = page.locator(`.leaflet-${pane}-pane path, .leaflet-${pane}-pane canvas, .leaflet-${pane}-pane .leaflet-marker-icon`);
    await expect(toggle).not.toBeChecked();
    // A failed load immediately resets the checkbox; check() wrongly requires it to stay checked.
    await toggle.click();
    await expect(page.locator("#map-status")).toContainText(`${label} could not be loaded.`);
    await expect(toggle).not.toBeChecked();
    await expect(toggle).toBeEnabled();
    await expect(legend).toBeHidden();
    await expect(geometry).toHaveCount(0);

    await page.unroute(pattern);
    await toggle.click();
    await expect(toggle).toBeChecked();
    await expect(toggle).toBeEnabled();
    await expect(geometry).not.toHaveCount(0);
    await expect(legend).toBeVisible();
    await expect(page.locator("#map-status")).toBeHidden();
    await expect(page.locator("#map-status")).toHaveText("");
  });
}

test("a recovered layer preserves other layer failures", async ({ page }) => {
  for (const file of ["virginia-counties", "virginia-regions"]) {
    await page.route(`**/${file}.geojson*`, (route) => route.fulfill({ status: 503, body: "Unavailable" }));
  }
  await page.goto("/map/");
  await expect(page.locator("[data-map-app]")).toHaveAttribute("aria-busy", "false");
  await page.locator(".map-layers summary").click();
  await page.locator("#county-layer-toggle").click();
  await expect(page.locator("#map-status")).toContainText("County boundaries could not be loaded.");
  await page.locator("#region-layer-toggle").click();
  await expect(page.locator("#map-status")).toContainText("Ecosystem region shading could not be loaded.");
  await expect(page.locator("#map-status")).toContainText("County boundaries could not be loaded.");
  await page.unroute("**/virginia-counties.geojson*");
  await page.locator("#county-layer-toggle").click();
  await expect(page.locator("#county-layer-toggle")).toBeEnabled();
  await expect(page.locator("#map-status")).not.toContainText("County boundaries");
  await expect(page.locator("#map-status")).toHaveText("Ecosystem region shading could not be loaded.");
  await page.locator("#heliport-layer-toggle").check();
  await expect(page.locator("#heliport-layer-toggle")).toBeEnabled();
  await expect(page.locator("#map-status")).toHaveText("Ecosystem region shading could not be loaded.");
  await page.unroute("**/virginia-regions.geojson*");
  await page.locator("#region-layer-toggle").click();
  await expect(page.locator("#region-layer-toggle")).toBeEnabled();
  await expect(page.locator("#map-status")).toBeHidden();
});

test("a recovered layer preserves the truncated listing notice", async ({ page }) => {
  await page.route("**/api/assets.geojson*", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    await route.fulfill({ response, json: {
      ...data, truncated: true, result_count: data.result_count + 1,
    } });
  });
  await page.route("**/virginia-counties.geojson*", (route) => route.fulfill({ status: 503, body: "Unavailable" }));
  await page.goto("/map/");
  await expect(page.locator("#map-status")).toContainText("Narrow the filters to see every result.");
  const listingNotice = await page.locator("#map-status").textContent();
  await page.locator(".map-layers summary").click();
  await page.locator("#county-layer-toggle").click();
  await expect(page.locator("#map-status")).toContainText("County boundaries could not be loaded.");
  await expect(page.locator("#map-status")).toContainText(listingNotice);
  await page.unroute("**/virginia-counties.geojson*");
  await page.locator("#county-layer-toggle").click();
  await expect(page.locator("#county-layer-toggle")).toBeEnabled();
  await expect(page.locator("#map-status")).toHaveText(listingNotice);
  await expect(page.locator("#map-status")).toBeVisible();
});

test("a recovered layer preserves an asset loading failure", async ({ page }) => {
  await page.route("**/api/assets.geojson*", (route) => route.fulfill({ status: 503, body: "Unavailable" }));
  await page.route("**/virginia-counties.geojson*", (route) => route.fulfill({ status: 503, body: "Unavailable" }));
  await page.goto("/map/");
  const assetFailure = "The map data could not be loaded. The directory remains available.";
  await expect(page.locator("#map-status")).toHaveText(assetFailure);
  await page.locator(".map-layers summary").click();
  await page.locator("#county-layer-toggle").click();
  await expect(page.locator("#map-status")).toContainText("County boundaries could not be loaded.");
  await expect(page.locator("#map-status")).toContainText(assetFailure);
  await page.unroute("**/virginia-counties.geojson*");
  await page.locator("#county-layer-toggle").click();
  await expect(page.locator("#county-layer-toggle")).toBeEnabled();
  await expect(page.locator(".leaflet-county-boundaries-pane path")).not.toHaveCount(0);
  await expect(page.locator("#map-status")).toHaveText(assetFailure);
  await expect(page.locator("#nearby-search")).toBeDisabled();
});

test("saved layer selections and printed legends omit inactive overlays", async ({ page }) => {
  await page.goto("/map/?map_layers=counties&map_layers_v=5");
  await expect(page.locator(".leaflet-county-boundaries-pane path")).not.toHaveCount(0);
  await page.locator(".map-legend summary").click();
  await expect(page.locator("[data-legend-toggle]:visible")).toHaveCount(1);
  await expect(page.locator(".legend-line.county-boundary")).toBeVisible();
  await expect(page.locator(".legend-line.state-boundary")).toBeHidden();
  await expect(page.locator(".legend-dot.university")).toBeHidden();
  await page.emulateMedia({ media: "print" });
  await expect(page.locator("[data-legend-toggle]:visible")).toHaveCount(1);
  await expect(page.locator(".legend-line.county-boundary")).toBeVisible();
});

test("simplified headings and unboxed profile sections fit all designs", async ({ page }, testInfo) => {
  test.setTimeout(120_000);
  for (const theme of THEMES) {
    await page.goto("/map/");
    await expect(page.locator(".result-row").first()).toBeVisible();
    await page.locator(".appearance-menu > summary").click();
    await page.locator(`[data-theme-choice="${theme}"]`).click();
    const cover = page.locator("[data-showcase-cover]");
    if (await cover.isVisible()) await page.locator("[data-showcase-enter]").first().click();
    await expect(cover).toBeHidden();
    await page.locator(".map-legend summary").click();
    await page.screenshot({ path: testInfo.outputPath(`map-${theme}.png`), fullPage: true, animations: "disabled" });

    await page.goto("/directory/");
    await expect(page.locator(".directory-filters .eyebrow, .directory-heading .eyebrow")).toHaveCount(0);
    await page.screenshot({ path: testInfo.outputPath(`directory-${theme}.png`), fullPage: true, animations: "disabled" });

    await page.goto("/assets/xelevate-leesburg-unmanned-systems-facility/");
    const sections = page.locator(".detail-sidebar section");
    await expect(sections.first()).toBeVisible();
    for (const section of await sections.all()) {
      await expect(section).toHaveCSS("border-left-width", "0px");
      await expect(section).toHaveCSS("border-right-width", "0px");
      await expect(section).toHaveCSS("border-bottom-width", "0px");
      await expect(section).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
    }
    await expect(sections.first()).toHaveCSS("border-top-width", "0px");
    await expect(sections.nth(1)).toHaveCSS("border-top-width", "1px");
    await expect(page.locator(".detail-sidebar")).toContainText("Contact and information");
    await expect(page.locator(".detail-sidebar")).toContainText("Location");
    await expect(page.locator(".detail-sidebar")).toContainText("Classification");
    await expect(page.locator(".detail-verification-footer")).toHaveCount(0);
    await expect(page.locator("main")).not.toContainText("Review status");
    await expect(page.locator("main")).not.toContainText("Record updated");
    const overflow = await page.locator(".detail-sidebar h2, .detail-sidebar dd")
      .evaluateAll((elements) => elements.filter((el) => el.scrollWidth > el.clientWidth + 1).map((el) => el.textContent));
    expect(overflow).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize().width);
    await page.screenshot({ path: testInfo.outputPath(`profile-${theme}.png`), fullPage: true, animations: "disabled" });
  }
});
