import { expect, test } from '@playwright/test';

async function openVersion(page, version) {
  if(version==='2.0') {
    test.skip(!process.env.COSOLVE_MULTISTATE_QA_USERNAME || !process.env.COSOLVE_MULTISTATE_QA_PASSWORD,
      'Requires the isolated owner preview account.');
    await page.goto('/login/');
    await page.locator('input[name="login"]').fill(process.env.COSOLVE_MULTISTATE_QA_USERNAME);
    await page.locator('input[name="password"]').fill(process.env.COSOLVE_MULTISTATE_QA_PASSWORD);
    await page.getByRole('button',{name:'Sign in',exact:true}).click();
    await page.getByRole('button',{name:'2.0',exact:true}).click();
  } else await page.goto('/map/');
  await expect(page.locator('[data-map-app]')).toHaveAttribute('aria-busy','false');
}

for(const version of ['Current','2.0']) {
  test(`${version} shows a loading message, then results or an error without getting stuck`,async({page},info)=>{
    await openVersion(page,version);
    let release;
    let pending=new Promise(resolve=>{release=resolve;});
    await page.route('**/api/assets.geojson?*',async route=>{
      await pending;
      if(new URL(route.request().url()).searchParams.get('q')==='__loading_error__') {
        await route.fulfill({status:503,body:'Unavailable'});
      } else await route.continue();
    });
    await page.goto('/map/?q=Adaptive%20Aerospace%20Group');
    await expect(page.locator('[data-assets-loading]')).toBeVisible();
    await expect(page.locator('[data-assets-loading]')).toHaveText('Loading assets...');
    await expect(page.locator('[data-result-count-summary]')).toBeHidden();
    await page.screenshot({path:info.outputPath(`loading-${version}.png`),animations:'disabled'});
    release();
    await expect(page.locator('[data-map-app]')).toHaveAttribute('aria-busy','false');
    await expect(page.locator('#asset-results-title')).toHaveText('1 asset');
    await expect(page.locator('[data-assets-loading]')).toBeHidden();
    pending=new Promise(resolve=>{release=resolve;});
    await page.goto('/map/?q=__loading_error__');
    await expect(page.locator('[data-assets-loading]')).toBeVisible();
    release();
    await expect(page.locator('#map-status')).toContainText('could not be loaded');
    await expect(page.locator('[data-assets-loading]')).toBeHidden();
    await expect(page.locator('#asset-results-title')).toHaveText('0 assets');
    await expect(page.locator('#result-list .empty-state')).toContainText('temporarily unavailable');
    await page.unroute('**/api/assets.geojson?*');
    await page.goto('/map/?q=Adaptive%20Aerospace%20Group');
    await expect(page.locator('#asset-results-title')).toHaveText('1 asset');
    await expect(page.locator('[data-assets-loading]')).toBeHidden();
  });

  test(`${version} keeps the dropdown focus outline inside the scrollable panel`,async({page},info)=>{
    await openVersion(page,version);
    if(await page.locator('.filter-open').isVisible()) {
      await page.locator('.filter-open').click();
      await expect(page.locator('.filters-panel')).toHaveCSS('transform','matrix(1, 0, 0, 1, 0, 0)');
    }
    const select=page.getByRole('combobox',{name:'Find resources',exact:true});
    await select.press('Home');
    const wrapper=select.locator('..');
    await expect(wrapper).toHaveCSS('outline-style','solid');
    await expect(wrapper).toHaveCSS('outline-width','2px');
    await expect(wrapper).toHaveCSS('outline-offset','-2px');
    await expect(select).toBeFocused();
    const contained=await wrapper.evaluate(el=>{
      const box=el.getBoundingClientRect();
      const panel=el.closest('.filter-fields-scroll').getBoundingClientRect();
      return box.left>=panel.left && box.right<=panel.right+1;
    });
    expect(contained).toBe(true);
    await page.screenshot({path:info.outputPath(`focus-${version}.png`),animations:'disabled'});
    const search=page.locator('#asset-filters input[name="q"]');
    await search.press('Home');
    await expect(search).toHaveCSS('outline-offset','-2px');
  });
}
