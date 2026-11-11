import {expect,test} from '@playwright/test';

const KEY='cosolve-asset-comparison-v1';
const names=page=>page.locator('[data-comparison-assets] [data-comparison-name]');
const tray=page=>page.locator('[data-comparison-tray]');
const selection=page=>page.evaluate(key=>JSON.parse(localStorage.getItem(key)||'[]'),KEY);

async function restore(page,values,query='Kollmorgen') {
  await page.goto(`/directory/?q=${encodeURIComponent(query)}`);
  await page.evaluate(({key,values})=>localStorage.setItem(key,JSON.stringify(values)),{key:KEY,values});
  await page.reload();
}

async function fits(page) {
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize().width);
  const overflow=await tray(page).locator('li,a,button').evaluateAll(elements=>elements.filter(el=>
    el.getClientRects().length&&el.scrollWidth>el.clientWidth+1).map(el=>el.textContent));
  expect(overflow).toEqual([]);
}

test('selected names survive filters and reloads and can be removed without revisiting a record',async({page})=>{
  await page.goto('/directory/?q=Allocortech');
  await page.getByRole('checkbox',{name:'Compare Allocortech',exact:true}).check();
  await expect(names(page)).toHaveText(['Allocortech']);
  await page.goto('/directory/?q=Kollmorgen');
  await expect(names(page)).toHaveText(['Allocortech']);
  await page.locator('[data-compare-asset]').first().check();
  await expect(names(page)).toHaveText(['Allocortech','Kollmorgen Radford Motion Systems']);
  await page.reload();
  await expect(names(page)).toHaveText(['Allocortech','Kollmorgen Radford Motion Systems']);
  await tray(page).getByRole('button',{name:'Remove Allocortech from comparison',exact:true}).click();
  await expect(names(page)).toHaveText(['Kollmorgen Radford Motion Systems']);
  await expect(tray(page)).toContainText('1 selected');
  await page.goto('/directory/?q=Allocortech');
  await expect(page.getByRole('checkbox',{name:'Compare Allocortech',exact:true})).not.toBeChecked();
  await expect(names(page)).toHaveText(['Kollmorgen Radford Motion Systems']);
  await tray(page).getByRole('link',{name:'Compare selected assets',exact:true}).click();
  await expect(page.locator('.asset-comparison caption')).toHaveText('1 selected asset');
  await expect(page.locator('.asset-comparison')).not.toContainText('Allocortech');
});

test('pagination and asset profiles keep the same named selection',async({page})=>{
  await page.goto('/directory/');
  const chosen=[];
  for(const index of [0,2]){
    const input=page.locator('[data-compare-asset]').nth(index);
    chosen.push(await input.getAttribute('data-compare-name'));
    await input.check();
  }
  let requests=0;
  page.on('request',request=>{if(new URL(request.url()).pathname==='/compare/selection/')requests++;});
  await page.getByRole('link',{name:'Next',exact:true}).click();
  await expect(names(page)).toHaveText(chosen);
  expect(requests).toBe(1);
  const next=page.locator('[data-compare-asset]').first();
  chosen.push(await next.getAttribute('data-compare-name'));
  await next.check();
  await expect(names(page)).toHaveText(chosen);
  await names(page).first().click();
  await expect(page.locator('.detail-header h1')).toHaveText(chosen[0]);
  await expect(names(page)).toHaveText(chosen);
  await page.getByRole('button',{name:'Remove from comparison',exact:true}).click();
  await expect(names(page)).toHaveText(chosen.slice(1));
  await page.goBack();
  await expect(names(page)).toHaveText(chosen.slice(1));
});

test('older saved selections resolve names and remove unavailable entries',async({page})=>{
  await restore(page,['allocortech','missing-asset']);
  await expect(names(page)).toHaveText(['Allocortech']);
  await expect(tray(page)).toContainText('1 selected');
  expect(await selection(page)).toEqual(['allocortech']);
  await expect(tray(page).locator('[data-comparison-status]')).toContainText('unavailable asset was removed');
});

test('name loading failures preserve selections and retry recovers the list',async({page})=>{
  let fail=true;
  await page.route('**/compare/selection/**',route=>fail?route.abort():route.continue());
  await restore(page,['allocortech']);
  await expect(tray(page).locator('[data-comparison-name-error]')).toBeVisible();
  await expect(names(page)).toHaveText(['Asset name unavailable']);
  expect(await selection(page)).toEqual(['allocortech']);
  fail=false;
  await tray(page).getByRole('button',{name:'Retry',exact:true}).click();
  await expect(names(page)).toHaveText(['Allocortech']);
  await expect(tray(page).locator('[data-comparison-name-error]')).toBeHidden();
});

test('a delayed name response cannot restore a cleared selection',async({page})=>{
  let release;
  const held=new Promise(resolve=>{release=resolve;});
  let requested;
  const started=new Promise(resolve=>{requested=resolve;});
  await page.route('**/compare/selection/**',async route=>{
    requested();
    await held;
    await route.fulfill({json:{assets:[{slug:'allocortech',name:'Allocortech',url:'/assets/allocortech/'}]}});
  });
  await restore(page,['allocortech']);
  await started;
  await expect(names(page)).toHaveText(['Loading asset name\u2026']);
  await tray(page).getByRole('button',{name:'Clear selection',exact:true}).click();
  release();
  await page.waitForLoadState('networkidle');
  await expect(names(page)).toHaveCount(0);
  await expect(tray(page)).toContainText('0 selected');
  expect(await selection(page)).toEqual([]);
});

test('five full asset names and remove controls fit desktop, tablet and small phones',async({page},testInfo)=>{
  test.setTimeout(90000);
  for(const width of [320,390,768,1440]){
    await page.setViewportSize({width,height:900});
    await page.goto('/directory/');
    if(await tray(page).locator('[data-comparison-clear]').isVisible())await tray(page).locator('[data-comparison-clear]').click();
    const chosen=[];
    for(let index=0;index<5;index++){
      const input=page.locator('[data-compare-asset]').nth(index);
      chosen.push(await input.getAttribute('data-compare-name'));
      await input.check();
    }
    await expect(names(page)).toHaveText(chosen);
    await expect(page.locator('[data-compare-asset]').nth(5)).toBeDisabled();
    await fits(page);
    await tray(page).screenshot({path:testInfo.outputPath(`comparison-names-${width}.png`)});
  }
});

test('names are rendered as text and keyboard removal keeps a useful focus',async({page})=>{
  const label='A <img src=x onerror=alert(1)> & "quoted" asset';
  await page.route('**/compare/selection/**',route=>route.fulfill({json:{assets:[
    {slug:'allocortech',name:label,url:'/assets/allocortech/'},
  ]}}));
  await restore(page,['allocortech']);
  await expect(names(page)).toHaveText([label]);
  await expect(tray(page).locator('img')).toHaveCount(0);
  await fits(page);
  const remove=tray(page).getByRole('button',{name:`Remove ${label} from comparison`,exact:true});
  await remove.focus();
  await remove.press('Enter');
  await expect(tray(page).getByRole('link',{name:'Compare assets',exact:true})).toBeFocused();
  await expect(names(page)).toHaveCount(0);
});

test('selection names and checkboxes stay synchronized between browser tabs',async({page})=>{
  const other=await page.context().newPage();
  try{
    await page.goto('/directory/?q=Allocortech');
    await other.goto('/directory/?q=Kollmorgen');
    await page.getByRole('checkbox',{name:'Compare Allocortech',exact:true}).check();
    await expect(names(other)).toHaveText(['Allocortech']);
    await other.locator('[data-compare-asset]').first().check();
    await expect(names(page)).toHaveText(['Allocortech','Kollmorgen Radford Motion Systems']);
    await tray(other).getByRole('button',{name:'Remove Allocortech from comparison',exact:true}).click();
    await expect(page.getByRole('checkbox',{name:'Compare Allocortech',exact:true})).not.toBeChecked();
    await expect(names(page)).toHaveText(['Kollmorgen Radford Motion Systems']);
  }finally{await other.close();}
});

test('slow script loading keeps selection controls inactive until ready',async({page})=>{
  let release;
  const held=new Promise(resolve=>{release=resolve;});
  await page.route('**/asset-comparison-state.js*',async route=>{
    await held;
    await route.continue();
  });
  try{
    await page.goto('/directory/?q=Allocortech',{waitUntil:'commit'});
    const input=page.getByRole('checkbox',{name:'Compare Allocortech',exact:true});
    await expect(input).toBeVisible();
    await expect(input).toBeDisabled();
    release();
    await expect(input).toBeEnabled();
    await input.check();
    await expect(names(page)).toHaveText(['Allocortech']);
    expect(await selection(page)).toEqual(['allocortech']);
  }finally{release();}
});
