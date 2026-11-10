import {expect,test} from '@playwright/test';
import {readFileSync} from 'node:fs';

const changes=JSON.parse(readFileSync(new URL('../../data/facility_profiles_2026_11_10.json',import.meta.url))).corrections;
const slug=name=>name.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');

test('36 practical facility profiles show uses, contact routes and fitting text',async({page},testInfo)=>{
  test.setTimeout(180_000);
  for(const change of changes){
    await page.goto(`/assets/${slug(change.name)}/`);
    await expect(page.locator('.overview-section')).toContainText(change.after.overview.split('\n\n')[0]);
    await expect(page.locator('.contact-section')).toContainText(change.after.contact_text);
    const route=page.getByRole('link',{name:'Open contact information',exact:true});
    if(change.after.contact_url)await expect(route).toHaveAttribute('href',change.after.contact_url);
    await expect(route).toHaveAttribute('target','_blank');
    const overflow=await page.locator('main h1, main h2, main p, main dd, main li').evaluateAll(
      elements=>elements.filter(el=>el.getClientRects().length&&el.scrollWidth>el.clientWidth+1).map(el=>el.textContent));
    expect(overflow,change.name).toEqual([]);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize().width);
    await expect(page.locator('main')).not.toContainText('Catalog updated');
    if(['Phoenix International Chesapeake Operations','NOVA Fab Lab Manassas'].includes(change.name)){
      await page.screenshot({path:testInfo.outputPath(`${slug(change.name)}.png`),fullPage:true});
    }
  }
});

test('practical equipment and access terms find the corresponding resources',async({page})=>{
  for(const [query,name] of [
    ['electrode','Phoenix International Chesapeake Operations'],
    ['Canvas','NOVA Fab Lab Manassas'],
    ['Vicon','Virginia Tech Advanced Control Systems Lab'],
  ]){
    await page.goto(`/directory/?q=${encodeURIComponent(query)}`);
    await expect(page.locator('.directory-row')).toContainText([name]);
  }
});
