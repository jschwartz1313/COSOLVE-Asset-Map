import {expect,test} from '@playwright/test';

async function assertPageFits(page) {
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize().width);
  const overflow=await page.locator('main h1,main h2,main p,main label,main button,main li').evaluateAll(
    els=>els.filter(el=>el.getClientRects().length&&getComputedStyle(el).textOverflow!=='ellipsis'&&el.scrollWidth>el.clientWidth+1).map(el=>el.textContent));
  expect(overflow).toEqual([]);
}

test('select assets from directory and compare without leaving the inventory',async({page},testInfo)=>{
  await page.goto('/directory/?q=Allocortech');
  await page.getByRole('button',{name:'Compare Allocortech',exact:true}).click();
  await expect(page.locator('[data-comparison-tray]')).toContainText('1 selected');
  await page.goto('/directory/?q=Kollmorgen');
  await page.locator('[data-compare-asset]').first().click();
  await expect(page.locator('[data-comparison-tray]')).toContainText('2 selected');
  await assertPageFits(page);
  await page.getByRole('link',{name:'Compare selected assets'}).click();
  await expect(page.locator('.asset-comparison')).toContainText('Allocortech');
  await expect(page.locator('.asset-comparison')).toContainText('Kollmorgen');
  await expect(page.getByRole('link',{name:'Export comparison CSV'})).toBeVisible();
  await assertPageFits(page);
  await page.screenshot({path:testInfo.outputPath('asset-comparison.png'),fullPage:true});
  await page.getByRole('link',{name:'Remove Allocortech from comparison',exact:true}).click();
  await page.goto('/directory/?q=Allocortech');
  await expect(page.locator('[data-comparison-tray]')).toContainText('1 selected');
  await expect(page.locator('[data-compare-asset="allocortech"]')).toHaveAttribute('aria-pressed','false');
});

test('inquiry creates a private draft and download, with contact details and no automatic email',async({page},testInfo)=>{
  await page.goto('/assets/allocortech/inquiry/');
  await page.getByLabel('Project or intended use').fill('Evaluate avionics for a coastal inspection aircraft.');
  await page.getByLabel('Aircraft, part or technical requirements').fill('Flight-control integration, environmental tests and a pilot production batch.');
  await page.getByLabel('Timing and quantities').fill('10 units, next quarter');
  await page.getByRole('button',{name:'Prepare draft',exact:true}).click();
  await expect(page.getByLabel('Message',{exact:true})).toHaveValue(/coastal inspection/);
  await expect(page.locator('main')).toContainText('Nothing is sent or saved');
  await assertPageFits(page);
  const downloadPromise=page.waitForEvent('download');
  await page.getByRole('button',{name:'Download draft',exact:true}).click();
  const download=await downloadPromise;
  expect(download.suggestedFilename()).toBe('cosolve-inquiry.txt');
  await page.screenshot({path:testInfo.outputPath('inquiry-draft.png'),fullPage:true});
});

test('comparison chooser works without browser storage',async({page})=>{
  await page.goto('/compare/');
  await page.getByLabel('Find an asset to compare').fill('Allocortech');
  await page.getByRole('button',{name:'Search',exact:true}).click();
  await page.getByRole('link',{name:'Add Allocortech',exact:true}).click();
  await expect(page.locator('.asset-comparison')).toContainText('Allocortech');
  await page.getByRole('link',{name:'Remove Allocortech from comparison',exact:true}).click();
  await expect(page.locator('main')).toContainText('No assets selected.');
});

test('manufacturing search distinguishes documented processes and unknown materials',async({page},testInfo)=>{
  await page.goto('/manufacturing/');
  await page.getByLabel('Process',{exact:true}).selectOption('cnc-machining');
  await page.getByLabel('Results',{exact:true}).selectOption('match');
  await page.getByRole('button',{name:'Compare capabilities',exact:true}).click();
  await expect(page.locator('.test-site-results')).toContainText('Institute for Advanced Learning and Research');
  await expect(page.locator('.test-site-results')).toContainText('Fulcrum Concepts Newport News Machine Shop');
  await expect(page.locator('.test-site-results')).not.toContainText('Kollmorgen Radford Motion Systems');
  await assertPageFits(page);
  await page.screenshot({path:testInfo.outputPath('manufacturing-search.png'),fullPage:true});
  await page.getByLabel('Material',{exact:true}).selectOption('titanium');
  await page.getByRole('button',{name:'Compare capabilities',exact:true}).click();
  await expect(page.locator('.empty-state')).toBeVisible();
  await page.getByLabel('Results',{exact:true}).selectOption('unknown');
  await page.getByRole('button',{name:'Compare capabilities',exact:true}).click();
  await expect(page.locator('.test-site-results')).toContainText('Needs confirmation');
  await assertPageFits(page);
});

test('invalid operator invitations do not expose assets or private data',async({page})=>{
  const response=await page.goto('/operator-review/not-a-valid-invitation/');
  expect(response.status()).toBe(404);
  await expect(page.locator('main')).toContainText('Invitation unavailable');
  expect(response.headers()['referrer-policy']).toBe('strict-origin');
  await assertPageFits(page);
});
