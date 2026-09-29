import { expect, test } from "@playwright/test";

async function enterSite(page) {
  if (await page.locator("[data-showcase-cover]").isVisible()) {
    await page.locator("[data-showcase-enter]").first().click();
    await expect(page.locator("[data-showcase-cover]")).toBeHidden();
  }
}

test("practical-use searches find the relevant facilities and suppliers", async ({ page }) => {
  for (const [query, name] of [
    ["jib crane", "ODU Maritime Autonomous Systems Test Site"],
    ["AL1000", "Blue Vigil"],
    ["crashworthiness", "NASA Langley Landing and Impact Research Facility"],
    ["sensor degradation", "Global Center for Automotive Performance Simulation"],
  ]) {
    await page.goto(`/directory/?q=${encodeURIComponent(query)}`);
    await expect(page.locator(".directory-row")).toContainText([name]);
  }
});

test("historical corridor evidence and a published business contact remain distinct", async ({ page }) => {
  await page.goto("/assets/longbow-unmanned-systems-research-and-test-center/");
  await expect(page.locator(".activity-section")).toContainText("2021");
  await expect(page.locator(".activity-section")).toContainText("not confirmed");
  await expect(page.locator(".activity-section")).not.toContainText("Active");
  await expect(page.locator(".detail-sidebar")).toContainText("msterk@thelongbowgroup.com");
  await expect(page.locator(".detail-sidebar")).toContainText("901-336-6551");
});

test("new testing profiles fit desktop and mobile in all four designs", async ({ page }, testInfo) => {
  test.setTimeout(120_000);
  const profiles = [
    ["nasa-langley-landing-and-impact-research-facility", "crash-test"],
    ["virginia-tech-stability-wind-tunnel", "aeroacoustic"],
    ["global-center-for-automotive-performance-simulation", "sensor fusion"],
    ["xelevate-luray-mountain-range", "mountainous terrain"],
    ["nasa-wallops-uas-test-and-integration-facility", "bench checkout"],
  ];
  for (const theme of ["classic", "dark", "showcase", "showcase-light"]) {
    await page.goto(`/assets/${profiles[0][0]}/`);
    await enterSite(page);
    await page.locator(".appearance-menu > summary").click();
    await page.locator(`[data-theme-choice="${theme}"]`).click();
    await enterSite(page);
    for (const [slug, use] of profiles) {
      await page.goto(`/assets/${slug}/`);
      await expect(page.locator(".overview-section")).toContainText(use);
      await expect(page.locator(".test-specifications")).toContainText("2026");
      const overflow = await page
        .locator("h1, .detail-main p, .test-spec-list dd, .detail-sidebar dd")
        .evaluateAll(elements => elements
          .filter(el => el.scrollWidth > el.clientWidth + 1)
          .map(el => el.textContent));
      expect(overflow).toEqual([]);
      expect(await page.evaluate(() => document.documentElement.scrollWidth))
        .toBeLessThanOrEqual(page.viewportSize().width);
    }
    await page.screenshot({
      path: testInfo.outputPath(`testing-profiles-${theme}.png`),
      fullPage: true, animations: "disabled",
    });
  }
});
