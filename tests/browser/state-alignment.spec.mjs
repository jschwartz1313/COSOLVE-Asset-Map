import {expect, test} from '@playwright/test';
import {readFileSync} from 'node:fs';

const additions = JSON.parse(readFileSync(new URL(
  '../../data/multistate/expansion_2026_11_24_starter.json', import.meta.url,
))).records;
const profiles = JSON.parse(readFileSync(new URL(
  '../../data/multistate/profiles_2026_11_24.json', import.meta.url,
))).profiles;
const stateSlugs = {AZ:'arizona', CA:'california', CO:'colorado', FL:'florida',
  MI:'michigan', NY:'new-york', NC:'north-carolina', ND:'north-dakota',
  OH:'ohio', OK:'oklahoma', PA:'pennsylvania', TX:'texas', UT:'utah'};

const states = ['', 'arizona', 'california', 'colorado', 'florida', 'michigan',
  'new-york', 'north-carolina', 'north-dakota', 'ohio', 'oklahoma',
  'pennsylvania', 'texas', 'utah'];

async function signIn(page, version) {
  test.skip(!process.env.COSOLVE_MULTISTATE_QA_USERNAME, 'Requires an isolated owner account.');
  await page.goto('/login/');
  await page.locator('input[name="login"]').fill(process.env.COSOLVE_MULTISTATE_QA_USERNAME);
  await page.locator('input[name="password"]').fill(process.env.COSOLVE_MULTISTATE_QA_PASSWORD);
  await page.getByRole('button', {name:'Sign in', exact:true}).click();
  if (version === '2.0') await page.getByRole('button', {name:'2.0', exact:true}).click();
}

async function fits(page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(await page.locator('h1,h2,h3,.button,.filter-select,.type-pill,.affiliation-tag')
    .evaluateAll(items => items.filter(el => el.getClientRects().length
      && getComputedStyle(el).textOverflow !== 'ellipsis'
      && el.scrollWidth > el.clientWidth + 2).map(el => el.textContent))).toEqual([]);
}

for (const version of ['Current', '2.0']) {
  test(`${version} all new state maps start on Street and preserve explicit saved choices`, async ({page}) => {
    await signIn(page, version);
    for (const state of states) {
      const prefix = state ? `/states/${state}` : '';
      await page.goto(`${prefix}/map/`);
      await expect(page.locator('[data-map-app]')).toHaveAttribute('aria-busy', 'false');
      await expect(page.getByRole('radio', {name:'Street', exact:true})).toBeChecked();
      await fits(page);
    }
    await page.goto('/map/?map_basemap=light');
    await expect(page.getByRole('radio', {name:'Grey', exact:true})).toBeChecked();
  });

  test(`${version} directory columns and page controls stay aligned`, async ({page}, info) => {
    await signIn(page, version);
    for (const prefix of ['', '/states/california', '/states/north-dakota']) {
      await page.goto(`${prefix}/directory/`);
      await expect(page.locator('.directory-row').first()).toBeVisible();
      await fits(page);
      if (await page.locator('.directory-columns').isVisible()) {
        const alignment = await page.locator('.directory-columns').evaluate(header => {
          const row = document.querySelector('.directory-row');
          return [...header.children].map((label, index) => Math.abs(
            label.getBoundingClientRect().left - row.children[index].getBoundingClientRect().left,
          ));
        });
        expect(alignment.every(delta => delta <= 2)).toBe(true);
      }
    }
    await page.screenshot({path:info.outputPath(`directory-alignment-${version}.png`), fullPage:true});
    for (const path of ['/test-sites/', '/manufacturing/', '/regions/compare/', '/about-data/']) {
      await page.goto(path);
      await fits(page);
    }
  });

  test(`${version} new and expanded peer profiles retain readable content`, async ({page}, info) => {
    await signIn(page, version);
    for (const record of [...additions, ...profiles]) {
      const prefix = `/states/${stateSlugs[record.state]}`;
      const response = await page.request.get(`${prefix}/compare/options/`, {
        params:{q:record.name.slice(0, 90)},
      });
      expect(response.ok()).toBe(true);
      const asset = (await response.json()).assets.find(asset => asset.name === record.name);
      expect(asset, record.name).toBeTruthy();
      await page.goto(asset.url.startsWith(prefix) ? asset.url : prefix + asset.url);
      await expect(page.locator('h1')).toHaveText(record.name);
      await fits(page);
      const overview = record.after?.overview || record.overview;
      await expect(page.locator('.overview-copy')).toContainText(overview.split('\n')[0]);
      expect(await page.locator('.detail-sidebar dd,.overview-copy p')
        .evaluateAll(elements => elements.filter(el => el.getClientRects().length
          && el.scrollWidth > el.clientWidth + 2).map(el => el.textContent))).toEqual([]);
      if (record.name.startsWith('Aerotech Pittsburgh')) {
        await page.screenshot({path:info.outputPath(`expanded-profile-${version}.png`),
          animations:'disabled'});
      }
    }
  });
}
