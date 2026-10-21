import { expect, test } from "@playwright/test";
import { publicAssetCount } from "./helpers.mjs";

async function expectLightDesign(page) {
  await expect(page.locator("html")).toHaveCSS("color-scheme", "light");
  await expect(page.locator(".site-header")).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(page.locator(".appearance-menu, [data-theme-choice], [data-showcase-cover], .theme-page-visual"))
    .toHaveCount(0);
}

test("the standard light design preserves map data and contiguous panels", async ({ page }, testInfo) => {
  const total = await publicAssetCount(page);
  const appearanceRequests = [];
  page.on("request", (request) => {
    if (/\/img\/themes\/|\/themes\.[^/]*css|\/theme-switcher\.[^/]*js/.test(request.url())) {
      appearanceRequests.push(request.url());
    }
  });
  await page.goto("/map/");
  await expect(page.locator("#result-count")).toHaveText(String(total));
  await expectLightDesign(page);
  if (page.viewportSize().width <= 650) {
    await expect(page.locator('[data-panel-resizer="left"]')).toBeHidden();
    await expect(page.locator('[data-panel-resizer="right"]')).toBeHidden();
  } else {
    const bounds = await page.locator(".map-workspace").evaluate((workspace) =>
      [".filters-panel", '[data-panel-resizer="left"]', ".map-stage",
        '[data-panel-resizer="right"]', ".results-panel"].map((selector) => {
        const { left, right } = workspace.querySelector(selector).getBoundingClientRect();
        return { left, right };
      }));
    for (let index = 1; index < bounds.length; index += 1) {
      expect(bounds[index].left).toBeCloseTo(bounds[index - 1].right, 0);
    }
  }
  await expect.poll(() => page.locator(".result-row").evaluateAll((rows) =>
    [...new Set(rows.slice(0, 6).map((row) => getComputedStyle(row).borderLeftWidth))],
  )).toEqual(["0px"]);
  expect(appearanceRequests).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("light-map.png"), animations: "disabled" });
});

for (const savedMode of ["dark", "showcase", "showcase-light", "color"]) {
  test(`saved ${savedMode} preferences and dark devices cannot change the light design`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.addInitScript((mode) => {
      localStorage.setItem("cosolve-display-mode", mode);
    }, savedMode);
    await page.goto("/directory/?q=reactor");
    await expectLightDesign(page);
    await page.locator(".directory-row-main h3 a").first().click();
    await expectLightDesign(page);
    await page.getByRole("link", { name: "Map", exact: true }).click();
    await expectLightDesign(page);
    await expect(page.locator("#map .leaflet-tile-pane")).toHaveCSS("filter", "none");
    await page.reload();
    await expectLightDesign(page);
  });
}

test("the light design and More menu remain usable without JavaScript", async ({ browser, baseURL }) => {
  const context = await browser.newContext({ javaScriptEnabled: false, baseURL, colorScheme: "dark" });
  const page = await context.newPage();
  try {
    await page.goto("/directory/");
    await expectLightDesign(page);
    await page.locator(".navigation-menu > summary").click();
    await page.getByRole("link", { name: "About data", exact: true }).click();
    await expect(page).toHaveURL(/\/about-data\//);
    await expectLightDesign(page);
  } finally {
    await context.close();
  }
});
