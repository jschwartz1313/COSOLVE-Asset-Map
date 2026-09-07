import { expect, test } from "@playwright/test";

async function enterSite(page) {
  if (await page.locator("[data-showcase-cover]").isVisible()) {
    const returnsToMap = !new URL(page.url()).pathname.startsWith("/map/");
    await page.locator("[data-showcase-enter]").first().click();
    if (returnsToMap) await expect(page).toHaveURL(/\/map\//);
    await expect(page.locator("[data-showcase-cover]")).toBeHidden();
  }
}

test("capability searches find the concrete services in updated profiles", async ({ page }) => {
  await page.goto("/directory/?q=ATOMx");
  await expect(page.locator(".directory-row")).toContainText(["DroneUp"]);
  await page.goto("/directory/?q=whirl");
  await expect(page.locator(".directory-row")).toContainText(["Eagle Aviation Technologies"]);
});

test("new testing and collaboration information fits all designs", async ({ page }, testInfo) => {
  test.setTimeout(120_000);
  for (const theme of ["classic", "dark", "showcase", "showcase-light"]) {
    await page.goto("/assets/mid-atlantic-aviation-partnership/");
    await enterSite(page);
    await page.locator(`[data-theme-choice="${theme}"]`).click();
    await enterSite(page);
    await page.goto("/assets/mid-atlantic-aviation-partnership/");
    await expect(page.locator("[data-showcase-cover]")).toBeHidden();
    await expect(page.locator(".test-specifications")).toContainText("no single MAAP-wide runway");
    await expect(page.locator(".activity-section")).toContainText("Contact MAAP");
    const overflow = await page.locator("h1, .detail-main p, .test-spec-list dd, .detail-sidebar dd")
      .evaluateAll((elements) => elements.filter((el) => el.scrollWidth > el.clientWidth + 1)
        .map((el) => el.textContent));
    expect(overflow).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth))
      .toBeLessThanOrEqual(page.viewportSize().width);
    await page.screenshot({
      path: testInfo.outputPath(`capabilities-${theme}.png`),
      fullPage: true, animations: "disabled",
    });
    await page.screenshot({
      path: testInfo.outputPath(`capabilities-${theme}-viewport.png`),
      animations: "disabled",
    });
  }
});

test("development and location limitations remain visible", async ({ page }) => {
  await page.goto("/assets/agricision/");
  await expect(page.locator(".activity-section")).toContainText("In development");
  await expect(page.locator(".activity-section")).toContainText("in testing");
  await page.goto("/assets/aurora-flight-sciences/");
  await expect(page.locator(".overview-section")).toContainText("Mississippi and West Virginia");
  await page.goto("/assets/magothy-river-technologies/");
  await expect(page.locator(".overview-section")).toContainText("Maryland");
});
