const normalizedQuantityMapCache = new WeakMap();
const normalizedPackedQuantityMapCache = new WeakMap();

export const normalizeItemKey = (value) =>
  String(value || "").trim().toLowerCase().replaceAll("ё", "е");

export const normalizeQuantityMap = (value = {}) =>
  Object.entries(value || {}).reduce((acc, [key, rawValue]) => {
    const normalizedKey = normalizeItemKey(key);
    const numericValue = Number(rawValue);
    if (!normalizedKey || !Number.isFinite(numericValue) || numericValue < 1) {
      return acc;
    }
    acc[normalizedKey] = Math.max(1, Math.round(numericValue));
    return acc;
  }, {});

export const getNormalizedQuantityMap = (value = {}) => {
  if (!value || typeof value !== "object") return {};
  const cached = normalizedQuantityMapCache.get(value);
  if (cached) return cached;
  const normalized = normalizeQuantityMap(value);
  normalizedQuantityMapCache.set(value, normalized);
  return normalized;
};

export const normalizePackedQuantityMap = (value = {}) =>
  Object.entries(value || {}).reduce((acc, [key, rawValue]) => {
    const normalizedKey = normalizeItemKey(key);
    const numericValue = Number(rawValue);
    if (!normalizedKey || !Number.isFinite(numericValue)) {
      return acc;
    }
    const safeValue = Math.max(0, Math.round(numericValue));
    if (safeValue === 0) {
      return acc;
    }
    acc[normalizedKey] = safeValue;
    return acc;
  }, {});

export const getNormalizedPackedQuantityMap = (value = {}) => {
  if (!value || typeof value !== "object") return {};
  const cached = normalizedPackedQuantityMapCache.get(value);
  if (cached) return cached;
  const normalized = normalizePackedQuantityMap(value);
  normalizedPackedQuantityMapCache.set(value, normalized);
  return normalized;
};

export const getItemQuantity = (quantityMap = {}, item) => {
  const normalizedKey = normalizeItemKey(item);
  if (!normalizedKey) return 1;
  return getNormalizedQuantityMap(quantityMap)[normalizedKey] || 1;
};

export const getPackedQuantity = (quantityMap = {}, item) => {
  const normalizedKey = normalizeItemKey(item);
  if (!normalizedKey) return 0;
  return getNormalizedPackedQuantityMap(quantityMap)[normalizedKey] || 0;
};

export const setItemQuantityInMap = (quantityMap = {}, item, nextQuantity) => {
  const normalizedKey = normalizeItemKey(item);
  if (!normalizedKey) return normalizeQuantityMap(quantityMap);
  const nextMap = normalizeQuantityMap(quantityMap);
  const parsedQuantity = Number(nextQuantity);
  if (!Number.isFinite(parsedQuantity) || parsedQuantity < 1) {
    delete nextMap[normalizedKey];
    return nextMap;
  }
  nextMap[normalizedKey] = Math.max(1, Math.round(parsedQuantity));
  return nextMap;
};

export const setPackedQuantityInMap = (quantityMap = {}, item, nextQuantity) => {
  const normalizedKey = normalizeItemKey(item);
  if (!normalizedKey) return normalizePackedQuantityMap(quantityMap);
  const nextMap = normalizePackedQuantityMap(quantityMap);
  const parsedQuantity = Number(nextQuantity);
  if (!Number.isFinite(parsedQuantity) || parsedQuantity <= 0) {
    delete nextMap[normalizedKey];
    return nextMap;
  }
  nextMap[normalizedKey] = Math.max(0, Math.round(parsedQuantity));
  return nextMap;
};
