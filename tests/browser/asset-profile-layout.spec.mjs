import { expect, test } from "@playwright/test";

const course = "/assets/blue-ridge-community-college-unmanned-systems-courses/";

test("profiles group descriptions and focus without oversized headings or boxed tags", async ({ page }) => {
  await page.goto(course);
  await expect(page.locator(".detail-header h1")).toHaveCSS(
    "font-size", page.viewportSize().width <= 760 ? "26px" : "32px",
  );
  expect((await page.locator(".detail-header").boundingBox()).height).toBeLessThan(300);
  await expect(page.locator(".overview-section h2")).toHaveText("Overview");
  await expect(page.locator(".overview-section .relevance-section"))
    .toContainText("education or credential pathway");
  await expect(page.locator(".focus-section"))
    .toContainText("Operations, maintenance, and sustainment");
  await expect(page.locator(".focus-section"))
    .toContainText("Training and experimentation");
  await expect(page.locator(".focus-section .tag-list")).toHaveCount(0);
  const classification = page.locator(".classification-section details");
  await expect(classification).not.toHaveAttribute("open");
  await classification.locator("summary").press("Enter");
  await expect(classification.getByText("Platform domains", { exact: true })).toBeVisible();
  await expect(page.locator(".location-section")).toContainText("Site or campus");
  await expect(page.getByRole("link", { name: "Visit website", exact: true })).toBeVisible();
});

test("short and detailed profiles wrap cleanly at desktop, tablet and phone sizes", async ({ page }, testInfo) => {
  for (const width of [320, 390, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    for (const slug of [
      "blue-ridge-community-college-unmanned-systems-courses",
      "xelevate-leesburg-unmanned-systems-facility",
      "norfolk-intl",
    ]) {
      await page.goto(`/assets/${slug}/`);
      const overflow = await page.locator(".detail-page h1, .detail-page h2, .detail-page p, .detail-page li, .detail-page dd, .detail-page summary")
        .evaluateAll(elements => elements.filter(el => el.getClientRects().length > 0
          && el.scrollWidth > el.clientWidth + 1).map(el => el.textContent));
      expect(overflow, `${slug} at ${width}px`).toEqual([]);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      if (slug.startsWith("blue-ridge") && [390, 1280].includes(width)) {
        await page.screenshot({ path: testInfo.outputPath(`profile-${width}.png`), fullPage: true });
      }
    }
  }
});

test("contact and location share a row below the description instead of a long sidebar", async ({ page }) => {
  for (const width of [390, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    for (const slug of [
      "blue-ridge-community-college-unmanned-systems-courses",
      "xelevate-leesburg-unmanned-systems-facility",
    ]) {
      await page.goto(`/assets/${slug}/`);
      const main = await page.locator(".detail-main").boundingBox();
      const details = await page.locator(".detail-sidebar").boundingBox();
      const contact = await page.locator(".contact-section").boundingBox();
      const location = await page.locator(".location-section").boundingBox();
      const supporting = await page.locator(".detail-supporting").boundingBox();
      expect(details.y).toBeGreaterThanOrEqual(main.y + main.height);
      expect(Math.abs(details.width - main.width)).toBeLessThan(2);
      expect(supporting.y).toBeGreaterThanOrEqual(details.y + details.height);
      if (width > 520) {
        expect(Math.abs(contact.y - location.y)).toBeLessThan(2);
        expect(location.x).toBeGreaterThanOrEqual(contact.x + contact.width);
      } else {
        expect(location.y).toBeGreaterThanOrEqual(contact.y + contact.height);
      }
    }
  }
});

test("printing includes supporting details and restores the reader's open sections", async ({ page }) => {
  await page.goto(course);
  const sources = page.locator(".sources-disclosure");
  await sources.locator("summary").click();
  const before = await page.locator(".detail-page details").evaluateAll(elements => elements.map(el => el.open));
  await page.evaluate(() => window.dispatchEvent(new Event("beforeprint")));
  await expect(page.locator(".detail-page details:not([open])")).toHaveCount(0);
  await page.emulateMedia({ media: "print" });
  await expect(page.locator(".classification-section dl")).toBeVisible();
  await expect(sources.locator(".source-list")).toBeVisible();
  await expect(page.locator(".profile-update-link")).toBeHidden();
  await page.emulateMedia({ media: "screen" });
  await page.evaluate(() => window.dispatchEvent(new Event("afterprint")));
  expect(await page.locator(".detail-page details").evaluateAll(elements => elements.map(el => el.open))).toEqual(before);
});

test("supporting profile details remain accessible without JavaScript", async ({ browser, baseURL }) => {
  const context = await browser.newContext({ javaScriptEnabled: false, baseURL });
  const page = await context.newPage();
  try {
    await page.goto(course);
    await page.locator(".classification-section summary").click();
    await expect(page.locator(".classification-section dl")).toBeVisible();
    await page.locator(".sources-disclosure summary").click();
    await expect(page.locator(".source-list")).toBeVisible();
  } finally {
    await context.close();
  }
});
