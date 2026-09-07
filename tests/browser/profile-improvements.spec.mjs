import { expect, test } from "@playwright/test";

async function enterMap(page) {
  const cover = page.locator("[data-showcase-cover]");
  if (await cover.isVisible()) await page.locator("[data-showcase-enter]").first().click();
}

test("airport codes rank the named airport first and preserve its existing URL", async ({ page }) => {
  await page.goto("/map/?q=ORF");
  await expect(page.locator(".result-row h3").first()).toHaveText("Norfolk International Airport");
  await page.locator(".result-row").first().click();
  await expect(page.locator(".map-popup")).toContainText("Airport reference point");
  await expect(page.locator(".map-popup a")).toHaveAttribute("href", "/assets/norfolk-intl/");
  await page.locator(".map-popup a").click();
  await expect(page.getByRole("heading", { name: "Norfolk International Airport", exact: true }))
    .toBeVisible();
  await expect(page.locator(".detail-sidebar")).toContainText("FAA airport reference point");
});

test("acronyms work across map and directory without losing the search", async ({ page }) => {
  await page.goto("/map/?q=KEAS");
  await expect(page.locator(".result-row h3").first())
    .toHaveText("Kentland Experimental Aerial Systems Laboratory");
  await page.locator("#directory-link").click();
  await expect(page.locator('input[name="q"]')).toHaveValue("KEAS");
  await expect(page.locator('select[name="sort"]')).toHaveValue("relevance");
  await expect(page.locator(".directory-row").first()).toContainText("Kentland");
});

test("unmapped networks remain listed without misleading point geometry", async ({ request }) => {
  const response = await request.get('/api/assets.geojson?q=Virginia%20Automated%20Corridors');
  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  const network = body.features.find((f) => f.properties.name === "Virginia Automated Corridors");
  expect(network).toBeTruthy();
  expect(network.geometry).toBeNull();
  expect(network.properties.location.role_label).toBe("Service area / multiple sites");
});

test("operator details and location evidence fit all four designs", async ({ page }, testInfo) => {
  test.setTimeout(120_000);
  for (const theme of ["classic", "dark", "showcase", "showcase-light"]) {
    await page.goto("/map/");
    await enterMap(page);
    await page.locator(`[data-theme-choice="${theme}"]`).click();
    await enterMap(page);
    await page.goto("/assets/xelevate-leesburg-unmanned-systems-facility/");
    await expect(page.locator(".test-specifications")).toContainText("66-acre");
    await expect(page.locator(".test-specifications")).toContainText("different site");
    await expect(page.locator('a[href="mailto:jburkel@xelevateus.com"]')).toBeVisible();
    const overflow = await page.locator("h1, .test-spec-list dd, .detail-sidebar dd")
      .evaluateAll((els) => els.filter((el) => el.scrollWidth > el.clientWidth + 1)
        .map((el) => el.textContent));
    expect(overflow).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth))
      .toBeLessThanOrEqual(page.viewportSize().width);
    await page.screenshot({
      path: testInfo.outputPath(`profile-${theme}.png`), fullPage: true, animations: "disabled",
    });
  }
});
