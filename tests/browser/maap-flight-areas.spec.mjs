import { expect, test } from "@playwright/test";

test("MAAP outlines toggle, restore, explain draft status and fit their popup", async ({ page }, testInfo) => {
  const errors = [];
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: async (text) => { window.copiedMapUrl = text; } },
    });
  });
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/map/");
  await expect(page.locator(".asset-marker, .marker-cluster").first()).toBeVisible();
  await expect(page.locator("#maap-flight-areas-toggle")).not.toBeChecked();
  await expect(page.locator(".leaflet-maap-flight-areas-pane path")).toHaveCount(0);
  await page.locator(".map-layers > summary").click();
  const toggle = page.locator("#maap-flight-areas-toggle");
  await toggle.scrollIntoViewIfNeeded();
  await toggle.check();
  await expect(toggle).toBeEnabled();
  await expect(page.locator(".leaflet-maap-flight-areas-pane path")).toHaveCount(3);
  await expect(page.locator('[data-legend-toggle="maap-flight-areas-toggle"]')).not.toHaveAttribute("hidden");
  await page.locator(".map-actions > summary").click();
  await page.locator("#copy-view-link").click();
  const savedQuery = new URL(await page.evaluate(() => window.copiedMapUrl)).search;
  expect(new URLSearchParams(savedQuery).get("map_layers")).toContain("maap-flight-areas");
  await page.goto(`/map/${savedQuery}`);
  await expect(page.locator("#map-status")).toBeHidden();
  await expect(page.locator(".asset-marker, .marker-cluster").first()).toBeVisible();
  await expect(toggle).toBeChecked();
  const outlines = page.locator(".leaflet-maap-flight-areas-pane path");
  await expect(outlines).toHaveCount(3);
  const draft = page.locator('.leaflet-maap-flight-areas-pane path[stroke-dasharray="7 5"]');
  await expect(draft).toHaveCount(1);
  const clickPoint = await draft.evaluate((path) => {
    for (let step = 1; step < 20; step += 1) {
      const point = path.getPointAtLength(path.getTotalLength() * step / 20)
        .matrixTransform(path.getScreenCTM());
      if (document.elementFromPoint(point.x, point.y) === path) {
        return { x: point.x, y: point.y };
      }
    }
    return null;
  });
  expect(clickPoint).not.toBeNull();
  await page.mouse.click(clickPoint.x, clickPoint.y);
  const popup = page.locator(".maap-flight-popup");
  await expect(popup).toBeVisible();
  await expect(popup).toHaveCSS("opacity", "1");
  await expect(popup).toContainText("Draft source");
  await expect(popup).toContainText("COA DRAFT 108625");
  await expect(popup).toContainText("7,000 ft MSL");
  await expect(popup.locator(".leaflet-popup-close-button")).toBeInViewport();
  await expect(popup.getByRole("link", { name: "Asset profile" })).toHaveAttribute(
    "href", "/assets/maap-central-virginia-flight-area/",
  );
  expect(await popup.locator(".drone-reference-popup").evaluate(
    (el) => el.scrollWidth <= el.clientWidth + 1,
  )).toBeTruthy();
  await page.screenshot({ path: testInfo.outputPath("maap-draft-popup.png"), animations: "disabled" });
  await popup.locator(".leaflet-popup-close-button").click();
  await page.locator(".map-layers > summary").click();
  await toggle.scrollIntoViewIfNeeded();
  await toggle.uncheck();
  await expect(page.locator(".leaflet-maap-flight-areas-pane path")).toHaveCount(0);
  await expect(page.locator('[data-legend-toggle="maap-flight-areas-toggle"]')).toHaveAttribute("hidden");
  expect(errors).toEqual([]);
});

test("MAAP source notes and site profiles remain usable across designs", async ({ page }, testInfo) => {
  for (const theme of ["classic", "dark", "showcase", "showcase-light"]) {
    await page.addInitScript((mode) => {
      localStorage.setItem("cosolve-display-mode", mode);
    }, theme);
    await page.goto("/references/maap/");
    await page.keyboard.press("Escape");
    await expect(page.getByRole("heading", { name: "MAAP facilities and flight areas", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
    await page.screenshot({ path: testInfo.outputPath(`maap-reference-${theme}.png`), fullPage: true });
  }
  await page.goto("/assets/virginia-tech-vtti-smart-airspace-vertiport/");
  await page.keyboard.press("Escape");
  await expect(page.locator("main")).toContainText("8VA2");
  await expect(page.locator("main")).toContainText("prior permission");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
});
