import { isChecklistShared, normalizeUserId, safeParseJson } from "./appUtils";

const STORAGE_VERSION = 1;
const LAST_CHECKLIST_KEY = "luggify:last-checklist";
const PENDING_CHECKLIST_KEY = "luggify:last-checklist-pending";

const canUseStorage = () => typeof window !== "undefined" && typeof window.localStorage !== "undefined";

const cloneChecklistForStorage = (checklist) => {
  if (!checklist) return null;

  try {
    const cloned = JSON.parse(JSON.stringify(checklist));
    if (cloned && typeof cloned === "object") {
      delete cloned.reviews;
    }
    return cloned;
  } catch {
    return null;
  }
};

const buildStoredEntry = (checklist, currentUserId) => {
  const storedChecklist = cloneChecklistForStorage(checklist);
  if (!storedChecklist?.slug) return null;

  return {
    version: STORAGE_VERSION,
    savedAt: Date.now(),
    slug: storedChecklist.slug,
    editableOffline: isOfflineChecklistEditable(storedChecklist, currentUserId),
    checklist: storedChecklist,
  };
};

const readStoredEntry = (storageKey) => {
  if (!canUseStorage()) return null;

  const parsed = safeParseJson(window.localStorage.getItem(storageKey), null);
  if (!parsed || parsed.version !== STORAGE_VERSION || !parsed.checklist?.slug) {
    return null;
  }

  return parsed;
};

const writeStoredEntry = (storageKey, checklist, currentUserId) => {
  if (!canUseStorage()) return false;

  const entry = buildStoredEntry(checklist, currentUserId);
  if (!entry) return false;

  try {
    window.localStorage.setItem(storageKey, JSON.stringify(entry));
    return true;
  } catch {
    return false;
  }
};

const clearStoredEntry = (storageKey) => {
  if (!canUseStorage()) return;
  window.localStorage.removeItem(storageKey);
};

export const isOfflineChecklistEditable = (checklist, currentUserId) => {
  if (!checklist || currentUserId == null) return false;

  const normalizedCurrentUserId = normalizeUserId(currentUserId);
  const normalizedOwnerId = normalizeUserId(checklist.user_id);

  if (normalizedOwnerId !== normalizedCurrentUserId) return false;
  return !isChecklistShared(checklist, currentUserId);
};

export const saveLastChecklistSnapshot = (checklist, currentUserId) =>
  writeStoredEntry(LAST_CHECKLIST_KEY, checklist, currentUserId);

export const loadLastChecklistSnapshot = (expectedSlug = null) => {
  const entry = readStoredEntry(LAST_CHECKLIST_KEY);
  if (!entry) return null;
  if (expectedSlug && entry.slug !== expectedSlug) return null;
  return entry.checklist;
};

export const savePendingChecklistSnapshot = (checklist, currentUserId) =>
  writeStoredEntry(PENDING_CHECKLIST_KEY, checklist, currentUserId);

export const loadPendingChecklistSnapshot = (expectedSlug = null) => {
  const entry = readStoredEntry(PENDING_CHECKLIST_KEY);
  if (!entry) return null;
  if (expectedSlug && entry.slug !== expectedSlug) return null;
  return entry;
};

export const clearPendingChecklistSnapshot = () => {
  clearStoredEntry(PENDING_CHECKLIST_KEY);
};

export const clearOfflineChecklistSnapshots = () => {
  clearStoredEntry(LAST_CHECKLIST_KEY);
  clearStoredEntry(PENDING_CHECKLIST_KEY);
};
