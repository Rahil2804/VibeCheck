export function shouldSearchPlaces(query, selectedQuery) {
  const normalizedQuery = query.trim();
  if (!normalizedQuery) return false;
  return normalizedQuery !== selectedQuery.trim();
}
