import { expect, test } from "@playwright/test";

const face = (select) => select.locator("..").locator(".filter-select-value");

test("long filter selections fit a narrow panel", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/map/?purpose=business&record_type=operating-environment&activity=undocumented");
  await page.locator(".panel-resizer-left").press("Home");
  await expect(page.locator(".filters-panel")).toHaveCSS("width", "220px");
  const resource = page.getByRole("combobox", { name: "Find resources", exact: true });
  await expect(face(resource)).toHaveText("Business support and partnerships");
  await expect(face(resource)).toHaveCSS("font-size", "13px");
  await expect(face(resource)).toHaveAttribute("aria-hidden", "true");
  for (const select of await page.locator("#asset-filters select").all()) {
    const options = await select.locator("option").evaluateAll((options) =>
      options.map((el) => ({ value: el.value, label: el.label })));
    for (const option of options) {
      await select.selectOption(option.value);
      await expect(face(select)).toHaveText(option.label);
      const fits = await face(select).evaluate((el) =>
        el.scrollWidth <= el.clientWidth && el.scrollHeight <= el.clientHeight);
      expect(fits, option.label).toBe(true);
    }
  }
  await resource.selectOption("business");
  await page.screenshot({ path: testInfo.outputPath("narrow-filters-light.png"), animations: "disabled" });
});

test("native keyboard selection and filter resets keep the displayed value synchronized", async ({ page }) => {
  await page.goto("/map/?purpose=business");
  if (await page.locator(".filter-open").isVisible()) await page.locator(".filter-open").click();
  const resource = page.getByRole("combobox", { name: "Find resources", exact: true });
  await expect(face(resource)).toHaveText("Business support and partnerships");
  await resource.press("Home");
  await resource.press("ArrowDown");
  const label = await resource.evaluate((el) => el.selectedOptions[0].label);
  await expect(face(resource)).toHaveText(label);
  await resource.selectOption("testing");
  await page.locator("#asset-filters button[type=submit]").click();
  await expect(page).toHaveURL(/purpose=testing/);
  if (await page.locator(".filter-open").isVisible()) await page.locator(".filter-open").click();
  await page.locator("#asset-filters").getByRole("button", { name: "Clear all", exact: true }).click();
  await expect(face(resource)).toHaveText("All resources");
  await expect(page).not.toHaveURL(/purpose=/);
  await page.goBack();
  if (await page.locator(".filter-open").isVisible()) await page.locator(".filter-open").click();
  await expect(resource).toHaveValue("testing");
  await expect(face(resource)).toHaveText("Test sites and environments");
  await page.goBack();
  if (await page.locator(".filter-open").isVisible()) await page.locator(".filter-open").click();
  await expect(resource).toHaveValue("business");
  await expect(face(resource)).toHaveText("Business support and partnerships");
});

test("directory filters and sorting preserve native form submissions", async ({ page }, testInfo) => {
  await page.goto("/directory/?purpose=business&sort=type");
  const form = page.locator(".directory-filters form");
  const resource = form.getByRole("combobox", { name: "Find resources", exact: true });
  await expect(face(resource)).toHaveText("Business support and partnerships");
  await expect(form.locator(".filter-select.is-enhanced")).toHaveCount(5);
  await resource.selectOption("workforce");
  await form.getByRole("button", { name: "Apply filters", exact: true }).click();
  await expect(resource).toHaveValue("workforce");
  expect(new URL(page.url()).searchParams.get("sort")).toBe("type");
  await expect(face(resource)).toHaveText("Workforce and training");
  await page.screenshot({ path: testInfo.outputPath("directory-filters.png"), animations: "disabled" });
});

test("native dropdowns remain usable without JavaScript", async ({ browser, baseURL }) => {
  const context = await browser.newContext({
    javaScriptEnabled: false, baseURL, viewport: { width: 1280, height: 800 },
    isMobile: false, hasTouch: false,
  });
  const page = await context.newPage();
  try {
    for (const path of ["/map/", "/directory/"]) {
      await page.goto(path);
      const resource = page.getByRole("combobox", { name: "Find resources", exact: true });
      await expect(resource).toBeVisible();
      await expect(resource).toHaveCSS("opacity", "1");
      await expect(page.locator(".filter-select.is-enhanced")).toHaveCount(0);
      await resource.selectOption("business");
      await page.getByRole("button", { name: "Apply filters", exact: true }).click();
      await expect(resource).toHaveValue("business");
    }
  } finally {
    await context.close();
  }
});
