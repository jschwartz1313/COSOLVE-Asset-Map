import { comparisonSlugs } from "./asset-comparison-state.js?v=20261111-3";

export function assetPickerPage(payload) {
  if (!payload || !Array.isArray(payload.assets) || payload.assets.length > 24
    || !Number.isSafeInteger(payload.count) || payload.count < payload.assets.length
    || !Number.isSafeInteger(payload.page) || !Number.isSafeInteger(payload.pages)
    || payload.page < 1 || payload.pages !== Math.max(1, Math.ceil(payload.count / 24))
    || payload.page > payload.pages) throw new Error("Invalid asset list");
  const seen = new Set();
  for (const asset of payload.assets) {
    if (!asset || !comparisonSlugs([asset.slug]).length || seen.has(asset.slug)
      || typeof asset.name !== "string" || !asset.name.trim() || asset.name.length > 220
      || asset.url !== `/assets/${asset.slug}/`
      || typeof asset.record_type !== "string" || asset.record_type.length > 30
      || typeof asset.record_type_label !== "string" || asset.record_type_label.length > 80
      || typeof asset.location !== "string" || asset.location.length > 260) {
      throw new Error("Invalid asset option");
    }
    seen.add(asset.slug);
  }
  return payload;
}

export function assetPickerQuery(existing, draft) {
  const values = [...existing, ...draft];
  const normalized = comparisonSlugs(values);
  if (values.length > 5 || normalized.length !== values.length) {
    throw new Error("Choose no more than five distinct assets");
  }
  const query = new URLSearchParams();
  normalized.forEach(slug => query.append("asset", slug));
  return query.toString();
}
