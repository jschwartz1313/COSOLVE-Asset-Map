import { expect, test } from "@playwright/test";
import { THEMES } from "../../static/js/theme-switcher.js";

const radio = (page, value) => page.locator(`input[name="map-basemap"][value="${value}"]`);
const statefulMap = "/map/?q=airport&map_lat=37.2&map_lon=-80.4&map_zoom=9"
  + "&map_layers=assets,state&map_layers_v=5&map_basemap=topo";

test("four thumbnail basemaps are available directly on the map", async ({ page }) => {
  await page.goto("/map/");
  await expect(page.locator(".result-row").first()).toBeVisible();
  const total = await page.locator("#result-count").textContent();
  const picker = page.getByRole("group", { name: "Basemap", exact: true });
  await expect(picker).toBeVisible();
  await expect(picker.getByRole("radio")).toHaveCount(4);
  await expect(page.locator(".map-layers input[name='map-basemap']")).toHaveCount(0);
  await expect(radio(page, "street")).toBeChecked();

  for (const [value, provider, attribution] of [
    ["light", "basemaps.cartocdn.com", "CARTO"],
    ["topo", "USGSTopo", "USGS The National Map"],
    ["imagery", "USGSImageryOnly", "Orthoimagery"],
    ["street", "tile.openstreetmap.org", "OpenStreetMap"],
  ]) {
    await radio(page, value).check();
    await expect(page.locator("[data-map-app]")).toHaveAttribute("data-basemap", value);
    await expect(page.locator(".leaflet-tile-pane img").first()).toHaveAttribute("src", new RegExp(provider));
    await expect(page.locator(".leaflet-control-attribution")).toContainText(attribution);
    await expect(page.locator("#result-count")).toHaveText(total);
  }
});

test("topographic shared views preserve position, filters, and overlays", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto(statefulMap);
  await expect(page.locator(".result-row").first()).toBeVisible();
  await expect(radio(page, "topo")).toBeChecked();
  await expect(page.locator("[data-map-app]")).toHaveAttribute("data-basemap", "topo");
  await page.locator(".map-actions summary").click();
  await page.locator("#copy-view-link").click();
  await expect(page.locator("#copy-view-link")).toHaveText("Link copied");
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  const params = new URL(copied).searchParams;
  expect(params.get("map_basemap")).toBe("topo");
  expect(params.get("q")).toBe("airport");
  expect(params.get("map_layers")).toBe("assets,state");
  expect(Number(params.get("map_lat"))).toBeCloseTo(37.2, 1);
  expect(Number(params.get("map_lon"))).toBeCloseTo(-80.4, 1);
  expect(params.get("map_zoom")).toBe("9");
  await page.goto(copied);
  await expect(radio(page, "topo")).toBeChecked();
  await expect(page.locator('input[name="q"]')).toHaveValue("airport");
});

test("native radio keys switch basemaps and the chooser is omitted from print", async ({ page }) => {
  await page.goto("/map/");
  await radio(page, "street").focus();
  await radio(page, "street").press("ArrowDown");
  await expect(radio(page, "light")).toBeChecked();
  await radio(page, "light").press("ArrowDown");
  await expect(radio(page, "topo")).toBeChecked();
  await expect(page.locator("[data-map-app]")).toHaveAttribute("data-basemap", "topo");
  await page.emulateMedia({ media: "print" });
  await expect(page.locator(".basemap-picker")).toBeHidden();
});

test("the picker yields to asset popups and returns when they close", async ({ page }) => {
  await page.goto("/map/?q=Adaptive%20Aerospace%20Group");
  await page.locator(".asset-marker-shell").click();
  await expect(page.locator(".leaflet-popup")).toBeVisible();
  await expect(page.locator(".basemap-picker")).toBeHidden();
  await page.locator(".leaflet-popup-close-button").click();
  await expect(page.locator(".basemap-picker")).toBeVisible();
  await expect(radio(page, "street")).toBeChecked();
});

test("thumbnail controls fit both designs without covering zoom or source controls", async ({ page }, testInfo) => {
  for (const theme of THEMES) {
    await page.goto("/map/");
    await page.locator(".appearance-menu > summary").click();
    await page.locator(`[data-theme-choice="${theme}"]`).click();
    await radio(page, "topo").check();
    await expect(page.locator("#map .leaflet-tile-pane")).toHaveCSS("filter", "none");
    const layout = await page.evaluate(() => {
      const box = (selector) => document.querySelector(selector).getBoundingClientRect();
      const stage = box(".map-stage");
      const picker = box(".basemap-picker");
      const zoom = box(".leaflet-control-zoom");
      const sources = box(".map-source-disclosure");
      const overlaps = (a, b) => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
      return {
        inside: picker.left >= stage.left && picker.right <= stage.right && picker.top >= stage.top && picker.bottom <= stage.bottom,
        zoomOverlap: overlaps(picker, zoom), sourcesOverlap: overlaps(picker, sources),
        labelsFit: [...document.querySelectorAll(".basemap-picker span")].every(el => el.scrollWidth <= el.clientWidth),
      };
    });
    expect(layout).toEqual({inside:true, zoomOverlap:false, sourcesOverlap:false, labelsFit:true});
    await page.screenshot({path:testInfo.outputPath(`basemaps-${theme}.png`), animations:"disabled"});
  }
});

test("short landscape maps use a compact two-by-two picker", async ({ page }, testInfo) => {
  await page.setViewportSize({width:844, height:390});
  await page.goto("/map/");
  const picker = page.locator(".basemap-picker");
  await expect(page.locator(".basemap-tiles")).toHaveCSS("grid-template-columns", "50px 50px");
  const tiles = await picker.locator("label").evaluateAll(labels => labels.map(el => {
    const { x, y, width, height } = el.getBoundingClientRect();
    return { x, y, width, height };
  }));
  expect(tiles[0].y).toBe(tiles[1].y);
  expect(tiles[2].y).toBe(tiles[3].y);
  expect(tiles[0].x).toBe(tiles[2].x);
  expect(tiles[1].x).toBeGreaterThan(tiles[0].x);
  expect(tiles[2].y).toBeGreaterThan(tiles[0].y);
  const withinMap = await picker.evaluate(el => {
    const picker = el.getBoundingClientRect();
    const map = document.querySelector(".map-stage").getBoundingClientRect();
    return picker.top >= map.top && picker.bottom <= map.bottom;
  });
  expect(withinMap).toBe(true);
  await page.screenshot({path:testInfo.outputPath("basemaps-landscape.png"), animations:"disabled"});
});
