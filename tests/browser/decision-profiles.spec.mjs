import {test,expect} from '@playwright/test';

test('practical profiles retain direct sources and fit desktop and phone layouts',async({page},testInfo)=>{
  for(const [slug,text] of [
    ['commonwealth-center-for-advanced-manufacturing','intellectual-property'],
    ['advanced-aircraft-company','alternative configuration-dependent'],
    ['vidarr-virginia-beach-manufacturing-facility','by appointment'],
    ['liquid-robotics-herndon-headquarters-and-production','whether all Herndon production has ceased'],
  ]) {
    await page.goto(`/assets/${slug}/`);
    await expect(page.locator('main')).toContainText(text);
    await expect(page.getByRole('link',{name:'Visit website',exact:true})).toHaveAttribute('target','_blank');
    expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize().width);
    const overflow=await page.locator('main h1,main p,main dd').evaluateAll(elements=>elements.filter(el=>el.getClientRects().length&&el.scrollWidth>el.clientWidth+1).map(el=>el.textContent));
    expect(overflow).toEqual([]);
  }
  await page.goto('/test-sites/?activity=enclosed&outcome=match');
  await expect(page.locator('.test-site-result')).toContainText(['Virginia Tech Drone Park']);
  await expect(page.locator('body')).not.toContainText('Catalog updated');
  await page.screenshot({path:testInfo.outputPath('evidence-backed-enclosed-testing.png'),fullPage:true});
});
