import { expect, test } from "@playwright/test";

test("resource filters persist between map and directory and clear completely", async ({ page }) => {
  await page.goto("/map/?purpose=testing&test_specs=1&min_runway=2500");
  await expect(page.locator("#result-count")).toHaveText("1");
  await expect(page.locator(".result-row")).toContainText("MARS");
  await expect(page.locator("[data-active-filter-bar]")).toContainText("Test sites and environments");
  await expect(page.locator("[data-applied-filter-count]")).toHaveText("3");
  await page.locator("#directory-link").click();
  await expect(page.locator(".directory-row")).toHaveCount(1);
  await expect(page.locator('select[name="purpose"]')).toHaveValue("testing");
  await expect(page.locator('input[name="min_runway"]')).toHaveValue("2500");
  await page.getByRole("link", { name: "View on map", exact: true }).click();
  await expect(page.locator("#result-count")).toHaveText("1");
  await page.locator("[data-clear-active-filters]").click();
  await expect(page.locator("[data-active-filter-bar]")).toBeHidden();
  await expect(page).toHaveURL(/\/map\/$/);
  expect(Number(await page.locator("#result-count").textContent())).toBeGreaterThan(500);
});

test("project status and published specifications are visible", async ({ page }) => {
  await page.goto("/map/?purpose=projects&activity=pilot");
  await expect(page.locator(".result-row").first()).toBeVisible();
  await expect(page.locator(".result-row .activity-label").first()).toHaveText("Pilot or demonstration");
  await page.goto("/assets/virginia-tech-drone-park/");
  await expect(page.locator(".test-specifications")).toContainText("300 x 120 x 85");
  await expect(page.locator(".test-specifications")).toContainText("Not documented");
  await expect(page.locator(".test-specifications a")).toHaveAttribute("href", /ictas\.vt\.edu/);
});

test("new resource controls and connection routes fit all four designs", async ({ page }, testInfo) => {
  test.setTimeout(90_000);
  for (const theme of ["classic", "dark", "showcase", "showcase-light"]) {
    await page.goto("/map/?test_specs=1");
    const cover = page.locator("[data-showcase-cover]");
    if (await cover.isVisible()) await page.locator("[data-showcase-enter]").first().click();
    await page.locator(`[data-theme-choice="${theme}"]`).click();
    if (await cover.isVisible()) await page.locator("[data-showcase-enter]").first().click();
    if (await page.locator(".filter-open").isVisible()) await page.locator(".filter-open").click();
    await expect(page.locator(".project-site-fields")).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath(`resource-${theme}.png`), fullPage: true });
    await page.goto("/connect/");
    if (await cover.isVisible()) await page.locator("[data-showcase-enter]").first().click();
    await expect(page.getByRole("heading", { name: "Get connected", exact: true })).toBeVisible();
    await expect(page.locator(".connection-row")).toHaveCount(5);
    const overflows = await page.locator(".connection-row h2, .connection-row p, .test-spec-list dd")
      .evaluateAll((elements) => elements.filter((el) => el.scrollWidth > el.clientWidth + 1)
        .map((el) => el.textContent));
    expect(overflows).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth))
      .toBeLessThanOrEqual(page.viewportSize().width);
    await page.screenshot({ path: testInfo.outputPath(`connect-${theme}.png`), fullPage: true });
  }
});
