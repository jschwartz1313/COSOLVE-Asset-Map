import { expect, test } from "@playwright/test";

test("new program links lead to operator pages without leaving the catalog", async ({ page }) => {
  for (const [slug, url] of [
    ["uva-coastal-research-center-uas-operations", "https://abcrc.virginia.edu/permits-access-drones"],
    ["southern-virginia-higher-education-center-robotics-training", "https://www.svhec.org/job-training/automation/"],
    ["virginia-tech-eastern-shore-arec-drone-application-research", "https://www.arec.vaes.vt.edu/arec/eastern-shore/programs/weed-science.html"],
    ["city-of-virginia-beach-uas-program", "https://police.virginiabeach.gov/your-vbpd/initiatives/drone-as-first-responder-program"],
  ]) {
    await page.goto(`/assets/${slug}/`);
    const website = page.getByRole("link", { name: "Visit website", exact: true });
    await expect(website).toHaveAttribute("href", url);
    await expect(website).toHaveAttribute("target", "_blank");
    await expect(website).toHaveAttribute("rel", /noopener/);
  }
});

test("expanded site details fit on phones and desktop without extra sections", async ({ page }, testInfo) => {
  for (const width of [320, 390, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    for (const slug of [
      "mars-unmanned-aircraft-systems-airfield",
      "nasa-langley-certain",
      "uva-coastal-research-center-uas-operations",
    ]) {
      await page.goto(`/assets/${slug}/`);
      await expect(page.locator(".focus-section .test-specifications")).toBeVisible();
      await page.locator(".supporting-disclosure summary").click();
      const overflow = await page.locator(
        ".detail-page h1, .detail-page h2, .detail-page p, .detail-page li, .detail-page dd, .detail-page a",
      ).evaluateAll(elements => elements.filter(el => el.getClientRects().length
        && el.scrollWidth > el.clientWidth + 1).map(el => el.textContent));
      expect(overflow, `${slug} at ${width}px`).toEqual([]);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      expect(await page.locator(".detail-page h2").allTextContents())
        .toEqual(["About this asset", "Capabilities and uses", "Contact and location"]);
      await expect(page.locator(".skip-link")).not.toBeInViewport();
      if (slug === "nasa-langley-certain" && [390, 1280].includes(width)) {
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.screenshot({ path: testInfo.outputPath(`certain-${width}.png`), fullPage: true });
      }
    }
  }
});

test("island runway and office points are distinct from operating permissions", async ({ page }) => {
  await page.goto("/assets/mars-unmanned-aircraft-systems-airfield/");
  await expect(page.locator(".location-section")).toContainText("Approximate");
  const response = await page.request.get("/api/assets.geojson?q=MARS");
  expect(response.ok()).toBeTruthy();
  const feature = (await response.json()).features
    .find(item => item.properties.name === "MARS Unmanned Aircraft Systems Airfield");
  expect(feature.geometry.coordinates).toEqual([-75.43706, 37.8853]);
  await expect(page.locator(".focus-section")).toContainText("Group 3");
  await expect(page.locator(".focus-section")).toContainText("Confirm usable hangar dimensions");
  await page.goto("/assets/systems-planning-analysis/");
  await expect(page.locator(".overview-section")).toContainText("not a counter-UAS flight-test area");
});
