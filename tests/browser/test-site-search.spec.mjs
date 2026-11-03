import {test, expect} from '@playwright/test';

test('aircraft criteria distinguish documented matches, strict conflicts and unknowns', async ({page},testInfo) => {
  await page.goto('/test-sites/');
  await expect(page.getByRole('heading', {name:'Find a test site'})).toBeVisible();
  await page.getByLabel('Aircraft weight (lb)', {exact:true}).fill('54.99');
  await page.getByLabel('Results', {exact:true}).selectOption('match');
  await page.getByRole('button', {name:'Compare sites',exact:true}).click();
  await expect(page.locator('.test-site-result')).toHaveCount(1);
  await expect(page.locator('.test-site-result')).toContainText('Xelevate Leesburg');
  await expect(page.locator('.test-site-result')).toContainText('Documented criteria match');
  if (testInfo.project.name === 'mobile-chromium') {
    await expect(page.locator('#test-results-heading')).toBeInViewport();
    await expect(page.getByRole('link',{name:'Edit requirements'})).toBeVisible();
  }
  await page.getByLabel('Aircraft weight (lb)', {exact:true}).fill('55');
  await page.getByLabel('Results', {exact:true}).selectOption('conflict');
  await page.getByRole('button', {name:'Compare sites',exact:true}).click();
  await expect(page.locator('.test-site-result')).toHaveCount(1);
  await expect(page.locator('.test-site-result')).toContainText('Published limit conflict');
  const download = page.waitForEvent('download');
  await page.getByRole('link', {name:'Export comparison CSV'}).click();
  expect((await download).suggestedFilename()).toBe('cosolve-test-site-comparison.csv');
  await page.getByRole('link', {name:'Clear',exact:true}).click();
  await page.getByLabel('Aircraft span / width (ft)', {exact:true}).fill('12');
  await page.getByLabel('Results', {exact:true}).selectOption('unknown');
  await page.getByRole('button', {name:'Compare sites',exact:true}).click();
  await expect(page.locator('.test-site-result').first()).toContainText('Needs confirmation');
});

test('criteria and long labels fit narrow and wide screens', async ({page}, testInfo) => {
  for (const width of [320,390,720,880,1280]) {
    await page.setViewportSize({width,height:900});
    await page.goto('/test-sites/?weight=55&span=12&launch=vertical&activity=counter-uas&access=commercial');
    const overflow = await page.locator('.test-sites-page h1,.test-sites-page h2,.test-sites-page h3,.test-sites-page p,.test-sites-page dd,.filter-select-value,.test-outcome').evaluateAll(elements => elements.filter(el => el.getClientRects().length && el.scrollWidth > el.clientWidth + 1).map(el=>el.textContent));
    expect(overflow).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    await expect(page.locator('.test-site-result').first()).toBeVisible();
    await page.screenshot({path:testInfo.outputPath(`test-sites-${width}.png`),fullPage:true});
  }
});

test('map access filter survives URL reload and clearing', async ({page}) => {
  await page.goto('/map/?access=partnership');
  await expect(page.locator('#asset-results-title')).toContainText('1 asset');
  await expect(page.locator('.result-list')).toContainText('MITRE National Range');
  await page.reload();
  await expect(page.locator('#asset-results-title')).toContainText('1 asset');
  await page.locator('[data-clear-active-filters]').click();
  await expect(page.locator('#asset-results-title')).toContainText('574 assets');
});

test('access filter is also a directory control and new links do not replace the site', async ({page}) => {
  await page.goto('/directory/?access=restricted');
  await expect(page.locator('.directory-row')).toHaveCount(1);
  await expect(page.locator('.directory-row')).toContainText('MARS');
  await expect(page.getByLabel('Documented test-site access')).toHaveValue('restricted');
  await page.getByRole('link',{name:'Compare aircraft requirements'}).click();
  await expect(page).toHaveURL(/\/test-sites\/$/);
});
