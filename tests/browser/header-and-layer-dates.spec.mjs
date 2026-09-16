import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

test("map images identify only the site origin to providers", async ({ page }) => {
  const tileRequests = [];
  await page.route("https://tile.openstreetmap.org/**", async (route) => {
    tileRequests.push(route.request());
    await route.fulfill({
      contentType: "image/png",
      body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jN1kAAAAASUVORK5CYII=", "base64"),
    });
  });
  await page.goto("/map/?q=airport");
  await expect.poll(() => tileRequests.length).toBeGreaterThan(0);
  for (const request of tileRequests) {
    expect(request.headers().referer).toBe("http://127.0.0.1:8002/");
  }
  await expect(page.locator("img.leaflet-tile").first()).toHaveAttribute("referrerpolicy", "strict-origin");
});

test("header menus are compact, keyboard accessible, and preserve navigation", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 780 });
  await page.goto("/map/");
  const appearance = page.locator(".appearance-menu");
  const more = page.locator(".navigation-menu");
  expect((await page.locator(".site-header").boundingBox()).height).toBeLessThanOrEqual(100);
  await appearance.locator("summary").focus();
  await page.keyboard.press("Enter");
  await expect(appearance).toHaveAttribute("open", "");
  await expect(appearance.getByRole("button", { name: "Showcase Light", exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(appearance).not.toHaveAttribute("open", "");
  await expect(appearance.locator("summary")).toBeFocused();
  await more.locator("summary").click();
  await expect(more.getByRole("link", { name: "About data", exact: true })).toBeVisible();
  await expect(more.getByRole("link", { name: "Get connected", exact: true })).toBeVisible();
  await appearance.locator("summary").click();
  await expect(more).not.toHaveAttribute("open", "");
  await page.keyboard.press("Escape");
  await more.locator("summary").click();
  await more.getByRole("link", { name: "About data", exact: true }).click();
  await expect(page).toHaveURL(/\/about-data\//);
});

test("dated reference controls fit on small screens and preserve the map", async ({ page }, testInfo) => {
  const layers = [
    ["heliport-layer-toggle", "virginia-heliports.geojson"],
    ["controlled-airspace-toggle", "virginia-surface-controlled-airspace.geojson"],
    ["uas-facility-map-toggle", "virginia-uas-facility-map.geojson"],
    ["flight-constraints-toggle", "virginia-flight-constraints.geojson"],
    ["uas-test-sites-toggle", "virginia-uas-test-sites.geojson"],
  ];
  await page.goto("/map/");
  await expect(page.locator(".asset-marker, .marker-cluster").first()).toBeVisible();
  await expect(page.locator("#map.leaflet-zoom-anim")).toHaveCount(0);
  await expect(page.locator("#map.leaflet-cluster-anim")).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("compact-header.png") });
  await page.locator(".map-layers > summary").click();
  for (const [id, filename] of layers) {
    const date = JSON.parse(readFileSync(new URL(`../../static/data/${filename}`, import.meta.url))).metadata.generated_at;
    const label = page.locator("label").filter({ has: page.locator(`#${id}`) });
    await expect(label.locator("time")).toHaveAttribute("datetime", date);
    await label.scrollIntoViewIfNeeded();
    await expect(label.locator(".layer-freshness")).toBeVisible();
    expect(await label.evaluate((el) => el.scrollWidth <= el.clientWidth + 1)).toBeTruthy();
    await expect(page.locator(".map-layers > summary")).toBeInViewport();
  }
  await page.locator("#controlled-airspace-toggle").check();
  await expect(page.locator(".leaflet-controlled-airspace-pane path").first()).toBeAttached();
  await page.locator("#controlled-airspace-toggle").scrollIntoViewIfNeeded();
  const drawerAboveMap = await page.locator(".leaflet-control-zoom").evaluate((control) => {
    const bounds = control.getBoundingClientRect();
    const drawer = document.querySelector(".map-layers[open]");
    const drawerBounds = drawer.getBoundingClientRect();
    const x = bounds.x + bounds.width / 2;
    const y = bounds.y + bounds.height / 2;
    if (x < drawerBounds.left || x > drawerBounds.right || y < drawerBounds.top || y > drawerBounds.bottom) return true;
    return drawer.contains(document.elementFromPoint(x, y));
  });
  expect(drawerAboveMap).toBeTruthy();
  await page.screenshot({ path: testInfo.outputPath("dated-layers.png") });
});
