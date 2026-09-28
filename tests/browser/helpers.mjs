import { expect } from "@playwright/test";

export async function publicAssetCount(page) {
  const response = await page.request.get("/api/assets/?limit=1");
  expect(response.ok()).toBeTruthy();
  return (await response.json()).result_count;
}
