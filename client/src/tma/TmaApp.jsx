import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./TmaApp.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const safeParseJson = (value, fallback = null) => {
  if (!value) return fallback;
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
};

const getTelegramWebApp = () =>
  typeof window !== "undefined" ? window.Telegram?.WebApp : null;

const readJsonSafely = async (response) => {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) return null;
  return response.json().catch(() => null);
};

const normalizeItemKey = (value) =>
  String(value || "").trim().toLowerCase().replaceAll("ё", "е");

const normalizeQuantityMap = (value = {}) =>
  Object.entries(value || {}).reduce((acc, [key, rawValue]) => {
    const normalizedKey = normalizeItemKey(key);
    const numericValue = Number(rawValue);
    if (!normalizedKey || !Number.isFinite(numericValue) || numericValue < 1) {
      return acc;
    }
    acc[normalizedKey] = Math.max(1, Math.round(numericValue));
    return acc;
  }, {});

const normalizePackedQuantityMap = (value = {}) =>
  Object.entries(value || {}).reduce((acc, [key, rawValue]) => {
    const normalizedKey = normalizeItemKey(key);
    const numericValue = Number(rawValue);
    if (!normalizedKey || !Number.isFinite(numericValue)) {
      return acc;
    }
    const safeValue = Math.max(0, Math.round(numericValue));
    if (safeValue > 0) {
      acc[normalizedKey] = safeValue;
    }
    return acc;
  }, {});

const getItemQuantity = (quantityMap = {}, item) => {
  const normalizedKey = normalizeItemKey(item);
  if (!normalizedKey) return 1;
  return normalizeQuantityMap(quantityMap)[normalizedKey] || 1;
};

const getPackedQuantity = (quantityMap = {}, item) => {
  const normalizedKey = normalizeItemKey(item);
  if (!normalizedKey) return 0;
  return normalizePackedQuantityMap(quantityMap)[normalizedKey] || 0;
};

const setItemQuantityInMap = (quantityMap = {}, item, nextQuantity) => {
  const normalizedKey = normalizeItemKey(item);
  if (!normalizedKey) return normalizeQuantityMap(quantityMap);
  const nextMap = normalizeQuantityMap(quantityMap);
  const numericValue = Number(nextQuantity);
  if (!Number.isFinite(numericValue) || numericValue < 1) {
    delete nextMap[normalizedKey];
    return nextMap;
  }
  nextMap[normalizedKey] = Math.max(1, Math.round(numericValue));
  return nextMap;
};

const setPackedQuantityInMap = (quantityMap = {}, item, nextQuantity) => {
  const normalizedKey = normalizeItemKey(item);
  if (!normalizedKey) return normalizePackedQuantityMap(quantityMap);
  const nextMap = normalizePackedQuantityMap(quantityMap);
  const numericValue = Number(nextQuantity);
  if (!Number.isFinite(numericValue) || numericValue <= 0) {
    delete nextMap[normalizedKey];
    return nextMap;
  }
  nextMap[normalizedKey] = Math.max(0, Math.round(numericValue));
  return nextMap;
};

const getBaggageEditorIds = (baggage) =>
  Array.isArray(baggage?.editor_user_ids)
    ? baggage.editor_user_ids
        .map((value) => Number(value))
        .filter((value) => Number.isFinite(value) && value > 0)
    : [];

const getOwnerBaggageEditorIds = (backpacks = [], ownerUserId, fallbackBaggage = null) => {
  const uniqueIds = [];
  (backpacks || []).forEach((baggage) => {
    if (baggage.user_id !== ownerUserId) return;
    getBaggageEditorIds(baggage).forEach((editorId) => {
      if (!uniqueIds.includes(editorId)) {
        uniqueIds.push(editorId);
      }
    });
  });
  return uniqueIds.length > 0 ? uniqueIds : getBaggageEditorIds(fallbackBaggage);
};

const canEditBaggage = (baggage, userId, allBackpacks = []) => {
  if (!baggage || !userId) return false;
  if (baggage.user_id === userId) return true;
  return getOwnerBaggageEditorIds(allBackpacks, baggage.user_id, baggage).includes(userId);
};

const getBaggageKindLabel = (baggage) => {
  const name = String(baggage?.name || "").toLowerCase();
  const kind = baggage?.kind || "";
  if (kind === "suitcase" || name.includes("чемод")) return "Чемодан";
  if (kind === "carry_on" || (name.includes("ручн") && name.includes("клад"))) return "Ручная кладь";
  if (kind === "bag" || name.includes("сумк")) return "Сумка";
  if (kind === "custom") return "Багаж";
  return "Рюкзак";
};

const guessBaggageKind = (name) => {
  const normalized = String(name || "").trim().toLowerCase();
  if (!normalized) return "custom";
  if (normalized.includes("чемод")) return "suitcase";
  if (normalized.includes("ручн") && normalized.includes("клад")) return "carry_on";
  if (normalized.includes("рюкзак")) return "backpack";
  if (normalized.includes("сумк")) return "bag";
  return "custom";
};

const formatDateRange = (checklist) => {
  if (!checklist?.start_date || !checklist?.end_date) return "Даты не указаны";
  const format = (value) =>
    new Date(`${value}T00:00:00`).toLocaleDateString("ru-RU", {
      day: "2-digit",
      month: "long",
    });
  return `${format(checklist.start_date)} - ${format(checklist.end_date)}`;
};

const getTripDays = (checklist) => {
  if (!checklist?.start_date || !checklist?.end_date) return null;
  const start = new Date(`${checklist.start_date}T00:00:00`);
  const end = new Date(`${checklist.end_date}T00:00:00`);
  const diff = Math.round((end - start) / (1000 * 60 * 60 * 24)) + 1;
  return diff > 0 ? diff : null;
};

const sortChecklists = (items = []) => {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return [...items].sort((a, b) => {
    const getBucket = (checklist) => {
      const start = checklist.start_date ? new Date(`${checklist.start_date}T00:00:00`) : null;
      const end = checklist.end_date ? new Date(`${checklist.end_date}T00:00:00`) : null;
      if (start && end && start <= today && end >= today) return 0;
      if (start && start > today) return 1;
      return 2;
    };
    const bucketDiff = getBucket(a) - getBucket(b);
    if (bucketDiff !== 0) return bucketDiff;
    return String(a.start_date || "").localeCompare(String(b.start_date || ""));
  });
};

const getTripCities = (value) =>
  value ? (value.includes(" + ") ? value.split(" + ").map((city) => city.trim()) : [value]) : [];

const buildAttractionQuery = (attraction, city) =>
  `${attraction?.name || ""} ${city || ""}`.trim();

const buildMapQuery = (title, address = "", city = "") =>
  `${title || ""} ${address || ""} ${city || ""}`.trim();

const formatItineraryDayLabel = (value) =>
  new Date(`${value}T00:00:00`).toLocaleDateString("ru-RU", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });

const sortBaggage = (items = [], userId) =>
  [...items].sort((a, b) => {
    const aMine = a.user_id === userId;
    const bMine = b.user_id === userId;
    if (aMine !== bMine) return aMine ? -1 : 1;
    if (Boolean(a.is_default) !== Boolean(b.is_default)) return a.is_default ? -1 : 1;
    if ((a.sort_order || 0) !== (b.sort_order || 0)) {
      return (a.sort_order || 0) - (b.sort_order || 0);
    }
    return (a.id || 0) - (b.id || 0);
  });

const cloneBaggage = (baggage) => ({
  ...baggage,
  items: [...(baggage?.items || [])],
  checked_items: [...(baggage?.checked_items || [])],
  removed_items: [...(baggage?.removed_items || [])],
  added_items: [...(baggage?.added_items || [])],
  item_quantities: normalizeQuantityMap(baggage?.item_quantities || {}),
  packed_quantities: normalizePackedQuantityMap(baggage?.packed_quantities || {}),
});

const getVisibleItems = (baggage) => {
  const removed = new Set((baggage?.removed_items || []).map(normalizeItemKey));
  return (baggage?.items || []).filter((item) => !removed.has(normalizeItemKey(item)));
};

const rebuildCheckedItems = (baggage) =>
  (baggage?.items || []).filter(
    (item) =>
      getPackedQuantity(baggage?.packed_quantities || {}, item) >=
      getItemQuantity(baggage?.item_quantities || {}, item)
  );

const getBaggageProgress = (baggage) => {
  const visibleItems = getVisibleItems(baggage);
  const total = visibleItems.reduce(
    (sum, item) => sum + getItemQuantity(baggage?.item_quantities || {}, item),
    0
  );
  const packed = visibleItems.reduce((sum, item) => {
    const needed = getItemQuantity(baggage?.item_quantities || {}, item);
    const current = getPackedQuantity(baggage?.packed_quantities || {}, item);
    return sum + Math.min(current, needed);
  }, 0);
  return {
    visibleItems,
    total,
    packed,
    remaining: Math.max(total - packed, 0),
    percent: total > 0 ? Math.round((packed / total) * 100) : 0,
  };
};

const getChecklistProgress = (baggage = []) => {
  const progress = baggage.map(getBaggageProgress);
  const total = progress.reduce((sum, item) => sum + item.total, 0);
  const packed = progress.reduce((sum, item) => sum + item.packed, 0);
  return {
    total,
    packed,
    remaining: Math.max(total - packed, 0),
    percent: total > 0 ? Math.round((packed / total) * 100) : 0,
  };
};

const formatForecastDate = (value) =>
  new Date(`${value}T00:00:00`).toLocaleDateString("ru-RU", {
    weekday: "short",
    day: "numeric",
  });

const formatTemperature = (value) => {
  const number = Number(value);
  return Number.isFinite(number) ? `${Math.round(number)}°` : "—";
};

const getForecastPreview = (forecast = []) => {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const upcoming = (forecast || []).filter((day) => new Date(`${day.date}T00:00:00`) >= today);
  return upcoming.length > 0 ? upcoming : forecast || [];
};

const getBaggageOwnerLabel = (baggage, userId) =>
  baggage?.user_id === userId ? "мой" : baggage?.user?.username || "участник";

function TmaApp() {
  const [authState, setAuthState] = useState("loading");
  const [authError, setAuthError] = useState("");
  const [token, setToken] = useState(() => localStorage.getItem("token") || "");
  const [user, setUser] = useState(() => safeParseJson(localStorage.getItem("user"), null));
  const [checklists, setChecklists] = useState([]);
  const [selectedSlug, setSelectedSlug] = useState("");
  const [checklist, setChecklist] = useState(null);
  const [loadingTrips, setLoadingTrips] = useState(false);
  const [loadingChecklist, setLoadingChecklist] = useState(false);
  const [activeBackpackId, setActiveBackpackId] = useState(null);
  const [newItem, setNewItem] = useState("");
  const [sheetItem, setSheetItem] = useState(null);
  const [moveItem, setMoveItem] = useState(null);
  const [showBaggagePicker, setShowBaggagePicker] = useState(false);
  const [newBaggageName, setNewBaggageName] = useState("");
  const [renamingBaggageId, setRenamingBaggageId] = useState(null);
  const [renamingBaggageName, setRenamingBaggageName] = useState("");
  const [showAttractionsSheet, setShowAttractionsSheet] = useState(false);
  const [activeAttractionCity, setActiveAttractionCity] = useState("");
  const [attractions, setAttractions] = useState([]);
  const [loadingAttractions, setLoadingAttractions] = useState(false);
  const [busy, setBusy] = useState(false);
  const [baggageMetaBusy, setBaggageMetaBusy] = useState(false);
  const [savingBackpackId, setSavingBackpackId] = useState(null);
  const [toast, setToast] = useState("");
  const toastTimerRef = useRef(null);

  const authHeaders = useMemo(
    () => (token ? { Authorization: `Bearer ${token}` } : {}),
    [token]
  );

  const showToast = useCallback((message) => {
    if (toastTimerRef.current) {
      window.clearTimeout(toastTimerRef.current);
    }
    setToast(message);
    toastTimerRef.current = window.setTimeout(() => {
      setToast("");
      toastTimerRef.current = null;
    }, 2400);
  }, []);

  useEffect(() => () => {
    if (toastTimerRef.current) {
      window.clearTimeout(toastTimerRef.current);
    }
  }, []);

  const requestJson = useCallback(
    async (path, options = {}) => {
      const response = await fetch(`${API_URL}${path}`, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          ...authHeaders,
          ...(options.headers || {}),
        },
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(data?.detail || "Не удалось выполнить запрос");
      }
      return data;
    },
    [authHeaders]
  );

  useEffect(() => {
    const webApp = getTelegramWebApp();
    webApp?.ready?.();
    webApp?.expand?.();
    webApp?.setHeaderColor?.("#11100e");
    webApp?.setBackgroundColor?.("#090908");

    let cancelled = false;

    const applyAuth = (nextToken, nextUser) => {
      if (cancelled) return;
      setToken(nextToken);
      setUser(nextUser);
      localStorage.setItem("token", nextToken);
      localStorage.setItem("user", JSON.stringify(nextUser));
      setAuthState("ready");
      setAuthError("");
    };

    const authenticate = async () => {
      setAuthState("loading");
      const initData = webApp?.initData || "";

      if (initData) {
        try {
          const response = await fetch(`${API_URL}/auth/telegram`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ init_data: initData }),
          });
          const data = await readJsonSafely(response);
          if (!response.ok) {
            throw new Error(data?.detail || "Backend не ответил на Telegram-авторизацию");
          }
          applyAuth(data.access_token, data.user);
          return;
        } catch (error) {
          if (!cancelled) {
            setAuthError(error.message || "Не удалось войти через Telegram");
            setAuthState("error");
          }
          return;
        }
      }

      const savedToken = localStorage.getItem("token");
      if (savedToken) {
        try {
          const response = await fetch(`${API_URL}/auth/me`, {
            headers: { Authorization: `Bearer ${savedToken}` },
          });
          const data = await response.json();
          if (!response.ok) throw new Error(data.detail || "Сессия устарела");
          applyAuth(savedToken, data);
          return;
        } catch {
          localStorage.removeItem("token");
          localStorage.removeItem("user");
        }
      }

      if (!cancelled) {
        setAuthState("missing");
        setAuthError("Открой mini app из Telegram, чтобы я смог войти в твой аккаунт.");
      }
    };

    authenticate();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!token || authState !== "ready") return undefined;
    let cancelled = false;

    const loadTrips = async () => {
      setLoadingTrips(true);
      try {
        const data = await requestJson("/my-checklists");
        if (cancelled) return;
        const sorted = sortChecklists(data || []);
        setChecklists(sorted);
        const urlSlug = new URLSearchParams(window.location.search).get("slug");
        setSelectedSlug((currentSlug) => (
          (urlSlug && sorted.find((item) => item.slug === urlSlug)?.slug) ||
          (currentSlug && sorted.find((item) => item.slug === currentSlug)?.slug) ||
          sorted[0]?.slug ||
          ""
        ));
      } catch (error) {
        if (!cancelled) {
          setAuthError(error.message || "Не удалось загрузить поездки");
        }
      } finally {
        if (!cancelled) setLoadingTrips(false);
      }
    };

    loadTrips();
    return () => {
      cancelled = true;
    };
  }, [authState, requestJson, token]);

  useEffect(() => {
    if (!selectedSlug || !token) return undefined;
    let cancelled = false;

    const loadChecklist = async () => {
      setLoadingChecklist(true);
      try {
        const data = await requestJson(`/checklist/${selectedSlug}`);
        if (!cancelled) {
          setChecklist(data);
        }
      } catch (error) {
        if (!cancelled) showToast(error.message || "Не удалось открыть чеклист");
      } finally {
        if (!cancelled) setLoadingChecklist(false);
      }
    };

    loadChecklist();
    return () => {
      cancelled = true;
    };
  }, [requestJson, selectedSlug, showToast, token]);

  const attractionCities = useMemo(() => getTripCities(checklist?.city), [checklist?.city]);
  const attractionsLimit = attractionCities.length > 1 ? 5 : 10;

  useEffect(() => {
    if (authState !== "ready" || !activeAttractionCity) {
      setAttractions([]);
      return undefined;
    }

    let cancelled = false;
    const loadAttractions = async () => {
      setLoadingAttractions(true);
      try {
        const data = await requestJson(
          `/attractions?city=${encodeURIComponent(activeAttractionCity)}&lang=ru&limit=${attractionsLimit}`
        );
        if (!cancelled) setAttractions(data?.attractions || []);
      } catch {
        if (!cancelled) setAttractions([]);
      } finally {
        if (!cancelled) setLoadingAttractions(false);
      }
    };

    loadAttractions();
    return () => {
      cancelled = true;
    };
  }, [activeAttractionCity, attractionsLimit, authState, requestJson]);

  const baggage = useMemo(
    () => sortBaggage(checklist?.backpacks || [], user?.id),
    [checklist?.backpacks, user?.id]
  );

  useEffect(() => {
    if (!baggage.length) {
      setActiveBackpackId(null);
      return;
    }
    const currentExists = baggage.some((item) => item.id === activeBackpackId);
    if (currentExists) return;
    const preferred =
      baggage.find((item) => item.user_id === user?.id && item.is_default) ||
      baggage.find((item) => item.user_id === user?.id) ||
      baggage.find((item) => canEditBaggage(item, user?.id, baggage)) ||
      baggage[0];
    setActiveBackpackId(preferred?.id || null);
  }, [activeBackpackId, baggage, user?.id]);

  const activeBackpack = useMemo(
    () => baggage.find((item) => item.id === activeBackpackId) || null,
    [activeBackpackId, baggage]
  );
  const activeProgress = useMemo(() => getBaggageProgress(activeBackpack), [activeBackpack]);
  const totalProgress = useMemo(() => getChecklistProgress(baggage), [baggage]);
  const ownBaggage = useMemo(
    () => baggage.filter((item) => item.user_id === user?.id),
    [baggage, user?.id]
  );
  const forecastPreview = useMemo(
    () => getForecastPreview(checklist?.daily_forecast || []),
    [checklist?.daily_forecast]
  );
  const tripDays = useMemo(() => getTripDays(checklist), [checklist]);
  const canEditActive = canEditBaggage(activeBackpack, user?.id, baggage);
  const isSavingActiveBackpack = savingBackpackId === activeBackpack?.id;
  const visibleItems = activeProgress.visibleItems;

  const replaceBackpacks = useCallback((nextBackpacks) => {
    setChecklist((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        backpacks: sortBaggage(nextBackpacks || [], user?.id),
      };
    });
  }, [user?.id]);

  useEffect(() => {
    setActiveAttractionCity(attractionCities[0] || "");
  }, [attractionCities]);

  const syncBackpack = useCallback(
    async (nextBackpack, payload, previousBackpack = null) => {
      if (!nextBackpack?.id) return null;
      const rollbackBackpack = previousBackpack ? cloneBaggage(previousBackpack) : null;

      setSavingBackpackId(nextBackpack.id);
      setChecklist((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          backpacks: (prev.backpacks || []).map((item) =>
            item.id === nextBackpack.id ? nextBackpack : item
          ),
        };
      });

      try {
        const updated = await requestJson(`/backpacks/${nextBackpack.id}/state`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        setChecklist((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            backpacks: (prev.backpacks || []).map((item) =>
              item.id === updated.id ? updated : item
            ),
          };
        });
        return updated;
      } catch (error) {
        if (rollbackBackpack) {
          setChecklist((prev) => {
            if (!prev) return prev;
            return {
              ...prev,
              backpacks: (prev.backpacks || []).map((item) =>
                item.id === rollbackBackpack.id ? rollbackBackpack : item
              ),
            };
          });
        }
        showToast(error.message || "Не удалось сохранить");
        getTelegramWebApp()?.HapticFeedback?.notificationOccurred?.("error");
        return null;
      } finally {
        setSavingBackpackId((currentId) => (currentId === nextBackpack.id ? null : currentId));
      }
    },
    [requestJson, showToast]
  );

  const updatePackedQuantity = useCallback(
    async (item, nextPackedQuantity) => {
      if (!activeBackpack || !canEditActive || isSavingActiveBackpack) return;
      const previousBackpack = cloneBaggage(activeBackpack);
      const nextBackpack = cloneBaggage(activeBackpack);
      const needed = getItemQuantity(nextBackpack.item_quantities, item);
      const packed = Math.max(0, Math.min(needed, Number(nextPackedQuantity) || 0));
      nextBackpack.packed_quantities = setPackedQuantityInMap(
        nextBackpack.packed_quantities,
        item,
        packed
      );
      nextBackpack.checked_items = rebuildCheckedItems(nextBackpack);
      const updated = await syncBackpack(
        nextBackpack,
        {
          checked_items: nextBackpack.checked_items,
          packed_quantities: nextBackpack.packed_quantities,
        },
        previousBackpack
      );
      if (updated) {
        getTelegramWebApp()?.HapticFeedback?.selectionChanged?.();
      }
    },
    [activeBackpack, canEditActive, isSavingActiveBackpack, syncBackpack]
  );

  const updateNeededQuantity = useCallback(
    async (item, delta) => {
      if (!activeBackpack || !canEditActive || isSavingActiveBackpack) return;
      const previousBackpack = cloneBaggage(activeBackpack);
      const nextBackpack = cloneBaggage(activeBackpack);
      const currentNeeded = getItemQuantity(nextBackpack.item_quantities, item);
      const nextNeeded = Math.max(1, currentNeeded + delta);
      const currentPacked = getPackedQuantity(nextBackpack.packed_quantities, item);
      nextBackpack.item_quantities = setItemQuantityInMap(
        nextBackpack.item_quantities,
        item,
        nextNeeded
      );
      nextBackpack.packed_quantities = setPackedQuantityInMap(
        nextBackpack.packed_quantities,
        item,
        Math.min(currentPacked, nextNeeded)
      );
      nextBackpack.checked_items = rebuildCheckedItems(nextBackpack);
      await syncBackpack(
        nextBackpack,
        {
          checked_items: nextBackpack.checked_items,
          item_quantities: nextBackpack.item_quantities,
          packed_quantities: nextBackpack.packed_quantities,
        },
        previousBackpack
      );
    },
    [activeBackpack, canEditActive, isSavingActiveBackpack, syncBackpack]
  );

  const handleAddItem = useCallback(
    async (event) => {
      event.preventDefault();
      if (!activeBackpack || !canEditActive || isSavingActiveBackpack) return;
      const value = newItem.trim();
      if (!value) return;

      const previousBackpack = cloneBaggage(activeBackpack);
      const nextBackpack = cloneBaggage(activeBackpack);
      const existingItem = nextBackpack.items.find(
        (item) => normalizeItemKey(item) === normalizeItemKey(value)
      );
      const targetItem = existingItem || value;

      if (!existingItem) {
        nextBackpack.items.push(value);
        nextBackpack.added_items = [...new Set([...(nextBackpack.added_items || []), value])];
      }

      nextBackpack.removed_items = nextBackpack.removed_items.filter(
        (item) => normalizeItemKey(item) !== normalizeItemKey(targetItem)
      );
      nextBackpack.item_quantities = setItemQuantityInMap(
        nextBackpack.item_quantities,
        targetItem,
        getItemQuantity(nextBackpack.item_quantities, targetItem)
      );
      nextBackpack.packed_quantities = setPackedQuantityInMap(
        nextBackpack.packed_quantities,
        targetItem,
        getPackedQuantity(nextBackpack.packed_quantities, targetItem)
      );
      nextBackpack.checked_items = rebuildCheckedItems(nextBackpack);
      setNewItem("");

      const updated = await syncBackpack(
        nextBackpack,
        {
          items: nextBackpack.items,
          checked_items: nextBackpack.checked_items,
          removed_items: nextBackpack.removed_items,
          added_items: nextBackpack.added_items,
          item_quantities: nextBackpack.item_quantities,
          packed_quantities: nextBackpack.packed_quantities,
        },
        previousBackpack
      );
      if (updated) {
        showToast(existingItem ? "Вернул вещь в багаж" : "Добавил вещь");
        getTelegramWebApp()?.HapticFeedback?.impactOccurred?.("light");
      } else {
        setNewItem(value);
      }
    },
    [activeBackpack, canEditActive, isSavingActiveBackpack, newItem, showToast, syncBackpack]
  );

  const handleRemoveItem = useCallback(
    async (item) => {
      if (!activeBackpack || !canEditActive || isSavingActiveBackpack) return;
      const previousBackpack = cloneBaggage(activeBackpack);
      const nextBackpack = cloneBaggage(activeBackpack);
      const normalizedItem = normalizeItemKey(item);
      if (!nextBackpack.removed_items.some((value) => normalizeItemKey(value) === normalizedItem)) {
        nextBackpack.removed_items.push(item);
      }
      nextBackpack.packed_quantities = setPackedQuantityInMap(
        nextBackpack.packed_quantities,
        item,
        0
      );
      nextBackpack.checked_items = rebuildCheckedItems(nextBackpack);
      setSheetItem(null);
      const updated = await syncBackpack(
        nextBackpack,
        {
          checked_items: nextBackpack.checked_items,
          removed_items: nextBackpack.removed_items,
          packed_quantities: nextBackpack.packed_quantities,
        },
        previousBackpack
      );
      if (updated) {
        showToast("Убрал вещь из багажа");
        getTelegramWebApp()?.HapticFeedback?.notificationOccurred?.("success");
      } else {
        setSheetItem(item);
      }
    },
    [activeBackpack, canEditActive, isSavingActiveBackpack, showToast, syncBackpack]
  );

  const handleMoveItem = useCallback(
    async (targetBackpackId) => {
      if (!checklist?.slug || !activeBackpack || !moveItem || !targetBackpackId || busy) return;
      setBusy(true);
      try {
        const updatedChecklist = await requestJson(`/checklists/${checklist.slug}/transfer-item`, {
          method: "POST",
          body: JSON.stringify({
            item: moveItem,
            source_backpack_id: activeBackpack.id,
            target_backpack_id: targetBackpackId,
          }),
        });
        setChecklist(updatedChecklist);
        setMoveItem(null);
        setSheetItem(null);
        showToast("Переложил вещь");
        getTelegramWebApp()?.HapticFeedback?.notificationOccurred?.("success");
      } catch (error) {
        showToast(error.message || "Не удалось переложить вещь");
      } finally {
        setBusy(false);
      }
    },
    [activeBackpack, busy, checklist?.slug, moveItem, requestJson, showToast]
  );

  const startRenameBaggage = useCallback((targetBaggage) => {
    setRenamingBaggageId(targetBaggage.id);
    setRenamingBaggageName(targetBaggage.name || "");
  }, []);

  const handleCreateBaggage = useCallback(async () => {
    const name = newBaggageName.trim();
    if (!name || !checklist?.slug || !user?.id || baggageMetaBusy) return;

    setBaggageMetaBusy(true);
    try {
      const created = await requestJson(`/checklists/${checklist.slug}/baggage`, {
        method: "POST",
        body: JSON.stringify({
          user_id: user.id,
          name,
          kind: guessBaggageKind(name),
        }),
      });
      replaceBackpacks([...(checklist?.backpacks || []), created]);
      setActiveBackpackId(created.id);
      setNewBaggageName("");
      showToast("Создал новый багаж");
    } catch (error) {
      showToast(error.message || "Не удалось создать багаж");
    } finally {
      setBaggageMetaBusy(false);
    }
  }, [baggageMetaBusy, checklist?.backpacks, checklist?.slug, newBaggageName, replaceBackpacks, requestJson, showToast, user?.id]);

  const handleRenameBaggage = useCallback(async (targetBaggage) => {
    const nextName = renamingBaggageName.trim();
    if (!nextName || baggageMetaBusy) return;

    setBaggageMetaBusy(true);
    try {
      const updated = await requestJson(`/baggage/${targetBaggage.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: nextName,
          kind: guessBaggageKind(nextName),
        }),
      });
      replaceBackpacks((checklist?.backpacks || []).map((item) => (item.id === updated.id ? updated : item)));
      setRenamingBaggageId(null);
      setRenamingBaggageName("");
      showToast("Переименовал багаж");
    } catch (error) {
      showToast(error.message || "Не удалось переименовать багаж");
    } finally {
      setBaggageMetaBusy(false);
    }
  }, [baggageMetaBusy, checklist?.backpacks, renamingBaggageName, replaceBackpacks, requestJson, showToast]);

  const handleDeleteBaggage = useCallback(async (targetBaggage) => {
    if (baggageMetaBusy) return;
    if (!window.confirm(`Удалить багаж «${targetBaggage.name || "Багаж"}»?`)) return;

    setBaggageMetaBusy(true);
    try {
      await requestJson(`/baggage/${targetBaggage.id}`, {
        method: "DELETE",
      });
      const nextBackpacks = (checklist?.backpacks || []).filter((item) => item.id !== targetBaggage.id);
      replaceBackpacks(nextBackpacks);
      if (activeBackpackId === targetBaggage.id) {
        const fallback =
          nextBackpacks.find((item) => item.user_id === user?.id && item.is_default) ||
          nextBackpacks.find((item) => item.user_id === user?.id) ||
          nextBackpacks[0];
        setActiveBackpackId(fallback?.id || null);
      }
      if (renamingBaggageId === targetBaggage.id) {
        setRenamingBaggageId(null);
        setRenamingBaggageName("");
      }
      showToast("Удалил багаж");
    } catch (error) {
      showToast(error.message || "Не удалось удалить багаж");
    } finally {
      setBaggageMetaBusy(false);
    }
  }, [activeBackpackId, baggageMetaBusy, checklist?.backpacks, renamingBaggageId, replaceBackpacks, requestJson, showToast, user?.id]);

  const openMapQuery = useCallback((query, fallbackUrl = "") => {
    const encodedQuery = encodeURIComponent(query);
    const webApp = getTelegramWebApp();
    const platform = String(webApp?.platform || "").toLowerCase();
    const yandexMapsUrl = `yandexmaps://maps.yandex.ru/?text=${encodedQuery}`;
    const yandexNavigatorUrl = `yandexnavi://map_search?text=${encodedQuery}`;
    const genericMapsUrl = /iphone|ipad|ios|macos/.test(platform)
      ? `maps://?q=${encodedQuery}`
      : `geo:0,0?q=${encodedQuery}`;
    const browserFallbackUrl = fallbackUrl || `https://yandex.ru/maps/?text=${encodedQuery}`;

    let fallbackHandled = false;
    const openFallback = () => {
      if (fallbackHandled) return;
      fallbackHandled = true;
      if (webApp?.openLink) {
        webApp.openLink(browserFallbackUrl);
        return;
      }
      window.open(browserFallbackUrl, "_blank", "noopener,noreferrer");
    };

    const handleVisibility = () => {
      if (document.hidden) {
        fallbackHandled = true;
      }
    };

    document.addEventListener("visibilitychange", handleVisibility, { once: true });

    try {
      window.location.href = yandexMapsUrl;
      window.setTimeout(() => {
        if (fallbackHandled) return;
        window.location.href = yandexNavigatorUrl;
      }, 400);
      window.setTimeout(() => {
        document.removeEventListener("visibilitychange", handleVisibility);
        if (!fallbackHandled) {
          try {
            window.location.href = genericMapsUrl;
          } catch {
            openFallback();
            return;
          }
        }
      }, 900);
      window.setTimeout(() => {
        document.removeEventListener("visibilitychange", handleVisibility);
        openFallback();
      }, 1200);
      return;
    } catch {
      document.removeEventListener("visibilitychange", handleVisibility);
    }
    openFallback();
  }, []);

  const openAttraction = useCallback((attraction) => {
    const query = buildAttractionQuery(attraction, activeAttractionCity || checklist?.city || "");
    openMapQuery(query, `https://yandex.ru/maps/?text=${encodeURIComponent(query)}`);
  }, [activeAttractionCity, checklist?.city, openMapQuery]);

  const openAttractionsBrowserSearch = useCallback(() => {
    const city = activeAttractionCity || checklist?.city || "";
    const query = `достопримечательности ${city}`.trim();
    const url = `https://yandex.ru/search/?text=${encodeURIComponent(query)}`;
    const webApp = getTelegramWebApp();
    if (webApp?.openLink) {
      webApp.openLink(url);
      return;
    }
    window.open(url, "_blank", "noopener,noreferrer");
  }, [activeAttractionCity, checklist?.city]);

  const selectedTripTitle = checklist?.city || "Luggify";
  const moveDestinations = baggage.filter(
    (item) => item.id !== activeBackpack?.id && canEditBaggage(item, user?.id, baggage)
  );
  const attractionPreview = attractions.slice(0, 2);
  const itineraryByDay = useMemo(() => {
    const groups = new Map();
    (checklist?.events || []).forEach((event) => {
      const dayKey = String(event?.event_date || "").trim();
      if (!dayKey) return;
      if (!groups.has(dayKey)) {
        groups.set(dayKey, []);
      }
      groups.get(dayKey).push(event);
    });

    return Array.from(groups.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([day, events]) => ({
        day,
        label: formatItineraryDayLabel(day),
        events: [...events].sort((a, b) => String(a.time || "").localeCompare(String(b.time || ""))),
      }));
  }, [checklist?.events]);

  if (authState === "loading") {
    return (
      <main className="tma-shell tma-centered">
        <div className="tma-loader" />
        <p>Открываю Luggify...</p>
      </main>
    );
  }

  if (authState === "missing" || authState === "error") {
    return (
      <main className="tma-shell tma-centered">
        <section className="tma-auth-card">
          <span className="tma-auth-kicker">Luggify mini app</span>
          <h1>Не вижу Telegram-сессию</h1>
          <p>{authError || "Закрой окно и открой mini app кнопкой Open Luggify в боте."}</p>
          <button type="button" onClick={() => window.location.reload()}>
            Попробовать ещё раз
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="tma-shell">
      <section className="tma-hero">
        <div>
          <h1>{selectedTripTitle}</h1>
          <p>
            {checklist ? formatDateRange(checklist) : "Выбери поездку"}
          </p>
        </div>
        <div className="tma-progress-ring" style={{ "--progress": `${totalProgress.percent}%` }}>
          <strong>{totalProgress.percent}%</strong>
        </div>
      </section>

      {toast && <div className="tma-toast">{toast}</div>}

      <section className="tma-trip-strip" aria-label="Поездки">
        {loadingTrips && <span className="tma-chip ghost">Загружаю поездки</span>}
        {!loadingTrips && checklists.length === 0 && (
          <div className="tma-empty-card">
            <strong>Поездок пока нет</strong>
            <span>Создай чеклист на сайте, и здесь появится мобильный редактор.</span>
          </div>
        )}
        {checklists.map((item) => (
          <button
            key={item.slug}
            className={`tma-trip-pill ${item.slug === selectedSlug ? "active" : ""}`}
            onClick={() => setSelectedSlug(item.slug)}
            type="button"
          >
            <strong>{item.city}</strong>
            <span>{formatDateRange(item)}</span>
          </button>
        ))}
      </section>

      {loadingChecklist && (
        <section className="tma-card">
          <div className="tma-skeleton wide" />
          <div className="tma-skeleton" />
          <div className="tma-skeleton short" />
        </section>
      )}

      {!loadingChecklist && checklist && (
        <>
          <section className="tma-summary-card">
            <div>
              <span>Собрано</span>
              <strong>
                {totalProgress.packed}/{totalProgress.total}
              </strong>
            </div>
            <div>
              <span>Багаж</span>
              <strong>{baggage.length}</strong>
            </div>
            <div>
              <span>Дней</span>
              <strong>{tripDays || "—"}</strong>
            </div>
          </section>

          {forecastPreview.length > 0 && (
            <section className="tma-info-section">
              <header>
                <span>Погода</span>
              </header>
              <div className="tma-weather-strip">
                {forecastPreview.map((day) => (
                  <article key={`${day.city || checklist.city}-${day.date}`} className="tma-weather-card">
                    <span>{formatForecastDate(day.date)}</span>
                    {day.icon && (
                      <img
                        src={`https://openweathermap.org/img/wn/${day.icon}@2x.png`}
                        alt={day.condition}
                      />
                    )}
                    <strong>
                      {formatTemperature(day.temp_min)} / {formatTemperature(day.temp_max)}
                    </strong>
                  </article>
                ))}
              </div>
            </section>
          )}

          {activeAttractionCity && (
            <section className="tma-info-section">
              <header>
                <span>Места</span>
                <button
                  type="button"
                  onClick={() => setShowAttractionsSheet(true)}
                  disabled={loadingAttractions || attractions.length === 0}
                  className="tma-more-btn"
                >
                  БОЛЬШЕ
                </button>
              </header>
              {attractionCities.length > 1 && (
                <div className="tma-city-tabs" aria-label="Города маршрута">
                  {attractionCities.map((city) => (
                    <button
                      key={city}
                      type="button"
                      className={`tma-city-tab ${city === activeAttractionCity ? "active" : ""}`}
                      onClick={() => setActiveAttractionCity(city)}
                    >
                      {city.split(",")[0]}
                    </button>
                  ))}
                </div>
              )}
              <div className="tma-attractions-preview">
                {loadingAttractions && (
                  <>
                    <div className="tma-attraction-preview skeleton" />
                    <div className="tma-attraction-preview skeleton" />
                  </>
                )}
                {!loadingAttractions &&
                  (attractionPreview.length > 0 ? (
                    attractionPreview.map((attraction) => (
                      <button
                        key={attraction.name}
                        type="button"
                        className="tma-attraction-preview"
                        onClick={() => openAttraction(attraction)}
                      >
                        {attraction.image && <img src={attraction.image} alt="" loading="lazy" />}
                        <span className="tma-attraction-copy">
                          <strong>{attraction.name}</strong>
                        </span>
                      </button>
                    ))
                  ) : (
                    <div className="tma-attractions-empty">
                      Подборка мест пока не загрузилась для этого города.
                    </div>
                  ))}
              </div>
            </section>
          )}

          {itineraryByDay.length > 0 && (
            <section className="tma-info-section">
              <header>
                <span>План</span>
              </header>
              <div className="tma-itinerary-list">
                {itineraryByDay.map((day) => (
                  <article key={day.day} className="tma-itinerary-day">
                    <div className="tma-itinerary-dayhead">
                      <strong>{day.label}</strong>
                      <span>{day.events.length} событий</span>
                    </div>
                    <div className="tma-itinerary-events">
                      {day.events.map((event) => (
                        <button
                          key={event.id}
                          type="button"
                          className="tma-itinerary-event"
                          onClick={() => {
                            if (!event.address) return;
                            openMapQuery(
                              buildMapQuery(event.title, event.address, checklist?.city || ""),
                              `https://yandex.ru/maps/?text=${encodeURIComponent(event.address)}`
                            );
                          }}
                          disabled={!event.address}
                        >
                          <div className="tma-itinerary-meta">
                            <b>{event.time || "Весь день"}</b>
                          </div>
                          <div className="tma-itinerary-copy">
                            <strong>{event.title}</strong>
                            {event.description && <p>{event.description}</p>}
                            {event.address && <small>{event.address}</small>}
                          </div>
                        </button>
                      ))}
                    </div>
                  </article>
                ))}
              </div>
            </section>
          )}

          {activeBackpack && (
            <button
              className="tma-baggage-switcher"
              type="button"
              onClick={() => setShowBaggagePicker(true)}
            >
              <span>
                <small>Текущий багаж</small>
                <strong>{activeBackpack.name || getBaggageKindLabel(activeBackpack)}</strong>
                <em>
                  {getBaggageOwnerLabel(activeBackpack, user?.id)} • {activeProgress.packed}/{activeProgress.total} собрано
                </em>
              </span>
              <b>Сменить</b>
            </button>
          )}

          {activeBackpack ? (
            <section className="tma-card tma-checklist-card">
              <header className="tma-section-head">
                <div>
                  <span>{activeBackpack.user_id === user?.id ? "Твой багаж" : "Багаж участника"}</span>
                  <h2>{activeBackpack.name || getBaggageKindLabel(activeBackpack)}</h2>
                </div>
                <div className="tma-mini-progress">
                  {activeProgress.packed}/{activeProgress.total}
                </div>
              </header>

              <div className="tma-progress-bar">
                <span style={{ width: `${activeProgress.percent}%` }} />
              </div>

              {!canEditActive && (
                <div className="tma-note">Этот багаж можно смотреть, но редактировать его нельзя.</div>
              )}

              <form className="tma-add-form" onSubmit={handleAddItem}>
                <input
                  value={newItem}
                  onChange={(event) => setNewItem(event.target.value)}
                  placeholder="Добавить вещь"
                  disabled={!canEditActive || isSavingActiveBackpack}
                />
                <button type="submit" disabled={!canEditActive || isSavingActiveBackpack || !newItem.trim()}>
                  +
                </button>
              </form>

              <div className="tma-item-list">
                {visibleItems.length === 0 && (
                  <div className="tma-empty-list">
                    <strong>Здесь пока пусто</strong>
                    <span>Добавь первую вещь, и чеклист станет живым.</span>
                  </div>
                )}

                {visibleItems.map((item) => {
                  const needed = getItemQuantity(activeBackpack.item_quantities || {}, item);
                  const packed = getPackedQuantity(activeBackpack.packed_quantities || {}, item);
                  const done = packed >= needed;
                  return (
                    <article key={item} className={`tma-item ${done ? "done" : ""}`}>
                      <button
                        type="button"
                        className="tma-item-main"
                        onClick={() => setSheetItem(item)}
                      >
                        <span className="tma-item-check">{done ? "✓" : packed > 0 ? packed : ""}</span>
                        <span>
                          <strong>{item}</strong>
                          <small>{packed}/{needed}</small>
                        </span>
                      </button>
                      <div className="tma-item-actions">
                        <button
                          type="button"
                          onClick={() => updatePackedQuantity(item, packed - 1)}
                          disabled={!canEditActive || isSavingActiveBackpack || packed <= 0}
                        >
                          -1
                        </button>
                        <button
                          type="button"
                          onClick={() => updatePackedQuantity(item, packed + 1)}
                          disabled={!canEditActive || isSavingActiveBackpack || packed >= needed}
                        >
                          +1
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>
            </section>
          ) : (
            <section className="tma-empty-card">
              <strong>Багажа пока нет</strong>
              <span>Добавь багаж в основном приложении, и он появится здесь.</span>
            </section>
          )}
        </>
      )}

      {showBaggagePicker && (
        <div className="tma-sheet-backdrop" onClick={() => setShowBaggagePicker(false)}>
          <section className="tma-sheet compact" onClick={(event) => event.stopPropagation()}>
            <div className="tma-sheet-handle" />
            <header>
              <span>Выбор багажа</span>
              <h2>С чем работаем?</h2>
            </header>
            <div className="tma-baggage-list">
              {baggage.map((item) => {
                const progress = getBaggageProgress(item);
                const isActive = item.id === activeBackpackId;
                const isOwnBaggage = item.user_id === user?.id;
                const isRenaming = renamingBaggageId === item.id;
                return (
                  <div key={item.id} className={`tma-baggage-card ${isActive ? "active" : ""}`}>
                    <div className="tma-baggage-card-row">
                      <button
                        type="button"
                        className={`tma-baggage-option ${isActive ? "active" : ""} ${!isRenaming ? "with-side" : ""} ${!isRenaming && isOwnBaggage ? "with-actions" : ""}`}
                        onClick={() => {
                          setActiveBackpackId(item.id);
                          setShowBaggagePicker(false);
                        }}
                      >
                        <span>
                          <small>{getBaggageOwnerLabel(item, user?.id)}</small>
                          <strong>{item.name || getBaggageKindLabel(item)}</strong>
                        </span>
                      </button>
                      {!isRenaming && (
                        <div className="tma-baggage-option-side">
                          <b>{progress.packed}/{progress.total}</b>
                          {isOwnBaggage && (
                            <div className="tma-baggage-inline-actions">
                              <button
                                type="button"
                                className="edit"
                                onClick={() => startRenameBaggage(item)}
                                disabled={baggageMetaBusy}
                                title="Переименовать багаж"
                                aria-label="Переименовать багаж"
                              >
                                ✎
                              </button>
                              <button
                                type="button"
                                className="danger"
                                onClick={() => handleDeleteBaggage(item)}
                                disabled={baggageMetaBusy}
                                title="Удалить багаж"
                                aria-label="Удалить багаж"
                              >
                                ×
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                    {isOwnBaggage && isRenaming && (
                      <div className={`tma-baggage-meta-actions ${isRenaming ? "renaming" : ""}`}>
                        <input
                          value={renamingBaggageName}
                          onChange={(event) => setRenamingBaggageName(event.target.value)}
                          placeholder="Название багажа"
                          disabled={baggageMetaBusy}
                        />
                        <button
                          type="button"
                          className="accent"
                          onClick={() => handleRenameBaggage(item)}
                          disabled={baggageMetaBusy || !renamingBaggageName.trim()}
                        >
                          Сохранить
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setRenamingBaggageId(null);
                            setRenamingBaggageName("");
                          }}
                          disabled={baggageMetaBusy}
                        >
                          Отмена
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            <div className="tma-baggage-create">
              <span>Новый багаж</span>
              <div className="tma-baggage-create-row">
                <input
                  value={newBaggageName}
                  onChange={(event) => setNewBaggageName(event.target.value)}
                  placeholder={ownBaggage.length === 0 ? "Рюкзак" : "Например, чемодан"}
                  disabled={baggageMetaBusy}
                />
                <button
                  type="button"
                  className="accent"
                  onClick={handleCreateBaggage}
                  disabled={baggageMetaBusy || !newBaggageName.trim()}
                >
                  Создать
                </button>
              </div>
            </div>
          </section>
        </div>
      )}

      {showAttractionsSheet && (
        <div className="tma-sheet-backdrop" onClick={() => setShowAttractionsSheet(false)}>
          <section className="tma-sheet compact" onClick={(event) => event.stopPropagation()}>
            <div className="tma-sheet-handle" />
            <header className="tma-sheet-header-row">
              <div>
                <span>Достопримечательности</span>
                <h2>{activeAttractionCity || checklist?.city}</h2>
              </div>
              <button
                type="button"
                className="tma-more-btn tma-sheet-more-btn"
                onClick={openAttractionsBrowserSearch}
              >
                ЕЩЁ БОЛЬШЕ
              </button>
            </header>
            <div className="tma-attractions-list">
              {attractions.map((attraction) => (
                <button
                  key={attraction.name}
                  type="button"
                  onClick={() => openAttraction(attraction)}
                >
                  {attraction.image && <img src={attraction.image} alt="" loading="lazy" />}
                  <span>
                    <strong>{attraction.name}</strong>
                  </span>
                </button>
              ))}
            </div>
          </section>
        </div>
      )}

      {sheetItem && activeBackpack && (
        <div className="tma-sheet-backdrop" onClick={() => setSheetItem(null)}>
          <section className="tma-sheet" onClick={(event) => event.stopPropagation()}>
            <div className="tma-sheet-handle" />
            <header>
              <span>Настройка вещи</span>
              <h2>{sheetItem}</h2>
            </header>
            <div className="tma-sheet-grid">
              <div>
                <span>Собрано</span>
                <strong>
                  {getPackedQuantity(activeBackpack.packed_quantities || {}, sheetItem)}/
                  {getItemQuantity(activeBackpack.item_quantities || {}, sheetItem)}
                </strong>
              </div>
              <div>
                <span>Нужно</span>
                <strong>{getItemQuantity(activeBackpack.item_quantities || {}, sheetItem)}</strong>
              </div>
            </div>
            <div className="tma-sheet-actions">
              <button
                type="button"
                onClick={() =>
                  updatePackedQuantity(
                    sheetItem,
                    getPackedQuantity(activeBackpack.packed_quantities || {}, sheetItem) - 1
                  )
                }
                disabled={!canEditActive || isSavingActiveBackpack}
              >
                -1 собрано
              </button>
              <button
                type="button"
                onClick={() =>
                  updatePackedQuantity(
                    sheetItem,
                    getPackedQuantity(activeBackpack.packed_quantities || {}, sheetItem) + 1
                  )
                }
                disabled={!canEditActive || isSavingActiveBackpack}
              >
                +1 собрано
              </button>
              <button
                type="button"
                className="accent"
                onClick={() =>
                  updatePackedQuantity(
                    sheetItem,
                    getPackedQuantity(activeBackpack.packed_quantities || {}, sheetItem) >=
                      getItemQuantity(activeBackpack.item_quantities || {}, sheetItem)
                      ? 0
                      : getItemQuantity(activeBackpack.item_quantities || {}, sheetItem)
                  )
                }
                disabled={!canEditActive || isSavingActiveBackpack}
              >
                ✓ всё
              </button>
            </div>
            <div className="tma-quantity-row">
              <span>Количество в списке</span>
              <div>
                <button
                  type="button"
                  onClick={() => updateNeededQuantity(sheetItem, -1)}
                  disabled={!canEditActive || isSavingActiveBackpack}
                >
                  -
                </button>
                <strong>{getItemQuantity(activeBackpack.item_quantities || {}, sheetItem)}</strong>
                <button
                  type="button"
                  onClick={() => updateNeededQuantity(sheetItem, 1)}
                  disabled={!canEditActive || isSavingActiveBackpack}
                >
                  +
                </button>
              </div>
            </div>
            <div className="tma-sheet-secondary">
              <button
                type="button"
                onClick={() => setMoveItem(sheetItem)}
                disabled={!canEditActive || isSavingActiveBackpack || moveDestinations.length === 0}
              >
                Переложить
              </button>
              <button
                type="button"
                className="danger"
                onClick={() => handleRemoveItem(sheetItem)}
                disabled={!canEditActive || isSavingActiveBackpack}
              >
                Убрать
              </button>
            </div>
          </section>
        </div>
      )}

      {moveItem && (
        <div className="tma-sheet-backdrop" onClick={() => setMoveItem(null)}>
          <section className="tma-sheet compact" onClick={(event) => event.stopPropagation()}>
            <div className="tma-sheet-handle" />
            <header>
              <span>Куда переложить</span>
              <h2>{moveItem}</h2>
            </header>
            <div className="tma-destination-list">
              {moveDestinations.map((destination) => (
                <button
                  key={destination.id}
                  type="button"
                  onClick={() => handleMoveItem(destination.id)}
                  disabled={busy}
                >
                  <strong>{destination.name || getBaggageKindLabel(destination)}</strong>
                  <span>
                    {destination.user_id === user?.id
                      ? "мой багаж"
                      : destination.user?.username || "участник"}
                  </span>
                </button>
              ))}
            </div>
          </section>
        </div>
      )}
    </main>
  );
}

export default TmaApp;
