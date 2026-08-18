import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

const catalog = JSON.parse(
  readFileSync(new URL("../../data/virginia_real_assets.json", import.meta.url), "utf8"),
);

async function expectContiguousMapPanels(page) {
  if ((await page.viewportSize()).width <= 650) {
    await expect(page.locator('[data-panel-resizer="left"]')).toBeHidden();
    await expect(page.locator('[data-panel-resizer="right"]')).toBeHidden();
    return;
  }

  const layout = await page.locator(".map-workspace").evaluate((workspace) => {
    const filter = workspace.querySelector(".filters-panel").getBoundingClientRect();
    const leftResizer = workspace.querySelector('[data-panel-resizer="left"]').getBoundingClientRect();
    const map = workspace.querySelector(".map-stage").getBoundingClientRect();
    const rightResizer = workspace.querySelector('[data-panel-resizer="right"]').getBoundingClientRect();
    const results = workspace.querySelector(".results-panel").getBoundingClientRect();
    return {
      filterRight: filter.right,
      leftResizerLeft: leftResizer.left,
      leftResizerRight: leftResizer.right,
      mapLeft: map.left,
      mapRight: map.right,
      rightResizerLeft: rightResizer.left,
      rightResizerRight: rightResizer.right,
      resultsLeft: results.left,
    };
  });

  expect(layout.leftResizerLeft).toBeCloseTo(layout.filterRight, 0);
  expect(layout.mapLeft).toBeCloseTo(layout.leftResizerRight, 0);
  expect(layout.rightResizerLeft).toBeCloseTo(layout.mapRight, 0);
  expect(layout.resultsLeft).toBeCloseTo(layout.rightResizerRight, 0);
}

test("four presentation modes preserve the same map data and controls", async ({ page }) => {
  await page.goto("/map/");
  await expect(page.locator("#result-count")).toHaveText(String(catalog.record_count));
  await expectContiguousMapPanels(page);

  const originalWorkspace = await page.locator(".map-workspace").boundingBox();
  const originalFilters = await page.locator(".filters-panel").boundingBox();

  await page.locator('[data-theme-choice="dark"]').click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.locator('[data-theme-choice="dark"]')).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.locator("#result-count")).toHaveText(String(catalog.record_count));
  await expectContiguousMapPanels(page);
  expect(await page.locator(".map-workspace").boundingBox()).toEqual(originalWorkspace);
  expect(await page.locator(".filters-panel").boundingBox()).toEqual(originalFilters);

  await page.locator('[data-theme-choice="showcase"]').click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "showcase");
  await expect(page.locator("[data-showcase-cover]")).toBeVisible();
  await expect(page.locator(".showcase-photo")).toHaveCount(3);
  await page.locator("[data-showcase-enter]").first().click();
  await expect(page.locator("[data-showcase-cover]")).toBeHidden();
  await expect(page.locator("#result-count")).toHaveText(String(catalog.record_count));
  await expectContiguousMapPanels(page);

  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "showcase");
  await expect(page.locator("[data-showcase-cover]")).toBeHidden();

  await page.locator('[data-theme-choice="showcase-light"]').click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "showcase-light");
  await expect(page.locator('[data-theme-choice="showcase-light"]')).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.locator("[data-showcase-cover]")).toBeVisible();
  await page.locator("[data-showcase-enter]").first().click();
  await expect(page.locator("[data-showcase-cover]")).toBeHidden();
  await expect(page.locator("#result-count")).toHaveText(String(catalog.record_count));
  await expectContiguousMapPanels(page);

  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "showcase-light");
  await expect(page.locator("[data-showcase-cover]")).toBeHidden();

  await page.locator('[data-theme-choice="classic"]').click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "classic");
});

test("showcase imagery appears on supporting pages", async ({ page }) => {
  await page.goto("/directory/");
  await expect(page.locator(".directory-list")).toBeVisible();

  await page.locator('[data-theme-choice="showcase"]').click();
  await expect(page.locator("[data-showcase-cover]")).toBeVisible();
  await page.locator("[data-showcase-enter]").first().click();
  await expect(page).toHaveURL(/\/map\/$/);
  await expect(page.locator("#result-count")).toHaveText(String(catalog.record_count));
});

test("the four-mode switch remains usable on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/map/");
  const switcher = page.locator(".appearance-switcher");
  await expect(switcher).toBeVisible();
  await expect(switcher.locator("button")).toHaveCount(4);
  expect(
    await switcher.locator("button").evaluateAll((buttons) =>
      buttons.map((button) => getComputedStyle(button, "::after").content.replaceAll('"', "")),
    ),
  ).toEqual(["Current", "Dark", "Show", "Light"]);

  const switchBox = await switcher.boundingBox();
  expect(switchBox.x).toBeGreaterThanOrEqual(0);
  expect(switchBox.x + switchBox.width).toBeLessThanOrEqual(390);
  expect(switchBox.y + switchBox.height).toBeLessThanOrEqual(844);

  await page.locator('[data-theme-choice="showcase-light"]').click();
  await expect(page.locator("[data-showcase-cover]")).toBeVisible();
  const coverBox = await page.locator("[data-showcase-cover]").boundingBox();
  expect(coverBox.width).toBe(390);
  expect(coverBox.height).toBeGreaterThanOrEqual(844);
  await expect(page.locator(".showcase-topbar")).toBeVisible();
  await expect(page.locator(".showcase-hero h1")).toBeVisible();
});

test("showcase light keeps the cinematic experience in the current light palette", async ({ page }) => {
  await page.goto("/map/");
  await page.locator('[data-theme-choice="showcase-light"]').click();

  const cover = page.locator("[data-showcase-cover]");
  await expect(cover).toBeVisible();
  await expect(cover).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(cover.locator(".showcase-statement")).toHaveCSS(
    "background-color",
    "rgb(255, 255, 255)",
  );
  await expect(cover.locator('img[src*="nasa-langley-autonomous-drone"]')).toBeVisible();

  await cover.locator("[data-showcase-enter]").first().click();
  await expect(cover).toBeHidden();
  await expect(page.locator(".filters-panel")).toHaveCSS(
    "background-color",
    "rgba(255, 255, 255, 0.97)",
  );
  await expect(page.locator("#result-count")).toHaveText(String(catalog.record_count));
});

test("showcase entrance scrolls through real Virginia imagery and returns to the map", async ({ page }) => {
  await page.goto("/map/");
  await page.locator('[data-theme-choice="showcase"]').click();
  const cover = page.locator("[data-showcase-cover]");
  await expect(cover).toBeVisible();
  await expect(cover.locator('img[src*="nasa-langley-autonomous-drone"]')).toBeVisible();

  await cover.locator("[data-showcase-scroll-story]").click();
  await expect(cover.locator(".showcase-statement")).toBeInViewport();
  await cover.locator(".showcase-final").scrollIntoViewIfNeeded();
  await expect(cover.locator(".showcase-final")).toBeInViewport();
  await cover.locator(".showcase-final [data-showcase-enter]").click();

  await expect(cover).toBeHidden();
  await expect(page.locator("#result-count")).toHaveText(String(catalog.record_count));
});
