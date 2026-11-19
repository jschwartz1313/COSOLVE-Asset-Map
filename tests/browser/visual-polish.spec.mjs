import { expect, test } from "@playwright/test";

test("Reset stays regular weight and fits its button", async ({ page }, testInfo) => {
  for (const width of [320, 390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/map/?q=Adaptive%20Aerospace%20Group");
    const reset = page.getByRole("button", { name: "Reset map view", exact: true });
    await expect(reset).toHaveCSS("font-weight", "400");
    expect(await reset.evaluate(el => el.scrollWidth <= el.clientWidth
      && el.scrollHeight <= el.clientHeight)).toBe(true);
    await reset.screenshot({ path: testInfo.outputPath(`reset-${width}.png`) });
  }
});

test("map and list share one clear selection, including keyboard selection", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/map/?q=Hampton");
  const row = page.locator(".result-row").filter({ hasText: "Adaptive Aerospace Group" });
  await row.click();
  const id = await row.getAttribute("data-asset-id");
  const marker = page.locator(`.asset-marker-shell[data-asset-id="${id}"]`);
  await expect(marker).toHaveClass(/is-selected/);
  await expect(marker).toHaveAttribute("aria-pressed", "true");
  await expect(row).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".result-row.is-selected")).toHaveCount(1);
  await expect(page.locator(".asset-marker-shell.is-selected")).toHaveCount(1);
  await page.locator(".leaflet-popup-close-button").click();
  await marker.focus();
  await marker.press("Enter");
  await expect(page.locator(".leaflet-popup-content")).toContainText("Adaptive Aerospace Group");
  await expect(row).toHaveClass(/is-selected/);
  await page.locator(".map-layers summary").click();
  await page.locator("#precision-layer-toggle").check();
  await expect(marker).toHaveClass(/is-selected/);
  await page.locator(".map-layers summary").click();
  const next = page.locator(".result-row").filter({ hasText: "Advanced Aircraft Company" });
  await next.click();
  await expect(row).toHaveAttribute("aria-pressed", "false");
  await expect(next).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".asset-marker-shell.is-selected")).toHaveCount(1);
  const regional = page.locator(".result-row").filter({ hasText: "AUVSI Hampton Roads Chapter" });
  await regional.click();
  await expect(regional).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".asset-marker-shell.is-selected")).toHaveCount(0);
  await expect(page.locator(".leaflet-popup")).toHaveCount(0);
});

test("a failed grey provider falls back to Street and keeps the picker synchronized", async ({ page }) => {
  let failedRequests = 0;
  await page.route("**/*basemaps.cartocdn.com/**", route => {
    failedRequests += 1;
    return route.abort();
  });
  await page.goto("/map/?map_basemap=light");
  await expect.poll(() => failedRequests).toBeGreaterThanOrEqual(3);
  await expect(page.locator("[data-map-app]")).toHaveAttribute("aria-busy", "false");
  await expect(page.locator("[data-map-app]")).toHaveAttribute("data-basemap", "street");
  await expect(page.locator('input[name="map-basemap"][value="street"]')).toBeChecked();
  await expect(page.locator(".leaflet-control-attribution")).toContainText("OpenStreetMap");
  await expect(page.locator(".result-row").first()).toBeVisible();
});

test("restrained directory styles retain borders, readable text and responsive controls", async ({ page }, testInfo) => {
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/directory/");
    const rows = page.locator(".directory-row");
    await expect(rows.first().locator("h3")).toHaveCSS("font-size", "16px");
    await expect(page.locator(".directory-list")).toHaveCSS("border-left-width", "1px");
    const backgrounds = await rows.evaluateAll(elements => elements.slice(0, 2).map(el => getComputedStyle(el).backgroundColor));
    expect(backgrounds[0]).not.toBe(backgrounds[1]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const overflows = await page.locator(".directory-filters label, .directory-row h3, .directory-row .type-pill, .directory-heading button")
      .evaluateAll(elements => elements.filter(el => el.getClientRects().length && el.scrollWidth > el.clientWidth + 1).map(el => el.textContent));
    expect(overflows).toEqual([]);
    if ([390, 1440].includes(width)) await page.screenshot({ path: testInfo.outputPath(`directory-${width}.png`), fullPage: true });
  }
});

test("actual facility photos stay confined to their profiles with clear credits", async ({ page }, testInfo) => {
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const slug of ["nasa-flight-dynamics-research-facility", "nasa-langley-roam-uas-operations-center"]) {
      await page.goto(`/assets/${slug}/`);
      const figure = page.locator(".profile-photo");
      await expect(figure).toBeVisible();
      await expect(figure.locator("img")).toHaveJSProperty("complete", true);
      expect(await figure.locator("img").evaluate(el => el.naturalWidth)).toBe(1024);
      await expect(figure).toContainText("NASA");
      await expect(figure.getByRole("link", { name: "Photo source" })).toHaveAttribute("target", "_blank");
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      if (width === 390 || width === 1440) await page.screenshot({ path: testInfo.outputPath(`${slug}-${width}.png`), fullPage: true });
    }
  }
  await page.goto("/directory/");
  await expect(page.locator(".profile-photo")).toHaveCount(0);
});

test("reduced motion disables decorative transitions without disabling selection", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/map/?q=Adaptive%20Aerospace%20Group");
  await page.locator(".result-row").click();
  await expect(page.locator(".asset-marker-shell.is-selected")).toHaveCount(1);
  const seconds = await page.locator(".asset-marker").evaluate(el => parseFloat(getComputedStyle(el, "::before").transitionDuration));
  expect(seconds).toBeLessThan(0.001);
});
