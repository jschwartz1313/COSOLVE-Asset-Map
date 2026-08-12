import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

const catalog = JSON.parse(
  readFileSync(new URL("../../data/virginia_real_assets.json", import.meta.url), "utf8"),
);

test("map layers toggle without moving the reset control", async ({ page }) => {
  await page.goto("/map/");
  await expect(page.locator(".result-row").first()).toBeVisible();

  const reset = page.locator("#reset-view");
  const initialTop = (await reset.boundingBox()).y;
  await page.locator(".map-legend summary").click();
  expect((await reset.boundingBox()).y).toBe(initialTop);
  await expect(page.locator(".legend-line.county-boundary")).toBeVisible();
  await expect(page.locator(".legend-content")).toContainText("County boundary");
  await expect(page.locator(".legend-dot img")).toHaveCount(6);
  await expect(page.locator(".legend-dot.university img")).toHaveAttribute(
    "src",
    /university\.svg$/,
  );
  await page.locator(".map-legend summary").click();
  await page.locator(".map-layers summary").click();

  const assetToggle = page.locator("#asset-layer-toggle");
  await expect(assetToggle).toBeChecked();
  await expect(page.locator(".asset-marker-shell, .marker-cluster")).not.toHaveCount(0);
  await assetToggle.uncheck();
  await expect(page.locator(".asset-marker-shell, .marker-cluster")).toHaveCount(0);
  await assetToggle.check();
  await expect(page.locator(".asset-marker-shell, .marker-cluster")).not.toHaveCount(0);

  const stateToggle = page.locator("#state-boundary-toggle");
  await expect(stateToggle).toBeChecked();
  await expect(page.locator(".leaflet-state-boundary-pane path")).not.toHaveCount(0);
  await stateToggle.uncheck();
  await expect(page.locator(".leaflet-state-boundary-pane path")).toHaveCount(0);
  await stateToggle.check();
  await expect(page.locator(".leaflet-state-boundary-pane path")).not.toHaveCount(0);

  const regionToggle = page.locator("#region-layer-toggle");
  await expect(regionToggle).not.toBeChecked();
  await expect(page.locator(".leaflet-ecosystem-regions-pane path")).toHaveCount(0);
  await regionToggle.check();
  await expect(page.locator(".leaflet-ecosystem-regions-pane path")).toHaveCount(12);
  await expect(page.locator(".region-map-label")).toHaveCount(12);
  await regionToggle.uncheck();
  await expect(page.locator(".leaflet-ecosystem-regions-pane path")).toHaveCount(0);

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

  const heliportToggle = page.locator("#heliport-layer-toggle");
  await expect(heliportToggle).not.toBeChecked();
  await expect(page.locator(".leaflet-heliports-pane .heliport-reference-shell")).toHaveCount(0);
  await heliportToggle.check();
  await expect(page.locator(".leaflet-heliports-pane .heliport-reference-shell")).toHaveCount(127);
  await page
    .locator(".leaflet-heliports-pane .heliport-reference-shell")
    .first()
    .dispatchEvent("click");
  await expect(page.locator(".heliport-popup")).toContainText("Private use");
  await expect(page.locator(".heliport-popup")).toContainText("does not indicate public access");

  const controlledAirspaceToggle = page.locator("#controlled-airspace-toggle");
  await expect(controlledAirspaceToggle).not.toBeChecked();
  await controlledAirspaceToggle.check();
  await expect(page.locator(".leaflet-controlled-airspace-pane path")).toHaveCount(33);
  await expect(page.locator("[data-controlled-airspace-legend]")).not.toHaveAttribute("hidden");
  await page.locator(".map-legend summary").click();
  await expect(page.locator("[data-controlled-airspace-legend]")).toBeVisible();
  await page.locator(".leaflet-controlled-airspace-pane path").first().dispatchEvent("click");
  await expect(page.locator(".drone-reference-popup")).toContainText(
    "generally require FAA authorization",
  );

  const facilityMapToggle = page.locator("#uas-facility-map-toggle");
  await facilityMapToggle.check();
  await expect(page.locator(".leaflet-uas-facility-map-pane canvas")).toBeVisible();
  await expect(page.locator("[data-uas-facility-map-legend]")).toContainText("0 ft AGL");

  const constraintToggle = page.locator("#flight-constraints-toggle");
  await constraintToggle.check();
  await expect(page.locator(".leaflet-flight-constraints-pane path")).toHaveCount(139);
  await expect(page.locator("[data-flight-constraints-legend]")).toContainText(
    "National-security UAS restriction",
  );

  const testSitesToggle = page.locator("#uas-test-sites-toggle");
  await testSitesToggle.check();
  await expect(page.locator(".leaflet-uas-test-sites-pane .uas-test-site-shell")).toHaveCount(3);
  await page
    .locator(".leaflet-uas-test-sites-pane .uas-test-site-shell")
    .first()
    .dispatchEvent("click");
  const testSitePopup = page.locator(".drone-reference-popup", { hasText: "Published size" });
  await expect(testSitePopup).toBeVisible();
  await expect(testSitePopup).toContainText(
    "does not establish access or authorization",
  );
});

test("map credits stay compact while full source notes remain available", async ({
  page,
}) => {
  await page.goto("/map/");
  await expect(page.locator(".result-row").first()).toBeVisible();

  const attribution = page.locator(".leaflet-control-attribution");
  await expect(attribution).toContainText("OpenStreetMap");
  await expect(attribution).not.toContainText("County boundaries");
  await expect(attribution).not.toContainText("Leaflet");
  await expect(attribution).toHaveCSS("white-space", "nowrap");

  const sources = page.locator(".map-source-disclosure");
  await expect(sources).not.toHaveAttribute("open", "");
  await expect(sources).toHaveCSS("padding-top", "0px");
  await sources.locator("summary").click();
  await expect(sources).toHaveAttribute("open", "");
  await expect(sources).toContainText("U.S. Census Bureau TIGERweb");
  await expect(sources).toContainText("planning candidates, not federal designations");
  await expect(sources).toContainText("FAA-recorded operational private-use heliports");
  await expect(sources).toContainText("FAA UAS Facility Map");
  await expect(sources).toContainText("Virginia Spaceport Authority");
});

test("copy view link preserves the map position, filters, and layers", async ({
  context,
  page,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/map/?region=hampton-roads");
  await expect(page.locator(".result-row").first()).toBeVisible();

  await page.locator(".leaflet-control-zoom-in").click();
  await page.locator(".map-layers summary").click();
  await page.locator("#county-layer-toggle").check();
  await page.locator("#mpz-layer-toggle").check();
  await page.locator("#heliport-layer-toggle").check();
  await page.locator("#controlled-airspace-toggle").check();
  await page.locator("#uas-facility-map-toggle").check();
  await page.locator("#flight-constraints-toggle").check();
  await page.locator("#uas-test-sites-toggle").check();
  await page.locator(".map-actions summary").click();
  await page.locator("#copy-view-link").click();
  await expect(page.locator("#copy-view-link")).toHaveText("Link copied");

  const copiedUrl = await page.evaluate(() => navigator.clipboard.readText());
  const copied = new URL(copiedUrl);
  expect(copied.searchParams.get("region")).toBe("hampton-roads");
  expect(copied.searchParams.get("map_lat")).toBeTruthy();
  expect(copied.searchParams.get("map_lon")).toBeTruthy();
  expect(copied.searchParams.get("map_zoom")).toBeTruthy();
  expect(copied.searchParams.get("map_layers")).toContain("assets");
  expect(copied.searchParams.get("map_layers")).toContain("counties");
  expect(copied.searchParams.get("map_layers")).toContain("mpz");
  expect(copied.searchParams.get("map_layers")).toContain("heliports");
  expect(copied.searchParams.get("map_layers")).toContain("controlled-airspace");
  expect(copied.searchParams.get("map_layers")).toContain("uas-facility-map");
  expect(copied.searchParams.get("map_layers")).toContain("flight-constraints");
  expect(copied.searchParams.get("map_layers")).toContain("uas-test-sites");
  expect(copied.searchParams.get("map_layers_v")).toBe("5");
  expect(copied.searchParams.get("map_basemap")).toBe("street");

  await page.goto(copiedUrl);
  await expect(page.locator("#asset-layer-toggle")).toBeChecked();
  await expect(page.locator("#county-layer-toggle")).toBeChecked();
  await expect(page.locator("#mpz-layer-toggle")).toBeChecked();
  await expect(page.locator("#heliport-layer-toggle")).toBeChecked();
  await expect(page.locator("#controlled-airspace-toggle")).toBeChecked();
  await expect(page.locator("#uas-facility-map-toggle")).toBeChecked();
  await expect(page.locator("#flight-constraints-toggle")).toBeChecked();
  await expect(page.locator("#uas-test-sites-toggle")).toBeChecked();
  await expect(page.locator(".leaflet-county-boundaries-pane path")).not.toHaveCount(0);
  await expect(page.locator(".leaflet-maritime-prosperity-zones-pane path")).toHaveCount(11);
  await expect(page.locator(".leaflet-heliports-pane .heliport-reference-shell")).toHaveCount(127);
  await expect(page.locator(".leaflet-controlled-airspace-pane path")).toHaveCount(33);
  await expect(page.locator(".leaflet-uas-facility-map-pane canvas")).toBeVisible();
  await expect(page.locator(".leaflet-flight-constraints-pane path")).toHaveCount(139);
  await expect(page.locator(".leaflet-uas-test-sites-pane .uas-test-site-shell")).toHaveCount(3);
});

test("print view opens the browser print or PDF workflow", async ({ page }) => {
  await page.addInitScript(() => {
    window.print = () => {
      document.documentElement.dataset.printRequested = "true";
    };
  });
  await page.goto("/map/");
  await expect(page.locator(".result-row").first()).toBeVisible();
  await page.locator(".map-actions summary").click();
  await page.locator("#print-view").click();
  await expect(page.locator("html")).toHaveAttribute("data-print-requested", "true");
  await expect(page.locator("#print-report-title")).toHaveText("Current map asset report");
  await expect(page.locator("#print-report-rows tr")).toHaveCount(
    Number(await page.locator("#result-count").textContent()),
  );
  await expect(page.locator("#print-report-context")).toContainText("Generated");
});

test("print view preserves asset marker and legend colors", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/map/?q=Adaptive%20Aerospace%20Group");
  await expect(page.locator(".asset-marker.organization")).toHaveCount(1);
  await page.emulateMedia({ media: "print" });

  const marker = page.locator(".asset-marker.organization");
  const legendDot = page.locator(".legend-dot.organization");
  await expect(page.locator(".skip-link")).toBeHidden();
  await expect(marker).toHaveCSS("background-color", "rgb(47, 111, 159)");
  await expect(legendDot).toHaveCSS("background-color", "rgb(47, 111, 159)");
  await expect(marker).toHaveCSS("print-color-adjust", "exact");
  await expect(legendDot).toHaveCSS("print-color-adjust", "exact");

  const mapBox = await page.locator("#map").boundingBox();
  const headingBox = await page.locator(".print-map-heading").boundingBox();
  const legendBox = await page.locator(".map-legend").boundingBox();
  expect(legendBox.y).toBeGreaterThanOrEqual(mapBox.y + 8);
  expect(legendBox.y).toBeGreaterThanOrEqual(headingBox.y + headingBox.height);
  expect(legendBox.y + legendBox.height).toBeLessThanOrEqual(mapBox.y + mapBox.height);
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

test("clear all removes filters inherited from a filtered URL", async ({ page }) => {
  await page.goto("/map/?record_type=university");
  if (await page.locator(".filter-open").isVisible()) {
    await page.locator(".filter-open").click();
  }
  const form = page.locator("#asset-filters");
  const activeBadge = form.locator("[data-active-filter-count]");
  await expect(form.locator('select[name="record_type"]')).toHaveValue("university");
  await expect(activeBadge).toHaveText("1");

  await form.locator('button[type="reset"]').click();

  await expect(form.locator('select[name="record_type"]')).toHaveValue("");
  await expect(activeBadge).toBeHidden();
  await expect(page.locator("#result-count")).toHaveText(String(catalog.record_count));
  await expect(page).toHaveURL(/\/map\/$/);
});

test("active filters remain visible on the map and can be removed individually", async ({
  page,
}) => {
  await page.goto("/map/?record_type=university&region=hampton-roads");
  await expect(page.locator(".result-row").first()).toBeVisible();

  const filterBar = page.locator("[data-active-filter-bar]");
  await expect(filterBar).toBeVisible();
  await expect(page.locator("#asset-results-view > [data-active-filter-bar]")).toHaveCount(1);
  await expect(page.locator(".map-stage [data-active-filter-bar]")).toHaveCount(0);
  await expect(filterBar.locator("[data-applied-filter-count]")).toHaveText("2");
  await expect(filterBar.locator(".active-filter-chip")).toHaveCount(2);
  await expect(filterBar).toContainText("Asset type: University");
  await expect(filterBar).toContainText("Region: Hampton Roads");

  await filterBar.getByRole("button", { name: /Remove Asset type: University filter/ }).click();
  await expect(filterBar.locator(".active-filter-chip")).toHaveCount(1);
  await expect(filterBar).not.toContainText("Asset type: University");
  await expect(page).toHaveURL(/region=hampton-roads/);
  await expect(page).not.toHaveURL(/record_type=/);

  await filterBar.getByRole("button", { name: "Clear all" }).click();
  await expect(filterBar).toBeHidden();
  await expect(page).toHaveURL(/\/map\/$/);
});

test("desktop filter panel uses comfortable spacing without overflow", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto("/map/");
  await expect(page.locator(".result-row").first()).toBeVisible();

  await expect(page.locator(".filters-panel")).toHaveCSS("width", "276px");
  await expect(page.locator(".filter-fields-scroll")).toHaveCSS("align-content", "start");
  await expect(page.locator(".filter-fields-scroll")).toHaveCSS("gap", "13px");
  await expect(page.locator("#asset-filters input[type=search]")).toHaveCSS("height", "40px");
  await expect(page.locator("#asset-filters button[type=submit]")).toBeVisible();
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
  await page.setViewportSize({ width: 1280, height: 720 });
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
  await expect(marker.locator("img")).toHaveAttribute("src", /building-2\.svg$/);
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

test("analytical map tools expose quality, summaries, and saved basemaps", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/map/");
  await expect(page.locator(".composition-cluster").first()).toBeVisible();
  const fullResultCount = await page.locator("#result-count").textContent();
  await expect(page.locator(".composition-cluster .cluster-segment").first()).toBeVisible();
  await page.locator(".composition-cluster").first().hover();
  const clusterRows = page.locator(".cluster-composition-tooltip .cluster-composition-row");
  await expect(clusterRows.first()).toBeVisible();
  await expect(clusterRows.first()).toHaveCSS("white-space", "nowrap");
  await expect(clusterRows.first()).toContainText(/\b\d+$/);
  const clusterTooltip = page.locator(".cluster-composition-tooltip");
  await expect(clusterTooltip).not.toContainText("Organization");
  await expect(clusterTooltip).not.toContainText("Infrastructure");
  await expect(clusterTooltip).not.toContainText("Operating environment");

  await page.locator(".map-layers summary").click();
  await page.locator('input[name="map-basemap"][value="light"]').check();
  await expect
    .poll(async () =>
      page
        .locator(".leaflet-tile-pane img")
        .first()
        .getAttribute("src"),
    )
    .toContain("basemaps.cartocdn.com");
  await page.locator('input[name="map-basemap"][value="imagery"]').check();
  await expect
    .poll(async () =>
      page
        .locator(".leaflet-tile-pane img")
        .first()
        .getAttribute("src"),
    )
    .toContain("basemap.nationalmap.gov");

  await page.locator("#verification-layer-toggle").check();
  await page.locator("#precision-layer-toggle").check();
  await page.locator(".map-legend summary").click();
  await expect(page.locator("[data-verification-legend]")).toBeVisible();
  await expect(page.locator("[data-precision-legend]")).toBeVisible();

  await page.locator(".map-analysis summary").click();
  await page.locator("#summary-region").selectOption("hampton-roads");
  await page.locator("#show-region-summary").click();
  await expect(page.locator("#map-insight-panel")).toBeVisible();
  await expect(page.locator("#asset-results-view")).toBeHidden();
  await expect(page.locator("#map-insight-title")).toHaveText("Hampton Roads");
  await expect(page.locator(".insight-metrics")).toContainText("Assets");
  await expect(page.locator("#map-insight-panel")).toHaveCSS("position", "static");
  await page.locator("#close-map-insight").click();
  await expect(page.locator("#asset-results-view")).toBeVisible();
  await expect(page.locator("#map-insight-panel")).toBeHidden();

  await page.locator(".map-analysis summary").click();
  await page.locator("#select-extent").click();
  await expect(page.locator("#analysis-status")).toContainText("assets selected");
  await expect(page.locator("#export-area")).toBeEnabled();
  await page.locator("#clear-analysis").click();
  await expect(page.locator("#result-count")).toHaveText(fullResultCount);

  await page.locator(".map-actions summary").click();
  await page.locator("#presentation-view").click();
  await expect(page.locator("body")).toHaveClass(/presentation-mode/);
  await expect(page.locator("#exit-presentation")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator("body")).not.toHaveClass(/presentation-mode/);
});

test("drawn area selection filters assets and enables export", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/map/?region=hampton-roads");
  await expect(page.locator(".result-row").first()).toBeVisible();
  const regionalTotal = Number(await page.locator("#result-count").textContent());

  await page.locator(".map-analysis summary").click();
  await page.locator("#select-area").click();
  const mapBox = await page.locator("#map").boundingBox();
  if (!mapBox) throw new Error("Map did not render");
  await page.mouse.move(mapBox.x + mapBox.width * 0.15, mapBox.y + mapBox.height * 0.15);
  await page.mouse.down();
  await page.mouse.move(mapBox.x + mapBox.width * 0.85, mapBox.y + mapBox.height * 0.85, {
    steps: 10,
  });
  await page.mouse.up();

  await expect(page.locator("#analysis-status")).toContainText("assets selected");
  await expect(page.locator(".leaflet-analysis-selection-pane path")).toHaveCount(1);
  const selectedCount = Number(await page.locator("#result-count").textContent());
  expect(selectedCount).toBeGreaterThan(0);
  expect(selectedCount).toBeLessThanOrEqual(regionalTotal);
  await expect(page.locator("#export-area")).toBeEnabled();
  await page.locator(".map-analysis summary").click();
  const downloadPromise = page.waitForEvent("download");
  await page.locator("#export-area").click();
  const download = await downloadPromise;
  const csv = readFileSync(await download.path(), "utf8").trim().split("\n");
  expect(csv).toHaveLength(selectedCount + 1);

});

test("drawn polygon selects and exports only enclosed assets", async ({ context, page }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/map/?region=hampton-roads");
  await expect(page.locator(".result-row").first()).toBeVisible();
  const regionalTotal = Number(await page.locator("#result-count").textContent());

  await page.locator(".map-analysis summary").click();
  await page.locator("#select-polygon").click();
  const mapBox = await page.locator("#map").boundingBox();
  if (!mapBox) throw new Error("Map did not render");
  const mobile = page.viewportSize().width <= 650;
  const vertices = mobile
    ? [
        [0.58, 0.55],
        [0.86, 0.55],
        [0.86, 0.78],
        [0.58, 0.78],
      ]
    : [
        [0.4, 0.25],
        [0.85, 0.35],
        [0.75, 0.85],
        [0.4, 0.75],
      ];
  for (const [x, y] of vertices) {
    const point = {
      x: mapBox.x + mapBox.width * x,
      y: mapBox.y + mapBox.height * y,
    };
    if (mobile) {
      await page.touchscreen.tap(point.x, point.y);
    } else {
      await page.mouse.click(point.x, point.y);
    }
    await page.waitForTimeout(150);
  }
  if (await page.locator("#finish-polygon").isVisible()) {
    await page.locator("#finish-polygon").click();
  }

  await expect(page.locator("#analysis-status")).toContainText("assets selected");
  await expect(page.locator(".analysis-selection-polygon")).toHaveCount(1);
  const selectedCount = Number(await page.locator("#result-count").textContent());
  expect(selectedCount).toBeGreaterThan(0);
  expect(selectedCount).toBeLessThan(regionalTotal);
  await expect(page.locator("#export-area")).toBeEnabled();
  await page.locator(".map-analysis summary").click();
  const downloadPromise = page.waitForEvent("download");
  await page.locator("#export-area").click();
  const download = await downloadPromise;
  const csv = readFileSync(await download.path(), "utf8").trim().split("\n");
  expect(csv).toHaveLength(selectedCount + 1);

  await page.locator(".map-actions summary").click();
  await page.locator("#copy-view-link").click();
  const copiedUrl = await page.evaluate(() => navigator.clipboard.readText());
  expect(new URL(copiedUrl).searchParams.get("map_analysis")).toMatch(/^polygon\|/);

  await page.goto(copiedUrl);
  await expect(page.locator(".analysis-selection-polygon")).toHaveCount(1);
  await expect(page.locator("#analysis-status")).toContainText("assets selected");
  await expect(page.locator("#result-count")).toHaveText(String(selectedCount));
});

test("nearby search filters from the current map center and can be cleared", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/map/?q=Adaptive%20Aerospace%20Group");
  await expect(page.locator(".asset-marker")).toHaveCount(1);

  await page.locator(".map-analysis summary").click();
  await page.locator("#nearby-radius").selectOption("25");
  await page.locator("#nearby-search").click();
  await expect(page.locator("#analysis-status")).toContainText("within 25 miles");
  await expect(page.locator(".leaflet-analysis-selection-pane path")).toHaveCount(1);
  await expect(page.locator("#export-area")).toBeEnabled();
  await page.locator("#clear-analysis").click();
  await expect(page.locator("#result-count")).toHaveText("1");
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
  await expect(page.locator("#result-count")).toHaveText(String(catalog.record_count));
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

test("asset detail profiles stay readable and within the viewport", async ({ page }) => {
  await page.goto("/assets/ata-aviation/");
  await expect(page.getByRole("heading", { name: "ATA Aviation" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Documented relevance" })).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true);
  expect(
    await page
      .locator(".detail-main section")
      .first()
      .evaluate((element) => element.getBoundingClientRect().height),
  ).toBeLessThan(300);
});

test("source-backed activity and site-readiness details are visible", async ({ page }) => {
  await page.goto("/assets/shenandoah-valley-aviation-technology-park/");
  await expect(
    page.getByRole("heading", { name: "Shenandoah Valley Aviation Technology Park" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Current activity and collaboration" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Site readiness" })).toBeVisible();
  await expect(page.locator(".detail-sidebar")).toContainText("58 acres");
  await expect(page.locator(".detail-sidebar")).toContainText("In development");
  await expect(page.getByRole("link", { name: "Activity source" })).toHaveAttribute("href", /^https:/);
  await expect(page.getByRole("link", { name: "Development source" })).toHaveAttribute("href", /^https:/);
});

test("about page reports review status without an empty date range", async ({ page }) => {
  await page.goto("/about-data/");
  await expect(page.getByText("Editorial review", { exact: true })).toBeVisible();
  await expect(page.getByText("Verification range", { exact: true })).toHaveCount(0);
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
