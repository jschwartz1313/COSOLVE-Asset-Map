import {test, expect} from '@playwright/test';

test('public pages omit maintenance dates without removing sources or breaking layout', async ({page}, testInfo) => {
  for (const path of [
    '/directory/', '/about-data/', '/connect/',
    '/test-sites/?weight=54.99&outcome=match',
    '/assets/mars-unmanned-aircraft-systems-airfield/',
  ]) {
    await page.goto(path);
    await expect(page.locator('body')).not.toContainText(
      /Catalog updated|Record updated|Latest source-link check|Public routes reviewed|(?:Reviewed|Checked|Link checked) [A-Z][a-z]+ \d{1,2}, \d{4}/,
    );
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize().width);
  }
  await page.getByText('Searchable site criteria', {exact:true}).click();
  await expect(page.getByRole('link', {name:'Criteria source',exact:true})).toBeVisible();
  await expect(page.locator('.test-specifications')).not.toContainText(/Reviewed|Checked/);
  await page.getByText('Supporting details', {exact:true}).click();
  await expect(page.locator('.source-list a').first()).toBeVisible();
  await expect(page.locator('.source-list')).not.toContainText('Link checked');
  const overflow = await page.locator('h1,h2,h3,.test-spec-list dd,.source-list').evaluateAll(elements =>
    elements.filter(el => el.getClientRects().length && el.scrollWidth > el.clientWidth + 1).map(el => el.textContent),
  );
  expect(overflow).toEqual([]);
  await page.screenshot({path:testInfo.outputPath('profile-without-maintenance-dates.png'),fullPage:true});
});

for (const version of ['Current', '2.0']) {
  test(`${version} keeps verification private while map tools and old saved links still work`, async ({page}, info) => {
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    if (version === '2.0') {
      test.skip(!process.env.COSOLVE_MULTISTATE_QA_USERNAME, 'Requires an isolated owner account.');
      await page.goto('/login/');
      await page.locator('input[name="login"]').fill(process.env.COSOLVE_MULTISTATE_QA_USERNAME);
      await page.locator('input[name="password"]').fill(process.env.COSOLVE_MULTISTATE_QA_PASSWORD);
      await page.getByRole('button', {name:'Sign in', exact:true}).click();
      await page.getByRole('button', {name:'2.0', exact:true}).click();
    }
    await page.goto('/map/?map_layers=assets,state,verification&map_layers_v=5');
    await expect(page.locator('[data-map-app]')).toHaveAttribute('aria-busy', 'false');
    await expect(page.locator('.result-row').first()).toBeVisible();
    await page.locator('.map-layers > summary').click();
    await expect(page.locator('#verification-layer-toggle, [data-verification-legend]')).toHaveCount(0);
    await page.locator('#precision-layer-toggle').check();
    await expect(page.locator('[data-precision-legend]')).toBeVisible();
    await expect(page.locator('.map-layers')).not.toContainText(/Verification|Review pending/);
    await page.screenshot({path:info.outputPath(`layers-${version}.png`), animations:'disabled'});
    await page.locator('.map-analysis > summary').click();
    await page.locator('#summary-region').selectOption('hampton-roads');
    await page.locator('#show-region-summary').click();
    await expect(page.locator('.insight-metrics')).toContainText('Assets');
    await expect(page.locator('.insight-metrics')).not.toContainText('Reviewed');
    expect(await page.locator('.print-analysis-report th').allTextContents()).toEqual([
      'Asset', 'Type', 'Region', 'Location precision',
    ]);
    await page.goto('/assets/mars-unmanned-aircraft-systems-airfield/');
    await page.getByText('Supporting details', {exact:true}).click();
    await expect(page.locator('.source-list a').first()).toBeVisible();
    await expect(page.locator('.source-list')).not.toContainText(/Verified|Unreviewed|Last verified|Review pending/);
    await page.goto('/about-data/');
    await expect(page.locator('.methodology-panel')).not.toContainText(/Editorial review|records pending|records reviewed/);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize().width);
    expect(errors).toEqual([]);
  });
}
