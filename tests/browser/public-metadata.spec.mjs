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
