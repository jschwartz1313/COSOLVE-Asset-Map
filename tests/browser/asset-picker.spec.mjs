import {expect,test} from '@playwright/test';

const OPTIONS='**/compare/options/**';
const REAKTOR='REaKTOR Technology Innovation Center';
const KOLLMORGEN='Kollmorgen Radford Motion Systems';
const FULCRUM='Fulcrum Concepts Newport News Machine Shop';
const dialog=page=>page.getByRole('dialog',{name:'Add assets',exact:true});
const opener=page=>page.getByRole('button',{name:'Add assets',exact:true});
const search=page=>dialog(page).getByLabel('Search assets',{exact:true});
const assetType=page=>dialog(page).getByLabel('Asset type',{exact:true});
const region=page=>dialog(page).getByLabel('Region',{exact:true});
const option=(page,name)=>dialog(page).getByRole('checkbox',{name,exact:true});
const draft=page=>dialog(page).locator('[data-picker-draft]');
const remove=(page,name)=>draft(page).getByRole('button',{name:`Remove ${name} from selection`,exact:true});
const confirm=page=>dialog(page).getByRole('button',{name:/^Add selected assets(?: \(\d+\))?$/});
const selectedSlugs=page=>new URL(page.url()).searchParams.getAll('asset');

function isOptions(url,params={}) {
  const parsed=new URL(url);
  return parsed.pathname==='/compare/options/'&&Object.entries(params).every(([key,value])=>
    (parsed.searchParams.get(key)||(key==='page'?'1':''))===String(value));
}

async function seedOptions(request,params={}) {
  const response=await request.get('/compare/options/',{
    params:{q:'',record_type:'',region:'',page:1,...params},
  });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function seedAsset(request,name) {
  const data=await seedOptions(request,{q:name});
  const asset=data.assets.find(item=>item.name===name);
  expect(asset,`Seeded public asset: ${name}`).toBeTruthy();
  return asset;
}

async function renderedOptions(page,data) {
  await expect(dialog(page).getByRole('checkbox')).toHaveCount(data.assets.length);
  for(const asset of data.assets) await expect(option(page,asset.name)).toBeVisible();
}

async function optionsAfter(page,action,params={}) {
  const pending=page.waitForResponse(response=>
    response.request().method()==='GET'&&isOptions(response.url(),params));
  await action();
  const response=await pending;
  expect(response.ok()).toBeTruthy();
  const data=await response.json();
  await renderedOptions(page,data);
  return data;
}

async function openPicker(page) {
  const data=await optionsAfter(page,()=>opener(page).click(),{q:'',record_type:'',region:'',page:1});
  await expect(dialog(page)).toBeVisible();
  return data;
}

async function expectDraft(page,names) {
  await expect(draft(page).getByRole('button',{name:/^Remove .+ from selection$/})).toHaveCount(names.length);
  for(const name of names) await expect(remove(page,name)).toBeVisible();
  if(names.length) {
    await expect(confirm(page)).toBeEnabled();
    await expect(confirm(page)).toHaveAccessibleName(new RegExp(`^Add selected assets(?: \\(${names.length}\\))?$`));
  } else await expect(confirm(page)).toBeDisabled();
}

async function fits(page) {
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize().width);
  const bounds=await dialog(page).boundingBox();
  expect(bounds.x).toBeGreaterThanOrEqual(-1);
  expect(bounds.y).toBeGreaterThanOrEqual(-1);
  expect(bounds.x+bounds.width).toBeLessThanOrEqual(page.viewportSize().width+1);
  expect(bounds.y+bounds.height).toBeLessThanOrEqual(page.viewportSize().height+1);
  const overflow=await dialog(page).locator('h1,h2,p,label,button,li,span,strong,small,select,input').evaluateAll(elements=>
    elements.filter(el=>el.getClientRects().length&&el.scrollWidth>el.clientWidth+1)
      .map(el=>el.textContent||el.getAttribute('aria-label')));
  expect(overflow).toEqual([]);
  for(const button of [confirm(page),dialog(page).getByRole('button',{name:'Cancel',exact:true})]) {
    await expect(button).toBeInViewport();
    const box=await button.boundingBox();
    expect(box.x).toBeGreaterThanOrEqual(bounds.x-1);
    expect(box.x+box.width).toBeLessThanOrEqual(bounds.x+bounds.width+1);
    expect(box.y).toBeGreaterThanOrEqual(bounds.y-1);
    expect(box.y+box.height).toBeLessThanOrEqual(bounds.y+bounds.height+1);
  }
  const confirmBox=await confirm(page).boundingBox();
  const cancelBox=await dialog(page).getByRole('button',{name:'Cancel',exact:true}).boundingBox();
  const overlapWidth=Math.min(confirmBox.x+confirmBox.width,cancelBox.x+cancelBox.width)-Math.max(confirmBox.x,cancelBox.x);
  const overlapHeight=Math.min(confirmBox.y+confirmBox.height,cancelBox.y+cancelBox.height)-Math.max(confirmBox.y,cancelBox.y);
  expect(overlapWidth>1&&overlapHeight>1).toBe(false);
}

test('empty search opens a browsable native asset dialog with focused search',async({page},testInfo)=>{
  await page.goto('/compare/');
  await expect(page.getByLabel('Find an asset to compare',{exact:true})).toBeHidden();
  const data=await openPicker(page);
  expect(await dialog(page).evaluate(el=>el.tagName)).toBe('DIALOG');
  await expect(dialog(page)).toHaveAttribute('open','');
  await expect(search(page)).toBeFocused();
  await expect(search(page)).toHaveValue('');
  await expect(assetType(page)).toHaveValue('');
  await expect(region(page)).toHaveValue('');
  const types=await assetType(page).locator('option').evaluateAll(elements=>elements.map(el=>el.value));
  expect(types).toEqual(expect.arrayContaining(['','organization','facility']));
  const regions=await region(page).locator('option').evaluateAll(elements=>elements.map(el=>el.value));
  expect(regions).toEqual(expect.arrayContaining(['','hampton-roads','new-river-valley']));
  expect(data.assets).toHaveLength(24);
  expect(data.count).toBeGreaterThan(24);
  expect(data.page).toBe(1);
  expect(data.pages).toBe(Math.ceil(data.count/24));
  for(const asset of data.assets) {
    expect(asset).toEqual(expect.objectContaining({
      slug:expect.any(String),name:expect.any(String),url:expect.any(String),
      record_type:expect.any(String),record_type_label:expect.any(String),location:expect.any(String),
    }));
  }
  await expectDraft(page,[]);
  await expect(dialog(page).getByRole('button',{name:'Previous page',exact:true})).toBeDisabled();
  await expect(dialog(page).getByRole('button',{name:'Next page',exact:true})).toBeEnabled();
  await fits(page);
  await page.screenshot({path:testInfo.outputPath('asset-picker-browse.png'),animations:'disabled'});
});

test('live debounced fuzzy search finds an already compared REaKTOR without submitting',async({page,request})=>{
  const existing=await seedAsset(request,REAKTOR);
  await page.goto(`/compare/?asset=${existing.slug}`);
  const originalURL=page.url();
  await openPicker(page);
  const now=new Date('2026-11-12T12:00:00Z');
  await page.clock.install({time:now});
  await page.clock.pauseAt(new Date(now.getTime()+1000));
  const queries=[];
  page.on('request',request=>{
    if(isOptions(request.url())) queries.push(new URL(request.url()).searchParams.get('q'));
  });
  await optionsAfter(page,async()=>{
    await search(page).fill('reac');
    await search(page).fill('react');
    await search(page).fill('reactor');
    await page.clock.runFor(1000);
  },{q:'reactor',page:1});
  expect(queries).toEqual(['reactor']);
  await expect(option(page,REAKTOR)).toBeChecked();
  await expect(option(page,REAKTOR)).toBeDisabled();
  await expectDraft(page,[]);
  await expect(search(page)).toBeFocused();
  expect(page.url()).toBe(originalURL);
});

test('draft selections survive type, region and search filters and confirm preserves existing assets',async({page})=>{
  await page.goto('/compare/?asset=allocortech');
  await openPicker(page);
  await optionsAfter(page,()=>assetType(page).selectOption('facility'),{record_type:'facility',page:1});
  await optionsAfter(page,()=>region(page).selectOption('hampton-roads'),{record_type:'facility',region:'hampton-roads',page:1});
  const facilities=await optionsAfter(page,()=>search(page).fill('Fulcrum'),{q:'Fulcrum',record_type:'facility',region:'hampton-roads'});
  expect(facilities.assets.every(asset=>asset.record_type==='facility')).toBe(true);
  await option(page,FULCRUM).check();
  await expectDraft(page,[FULCRUM]);
  await optionsAfter(page,()=>search(page).fill('Kollmorgen'),{q:'Kollmorgen',record_type:'facility',region:'hampton-roads'});
  await expectDraft(page,[FULCRUM]);
  await optionsAfter(page,()=>assetType(page).selectOption('organization'),{q:'Kollmorgen',record_type:'organization',region:'hampton-roads'});
  const organizations=await optionsAfter(page,()=>region(page).selectOption('new-river-valley'),{
    q:'Kollmorgen',record_type:'organization',region:'new-river-valley',page:1,
  });
  const added=organizations.assets.find(asset=>asset.name===KOLLMORGEN);
  expect(added).toBeTruthy();
  await option(page,KOLLMORGEN).check();
  await expectDraft(page,[FULCRUM,KOLLMORGEN]);
  await optionsAfter(page,()=>dialog(page).getByRole('button',{name:'Clear filters',exact:true}).click(),{
    q:'',record_type:'',region:'',page:1,
  });
  await expect(search(page)).toHaveValue('');
  await expect(assetType(page)).toHaveValue('');
  await expect(region(page)).toHaveValue('');
  await expectDraft(page,[FULCRUM,KOLLMORGEN]);
  await remove(page,FULCRUM).click();
  await expectDraft(page,[KOLLMORGEN]);
  expect(selectedSlugs(page)).toEqual(['allocortech']);
  await confirm(page).click();
  await expect(page).toHaveURL(url=>url.pathname==='/compare/'&&
    JSON.stringify(url.searchParams.getAll('asset'))===JSON.stringify(['allocortech',added.slug]));
  await expect(page.locator('.asset-comparison caption')).toHaveText('2 selected assets');
  await expect(page.locator('.asset-comparison thead th a')).toHaveText(['Allocortech',KOLLMORGEN]);
  await expect(page.locator('.asset-comparison')).not.toContainText(FULCRUM);
});

test('existing assets count toward five and five long draft names fit phones, landscape, tablet and desktop',async({page,request},testInfo)=>{
  test.setTimeout(90000);
  const data=await seedOptions(request,{q:'unmanned'});
  const assets=[...data.assets].sort((a,b)=>b.name.length-a.name.length).slice(0,6);
  expect(assets).toHaveLength(6);
  for(const asset of assets.slice(0,5)) expect(asset.name.length).toBeGreaterThan(35);
  const query=new URLSearchParams(assets.slice(0,2).map(asset=>['asset',asset.slug]));
  await page.goto(`/compare/?${query}`);
  await openPicker(page);
  await optionsAfter(page,()=>search(page).fill('unmanned'),{q:'unmanned'});
  for(const asset of assets.slice(0,2)) {
    await expect(option(page,asset.name)).toBeChecked();
    await expect(option(page,asset.name)).toBeDisabled();
  }
  for(const asset of assets.slice(2,5)) await option(page,asset.name).check();
  await expectDraft(page,assets.slice(2,5).map(asset=>asset.name));
  await expect(dialog(page).getByText('5 of 5 selected',{exact:true})).toBeVisible();
  await expect(option(page,assets[5].name)).toBeDisabled();
  await remove(page,assets[2].name).click();
  await expect(dialog(page).getByText('4 of 5 selected',{exact:true})).toBeVisible();
  await expect(option(page,assets[5].name)).toBeEnabled();
  await option(page,assets[5].name).check();
  await expect(option(page,assets[2].name)).toBeDisabled();
  await expectDraft(page,[assets[3].name,assets[4].name,assets[5].name]);
  const expected=[assets[0],assets[1],assets[3],assets[4],assets[5]].map(asset=>asset.slug);
  await confirm(page).click();
  await expect(page).toHaveURL(url=>url.pathname==='/compare/'&&
    JSON.stringify(url.searchParams.getAll('asset'))===JSON.stringify(expected));
  await expect(page.locator('.asset-comparison caption')).toHaveText('5 selected assets');
  await expect(opener(page)).toBeDisabled();

  await page.goto('/compare/?clear=1');
  await openPicker(page);
  await optionsAfter(page,()=>search(page).fill('unmanned'),{q:'unmanned'});
  for(const asset of assets.slice(0,5)) await option(page,asset.name).check();
  await expectDraft(page,assets.slice(0,5).map(asset=>asset.name));
  await expect(dialog(page).getByText('5 of 5 selected',{exact:true})).toBeVisible();
  await expect(option(page,assets[5].name)).toBeDisabled();
  for(const width of [320,390,768,1440]) {
    await page.setViewportSize({width,height:900});
    await search(page).focus();
    await draft(page).scrollIntoViewIfNeeded();
    await fits(page);
    for(const asset of assets.slice(0,5)) {
      await expect(remove(page,asset.name)).toBeInViewport();
      await expect(draft(page)).toContainText(asset.name);
    }
    await page.screenshot({path:testInfo.outputPath(`asset-picker-five-long-names-${width}.png`),animations:'disabled'});
  }
  await page.setViewportSize({width:844,height:390});
  await search(page).scrollIntoViewIfNeeded();
  await expect(search(page)).toBeInViewport();
  await fits(page);
  const footerY=(await confirm(page).boundingBox()).y;
  for(const asset of assets.slice(0,5)) {
    await remove(page,asset.name).scrollIntoViewIfNeeded();
    await expect(remove(page,asset.name)).toBeInViewport();
    await fits(page);
    expect((await confirm(page).boundingBox()).y).toBeCloseTo(footerY,0);
  }
  const next=dialog(page).getByRole('button',{name:'Next page',exact:true});
  await next.scrollIntoViewIfNeeded();
  await expect(next).toBeInViewport();
  await fits(page);
  expect((await confirm(page).boundingBox()).y).toBeCloseTo(footerY,0);
  await draft(page).scrollIntoViewIfNeeded();
  await fits(page);
  await page.screenshot({path:testInfo.outputPath('asset-picker-five-long-names-844x390.png'),animations:'disabled'});
});

test('focus stays in the dialog and Cancel, header close and Escape discard drafts and restore focus',async({page})=>{
  await page.goto('/compare/?asset=allocortech');
  const originalURL=page.url();
  const data=await openPicker(page);
  const candidate=data.assets.find(asset=>asset.slug!=='allocortech');
  const focusableCount=await dialog(page).locator('button,input,select,a[href],[tabindex="0"]').count();
  for(const key of ['Tab','Shift+Tab']) {
    for(let index=0;index<focusableCount+2;index++) {
      await page.keyboard.press(key);
      expect(await dialog(page).evaluate(el=>el.contains(document.activeElement))).toBe(true);
    }
  }
  for(const close of ['Cancel','Close asset picker','Escape']) {
    await expect(option(page,candidate.name)).not.toBeChecked();
    await expectDraft(page,[]);
    await option(page,candidate.name).check();
    await expectDraft(page,[candidate.name]);
    if(close==='Escape') await page.keyboard.press('Escape');
    else await dialog(page).getByRole('button',{name:close,exact:true}).click();
    await expect(dialog(page)).toBeHidden();
    await expect(opener(page)).toBeFocused();
    expect(page.url()).toBe(originalURL);
    await expect(page.locator('.asset-comparison caption')).toHaveText('1 selected asset');
    await opener(page).click();
    await expect(dialog(page)).toBeVisible();
    await expect(search(page)).toBeFocused();
    await expect(option(page,candidate.name)).not.toBeChecked();
  }
  await expectDraft(page,[]);
});

test('pagination browses distinct pages, retains draft checkboxes and resets after filtering',async({page})=>{
  await page.goto('/compare/');
  const first=await openPicker(page);
  await option(page,first.assets[0].name).check();
  const second=await optionsAfter(page,()=>dialog(page).getByRole('button',{name:'Next page',exact:true}).click(),{page:2});
  expect(second.page).toBe(2);
  expect(second.count).toBe(first.count);
  expect(second.assets).toHaveLength(24);
  expect(second.assets.some(asset=>first.assets.some(item=>item.slug===asset.slug))).toBe(false);
  await option(page,second.assets[0].name).check();
  await expectDraft(page,[first.assets[0].name,second.assets[0].name]);
  await optionsAfter(page,()=>dialog(page).getByRole('button',{name:'Previous page',exact:true}).click(),{page:1});
  await expect(option(page,first.assets[0].name)).toBeChecked();
  await expect(dialog(page).getByRole('button',{name:'Previous page',exact:true})).toBeDisabled();
  await optionsAfter(page,()=>dialog(page).getByRole('button',{name:'Next page',exact:true}).click(),{page:2});
  await expect(option(page,second.assets[0].name)).toBeChecked();
  const filtered=await optionsAfter(page,()=>assetType(page).selectOption('facility'),{record_type:'facility',page:1});
  expect(filtered.page).toBe(1);
  expect(filtered.assets.every(asset=>asset.record_type==='facility')).toBe(true);
  await expectDraft(page,[first.assets[0].name,second.assets[0].name]);
  await optionsAfter(page,()=>dialog(page).getByRole('button',{name:'Clear filters',exact:true}).click(),{
    q:'',record_type:'',region:'',page:1,
  });
  await expect(option(page,first.assets[0].name)).toBeChecked();
  await expectDraft(page,[first.assets[0].name,second.assets[0].name]);
});

test('failed loading retries and a stale search response cannot overwrite newer results or drafts',async({page,request})=>{
  const stale=await seedOptions(request,{q:'Allocortech'});
  let fail=true;
  let olderStarted=false;
  let release;
  const held=new Promise(resolve=>{release=resolve;});
  await page.route(OPTIONS,async route=>{
    if(fail) {
      fail=false;
      await route.fulfill({status:503,json:{error:'Temporarily unavailable'}});
    } else if(isOptions(route.request().url(),{q:'Allocortech'})) {
      olderStarted=true;
      await held;
      try { await route.fulfill({json:stale}); }
      catch(error) { if(!route.request().failure()) throw error; }
    } else await route.continue();
  });
  try {
    await page.goto('/compare/');
    await opener(page).click();
    await expect(dialog(page).getByRole('button',{name:'Retry',exact:true})).toBeVisible();
    await expect(confirm(page)).toBeDisabled();
    const initial=await optionsAfter(page,()=>dialog(page).getByRole('button',{name:'Retry',exact:true}).click(),{q:''});
    await expect(dialog(page).getByRole('button',{name:'Retry',exact:true})).toBeHidden();
    const chosen=initial.assets.find(asset=>asset.slug!=='allocortech'&&asset.name!==REAKTOR);
    await option(page,chosen.name).check();
    await search(page).fill('Allocortech');
    await expect.poll(()=>olderStarted).toBe(true);
    await optionsAfter(page,()=>search(page).fill('reactor'),{q:'reactor'});
    await expect(option(page,REAKTOR)).toBeVisible();
    release();
    await page.unrouteAll({behavior:'wait'});
    await page.waitForLoadState('networkidle');
    await expect(search(page)).toHaveValue('reactor');
    await expect(option(page,REAKTOR)).toBeVisible();
    await expect(option(page,'Allocortech')).toHaveCount(0);
    await expectDraft(page,[chosen.name]);
    await option(page,REAKTOR).check();
    await expectDraft(page,[chosen.name,REAKTOR]);
  } finally {
    release();
    await page.unrouteAll({behavior:'wait'});
  }
});

test.describe('without JavaScript',()=>{
  test.use({javaScriptEnabled:false});

  test('server search and Add Allocortech links still compare and remove assets',async({page})=>{
    const requests=[];
    page.on('request',request=>{if(isOptions(request.url())) requests.push(request.url());});
    await page.goto('/compare/');
    await expect(opener(page)).toBeHidden();
    await expect(page.getByLabel('Find an asset to compare',{exact:true})).toBeVisible();
    await page.getByLabel('Find an asset to compare',{exact:true}).fill('Allocortech');
    await page.getByRole('button',{name:'Search',exact:true}).click();
    await page.getByRole('link',{name:'Add Allocortech',exact:true}).click();
    await expect(page.locator('.asset-comparison')).toContainText('Allocortech');
    expect(selectedSlugs(page)).toEqual(['allocortech']);
    await page.getByRole('link',{name:'Remove Allocortech from comparison',exact:true}).click();
    await expect(page.locator('main')).toContainText('No assets selected.');
    expect(requests).toEqual([]);
  });
});

test('existing search URLs open the picker with the query preserved',async({page})=>{
  await page.goto('/compare/?q=Allocortech');
  await expect(dialog(page)).toBeVisible();
  await expect(search(page)).toHaveValue('Allocortech');
  await option(page,'Allocortech').check();
  await confirm(page).click();
  await expect(page.locator('.asset-comparison caption')).toHaveText('1 selected asset');
  await expect(page.locator('.asset-comparison thead th a')).toHaveText(['Allocortech']);
});
