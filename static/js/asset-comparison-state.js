const SLUG = /^[a-z0-9-]{1,240}$/;

export function comparisonSlugs(value) {
  return Array.isArray(value)
    ? [...new Set(value.filter(slug => typeof slug === "string" && SLUG.test(slug)))].slice(0, 5)
    : [];
}

export function comparisonLabels(payload, requested) {
  if (!payload || !Array.isArray(payload.assets) || payload.assets.length > 5) {
    throw new Error("Invalid comparison names response");
  }
  const labels = new Map();
  for (const asset of payload.assets) {
    if (!asset || !requested.includes(asset.slug) || labels.has(asset.slug)
      || typeof asset.name !== "string" || !asset.name.trim() || asset.name.length > 220
      || asset.url !== `/assets/${asset.slug}/`) {
      throw new Error("Invalid comparison asset label");
    }
    labels.set(asset.slug, { name: asset.name, url: asset.url });
  }
  return labels;
}
