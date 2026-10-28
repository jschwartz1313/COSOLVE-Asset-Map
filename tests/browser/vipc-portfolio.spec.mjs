import { expect, test } from "@playwright/test";

test("VIPC portfolio filter identifies 39 records without changing ordinary categories", async ({ page }) => {
  await page.goto("/map/?portfolio=vipc");
  await expect(page.locator("#result-count")).toHaveText("39");
  await expect(page.getByLabel("VIPC portfolio organizations only")).toBeChecked();
  await expect(page.locator(".active-filter-chip")).toContainText("VIPC portfolio organizations");
  await expect(page.locator(".result-row .affiliation-tag")).toHaveCount(39);
  const href = await page.locator("#directory-link").getAttribute("href");
  expect(href).toContain("portfolio=vipc");
  await page.locator("#directory-link").click();
  await expect(page.getByLabel("VIPC portfolio organizations only")).toBeChecked();
  await expect(page.locator(".directory-heading h2")).toHaveText("39 matching assets");
});

test("portfolio profiles preserve review separation and fit phone and desktop widths", async ({ page }) => {
  for (const width of [390, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/assets/allocortech/");
    await expect(page.locator(".detail-header .affiliation-tag")).toHaveText("VIPC portfolio organization");
    await expect(page.locator(".location-section")).toContainText("440 N Commerce Ave");
    await expect(page.locator(".location-section")).toContainText("Site or campus");
    await expect(page.getByRole("link", { name: "Visit website", exact: true }))
      .toHaveAttribute("href", "https://www.allocor.tech/");
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    await expect(page.locator(".detail-header")).not.toContainText("Editorially reviewed");
  }
  await page.goto("/assets/leaf/");
  await expect(page.getByRole("link", { name: "Visit website", exact: true })).toHaveCount(0);
  await expect(page.locator(".overview-section")).toContainText("does not identify an official company website");
});
