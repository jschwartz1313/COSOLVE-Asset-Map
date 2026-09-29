import { expect, test } from "@playwright/test";

test("propulsion profile is searchable and fits all designs", async ({ page }, testInfo) => {
  test.setTimeout(120_000);
  await page.goto("/directory/?q=VAPF");
  await expect(page.locator(".directory-row"))
    .toContainText(["L3Harris Orange County Propulsion Manufacturing Site"]);
  const slug = "/assets/l3harris-orange-county-propulsion-manufacturing-site/";
  for (const theme of ["classic", "dark", "showcase", "showcase-light"]) {
    await page.goto(slug);
    if (await page.locator("[data-showcase-cover]").isVisible()) {
      await page.keyboard.press("Escape");
      await expect(page.locator("[data-showcase-cover]")).toBeHidden();
    }
    await page.locator(".appearance-menu > summary").click();
    await page.locator(`[data-theme-choice="${theme}"]`).click();
    if (await page.locator("[data-showcase-cover]").isVisible()) {
      await page.keyboard.press("Escape");
      await expect(page.locator("[data-showcase-cover]")).toBeHidden();
    }
    await page.goto(slug);
    await expect(page.locator(".activity-section"))
      .toContainText("not confirmed completed capacity");
    await expect(page.locator(".test-specifications")).toContainText("OSTF");
    await expect(page.locator(".test-specifications"))
      .toContainText("not a public range-booking service");
    await expect(page.locator('.detail-sidebar a[href="https://www.l3harris.com/all-capabilities/solid-rocket-motors"]'))
      .toBeVisible();
    const overflow = await page
      .locator("h1, .detail-main p, .test-spec-list dd, .detail-sidebar dd")
      .evaluateAll(elements => elements
        .filter(el => el.scrollWidth > el.clientWidth + 1)
        .map(el => el.textContent));
    expect(overflow).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth))
      .toBeLessThanOrEqual(page.viewportSize().width);
    await page.screenshot({
      path: testInfo.outputPath(`propulsion-${theme}.png`),
      fullPage: true, animations: "disabled",
    });
  }
});
