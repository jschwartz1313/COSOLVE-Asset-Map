import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

test("airport names remain descriptive in search, pins, exports and profiles", async ({ page }, testInfo) => {
  await page.goto("/map/?q=MFV");
  const row = page.locator(".result-row").filter({ hasText: "Accomack County Airport" });
  await expect(row).toHaveCount(1);
  await row.click();
  await expect(page.locator(".map-popup h3")).toHaveText("Accomack County Airport");
  await expect(page.locator(".map-popup a")).toHaveAttribute("href", "/assets/accomack-county/");
  await page.locator(".map-analysis summary").click();
  await page.locator("#select-extent").click();
  await expect(page.locator("#export-area")).toBeEnabled();
  await page.locator(".map-analysis summary").click();
  const downloadEvent = page.waitForEvent("download");
  await page.locator("#export-area").click();
  const download = await downloadEvent;
  expect(readFileSync(await download.path(), "utf8")).toContain("Accomack County Airport");

  await page.goto("/directory/?q=Ingalls");
  await expect(page.getByRole("heading", { name: "Ingalls Field Airport", exact: true }))
    .toBeVisible();
  await page.goto("/assets/campbell-fld/");
  await expect(page.getByRole("heading", { name: "Campbell Field Airport", exact: true }))
    .toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("airport-label.png"), fullPage: true });
});

test("long airport names wrap within their containers", async ({ page }, testInfo) => {
  await page.goto("/directory/?q=Richmond%20Executive");
  await expect(page.getByRole("heading", {
    name: "Richmond Executive-Chesterfield County Airport", exact: true,
  })).toBeVisible();
  const overflow = await page.locator(".directory-row h3, .directory-row h3 a")
    .evaluateAll((elements) => elements.filter((el) => el.scrollWidth > el.clientWidth + 1)
      .map((el) => el.textContent));
  expect(overflow).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth))
    .toBeLessThanOrEqual(page.viewportSize().width);
  await page.screenshot({ path: testInfo.outputPath("long-airport-name.png"), fullPage: true });
});
