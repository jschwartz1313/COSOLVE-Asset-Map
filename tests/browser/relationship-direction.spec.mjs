import { expect, test } from "@playwright/test";

const relationships = [
  {
    source: "Tidewater Community College",
    target: "Maxbyte Industry 4.0 Centre of Excellence",
    outgoing: "Hosts",
    incoming: "Hosted by",
  },
  {
    source: "Old Dominion University",
    target: "Aerospace Academy of the Eastern Shore (AAES)",
    outgoing: "Supports",
    incoming: "Supported by",
  },
  {
    source: "Hampton Roads Mobility Innovation Center",
    target: "Newport News Park Radio Control Club Flying Field",
    outgoing: "Located at",
    incoming: "Location of",
  },
  {
    source: "P1 Technologies Keltech Division",
    target: "Blue Vigil",
    outgoing: "Manufactures for",
    incoming: "Receives manufacturing from",
  },
];

async function profilePath(request, name) {
  const response = await request.get("/api/assets/", { params: { q: name } });
  expect(response.ok()).toBeTruthy();
  const asset = (await response.json()).results.find((item) => item.name === name);
  expect(asset, `Public listing for ${name}`).toBeTruthy();
  return `/assets/${asset.slug}/`;
}

for (const relationship of relationships) {
  test(`relationship direction is clear for ${relationship.target}`, async ({ page, request }) => {
    const sourcePath = await profilePath(request, relationship.source);
    const targetPath = await profilePath(request, relationship.target);
    await page.goto(sourcePath);
    await page.locator(".supporting-disclosure summary").click();
    const outgoing = page.locator("section").filter({
      has: page.getByRole("heading", { name: "Related assets", exact: true }),
    }).locator(`a[href="${targetPath}"]`);
    await expect(outgoing.locator("span")).toHaveText(relationship.outgoing);
    await expect(outgoing.locator("strong")).toHaveText(relationship.target);
    await outgoing.click();
    await expect(page).toHaveURL(new RegExp(`${targetPath}$`));
    await page.locator(".supporting-disclosure summary").click();

    const incoming = page.locator("section").filter({
      has: page.getByRole("heading", { name: "Connected organizations and programs", exact: true }),
    }).locator(`a[href="${sourcePath}"]`);
    await expect(incoming.locator("span")).toHaveText(relationship.incoming);
    await expect(incoming.locator("strong")).toHaveText(relationship.source);
    await incoming.click();
    await expect(page).toHaveURL(new RegExp(`${sourcePath}$`));
    await expect(page.getByRole("heading", { name: relationship.source, exact: true })).toBeVisible();
  });
}
