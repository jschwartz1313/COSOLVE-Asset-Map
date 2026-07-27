export async function fetchAssets(searchParams) {
  const response = await fetch(`/api/assets.geojson?${searchParams.toString()}`, {
    headers: { Accept: "application/geo+json" },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Asset request failed (${response.status})`);
  return response.json();
}
