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

test("failed overlays do not appear in the legend", async ({ page }) => {
  await page.route("**/virginia-counties.geojson*", (route) => route.fulfill({ status: 503, body: "Unavailable" }));
  await page.goto("/map/");
  await expect(page.locator(".result-row").first()).toBeVisible();
  await page.locator(".map-legend summary").click();
  await page.locator(".map-layers summary").click();
  await page.locator("#county-layer-toggle").check();
  await expect(page.locator("#map-status")).toContainText("County boundaries could not be loaded");
  await expect(page.locator("#county-layer-toggle")).not.toBeChecked();
  await expect(page.locator('[data-legend-toggle="county-layer-toggle"]')).toBeHidden();
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
  for (const theme of ["classic", "dark", "showcase", "showcase-light"]) {
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
    await expect(page.locator(".detail-verification-footer")).toContainText("Review status");
    const overflow = await page.locator(".detail-sidebar h2, .detail-sidebar dd")
      .evaluateAll((elements) => elements.filter((el) => el.scrollWidth > el.clientWidth + 1).map((el) => el.textContent));
    expect(overflow).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize().width);
    await page.screenshot({ path: testInfo.outputPath(`profile-${theme}.png`), fullPage: true, animations: "disabled" });
  }
});
