export async function fetchAssets(searchParams) {
  const response = await fetch(`/api/assets.geojson?${searchParams.toString()}`, {
    headers: { Accept: "application/geo+json" },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Asset request failed (${response.status})`);
  return response.json();
}

export async function fetchRelationships(url) {
  const response = await fetch(url, {
    headers: { Accept: "application/geo+json" },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Relationship request failed (${response.status})`);
  return response.json();
}
