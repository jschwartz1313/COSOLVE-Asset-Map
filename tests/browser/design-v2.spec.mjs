import { expect, test } from '@playwright/test';

test.skip(!process.env.COSOLVE_MULTISTATE_QA_USERNAME || !process.env.COSOLVE_MULTISTATE_QA_PASSWORD,
  'Requires the isolated owner preview account.');

async function login(page, username = process.env.COSOLVE_MULTISTATE_QA_USERNAME) {
  await page.goto('/login/');
  await page.locator('input[name="login"]').fill(username);
  await page.locator('input[name="password"]').fill(process.env.COSOLVE_MULTISTATE_QA_PASSWORD);
  await page.getByRole('button', {name:'Sign in',exact:true}).click();
}

async function ready(page) {
  await expect(page.locator('[data-map-app]')).toHaveAttribute('aria-busy','false');
}

async function fits(page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const bad = await page.locator('h1, h2, h3, .button, .experience-switch button, .primary-nav > a')
    .evaluateAll(elements => elements.filter(el => el.getClientRects().length
      && getComputedStyle(el).textOverflow !== 'ellipsis' && el.scrollWidth > el.clientWidth + 2)
      .map(el => el.textContent));
  expect(bad).toEqual([]);
}

test('2.0 is reversible, preserves data and loads its navigation assets', async ({page}, info) => {
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await login(page);
  await ready(page);
  const original = await (await page.request.get('/api/assets.geojson')).json();
  await expect(page.locator('body')).not.toHaveClass(/is-v2/);
  await page.getByRole('button',{name:'2.0',exact:true}).click();
  await expect(page.locator('body')).toHaveClass(/is-v2/);
  await ready(page);
  expect((await (await page.request.get('/api/assets.geojson')).json()).features).toEqual(original.features);
  await expect(page.locator('#result-count')).toHaveText(String(original.result_count));
  for (const img of await page.locator('.v2-icon').all()) {
    expect(await img.evaluate(el=>el.complete && el.naturalWidth > 0)).toBe(true);
  }
  await fits(page);
  const toolbar=await page.locator('.map-toolbar').boundingBox();
  const map=await page.locator('#map').boundingBox();
  expect(toolbar.y+toolbar.height).toBeLessThanOrEqual(map.y+1);
  const tools=await page.locator('.map-tools').boundingBox();
  expect(tools.y+tools.height).toBeLessThanOrEqual(toolbar.y+toolbar.height+1);
  await page.screenshot({path:info.outputPath('v2-map.png'),animations:'disabled'});
  await page.getByRole('button',{name:'Current',exact:true}).click();
  await expect(page.locator('body')).not.toHaveClass(/is-v2/);
  await expect(page.locator('link[href*="experience-v2.css"]')).toHaveCount(0);
  await expect(page.locator('#result-count')).toHaveText(String(original.result_count));
  expect(errors).toEqual([]);
});

test('2.0 keeps filters, right-side tools, peer states, directory and comparison working', async ({page},info)=>{
  await login(page);
  await page.getByRole('button',{name:'2.0',exact:true}).click();
  await ready(page);
  if(await page.locator('.filter-open').isVisible()) await page.locator('.filter-open').click();
  await page.getByLabel('State inventory',{exact:true}).selectOption('ohio');
  await ready(page);
  await expect(page.locator('[data-map-app]')).toHaveAttribute('data-basemap','street');
  await page.locator('.map-analysis > summary').click();
  await expect(page.locator('.map-analysis-options')).toBeVisible();
  await page.locator('#select-polygon').click();
  await expect(page.locator('.map-analysis')).toHaveAttribute('open','');
  const stage=await page.locator('#map').boundingBox();
  for(const [x,y] of [[.18,.55],[.38,.55],[.3,.78]]) {
    await page.mouse.click(stage.x+stage.width*x,stage.y+stage.height*y);
  }
  const finish=page.locator('#finish-polygon');
  await expect(finish).toBeVisible();
  const box=await finish.boundingBox();
  expect(box.x+box.width/2).toBeGreaterThan(page.viewportSize().width/2);
  await page.locator('#cancel-polygon').click();
  await page.locator('.map-analysis > summary').click();
  await page.getByRole('link',{name:'Directory',exact:true}).first().click();
  await expect(page).toHaveURL(/states\/ohio\/directory/);
  await expect(page.locator('body')).toHaveClass(/is-v2/);
  await page.locator('[data-compare-asset]').nth(0).check();
  await page.locator('[data-compare-asset]').nth(1).check();
  await expect(page.locator('[data-comparison-assets] li')).toHaveCount(2);
  await fits(page);
  await page.screenshot({path:info.outputPath('v2-directory.png'),animations:'disabled'});
  await page.getByRole('link',{name:'Compare selected assets',exact:true}).click();
  await expect(page.locator('.asset-comparison')).toBeVisible();
  await fits(page);
  await page.screenshot({path:info.outputPath('v2-comparison.png'),animations:'disabled'});
  await page.goto('/assets/nasa-langley-roam-uas-operations-center/');
  await expect(page.locator('.profile-photo img')).toHaveJSProperty('complete',true);
  await fits(page);
  await page.screenshot({path:info.outputPath('v2-profile.png'),fullPage:true,animations:'disabled'});
  for(const path of ['/test-sites/','/manufacturing/','/regions/compare/','/about-data/','/saved-views/']) {
    await page.goto(path);
    await expect(page.locator('body')).toHaveClass(/is-v2/);
    await fits(page);
  }
});

test('other accounts have neither state selection nor the 2.0 button',async({page})=>{
  await login(page,'ui-denied');
  await expect(page.locator('.experience-switch')).toHaveCount(0);
  await expect(page.locator('[data-state-switcher]')).toHaveCount(0);
  expect((await page.request.get('/states/ohio/map/')).status()).toBe(404);
});

test('2.0 print and presentation retain the map without the navigation rail',async({page},info)=>{
  await login(page);
  await page.getByRole('button',{name:'2.0',exact:true}).click();
  await ready(page);
  await page.locator('.map-actions > summary').click();
  await page.locator('#presentation-view').click();
  await expect(page.locator('body')).toHaveClass(/presentation-mode/);
  await expect(page.locator('.site-header')).toBeHidden();
  const map=await page.locator('#map').boundingBox();
  expect(map.x).toBe(0);
  expect(Math.round(map.width)).toBe(page.viewportSize().width);
  await page.locator('#exit-presentation').click();
  await expect(page.locator('.experience-switch')).toBeVisible();
  await page.emulateMedia({media:'print'});
  await page.evaluate(()=>window.dispatchEvent(new Event('beforeprint')));
  await expect(page.locator('.primary-nav')).toBeHidden();
  await expect(page.locator('.experience-switch')).toBeHidden();
  await expect(page.locator('.map-legend')).toBeVisible();
  const printedMap=await page.locator('#map').boundingBox();
  const legend=await page.locator('.map-legend').boundingBox();
  expect(printedMap.height).toBeGreaterThan(650);
  expect(legend.y).toBeGreaterThanOrEqual(printedMap.y);
  expect(legend.y+legend.height).toBeLessThanOrEqual(printedMap.y+printedMap.height);
  await expect.poll(async()=>page.locator('.leaflet-tile-loaded').evaluateAll(images=>{
    const map=document.querySelector('#map').getBoundingClientRect();
    const tiles=images.map(image=>image.getBoundingClientRect());
    return Math.min(...tiles.map(tile=>tile.left))<=map.left
      && Math.max(...tiles.map(tile=>tile.right))>=map.right
      && Math.min(...tiles.map(tile=>tile.top))<=map.top
      && Math.max(...tiles.map(tile=>tile.bottom))>=map.bottom;
  })).toBe(true);
  await page.screenshot({path:info.outputPath('v2-print.png'),animations:'disabled'});
  await page.emulateMedia({media:'screen'});
  await fits(page);
});
