import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';

const changes = JSON.parse(readFileSync(new URL('../../data/facility_profiles_2026_11_06.json', import.meta.url))).corrections;
const slug = name => name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

test('all expanded facility profiles render their evidence-backed uses without overflow', async ({page}, testInfo) => {
  test.setTimeout(120_000);
  for (const change of changes) {
    await page.goto(`/assets/${slug(change.name)}/`);
    await expect(page.locator('.overview-section')).toContainText(change.after.overview.split('\n\n')[0]);
    await expect(page.locator('.contact-section')).toContainText(change.after.contact_text);
    const route = page.getByRole('link', {name:'Open contact information', exact:true});
    if (change.after.contact_url) await expect(route).toHaveAttribute('href', change.after.contact_url);
    await expect(route).toHaveAttribute('target','_blank');
    const overflow = await page.locator('main h1, main h2, main p, main dd, main li')
      .evaluateAll(elements => elements.filter(el=>el.getClientRects().length && el.scrollWidth>el.clientWidth+1).map(el=>el.textContent));
    expect(overflow, change.name).toEqual([]);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(page.viewportSize().width);
    await expect(page.locator('main')).not.toContainText('Catalog updated');
    if (['Fulcrum Concepts Newport News Machine Shop','NASA Flight Dynamics Research Facility'].includes(change.name)) {
      await page.screenshot({path:testInfo.outputPath(`${slug(change.name)}.png`),fullPage:true});
    }
  }
});

test('new practical-use terms lead to the relevant supplier and test facility', async ({page}) => {
  for (const [query, name] of [
    ['pallet-pool','Fulcrum Concepts Newport News Machine Shop'],
    ['probe calibration','Aeroprobe'],
    ['Hydro Impact','NASA Langley Landing and Impact Research Facility'],
  ]) {
    await page.goto(`/directory/?q=${encodeURIComponent(query)}`);
    await expect(page.locator('.directory-row')).toContainText([name]);
  }
});
