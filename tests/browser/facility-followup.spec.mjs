import {expect,test} from '@playwright/test';
import {readFileSync} from 'node:fs';

const changes=JSON.parse(readFileSync(new URL('../../data/facility_profiles_2026_11_10_followup.json',import.meta.url))).corrections;
const slug=name=>name.toLowerCase().replace(/[^\w\s-]/g,'').trim().replace(/[-\s]+/g,'-');

test('30 remaining facility profiles render practical detail and fit desktop and phone',async({page},testInfo)=>{
  test.setTimeout(180_000);
  for(const change of changes){
    await page.goto(`/assets/${slug(change.name)}/`);
    await expect(page.locator('.overview-section')).toContainText(change.after.overview.split('\n\n')[0]);
    await expect(page.locator('.contact-section')).toContainText(change.after.contact_text);
    const contact=page.getByRole('link',{name:'Open contact information',exact:true});
    if(change.after.contact_url)await expect(contact).toHaveAttribute('href',change.after.contact_url);
    await expect(contact).toHaveAttribute('target','_blank');
    const overflow=await page.locator('main h1,main h2,main p,main dd,main li').evaluateAll(
      els=>els.filter(el=>el.getClientRects().length&&el.scrollWidth>el.clientWidth+1).map(el=>el.textContent));
    expect(overflow,change.name).toEqual([]);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize().width);
    await expect(page.locator('main')).not.toContainText('Catalog updated');
    if(['Institute for Advanced Learning and Research','JMU X-Labs'].includes(change.name)){
      await page.screenshot({path:testInfo.outputPath(`${slug(change.name)}.png`),fullPage:true});
    }
  }
});

test('specific manufacturing and equipment terms find enriched profiles',async({page})=>{
  for(const [query,name] of [
    ['traceable calibration','Industrial Control Specialties'],
    ['photovoltaic','Polaris Semiconductor'],
    ['FlexBE','CNU Capable Humanitarian Robotics and Intelligent Systems Lab'],
  ]){
    await page.goto(`/directory/?q=${encodeURIComponent(query)}`);
    await expect(page.locator('.directory-row')).toContainText([name]);
  }
});
