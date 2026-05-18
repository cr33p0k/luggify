export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const safeParseJson = (value, fallback = null) => {
  if (!value) return fallback;
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
};

export const readJsonSafely = async (response) => {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) return null;
  return response.json().catch(() => null);
};

export const resolveInitialTheme = () => {
  if (typeof window === "undefined") return "light";
  const savedTheme = window.localStorage.getItem("theme");
  return savedTheme === "light" || savedTheme === "dark" ? savedTheme : "light";
};

export const normalizeUserId = (value) => {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : value;
};

export const isChecklistShared = (checklist, ownerUserId) => {
  if (!checklist) return false;
  const normalizedOwnerId = normalizeUserId(checklist.user_id);
  const normalizedViewerId = normalizeUserId(ownerUserId);
  if (normalizedOwnerId !== normalizedViewerId) return true;
  return (checklist.backpacks || []).some(
    (backpack) => normalizeUserId(backpack.user_id) !== normalizedOwnerId
  );
};

export const getChecklistItemCount = (checklist) => {
  const checklistItemsCount = Array.isArray(checklist?.items) ? checklist.items.length : 0;
  const baggageItemsCount = (checklist?.backpacks || []).reduce(
    (sum, backpack) => sum + (Array.isArray(backpack.items) ? backpack.items.length : 0),
    0
  );
  return checklistItemsCount + baggageItemsCount;
};

export const getChecklistTravelerCount = (checklist) => {
  if (!checklist) return 1;

  const participantIds = new Set();
  if (checklist.user_id != null) {
    participantIds.add(normalizeUserId(checklist.user_id));
  }
  (checklist.backpacks || []).forEach((backpack) => {
    if (backpack?.user_id != null) {
      participantIds.add(normalizeUserId(backpack.user_id));
    }
  });

  const tripProfile = checklist?.trip_profile && typeof checklist.trip_profile === "object"
    ? checklist.trip_profile
    : {};
  const adults = Math.max(1, Number.parseInt(tripProfile.adults, 10) || 1);
  const childrenAgesCount = Array.isArray(tripProfile.children_ages) ? tripProfile.children_ages.length : 0;
  const childProfilesCount = Array.isArray(tripProfile.child_profiles) ? tripProfile.child_profiles.length : 0;
  const travelersFromTripProfile = adults + Math.max(childrenAgesCount, childProfilesCount);

  return Math.max(1, participantIds.size, travelersFromTripProfile);
};
