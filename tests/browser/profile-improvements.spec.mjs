import { expect, test } from "@playwright/test";

test("misspelled names find the same asset in map and directory", async ({ page }, testInfo) => {
  await page.goto("/map/");
  const filtersButton = page.getByRole("button", { name: "Open filters" });
  if (await filtersButton.isVisible()) await filtersButton.click();
  await page.locator('input[name="q"]').fill("reactor");
  await page.locator('#asset-filters button[type="submit"]').click();
  await expect(page.locator(".result-row h3"))
    .toContainText(["REaKTOR Technology Innovation Center"]);
  await page.screenshot({ path: testInfo.outputPath("reactor-map.png"), animations: "disabled" });
  await page.locator("#directory-link").click();
  await expect(page.locator('input[name="q"]')).toHaveValue("reactor");
  await expect(page.locator(".directory-row").first())
    .toContainText("REaKTOR Technology Innovation Center");
  await page.screenshot({ path: testInfo.outputPath("reactor-directory.png"), animations: "disabled" });
});

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
  await page.locator(".supporting-disclosure summary").click();
  await expect(page.locator(".location-evidence")).toContainText("Published reference coordinates");
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

test("directory website links open a new tab and preserve the asset profile", async ({ page, context }) => {
  await page.goto("/directory/?q=Norfolk%20International%20Airport");
  const assetLink = page.locator(".directory-row h3 a").first();
  await expect(assetLink).not.toHaveAttribute("target", "_blank");
  await assetLink.click();
  await expect(page).toHaveURL(/\/assets\/norfolk-intl\/$/);

  const profileURL = page.url();
  const website = page.getByRole("link", { name: "Visit website", exact: true });
  const websiteURL = await website.getAttribute("href");
  await expect(website).toHaveAttribute("target", "_blank");
  await expect(website).toHaveAttribute("rel", "noopener noreferrer");
  await context.route(websiteURL, (route) => route.fulfill({
    contentType: "text/html",
    body: "<!doctype html><title>Official airport website</title><h1>Airport website</h1>",
  }));

  const popupPromise = page.waitForEvent("popup");
  await website.click();
  const websiteTab = await popupPromise;
  await expect(websiteTab).toHaveURL(websiteURL);
  await expect(websiteTab.getByRole("heading", { name: "Airport website" })).toBeVisible();
  expect(await websiteTab.evaluate(() => window.opener === null)).toBe(true);
  await expect(page).toHaveURL(profileURL);
  await expect(page.getByRole("heading", { name: "Norfolk International Airport", exact: true }))
    .toBeVisible();
  await websiteTab.close();
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

test("operator details and location evidence fit the standard design", async ({ page }, testInfo) => {
  test.setTimeout(120_000);
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
    path: testInfo.outputPath("profile-light.png"), fullPage: true, animations: "disabled",
  });
});
