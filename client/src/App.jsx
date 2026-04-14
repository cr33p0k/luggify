import React, { useState, useEffect } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import CitySelect from "./CitySelect";
import DateRangePicker from "./DateRangePicker";
import AuthModal from "./AuthModal";
import ProfilePage from "./ProfilePage";
import NavbarUserSearch from "./NavbarUserSearch";
import ConfirmDialog from "./ConfirmDialog";
import {
  PlaneIcon, TrainIcon, CarIcon, BusIcon,
  VacationIcon, BusinessIcon, ActiveIcon, BeachIcon, WinterIcon,
  CalendarIcon, SparkleIcon, WeatherIcon, LockIcon, UnlockIcon,
  ClockIcon, DropletIcon, WindIcon, BackpackIcon, HotelIcon, MuseumIcon, SmartphoneIcon, GlobeIcon
} from './Icons';
import "./App.css";
import "./AuthModal.css";
import AIChatWidget from "./AIChatWidget";
import "./AIChatWidget.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
import { TRANSLATIONS, formatDuration, pluralize } from "./i18n";

const FORECAST_DESKTOP_CARD_WIDTH = 146;
const FORECAST_DESKTOP_GAP = 12;

const getForecastRowLayout = (count) => {
  const safeCount = Math.max(1, Number(count) || 1);
  if (safeCount <= 7) return [safeCount];
  if (safeCount === 8) return [4, 4];
  if (safeCount === 9) return [5, 4];
  if (safeCount === 10) return [5, 5];
  if (safeCount <= 14) return [7, safeCount - 7];

  const rows = Math.ceil(safeCount / 7);
  const baseSize = Math.floor(safeCount / rows);
  const remainder = safeCount % rows;

  return Array.from({ length: rows }, (_, index) => baseSize + (index < remainder ? 1 : 0));
};

const getForecastRowWidth = (count) =>
  (count * FORECAST_DESKTOP_CARD_WIDTH) + (Math.max(0, count - 1) * FORECAST_DESKTOP_GAP);

const splitForecastDays = (days = []) => {
  const rows = [];
  let startIndex = 0;

  getForecastRowLayout(days.length).forEach((rowSize) => {
    rows.push(days.slice(startIndex, startIndex + rowSize));
    startIndex += rowSize;
  });

  return rows;
};

const safeParseJson = (value, fallback = null) => {
  if (!value) return fallback;
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
};

const readJsonSafely = async (response) => {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) return null;
  return response.json().catch(() => null);
};

const DEFAULT_PACKING_PROFILE = {
  gender: "unspecified",
  traveling_with_pet: false,
  has_allergies: false,
  always_include_items: [],
};

const normalizePackingProfileItems = (items = []) => {
  const normalized = [];
  (Array.isArray(items) ? items : []).forEach((rawValue) => {
    const item = String(rawValue || "").trim();
    if (!item || normalized.includes(item)) return;
    normalized.push(item);
  });
  return normalized;
};

const normalizePackingProfile = (value = {}) => {
  const rawGender = String(value?.gender || "").trim().toLowerCase();
  const gender = ["male", "female"].includes(rawGender) ? rawGender : "unspecified";
  return {
    gender,
    traveling_with_pet: Boolean(value?.traveling_with_pet),
    has_allergies: Boolean(value?.has_allergies),
    always_include_items: normalizePackingProfileItems(value?.always_include_items),
  };
};

const buildCheckedItemsMap = (items = [], checkedItems = [], quantityMap = {}, packedMap = {}) => {
  const checkedSet = new Set(checkedItems || []);
  return items.reduce((acc, item) => {
    const needed = getItemQuantity(quantityMap, item);
    const packed = getPackedQuantity(packedMap, item);
    acc[item] = packed >= needed || checkedSet.has(item);
    return acc;
  }, {});
};

const normalizeItemKey = (value) => (value || "").trim().toLowerCase().replaceAll("ё", "е");

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
    if (safeValue === 0) {
      return acc;
    }
    acc[normalizedKey] = safeValue;
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
  const parsedQuantity = Number(nextQuantity);
  if (!Number.isFinite(parsedQuantity) || parsedQuantity < 1) {
    delete nextMap[normalizedKey];
    return nextMap;
  }
  nextMap[normalizedKey] = Math.max(1, Math.round(parsedQuantity));
  return nextMap;
};

const setPackedQuantityInMap = (quantityMap = {}, item, nextQuantity) => {
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

const getBaggageEditorIds = (baggage) =>
  Array.isArray(baggage?.editor_user_ids)
    ? baggage.editor_user_ids.map((value) => Number(value)).filter((value) => Number.isFinite(value) && value > 0)
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
  if (uniqueIds.length > 0) {
    return uniqueIds;
  }
  return fallbackBaggage ? getBaggageEditorIds(fallbackBaggage) : [];
};

const canUserEditBaggage = (baggage, userId, allBackpacks = []) => {
  if (!baggage || !userId) return false;
  if (baggage.user_id === userId) return true;
  return getOwnerBaggageEditorIds(allBackpacks, baggage.user_id, baggage).includes(userId);
};

const sortBaggageList = (items = []) =>
  [...items].sort((a, b) => {
    if (Boolean(b.is_default) !== Boolean(a.is_default)) {
      return Number(Boolean(b.is_default)) - Number(Boolean(a.is_default));
    }
    if ((a.sort_order || 0) !== (b.sort_order || 0)) {
      return (a.sort_order || 0) - (b.sort_order || 0);
    }
    return (a.id || 0) - (b.id || 0);
  });

const sortAllBackpacks = (items = []) =>
  [...items].sort((a, b) => {
    if ((a.user_id || 0) !== (b.user_id || 0)) return (a.user_id || 0) - (b.user_id || 0);
    if (Boolean(b.is_default) !== Boolean(a.is_default)) {
      return Number(Boolean(b.is_default)) - Number(Boolean(a.is_default));
    }
    if ((a.sort_order || 0) !== (b.sort_order || 0)) {
      return (a.sort_order || 0) - (b.sort_order || 0);
    }
    return (a.id || 0) - (b.id || 0);
  });

const buildBaggageParticipants = (checklist, currentUser) => {
  const groups = new Map();

  const ensureGroup = (userId, username) => {
    if (!userId) return null;
    if (!groups.has(userId)) {
      groups.set(userId, {
        userId,
        username: username || `id:${userId}`,
        isCurrentUser: currentUser?.id === userId,
        isOwner: checklist?.user_id === userId,
        baggage: [],
      });
    }
    const group = groups.get(userId);
    if (username) {
      group.username = username;
    }
    group.isCurrentUser = currentUser?.id === userId;
    group.isOwner = checklist?.user_id === userId;
    return group;
  };

  (checklist?.backpacks || []).forEach((bp) => {
    const group = ensureGroup(bp.user_id, bp.user?.username || (currentUser?.id === bp.user_id ? currentUser.username : ""));
    if (group) {
      group.baggage.push(bp);
    }
  });

  if (currentUser && checklist?.user_id === currentUser.id) {
    ensureGroup(currentUser.id, currentUser.username);
  }

  return Array.from(groups.values())
    .map((group) => ({
      ...group,
      baggage: sortBaggageList(group.baggage),
    }))
    .sort((a, b) => {
      if (a.isCurrentUser !== b.isCurrentUser) return a.isCurrentUser ? -1 : 1;
      if (a.isOwner !== b.isOwner) return a.isOwner ? -1 : 1;
      return a.username.localeCompare(b.username, "ru");
    });
};

const normalizeUserId = (value) => {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : value;
};

const getChecklistParticipantIds = (checklist) => {
  const ids = new Set();
  if (checklist?.user_id) {
    ids.add(normalizeUserId(checklist.user_id));
  }
  (checklist?.backpacks || []).forEach((backpack) => {
    if (backpack.user_id) {
      ids.add(normalizeUserId(backpack.user_id));
    }
  });
  return ids;
};

const guessBaggageKind = (name) => {
  const normalized = (name || "").trim().toLowerCase();
  if (!normalized) return "custom";
  if (normalized.includes("чемод")) return "suitcase";
  if (normalized.includes("ручн") && normalized.includes("клад")) return "carry_on";
  if (normalized.includes("рюкзак")) return "backpack";
  if (normalized.includes("сумк")) return "bag";
  return "custom";
};

const getBaggageKindLabel = (baggage) => {
  const kind = baggage?.kind || guessBaggageKind(baggage?.name || "");
  if (kind === "suitcase") return "Чемодан";
  if (kind === "carry_on") return "Ручная кладь";
  if (kind === "bag") return "Сумка";
  if (kind === "custom") return "Багаж";
  return "Рюкзак";
};

const getBaggageVisibleItemCount = (baggage) => {
  const items = baggage?.items || [];
  const removed = new Set(baggage?.removed_items || []);
  return items.filter((item) => !removed.has(item)).length;
};

const getParticipantVisibleItemCount = (participant) =>
  (participant?.baggage || []).reduce((sum, baggage) => sum + getBaggageVisibleItemCount(baggage), 0);

const getInitial = (value = "") => (value.trim().charAt(0) || "?").toUpperCase();

const getBaggageMetaLine = (baggage) => {
  const name = (baggage?.name || "").trim().toLowerCase();
  const kindLabel = getBaggageKindLabel(baggage);
  const count = getBaggageVisibleItemCount(baggage);
  const parts = [];

  if (kindLabel.trim().toLowerCase() !== name) {
    parts.push(kindLabel);
  }
  parts.push(`${count} вещей`);
  return parts.join(" • ");
};

const escapeHtml = (value = "") =>
  String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");

const formatChecklistDateRange = (start, end) => {
  if (!start || !end) return "";
  const startDate = new Date(start);
  const endDate = new Date(end);
  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) return "";
  const startLabel = startDate.toLocaleDateString("ru-RU", { day: "numeric", month: "long" });
  const endLabel = endDate.toLocaleDateString("ru-RU", { day: "numeric", month: "long" });
  return `${startLabel} — ${endLabel}`;
};

const NOTIFICATION_CACHE_TTL_MS = 2000;
const notificationRequestCache = new Map();

const fetchNotificationsCached = async (authHeaders = {}) => {
  const cacheKey = authHeaders.Authorization || "__guest__";
  const now = Date.now();
  const cached = notificationRequestCache.get(cacheKey);

  if (cached?.promise) {
    return cached.promise;
  }

  if (cached && now - cached.timestamp < NOTIFICATION_CACHE_TTL_MS) {
    return cached.data;
  }

  const promise = fetch(`${API_URL}/notifications`, { headers: authHeaders })
    .then((response) => (response.ok ? response.json() : []))
    .then((data) => {
      notificationRequestCache.set(cacheKey, {
        data,
        timestamp: Date.now(),
        promise: null,
      });
      return data;
    })
    .catch((error) => {
      notificationRequestCache.delete(cacheKey);
      throw error;
    });

  notificationRequestCache.set(cacheKey, {
    data: cached?.data || [],
    timestamp: cached?.timestamp || 0,
    promise,
  });

  return promise;
};

const NotificationBell = ({ authHeaders, lang, navigate }) => {
  const [notifications, setNotifications] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const unreadCount = notifications.filter(n => !n.is_read).length;
  const refreshNotifications = React.useCallback(() => {
    fetchNotificationsCached(authHeaders)
      .then(setNotifications)
      .catch(e => console.error("Error fetching notifications:", e));
  }, [authHeaders]);

  useEffect(() => {
    refreshNotifications();
    const timer = setInterval(refreshNotifications, 30000);
    return () => clearInterval(timer);
  }, [refreshNotifications]);

  const markRead = async (id, link) => {
    try {
      await fetch(`${API_URL}/notifications/${id}/read`, {
        method: "PATCH",
        headers: authHeaders
      });
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
      if (link && typeof link === 'string') {
        navigate(link);
        setIsOpen(false);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleInviteAction = async (e, notif, action) => {
    e.stopPropagation();
    const token = notif.extra_data?.token;
    if (!token && action === 'accept') return;

    try {
      if (action === 'accept') {
        const res = await fetch(`${API_URL}/join/${token}`, {
          method: "POST",
          headers: authHeaders
        });
        if (res.ok) {
          const checklist = await res.json();
          if (window.location.pathname.includes(`/checklist/${checklist.slug}`)) {
            window.location.reload();
          } else {
            navigate(`/checklist/${checklist.slug}`);
          }
          setIsOpen(false);
        }
      }

      // Always mark as read
      await fetch(`${API_URL}/notifications/${notif.id}/read`, {
        method: "PATCH",
        headers: authHeaders
      });
      setNotifications(prev => prev.map(n => n.id === notif.id ? { ...n, is_read: true } : n));

      if (action === 'decline') {
        // Just refresh if we declined to update unread count locally
        refreshNotifications();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleFollowRequestAction = async (e, notif, action) => {
    e.stopPropagation();
    const requestId = notif.extra_data?.request_id;
    if (!requestId) return;

    try {
      const res = await fetch(`${API_URL}/follow-requests/${requestId}/${action}`, {
        method: "POST",
        headers: authHeaders
      });
      if (res.ok) {
        // Mark notification as read
        await fetch(`${API_URL}/notifications/${notif.id}/read`, {
          method: "PATCH",
          headers: authHeaders
        });
        setNotifications(prev => prev.map(n =>
          n.id === notif.id
            ? { ...n, is_read: true, _handled: action }
            : n
        ));
      }
    } catch (err) {
      console.error(err);
    }
  };

  const markAllRead = async () => {
    const unreadIds = notifications.filter(n => !n.is_read).map(n => n.id);
    for (const id of unreadIds) {
      fetch(`${API_URL}/notifications/${id}/read`, { method: "PATCH", headers: authHeaders }).catch(e => console.error(e));
    }
    setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
  };

  return (
    <div className="notification-bell-container">
      <button className="bell-btn" onClick={() => setIsOpen(!isOpen)}>
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="bell-svg"
        >
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        {unreadCount > 0 && <span className="bell-badge">{unreadCount}</span>}
      </button>

      {isOpen && (
        <div className="notifications-dropdown">
          <div className="notif-header">
            <span>{lang === 'ru' ? 'Уведомления' : 'Notifications'}</span>
            {notifications.length > 0 && (
              <button
                className={`mark-all-btn ${unreadCount > 0 ? 'has-unread' : 'all-read'}`}
                onClick={markAllRead}
                title={lang === 'ru' ? 'Прочитать всё' : 'Mark all read'}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 12l5 5L17 6" />
                  <path d="M7 12l5 5L23 6" />
                </svg>
              </button>
            )}
          </div>
          <div className="notif-list">
            {notifications.length > 0 ? notifications.map(n => (
              <div
                key={n.id}
                className={`notif-item ${!n.is_read ? 'unread' : ''}`}
                onClick={() => (n.type !== 'checklist_invitation' && n.type !== 'follow_request') && markRead(n.id, n.link)}
              >
                <div className="notif-content">{n.content}</div>
                {n.type === 'checklist_invitation' && !n.is_read && (
                  <div className="notif-actions">
                    <button
                      className="notif-action-btn accept"
                      onClick={(e) => handleInviteAction(e, n, 'accept')}
                    >
                      {lang === 'ru' ? 'Принять' : 'Accept'}
                    </button>
                    <button
                      className="notif-action-btn decline"
                      onClick={(e) => handleInviteAction(e, n, 'decline')}
                    >
                      {lang === 'ru' ? 'Отклонить' : 'Decline'}
                    </button>
                  </div>
                )}
                {n.type === 'follow_request' && !n.is_read && !n._handled && (
                  <div className="notif-actions">
                    <button
                      className="notif-action-btn accept"
                      onClick={(e) => handleFollowRequestAction(e, n, 'accept')}
                    >
                      {lang === 'ru' ? 'Принять' : 'Accept'}
                    </button>
                    <button
                      className="notif-action-btn decline"
                      onClick={(e) => handleFollowRequestAction(e, n, 'decline')}
                    >
                      {lang === 'ru' ? 'Отклонить' : 'Decline'}
                    </button>
                  </div>
                )}
                {n.type === 'follow_request' && n._handled && (
                  <div className="notif-actions">
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                      {n._handled === 'accept'
                        ? (lang === 'ru' ? '✓ Принято' : '✓ Accepted')
                        : (lang === 'ru' ? '✗ Отклонено' : '✗ Declined')}
                    </span>
                  </div>
                )}
                <div className="notif-time">
                  {new Date(n.created_at).toLocaleDateString(lang === 'ru' ? 'ru-RU' : 'en-US', { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>
            )) : (
              <div className="notif-empty">
                {lang === 'ru' ? 'Нет уведомлений' : 'No notifications'}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

const TelegramLinkButton = ({ user, token, onUserUpdate, lang }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [linkInfo, setLinkInfo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [hint, setHint] = useState("");

  const loadLinkInfo = async () => {
    setLoading(true);
    setError("");
    setCopied(false);
    setHint("");
    try {
      const res = await fetch(`${API_URL}/auth/telegram/link`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || (lang === "en" ? "Failed to prepare Telegram link" : "Не удалось подготовить ссылку Telegram"));
      }
      setLinkInfo(data);
      return data;
    } catch (e) {
      console.error(e);
      const message = e.message || (lang === "en" ? "Failed to prepare Telegram link" : "Не удалось подготовить ссылку Telegram");
      setError(message);
      return null;
    } finally {
      setLoading(false);
    }
  };

  const openModal = async () => {
    setIsOpen(true);
    await loadLinkInfo();
  };

  const unlinkTelegram = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/auth/telegram/link`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || (lang === "en" ? "Failed to unlink Telegram" : "Не удалось отвязать Telegram"));
      }
      onUserUpdate(data);
      return true;
    } catch (e) {
      console.error(e);
      setError(e.message || (lang === "en" ? "Failed to unlink Telegram" : "Не удалось отвязать Telegram"));
      return false;
    } finally {
      setLoading(false);
    }
  };

  const refreshStatus = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || (lang === "en" ? "Failed to refresh status" : "Не удалось обновить статус"));
      }
      onUserUpdate(data);
    } catch (e) {
      console.error(e);
      setError(e.message || (lang === "en" ? "Failed to refresh status" : "Не удалось обновить статус"));
    } finally {
      setLoading(false);
    }
  }, [lang, onUserUpdate, token]);

  useEffect(() => {
    if (!isOpen) return undefined;

    const handleFocus = () => {
      if (!user?.tg_id) {
        refreshStatus();
      }
    };

    window.addEventListener("focus", handleFocus);
    return () => window.removeEventListener("focus", handleFocus);
  }, [isOpen, refreshStatus, user?.tg_id]);

  const openTelegramBot = async (forceRefresh = false) => {
    const data = forceRefresh ? await loadLinkInfo() : (linkInfo || await loadLinkInfo());
    if (!data?.deep_link) {
      setError(lang === "en" ? "Telegram link is not ready yet" : "Ссылка на Telegram пока не готова");
      return;
    }

    let commandCopied = false;
    if (data.link_command && navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(data.link_command);
        commandCopied = true;
      } catch (e) {
        console.error(e);
      }
    }

    const popup = window.open(data.deep_link, "_blank", "noopener,noreferrer");
    if (!popup) {
      window.location.href = data.deep_link;
    }

    setCopied(commandCopied);
    setHint(
      commandCopied
        ? (lang === "en"
            ? "Bot opened. If Telegram only opens the chat, paste the copied /link command and send it."
            : "Бот открыт. Если Telegram просто открыл чат, вставь скопированную команду /link и отправь её.")
        : (lang === "en"
            ? "Bot opened. If nothing happened, return here and refresh the status."
            : "Бот открыт. Если ничего не произошло, вернись сюда и обнови статус.")
    );
  };

  const handlePrimaryAction = async () => {
    if (user?.tg_id) {
      const unlinked = await unlinkTelegram();
      if (!unlinked) {
        return;
      }
      setHint(
        lang === "en"
          ? "Previous Telegram binding has been removed. Continue in Telegram to link again."
          : "Старая привязка снята. Продолжи в Telegram, чтобы привязать аккаунт заново."
      );
      setCopied(false);
      setLinkInfo(null);
    }

    await openTelegramBot(Boolean(user?.tg_id));
  };

  const botHandle = `@${linkInfo?.bot_username || "luggify_bot"}`;
  const telegramUsername = user?.social_links?.telegram
    ? user.social_links.telegram.replace(/^@/, "")
    : "";

  if (!user || !token) {
    return null;
  }

  return (
    <>
      <button
        className={`navbar-telegram-btn ${user?.tg_id ? "linked" : ""}`}
        onClick={openModal}
        title={user?.tg_id
          ? (lang === "en" ? "Telegram connected" : "Telegram подключен")
          : (lang === "en" ? "Link Telegram" : "Привязать Telegram")}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <line x1="22" y1="2" x2="11" y2="13"></line>
          <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
        </svg>
        <span className="navbar-telegram-label">Telegram</span>
      </button>

      {isOpen && (
        <div className="modal-overlay modal-overlay-lifted telegram-modal-overlay" onClick={() => setIsOpen(false)}>
          <div className="modal-content telegram-modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setIsOpen(false)}>×</button>

            <div className="telegram-modal-head">
              <div className={`telegram-modal-badge ${user?.tg_id ? "linked" : ""}`}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <line x1="22" y1="2" x2="11" y2="13"></line>
                  <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                </svg>
              </div>
              <div>
                <h3 className="telegram-modal-title">Telegram</h3>
                <p className="telegram-modal-subtitle">
                  {user?.tg_id
                    ? (lang === "en"
                        ? "Account is already linked. You can reopen the bot or relink it."
                        : "Аккаунт уже связан. Можно открыть бота или перепривязать его.")
                    : (lang === "en"
                        ? "Link your site account with the bot so trips, AI and reminders work together."
                        : "Свяжи сайт и бота, чтобы поездки, AI и напоминания работали вместе.")}
                </p>
              </div>
            </div>

            <div className={`telegram-modal-status ${user?.tg_id ? "linked" : ""}`}>
              <span className="telegram-modal-status-label">
                {user?.tg_id
                  ? (lang === "en" ? "Status" : "Статус")
                  : (lang === "en" ? "Ready to link" : "Готово к привязке")}
              </span>
              <strong className="telegram-modal-status-value">
                {user?.tg_id
                  ? (telegramUsername
                      ? `@${telegramUsername}`
                      : (lang === "en" ? "Telegram is connected" : "Telegram подключен"))
                  : (lang === "en" ? "Not linked yet" : "Пока не привязан")}
              </strong>
            </div>

            <div className="telegram-modal-actions">
              <button className="telegram-modal-btn primary" onClick={handlePrimaryAction} disabled={loading}>
                {loading
                  ? "..."
                  : user?.tg_id
                    ? (lang === "en" ? "Relink Telegram" : "Перепривязать")
                    : (lang === "en" ? "Open bot" : "Открыть бота")}
              </button>
              <button className="telegram-modal-btn secondary" onClick={refreshStatus} disabled={loading}>
                {lang === "en" ? "Refresh status" : "Проверить статус"}
              </button>
            </div>

            {!user?.tg_id && (
              <div className="telegram-modal-note">
                {hint
                  ? hint
                  : (lang === "en"
                      ? `Open ${botHandle}. If Telegram does not trigger linking automatically, paste the /link command that we copy for you.`
                      : `Открой ${botHandle}. Если Telegram не запустит привязку сам, просто вставь команду /link, которую мы скопируем за тебя.`)}
              </div>
            )}

            {copied && !user?.tg_id && (
              <div className="telegram-modal-expiry">
                {lang === "en" ? "The /link command has been copied." : "Команда /link уже скопирована."}
              </div>
            )}

            {error && <div className="telegram-modal-error">{error}</div>}
          </div>
        </div>
      )}
    </>
  );
};

// === Sub-components for travel services ===

const TravelSectionShell = React.memo(({
  sectionKey,
  title,
  icon,
  children,
  defaultExpanded = true,
  actions = null,
  summary = "",
}) => {
  const [expanded, setExpanded] = useState(defaultExpanded);

  useEffect(() => {
    setExpanded(defaultExpanded);
  }, [defaultExpanded, sectionKey]);

  return (
    <div className={`travel-section travel-section-shell${expanded ? " expanded" : " collapsed"}`}>
      <div className="travel-section-header">
        <button
          type="button"
          className="travel-section-trigger"
          onClick={() => setExpanded((prev) => !prev)}
        >
          <span className="travel-section-title-wrap">
            <span className="travel-section-title-icon">{icon}</span>
            <span className="travel-section-title-copy">
              <span className="travel-section-title-text">{title}</span>
              {!expanded && summary && (
                <span className="travel-section-summary">{summary}</span>
              )}
            </span>
          </span>
        </button>
        <div className="travel-section-header-actions">
          {actions}
          <button
            type="button"
            className="collapse-toggle"
            onClick={() => setExpanded((prev) => !prev)}
            aria-expanded={expanded}
          >
            <span className={`chevron ${expanded ? "up" : ""}`}>▾</span>
          </button>
        </div>
      </div>
      {expanded && <div className="travel-section-body">{children}</div>}
    </div>
  );
});

const AttractionsCityBlock = React.memo(({ city, lang, limit }) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [expandedMap, setExpandedMap] = useState(null);

  useEffect(() => {
    if (!city) return;
    setLoading(true);
    setLoaded(false);
    fetch(`${API_URL}/attractions?city=${encodeURIComponent(city)}&lang=${lang}&limit=${limit}`)
      .then(r => r.json())
      .then(d => setData(d.attractions || []))
      .catch(() => setData([]))
      .finally(() => { setLoading(false); setLoaded(true); });
  }, [city, lang, limit]);

  if (loaded && data.length === 0) return null;
  if (!loaded && !loading) return null;

  return (
    <>
      {loading ? (
        <div className="section-loading">
          <div className="loading-spinner-wrap">
            <div className="loading-spinner" />
            <span className="loading-text">{TRANSLATIONS[lang].searchingAttractions}</span>
          </div>
        </div>
      ) : (
        <div className="attractions-grid">
          {data.map((a, i) => (
            <div key={i} className="attraction-card">
              <a href={lang === 'ru' ? `https://yandex.ru/search/?text=${encodeURIComponent(a.name + ' ' + city)}` : `https://www.google.com/search?q=${encodeURIComponent(a.name + ' ' + city)}`} target="_blank" rel="noopener noreferrer" className="attraction-bg-link">
                {a.image && <img src={a.image} alt={a.name} className="attraction-img" loading="lazy" />}
                <div className="attraction-body">
                  <div className="attraction-name">{a.name}</div>
                </div>
              </a>
              <div
                className={`attraction-map-btn ${expandedMap === i ? 'active' : ''}`}
                onClick={() => setExpandedMap(expandedMap === i ? null : i)}
                title={lang === 'ru' ? 'Показать на карте' : 'Show on map'}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                  <circle cx="12" cy="10" r="3" />
                </svg>

                {expandedMap === i && (
                  <div className="attraction-map-popup" onClick={e => e.stopPropagation()}>
                    <a
                      href={`https://yandex.ru/maps/?text=${encodeURIComponent(a.name + ' ' + city)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="map-link yandex"
                    >
                      Яндекс Карты
                    </a>
                    <a
                      href={a.link || `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(a.name + ', ' + city)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="map-link google"
                    >
                      Google Maps
                    </a>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
});

const AttractionsSection = React.memo(({ city, lang, compact = false }) => {
  const citiesList = city ? (city.includes(" + ") ? city.split(" + ").map(c => c.trim()) : [city]) : [];
  const primaryCity = citiesList[0] || "";
  const [activeCity, setActiveCity] = useState(primaryCity);
  const limit = citiesList.length > 1 ? 5 : 10;
  const sectionSummary = compact
    ? `${citiesList.length > 1 ? citiesList.length : limit} ${lang === "en" ? "spots" : "мест"}`
    : "";

  useEffect(() => {
    setActiveCity(primaryCity);
  }, [primaryCity]);

  if (!city) return null;

  return (
    <TravelSectionShell
      sectionKey={`attractions-${city}-${lang}-${compact ? "compact" : "full"}`}
      title={TRANSLATIONS[lang].whatToSee}
      icon={<MuseumIcon />}
      defaultExpanded={!compact}
      summary={sectionSummary}
    >
      {citiesList.length > 1 && (
        <div className="city-tabs">
          {citiesList.map((c, i) => (
            <button
              key={i}
              className={`city-tab ${activeCity === c ? "active" : ""}`}
              onClick={() => setActiveCity(c)}
            >
              {c.split(",")[0]}
            </button>
          ))}
        </div>
      )}
      <div key={activeCity}>
        <AttractionsCityBlock city={activeCity} lang={lang} limit={limit} />
      </div>
      <div style={{ display: "flex", justifyContent: "center", marginTop: "1rem" }}>
        <a
          href={`https://www.google.com/search?q=${encodeURIComponent((lang === "ru" ? "Достопримечательности " : "Attractions ") + activeCity.split(",")[0])}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flights-search-btn"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg>
          {TRANSLATIONS[lang].showMoreAttractions || "Показать больше"}
        </a>
      </div>
    </TravelSectionShell>
  );
});

const FlightsSection = React.memo(({ city, startDate, origin, returnDate, lang, compact = false }) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const [genericLink, setGenericLink] = useState("");

  useEffect(() => {
    if (!city) return;
    setLoading(true);
    setLoaded(false);
    const params = new URLSearchParams({ destination: city });
    if (startDate) params.append("date", startDate);
    if (origin) params.append("origin", origin);
    if (returnDate) params.append("return_date", returnDate);
    fetch(`${API_URL}/flights/search?${params}`)
      .then(r => r.json())
      .then(d => {
        setData(d.flights || []);
        if (d.generic_link) setGenericLink(d.generic_link);
      })
      .catch(() => setData([]))
      .finally(() => { setLoading(false); setLoaded(true); });
  }, [city, startDate, origin, returnDate]);

  if (loaded && data.length === 0 && !genericLink) return null;
  const t = TRANSLATIONS[lang] || TRANSLATIONS.ru;

  return (
    <TravelSectionShell
      sectionKey={`flights-${city}-${startDate || ""}-${returnDate || ""}-${compact ? "compact" : "full"}`}
      title={t.flightsTitle}
      icon={<PlaneIcon />}
      defaultExpanded={!compact}
      summary={loading ? (lang === "en" ? "Loading" : "Загружается") : (lang === "en" ? "Flight ideas" : "Подборка билетов")}
    >
      {loading ? (
        <div className="loading-spinner-wrap">
          <div className="loading-spinner" />
          <span className="loading-text">{t.searchingFlights}</span>
        </div>
      ) : (
        <>
          {data.length > 0 && (
            <div style={{ display: "flex", gap: "2rem", flexWrap: "wrap", marginBottom: "1.5rem" }}>
              {data.filter(f => f.type === "outbound" || !f.type).length > 0 && (
                <div style={{ flex: "1 1 300px" }}>
                  <h4 style={{ margin: "0 0 0.75rem 0", color: "#9ca3af", fontSize: "0.95rem", fontWeight: "600" }}>{t.outboundFlights}</h4>
                  <div className="flights-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
                    {data.filter(f => f.type === "outbound" || !f.type).map((f, i) => (
                      <a key={`out-${i}`} href={f.link} target="_blank" rel="noopener noreferrer" className="flight-card" style={{ height: "100%" }}>
                        {f.tag && <div className="flight-tag">{f.tag}</div>}
                        <div className="flight-price">{f.price ? `${f.price.toLocaleString("ru-RU")} ₽` : t.priceOnRequest}</div>
                        <div className="flight-route">
                          {f.origin} → {f.destination}
                        </div>
                        {f.departure_at && (
                          <div className="flight-date">
                            {new Date(f.departure_at).toLocaleDateString("ru-RU", { day: "numeric", month: "short" })}
                          </div>
                        )}
                        <div className="flight-info">
                          {f.airline && <span style={{ display: 'inline-flex', alignItems: 'center' }}><PlaneIcon style={{ width: '16px', height: '16px', marginRight: '4px', marginTop: '-2px' }} /> {f.airline}</span>}
                          <span>{f.transfers === 0 ? t.directFlight : pluralize(f.transfers, ['пересадка', 'пересадки', 'пересадок'], ['stop', 'stops'], lang)}</span>
                          {f.duration > 0 && <span style={{ display: 'inline-flex', alignItems: 'center' }}><ClockIcon style={{ width: '16px', height: '16px', marginRight: '4px', marginTop: '-1px' }} /> {formatDuration(f.duration, lang)}</span>}
                        </div>
                      </a>
                    ))}
                  </div>
                </div>
              )}
              {data.filter(f => f.type === "inbound").length > 0 && (
                <div style={{ flex: "1 1 300px" }}>
                  <h4 style={{ margin: "0 0 0.75rem 0", color: "#9ca3af", fontSize: "0.95rem", fontWeight: "600" }}>{t.inboundFlights}</h4>
                  <div className="flights-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
                    {data.filter(f => f.type === "inbound").map((f, i) => (
                      <a key={`in-${i}`} href={f.link} target="_blank" rel="noopener noreferrer" className="flight-card" style={{ height: "100%" }}>
                        {f.tag && <div className="flight-tag">{f.tag}</div>}
                        <div className="flight-price">{f.price ? `${f.price.toLocaleString("ru-RU")} ₽` : t.priceOnRequest}</div>
                        <div className="flight-route">
                          {f.origin} → {f.destination}
                        </div>
                        {f.departure_at && (
                          <div className="flight-date">
                            {new Date(f.departure_at).toLocaleDateString("ru-RU", { day: "numeric", month: "short" })}
                          </div>
                        )}
                        <div className="flight-info">
                          {f.airline && <span style={{ display: 'inline-flex', alignItems: 'center' }}><PlaneIcon style={{ width: '16px', height: '16px', marginRight: '4px', marginTop: '-2px' }} /> {f.airline}</span>}
                          <span>{f.transfers === 0 ? t.directFlight : pluralize(f.transfers, ['пересадка', 'пересадки', 'пересадок'], ['stop', 'stops'], lang)}</span>
                          {f.duration > 0 && <span style={{ display: 'inline-flex', alignItems: 'center' }}><ClockIcon style={{ width: '16px', height: '16px', marginRight: '4px', marginTop: '-1px' }} /> {formatDuration(f.duration, lang)}</span>}
                        </div>
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          {data.length === 0 && genericLink && (
            <div style={{ marginBottom: "1rem", textAlign: "center", color: "#9ca3af" }}>
              {t.noCachedTickets}<br /><br />
            </div>
          )}
          {genericLink && (
            <div style={{ display: "flex", justifyContent: "center", width: "100%", marginTop: "1rem" }}>
              <a href={genericLink} target="_blank" rel="noopener noreferrer" className="flights-search-btn">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z" /></svg>
                {t.searchReturnTickets}
              </a>
            </div>
          )}
        </>
      )}
    </TravelSectionShell>
  );
});

const HotelsSection = React.memo(({ city, startDate, endDate, lang, compact = false }) => {
  const citiesList = city ? city.split("+").map(c => c.trim()) : [];
  const primaryCity = citiesList[0] || "";
  const [activeCity, setActiveCity] = useState(primaryCity);

  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [triggered, setTriggered] = useState(false);

  const [provider, setProvider] = useState(null);
  const [links, setLinks] = useState({});

  const [adults, setAdults] = useState(2);
  const [childrenAges, setChildrenAges] = useState([]);
  const [showGuestMenu, setShowGuestMenu] = useState(false);

  const doFetch = () => {
    if (!activeCity) return;
    setLoading(true);
    setLoaded(false);
    setTriggered(true);
    const params = new URLSearchParams({ city: activeCity, adults });
    if (startDate) params.append("check_in", startDate);
    if (endDate) params.append("check_out", endDate);
    if (childrenAges.length > 0) params.append("children_ages", childrenAges.join(","));
    fetch(`${API_URL}/hotels/search?${params}&limit_per_city=${citiesList.length > 1 ? 5 : 10}`)
      .then(r => r.json())
      .then(d => {
        setData(d.hotels || []);
        setProvider(d.provider || null);
        setLinks(d.links || {});
      })
      .catch(() => setData([]))
      .finally(() => { setLoading(false); setLoaded(true); });
  };

  const cLower = activeCity ? activeCity.toLowerCase() : "";
  const ruCities = [
    "москва", "санкт-петербург", "питер", "спб", "сочи", "казань",
    "новосибирск", "екатеринбург", "нижний новгород", "краснодар",
    "калининград", "владивосток", "анапа", "геленджик", "адлер"
  ];
  const isRussia = cLower.includes("россия") || cLower.includes("russia") || ruCities.some(rc => cLower.includes(rc));

  const childrenQuery = childrenAges.length > 0 ? `&group_children=${childrenAges.length}` + childrenAges.map(age => `&age=${age}`).join("") : "";
  const bookingDirectLink = activeCity ? `https://www.booking.com/searchresults.html?ss=${encodeURIComponent(activeCity.split(",")[0].trim())}${startDate ? `&checkin=${startDate}` : ""}${endDate ? `&checkout=${endDate}` : ""}&group_adults=${adults}${childrenQuery}&no_rooms=1` : "#";

  useEffect(() => {
    setActiveCity(primaryCity);
  }, [primaryCity]);

  useEffect(() => {
    if (!activeCity) return;
    setTriggered(false);
    setData([]);
    setProvider(null);
    setLoaded(false);
    if (isRussia) {
      doFetch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeCity]);

  if (!city) return null;

  const t = TRANSLATIONS[lang] || TRANSLATIONS.ru;

  return (
    <TravelSectionShell
      sectionKey={`hotels-${city}-${startDate || ""}-${endDate || ""}-${compact ? "compact" : "full"}`}
      title={t.hotelsTitle}
      icon={<HotelIcon />}
      defaultExpanded={!compact}
      summary={triggered
        ? `${data.length || 0} ${lang === "en" ? "options" : "вариантов"}`
        : (lang === "en" ? "Ready when needed" : "Под рукой, когда понадобится")}
      actions={
        loaded && data.length > 0 && provider !== "ru_widgets" && !isRussia ? (
          <a href={bookingDirectLink} target="_blank" rel="noopener noreferrer" className="booking-corner-link" title={t.goToBooking}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </a>
        ) : null
      }
    >
      {citiesList.length > 1 && (
        <div className="city-tabs">
          {citiesList.map((c, i) => (
            <button
              key={i}
              className={`city-tab ${activeCity === c ? "active" : ""}`}
              onClick={() => setActiveCity(c)}
            >
              {c.split(",")[0]}
            </button>
          ))}
        </div>
      )}
      <div className="hotels-filter-wrap">
        <div className="guest-selector-container">
          <button className="guest-selector-toggle" onClick={() => setShowGuestMenu(!showGuestMenu)}>
            <span>👥 {adults} {t.adults.toLowerCase()}{childrenAges.length > 0 ? `, ${childrenAges.length} ${t.children.toLowerCase()}` : ""}</span>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ transform: showGuestMenu ? "rotate(180deg)" : "none", transition: "transform 0.2s" }}><polyline points="6 9 12 15 18 9"></polyline></svg>
          </button>
          {showGuestMenu && (
            <div className="guest-selector-dropdown">
              <div className="guest-row">
                <div className="guest-info">
                  <span className="guest-label">{t.adults}</span>
                </div>
                <div className="guest-controls">
                  <button onClick={() => setAdults(Math.max(1, adults - 1))} className="guest-control-btn">-</button>
                  <span className="guest-value">{adults}</span>
                  <button onClick={() => setAdults(adults + 1)} className="guest-control-btn">+</button>
                </div>
              </div>
              <div className="guest-row">
                <div className="guest-info">
                  <span className="guest-label">{t.children}</span>
                </div>
                <div className="guest-controls">
                  <button onClick={() => setChildrenAges(childrenAges.slice(0, -1))} className="guest-control-btn" disabled={childrenAges.length === 0}>-</button>
                  <span className="guest-value">{childrenAges.length}</span>
                  <button onClick={() => setChildrenAges([...childrenAges, 7])} className="guest-control-btn">+</button>
                </div>
              </div>
              {childrenAges.length > 0 && (
                <div className="children-ages-wrap">
                  {childrenAges.map((age, idx) => (
                    <div key={idx} className="child-age-row">
                      <span className="child-age-label">{t.childAge} {idx + 1}</span>
                      <select
                        value={age}
                        onChange={(e) => {
                          const newAges = [...childrenAges];
                          newAges[idx] = parseInt(e.target.value, 10);
                          setChildrenAges(newAges);
                        }}
                        className="child-age-select"
                      >
                        {[...Array(18)].map((_, i) => (
                          <option key={i} value={i}>{i}</option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
              )}
              <button className="guest-done-btn" onClick={() => {
                setShowGuestMenu(false);
                if (triggered) doFetch();
              }}>{t.doneBtn}</button>
            </div>
          )}
        </div>
        <div className="hotels-buttons-row">
          {!triggered && (
            <button className="flights-search-btn" onClick={doFetch}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
                <polyline points="9 22 9 12 15 12 15 22" />
              </svg>
              {t.showHotels}
            </button>
          )}
          {!isRussia && (
            <a href={bookingDirectLink} target="_blank" rel="noopener noreferrer" className="booking-secondary-btn" title={t.searchDirectlyBooking}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                <polyline points="15 3 21 3 21 9"></polyline>
                <line x1="10" y1="14" x2="21" y2="3"></line>
              </svg>
              {t.goToBooking}
            </a>
          )}
        </div>
      </div>
      {loading ? (
        <div className="loading-spinner-wrap">
          <div className="loading-spinner" />
          <span className="loading-text">{t.searchingHotels}</span>
        </div>
      ) : provider === "ru_widgets" ? (
        <div className="ru-widgets-container">
          <div className="ru-widgets-text">
            {t.ruWidgetsDisclaimer}
          </div>
          <div className="ru-widgets-grid">
            <a href={links.ostrovok} target="_blank" rel="noopener noreferrer" className="ru-widget-card">
              <div className="ru-widget-icon">
                <HotelIcon style={{ width: '28px', height: '28px' }} />
              </div>
              <h4 className="ru-widget-title">Ostrovok.ru</h4>
              <p className="ru-widget-description">
                <span className="ru-widget-copy-full">
                  {lang === "en"
                    ? "Hotels and apartments across Russia"
                    : "Более миллиона отелей и апартаментов по всей России"}
                </span>
                <span className="ru-widget-copy-mobile">
                  {lang === "en" ? "Hotels in Russia" : "Отели и апартаменты"}
                </span>
              </p>
              <div className="ru-widget-cta">
                <span className="ru-widget-cta-full">{lang === "en" ? "Search Ostrovok" : "Поиск на Ostrovok"}</span>
                <span className="ru-widget-cta-mobile">{lang === "en" ? "Open" : "Открыть"}</span>
              </div>
            </a>
            <a href={links.sutochno} target="_blank" rel="noopener noreferrer" className="ru-widget-card">
              <div className="ru-widget-icon">
                <GlobeIcon style={{ width: '28px', height: '28px' }} />
              </div>
              <h4 className="ru-widget-title">Суточно.ру</h4>
              <p className="ru-widget-description">
                <span className="ru-widget-copy-full">
                  {lang === "en"
                    ? "Private apartments and daily rentals"
                    : "Лучший сервис для аренды частного жилья и квартир"}
                </span>
                <span className="ru-widget-copy-mobile">
                  {lang === "en" ? "Daily rentals" : "Квартиры посуточно"}
                </span>
              </p>
              <div className="ru-widget-cta">
                <span className="ru-widget-cta-full">{lang === "en" ? "Search Sutochno" : "Поиск на Суточно"}</span>
                <span className="ru-widget-cta-mobile">{lang === "en" ? "Open" : "Открыть"}</span>
              </div>
            </a>
          </div>
        </div>
      ) : loaded && data.length === 0 ? (
        <div style={{ textAlign: "center", color: "#9ca3af", padding: "1rem 0" }}>
          {t.noHotelsFound}
        </div>
      ) : (
        <div className="hotels-grid">
          {data.map((h, i) => (
            <a key={i} href={h.link} target="_blank" rel="noopener noreferrer" className="hotel-card">
              {h.image ? (
                <img src={h.image} alt={h.name} className="hotel-img" loading="lazy" />
              ) : (
                <div className="hotel-img-placeholder" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}><HotelIcon style={{ width: '32px', height: '32px', color: 'var(--text-secondary)' }} /></div>
              )}
              <div className="hotel-body">
                <div className="hotel-name">{h.name}</div>
                <div className="hotel-meta">
                  {h.stars > 0 && <span className="hotel-stars">{"★".repeat(h.stars)}</span>}
                  {h.rating && (
                    <span className="hotel-rating-badge">
                      {h.rating}
                      {h.review_word && <span className="hotel-review-word"> · {h.review_word}</span>}
                    </span>
                  )}
                </div>
                {h.price_per_night && (
                  <div className="hotel-price">
                    {h.currency === "RUB"
                      ? `${h.price_per_night.toLocaleString("ru-RU")} ₽ / ${t.perNight}`
                      : `${h.currency === "EUR" ? "€" : h.currency === "USD" ? "$" : h.currency} ${h.price_per_night.toLocaleString("ru-RU")} / ${t.perNight}`}
                    {h.price_rub && h.currency !== "RUB" && (
                      <span className="hotel-price-rub"> (~{h.price_rub.toLocaleString("ru-RU")} ₽)</span>
                    )}
                  </div>
                )}
              </div>
            </a>
          ))}
        </div>
      )}
    </TravelSectionShell>
  );
});

const EsimSection = React.memo(({ city, lang, compact = false }) => {
  const citiesList = city ? (city.includes(" + ") ? city.split(" + ").map(c => c.trim()) : [city]) : [];
  const [activeCity, setActiveCity] = useState(citiesList[0] || "");

  const [data, setData] = useState(null);
  const [browseLink, setBrowseLink] = useState("");
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!activeCity) return;
    setData(null);
    setBrowseLink("");
    setLoading(true);
    setLoaded(false);
    const params = new URLSearchParams({ city: activeCity, lang });
    fetch(`${API_URL}/esim/search?${params}`)
      .then(r => r.json())
      .then(d => {
        setData(d.esim || null);
        if (d.browse_link) setBrowseLink(d.browse_link);
      })
      .catch(() => setData(null))
      .finally(() => { setLoading(false); setLoaded(true); });
  }, [activeCity, lang]);

  if (loaded && !data && !browseLink) return null;
  if (!loaded && !loading) return null;

  const t = TRANSLATIONS[lang] || TRANSLATIONS.ru;

  return (
    <TravelSectionShell
      sectionKey={`esim-${city}-${lang}-${compact ? "compact" : "full"}`}
      title={t.esimTitle}
      icon={<SmartphoneIcon />}
      defaultExpanded={!compact}
      summary={lang === "en" ? "Connectivity" : "Связь в поездке"}
    >
      {citiesList.length > 1 && (
        <div className="city-tabs">
          {citiesList.map((c, i) => (
            <button
              key={i}
              className={`city-tab ${activeCity === c ? "active" : ""}`}
              onClick={() => setActiveCity(c)}
            >
              {c.split(",")[0]}
            </button>
          ))}
        </div>
      )}
      {loading ? (
        <div className="skeleton-grid">
          <div className="skeleton-card short" />
        </div>
      ) : (
        <div className="esim-content">
          {data ? (
            <div className="esim-card">
              <div className="esim-icon" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}><SmartphoneIcon style={{ width: '32px', height: '32px' }} /></div>
              <div className="esim-details">
                <div className="esim-country">{data.country}</div>
                <div className="esim-provider">
                  <span className="esim-provider-badge">Airalo</span>
                </div>
                <div className="esim-description">
                  {t.esimDesc}
                </div>
              </div>
              <a href={data.link} target="_blank" rel="noopener noreferrer" className="esim-cta-btn">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="5" y="2" width="14" height="20" rx="2" ry="2" /><line x1="12" y1="18" x2="12" y2="18" />
                </svg>
                {t.chooseEsim}
              </a>
            </div>
          ) : (
            browseLink && (
              <div className="esim-card esim-generic">
                <div className="esim-icon" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}><GlobeIcon style={{ width: '32px', height: '32px' }} /></div>
                <div className="esim-details">
                  <div className="esim-description">
                    {t.esimDescBrowse}
                  </div>
                </div>
                <a href={browseLink} target="_blank" rel="noopener noreferrer" className="esim-cta-btn">
                  {t.browseEsim}
                </a>
              </div>
            )
          )}
        </div>
      )}
    </TravelSectionShell>
  );
});

// === Itinerary Section ===
const ItinerarySection = React.memo(({ checklist, lang, slug, isOwner, realOwnerId, currentUserId, hiddenSections, onToggleVisibility, requestConfirm }) => {
  const [events, setEvents] = useState(checklist?.events || []);
  const [addingDay, setAddingDay] = useState(null);
  const [newEvent, setNewEvent] = useState({ time: "", title: "", description: "", address: "" });
  const [loading, setLoading] = useState(false);
  const [showItinerary, setShowItinerary] = useState(false);
  const [expandedAddress, setExpandedAddress] = useState(null);
  const [editingEvent, setEditingEvent] = useState(null);
  const [editData, setEditData] = useState({ time: "", title: "", description: "", address: "" });
  const t = TRANSLATIONS[lang] || TRANSLATIONS.ru;
  const token = localStorage.getItem("token");

  // Sync state if checklist changes externally 
  useEffect(() => {
    if (checklist?.events) setEvents(checklist.events);
  }, [checklist]);

  if (!checklist || !checklist.start_date || !checklist.end_date) return null;

  // Generate days timeline
  const startDt = new Date(checklist.start_date);
  const endDt = new Date(checklist.end_date);
  const days = [];
  let curr = new Date(startDt);
  while (curr <= endDt) {
    days.push(new Date(curr));
    curr.setDate(curr.getDate() + 1);
  }

  const handleAddSubmit = async (dateStr) => {
    if (!newEvent.title) return alert("Введите название события");
    setLoading(true);
    try {
      const resp = await fetch(`${API_URL}/checklists/${slug}/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          event_date: dateStr,
          time: newEvent.time || null,
          title: newEvent.title,
          description: newEvent.description || null,
          address: newEvent.address || null
        })
      });
      if (resp.ok) {
        const ev = await resp.json();
        setEvents([...events, ev]);
        setAddingDay(null);
        setNewEvent({ time: "", title: "", description: "", address: "" });
      } else {
        alert("Ошибка при сохранении события");
      }
    } catch (e) {
      console.error(e);
      alert("Сбой сети");
    }
    setLoading(false);
  };

  const handleEditSubmit = async (eventId) => {
    if (!editData.title) return alert("Введите название события");
    setLoading(true);
    try {
      const resp = await fetch(`${API_URL}/events/${eventId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          time: editData.time || null,
          title: editData.title,
          description: editData.description || null,
          address: editData.address || null
        })
      });
      if (resp.ok) {
        const updated = await resp.json();
        setEvents(events.map(ev => ev.id === eventId ? updated : ev));
        setEditingEvent(null);
      } else {
        alert("Ошибка при сохранении изменений");
      }
    } catch (e) {
      console.error(e);
      alert("Сбой сети");
    }
    setLoading(false);
  };

  const handleRemoveEvent = async (eventId) => {
    const confirmed = await requestConfirm({
      title: lang === "en" ? "Delete event" : "Удалить событие",
      message: lang === "en" ? "This action cannot be undone." : "Это действие нельзя отменить.",
      confirmLabel: lang === "en" ? "Delete" : "Удалить",
      cancelLabel: lang === "en" ? "Cancel" : "Отмена",
      tone: "danger",
    });
    if (!confirmed) return;
    try {
      const resp = await fetch(`${API_URL}/events/${eventId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (resp.ok) {
        setEvents(events.filter(ev => ev.id !== eventId));
      } else {
        alert("Ошибка при удалении");
      }
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className={`forecast-section ${!showItinerary ? 'collapsed' : ''}`}>
      <div className="forecast-header">
        <div className="forecast-header-left" onClick={() => setShowItinerary(!showItinerary)}>
          <h3><span style={{ display: 'flex', alignItems: 'center' }}><CalendarIcon /> {t.itineraryTitle || "План поездки"}</span></h3>
        </div>
        <div className="forecast-header-actions">
          {realOwnerId === currentUserId && (
            <span
              className={`section-visibility-toggle ${hiddenSections?.includes('itinerary') ? 'hidden' : 'visible'}`}
              onClick={(e) => { e.stopPropagation(); onToggleVisibility('itinerary'); }}
              title={hiddenSections?.includes('itinerary') ? 'План скрыт от других' : 'План виден всем'}
            >
              {hiddenSections?.includes('itinerary') ? <LockIcon style={{ marginRight: 0 }} /> : <UnlockIcon style={{ marginRight: 0 }} />}
            </span>
          )}
          <button className="collapse-toggle" onClick={() => setShowItinerary(!showItinerary)}>
            <span className={`chevron ${showItinerary ? 'up' : ''}`}>▾</span>
          </button>
        </div>
      </div>

      {showItinerary && (
        <div className="forecast-content itinerary-section">
          <div className="itinerary-timeline">
            {days.map((d, index) => {
              const dStr = d.toISOString().split("T")[0];
              const hasEvents = events.filter(e => e.event_date === dStr).sort((a, b) => (a.time || "").localeCompare(b.time || ""));
              const isAdding = addingDay === dStr;

              return (
                <div key={dStr} className="itinerary-day-block">
                  <div className="itinerary-day-header">
                    <strong>{t.dayRoute} {index + 1}</strong>
                    <span className="itinerary-day-date">
                      • {d.toLocaleDateString(lang === "en" ? "en-US" : "ru-RU", { weekday: 'short', month: 'short', day: 'numeric' })}
                    </span>
                  </div>

                  <div className="itinerary-events-list">
                    {hasEvents.length === 0 && !isAdding && (
                      <div className="itinerary-empty">{t.noEvents}</div>
                    )}
                    {hasEvents.map(ev => (
                      <div key={ev.id} className="itinerary-event-card">
                        {editingEvent === ev.id ? (
                          /* === Edit Mode === */
                          <div className="itinerary-form" style={{ flex: 1 }}>
                            <div className="itinerary-form-row">
                              <input type="time" value={editData.time || ""} onChange={e => setEditData({ ...editData, time: e.target.value })} />
                              <input type="text" value={editData.title} onChange={e => setEditData({ ...editData, title: e.target.value })} placeholder={t.eventTitlePlaceholder} autoFocus />
                            </div>
                            <input type="text" className="full-w" value={editData.description || ""} onChange={e => setEditData({ ...editData, description: e.target.value })} placeholder={t.eventDescPlaceholder} />
                            <input type="text" className="full-w" value={editData.address || ""} onChange={e => setEditData({ ...editData, address: e.target.value })} placeholder={lang === "ru" ? "📍 Адрес" : "📍 Address"} />
                            <div className="itinerary-form-actions">
                              <button className="action-btn primary" onClick={() => handleEditSubmit(ev.id)} disabled={loading}>{t.saveEventBtn}</button>
                              <button className="action-btn" onClick={() => setEditingEvent(null)}>{t.cancel}</button>
                            </div>
                          </div>
                        ) : (
                          /* === View Mode === */
                          <>
                            {ev.time && <div className="itinerary-event-time">{ev.time}</div>}
                            <div className="itinerary-event-content">
                              <div className="itinerary-event-title">{ev.title}</div>
                              {ev.description && <div className="itinerary-event-desc">{ev.description}</div>}
                              {ev.address && (
                                <div className="itinerary-event-address">
                                  <span
                                    className="address-link"
                                    onClick={(e) => { e.stopPropagation(); setExpandedAddress(expandedAddress === ev.id ? null : ev.id); }}
                                  >
                                    📍 {ev.address}
                                  </span>
                                  {expandedAddress === ev.id && (
                                    <div className="address-map-links">
                                      <a href={`https://yandex.ru/maps/?text=${encodeURIComponent(ev.address)}`} target="_blank" rel="noopener noreferrer" className="map-link yandex" onClick={e => e.stopPropagation()}>Яндекс Карты</a>
                                      <a href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(ev.address)}`} target="_blank" rel="noopener noreferrer" className="map-link google" onClick={e => e.stopPropagation()}>Google Maps</a>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                            {isOwner && (
                              <div className="evt-actions">
                                <button className="edit-evt-btn" onClick={() => { setEditingEvent(ev.id); setEditData({ time: ev.time || "", title: ev.title, description: ev.description || "", address: ev.address || "" }); }} title="Редактировать">✎</button>
                                <button className="del-evt-btn" onClick={() => handleRemoveEvent(ev.id)} title="Удалить">×</button>
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    ))}

                    {/* Add new event slot */}
                    {isOwner && (
                      <div className="itinerary-add-slot">
                        {!isAdding ? (
                          <button className="add-evt-btn" onClick={() => setAddingDay(dStr)}>
                            {t.addEvent}
                          </button>
                        ) : (
                          <div className="itinerary-form">
                            <div className="itinerary-form-row">
                              <input
                                type="time"
                                value={newEvent.time}
                                onChange={e => setNewEvent({ ...newEvent, time: e.target.value })}
                                title={t.eventTimePlaceholder}
                              />
                              <input
                                type="text"
                                value={newEvent.title}
                                onChange={e => setNewEvent({ ...newEvent, title: e.target.value })}
                                placeholder={t.eventTitlePlaceholder}
                                autoFocus
                              />
                            </div>
                            <input
                              type="text"
                              className="full-w"
                              value={newEvent.description}
                              onChange={e => setNewEvent({ ...newEvent, description: e.target.value })}
                              placeholder={t.eventDescPlaceholder}
                            />
                            <input
                              type="text"
                              className="full-w"
                              value={newEvent.address}
                              onChange={e => setNewEvent({ ...newEvent, address: e.target.value })}
                              placeholder={lang === "ru" ? "📍 Адрес (необязательно)" : "📍 Address (optional)"}
                            />
                            <div className="itinerary-form-actions">
                              <button className="action-btn primary" onClick={() => handleAddSubmit(dStr)} disabled={loading}>
                                {t.saveEventBtn}
                              </button>
                              <button className="action-btn" onClick={() => { setAddingDay(null); setNewEvent({ time: "", title: "", description: "", address: "" }); }}>
                                {t.cancel}
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
});

const TripReviewsSection = React.memo(({ checklist, user, token, lang, canReview, onReviewSaved, requestConfirm }) => {
  const [rating, setRating] = useState(0);
  const [text, setText] = useState("");
  const [photo, setPhoto] = useState("");
  const [saving, setSaving] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const photoInputRef = React.useRef(null);

  const tripEnded = Boolean(checklist?.end_date && checklist.end_date <= new Date().toISOString().slice(0, 10));
  const reviews = [...(checklist?.reviews || [])].sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
  const myReview = reviews.find((review) => review.user?.id === user?.id) || null;
  const averageRating = reviews.length
    ? (reviews.reduce((sum, review) => sum + review.rating, 0) / reviews.length).toFixed(1)
    : null;

  useEffect(() => {
    setRating(myReview?.rating || 0);
    setText(myReview?.text || "");
    setPhoto(myReview?.photo || "");
    setIsEditing(false);
    setError("");
    setSuccess("");
  }, [checklist?.slug, myReview?.id, myReview?.photo, myReview?.rating, myReview?.text, user?.id]);

  if (!tripEnded && reviews.length === 0 && !canReview) {
    return null;
  }

  const handlePhotoChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (loadEvent) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement("canvas");
        const MAX_SIZE = 1280;
        let { width, height } = img;

        if (width > height && width > MAX_SIZE) {
          height *= MAX_SIZE / width;
          width = MAX_SIZE;
        } else if (height > MAX_SIZE) {
          width *= MAX_SIZE / height;
          height = MAX_SIZE;
        }

        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0, width, height);
        setPhoto(canvas.toDataURL("image/jpeg", 0.82));
      };
      img.src = loadEvent.target.result;
    };
    reader.readAsDataURL(file);
  };

  const handleSubmit = async () => {
    setError("");
    setSuccess("");

    if (!token) {
      setError(lang === "en" ? "Please log in to leave a review" : "Войдите в аккаунт, чтобы оставить отзыв");
      return;
    }
    if (rating < 1 || rating > 5) {
      setError(lang === "en" ? "Choose a rating from 1 to 5" : "Выберите оценку от 1 до 5");
      return;
    }
    if (text.trim().length < 10) {
      setError(lang === "en" ? "Review should be at least 10 characters long" : "Отзыв должен быть длиннее 10 символов");
      return;
    }

    setSaving(true);
    try {
      const response = await fetch(`${API_URL}/checklists/${checklist.slug}/review`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          rating,
          text: text.trim(),
          photo: photo || null,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        setError(data.detail || (lang === "en" ? "Failed to save review" : "Не удалось сохранить отзыв"));
        return;
      }

      onReviewSaved(data);
      setIsEditing(false);
      setSuccess(lang === "en" ? "Review saved" : "Отзыв сохранён");
    } catch (submitError) {
      console.error(submitError);
      setError(lang === "en" ? "Network error while saving review" : "Ошибка сети при сохранении отзыва");
    } finally {
      setSaving(false);
    }
  };

  const handleStartEdit = () => {
    if (!myReview) return;
    setRating(myReview.rating || 0);
    setText(myReview.text || "");
    setPhoto(myReview.photo || "");
    setError("");
    setSuccess("");
    setIsEditing(true);
  };

  const handleDelete = async () => {
    if (!token || !checklist?.slug || !myReview || saving) return;
    const confirmed = await requestConfirm({
      title: lang === "en" ? "Delete review" : "Удалить отзыв",
      message: lang === "en" ? "Your review will disappear from the trip page." : "Ваш отзыв исчезнет со страницы поездки.",
      confirmLabel: lang === "en" ? "Delete" : "Удалить",
      cancelLabel: lang === "en" ? "Cancel" : "Отмена",
      tone: "danger",
    });
    if (!confirmed) {
      return;
    }

    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const response = await fetch(`${API_URL}/checklists/${checklist.slug}/review`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      const data = await readJsonSafely(response);
      if (!response.ok) {
        setError(data?.detail || (lang === "en" ? "Failed to delete review" : "Не удалось удалить отзыв"));
        return;
      }

      onReviewSaved(null, user?.id);
      setRating(0);
      setText("");
      setPhoto("");
      setIsEditing(false);
      setSuccess(lang === "en" ? "Review deleted" : "Отзыв удалён");
    } catch (deleteError) {
      console.error(deleteError);
      setError(lang === "en" ? "Network error while deleting review" : "Ошибка сети при удалении отзыва");
    } finally {
      setSaving(false);
    }
  };

  const shouldShowReviewForm = tripEnded && canReview && (!myReview || isEditing);

  return (
    <section className="trip-reviews-section">
      <div className="trip-reviews-header">
        <div>
          <h3>{lang === "en" ? "Trip reviews" : "Отзывы о поездке"}</h3>
          <p>
            {reviews.length > 0
              ? (lang === "en"
                  ? `${reviews.length} review${reviews.length > 1 ? "s" : ""} • average ${averageRating}`
                  : `${reviews.length} ${reviews.length === 1 ? "отзыв" : reviews.length < 5 ? "отзыва" : "отзывов"} • средняя оценка ${averageRating}`)
              : (lang === "en" ? "No reviews yet" : "Пока нет отзывов")}
          </p>
        </div>
        {!tripEnded && (
          <span className="trip-reviews-chip">
            {lang === "en" ? "Available after the trip" : "Откроется после поездки"}
          </span>
        )}
      </div>

      {shouldShowReviewForm && (
        <div className="trip-review-form-card">
          <div className="trip-review-form-head">
            <div>
              <h4>{myReview ? (lang === "en" ? "Edit your review" : "Обновить отзыв") : (lang === "en" ? "Share your impression" : "Поделитесь впечатлением")}</h4>
              <p>{lang === "en" ? "Tell others how the trip went and add a photo." : "Расскажите, как прошла поездка, и при желании добавьте фото."}</p>
            </div>
            <div className="trip-review-stars" aria-label="rating">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  className={`trip-review-star ${rating >= star ? "active" : ""}`}
                  onClick={() => setRating(star)}
                >
                  ★
                </button>
              ))}
            </div>
          </div>

          <textarea
            className="trip-review-textarea"
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder={lang === "en" ? "What was great, what surprised you, what would you advise to others?" : "Что понравилось, что удивило, что посоветуете другим?"}
            rows={5}
          />

          <div className="trip-review-actions">
            <input
              ref={photoInputRef}
              type="file"
              accept="image/*"
              className="visually-hidden-input"
              onChange={handlePhotoChange}
            />
            <button type="button" className="action-btn" onClick={() => photoInputRef.current?.click()}>
              {photo ? (lang === "en" ? "Change photo" : "Сменить фото") : (lang === "en" ? "Attach photo" : "Прикрепить фото")}
            </button>
            {photo && (
              <button type="button" className="action-btn" onClick={() => setPhoto("")}>
                {lang === "en" ? "Remove photo" : "Убрать фото"}
              </button>
            )}
            {myReview && (
              <button
                type="button"
                className="action-btn"
                onClick={() => {
                  setIsEditing(false);
                  setRating(myReview.rating || 0);
                  setText(myReview.text || "");
                  setPhoto(myReview.photo || "");
                  setError("");
                  setSuccess("");
                }}
              >
                {lang === "en" ? "Cancel" : "Отмена"}
              </button>
            )}
            <button type="button" className="action-btn primary" onClick={handleSubmit} disabled={saving}>
              {saving ? (lang === "en" ? "Saving..." : "Сохраняем...") : (myReview ? (lang === "en" ? "Update review" : "Обновить отзыв") : (lang === "en" ? "Publish review" : "Опубликовать отзыв"))}
            </button>
          </div>

          {photo && (
            <div className="trip-review-photo-preview">
              <img src={photo} alt={lang === "en" ? "Review preview" : "Предпросмотр отзыва"} />
            </div>
          )}

          {error && <div className="trip-review-feedback error">{error}</div>}
          {success && <div className="trip-review-feedback success">{success}</div>}
        </div>
      )}

      {tripEnded && !token && (
        <div className="trip-review-guest-hint">
          {lang === "en" ? "Log in after the trip to leave your own review." : "После поездки войдите в аккаунт, чтобы оставить свой отзыв."}
        </div>
      )}

      <div className="trip-reviews-list">
        {reviews.length === 0 ? (
          <div className="trip-reviews-empty">
            {lang === "en" ? "There are no public impressions for this trip yet." : "У этой поездки пока нет публичных впечатлений."}
          </div>
        ) : (
          reviews.map((review) => (
            <article key={review.id} className="trip-review-card">
              <div className="trip-review-card-head">
                <div className="trip-review-author">
                  <div className="trip-review-avatar">
                    {review.user?.avatar && (review.user.avatar.startsWith("data:image") || review.user.avatar.startsWith("http")) ? (
                      <img src={review.user.avatar} alt={review.user.username} />
                    ) : (
                      review.user?.avatar || review.user?.username?.charAt(0)?.toUpperCase() || "?"
                    )}
                  </div>
                  <div>
                    <div className="trip-review-username">{review.user?.username || "Traveler"}</div>
                    <div className="trip-review-date">
                      {review.created_at
                        ? new Date(review.created_at).toLocaleDateString(lang === "en" ? "en-US" : "ru-RU", { day: "numeric", month: "long", year: "numeric" })
                        : ""}
                    </div>
                  </div>
                </div>
                <div className="trip-review-rating">
                  <span className="trip-review-rating-stars">{"★".repeat(review.rating)}{"☆".repeat(5 - review.rating)}</span>
                </div>
              </div>

              {review.user?.id === user?.id && (
                <div className="trip-review-card-actions">
                  <button
                    type="button"
                    className="trip-review-icon-btn"
                    title={lang === "en" ? "Edit review" : "Редактировать отзыв"}
                    onClick={handleStartEdit}
                  >
                    ✎
                  </button>
                  <button
                    type="button"
                    className="trip-review-icon-btn danger"
                    title={lang === "en" ? "Delete review" : "Удалить отзыв"}
                    onClick={handleDelete}
                  >
                    ×
                  </button>
                </div>
              )}

              <p className="trip-review-text">{review.text}</p>

              {review.photo && (
                <div className="trip-review-photo">
                  <img src={review.photo} alt={lang === "en" ? "Trip review" : "Фото из поездки"} />
                </div>
              )}
            </article>
          ))
        )}
      </div>
    </section>
  );
});

const App = ({ page }) => {
  const { id } = useParams(); // slug из URL
  const navigate = useNavigate();
  const location = useLocation();

  const [lang, setLang] = useState("ru");
  const t = TRANSLATIONS[lang];

  const [destinations, setDestinations] = useState([
    { id: 1, city: null, dates: { start: null, end: null }, transport: "plane" }
  ]);
  const [options, setOptions] = useState({
    trip_type: "vacation",
  });
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [originCity, setOriginCity] = useState("");
  const [returnTransport, setReturnTransport] = useState("plane");
  const [showAuth, setShowAuth] = useState(false);
  const [showForecast, setShowForecast] = useState(() =>
    typeof window === "undefined" ? true : window.innerWidth > 600
  ); // Collapsible forecast state
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem("user");
    return safeParseJson(saved, null);
  });
  const [token, setToken] = useState(() => localStorage.getItem("token"));
  const [savedSlug, setSavedSlug] = useState(null);

  // Состояние для чеклиста
  const [checkedItems, setCheckedItems] = useState({});
  // Состояние для удалённых вещей
  const [removedItems, setRemovedItems] = useState([]);
  const [addItemMode, setAddItemMode] = useState(false);
  const [newItem, setNewItem] = useState("");
  const [showPackingModal, setShowPackingModal] = useState(false);
  const [packingProfileDraft, setPackingProfileDraft] = useState(() => normalizePackingProfile(DEFAULT_PACKING_PROFILE));
  const [packingProfileSaving, setPackingProfileSaving] = useState(false);
  const [newBaseItem, setNewBaseItem] = useState("");
  const [quantityEditor, setQuantityEditor] = useState(null);
  const [activeTab, setActiveTab] = useState("shared");
  const [activeParticipantId, setActiveParticipantId] = useState(null);
  const [showBaggageCreator, setShowBaggageCreator] = useState(false);
  const [newBaggageName, setNewBaggageName] = useState("");
  const [baggageBusy, setBaggageBusy] = useState(false);
  const [renamingBaggageId, setRenamingBaggageId] = useState(null);
  const [renamingBaggageName, setRenamingBaggageName] = useState("");
  const [accessOwner, setAccessOwner] = useState(null);
  const [accessEditorIds, setAccessEditorIds] = useState([]);
  const [moveItemDialog, setMoveItemDialog] = useState(null);
  const [moveItemBusy, setMoveItemBusy] = useState(false);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState(null);
  const [inviteToken, setInviteToken] = useState("");
  const [followers, setFollowers] = useState([]);
  const [inviteBusyIds, setInviteBusyIds] = useState([]);
  const [inviteSentIds, setInviteSentIds] = useState([]);
  const [inviteAlreadyIds, setInviteAlreadyIds] = useState([]);
  const [collaboratorQuery, setCollaboratorQuery] = useState("");
  const [collaboratorResults, setCollaboratorResults] = useState([]);
  const [selectedCollaborators, setSelectedCollaborators] = useState([]);
  const [viewportWidth, setViewportWidth] = useState(() =>
    typeof window === "undefined" ? 1280 : window.innerWidth
  );

  // Computed: can current user view/edit different sections of this checklist?
  const isChecklistParticipant = Boolean(user && result && (result.user_id === user.id || (result.backpacks && result.backpacks.some(b => b.user_id === user.id))));
  const baggageParticipants = buildBaggageParticipants(result, user);
  const checklistParticipantIds = getChecklistParticipantIds(result);
  const inviteBusyIdSet = new Set(inviteBusyIds);
  const inviteSentIdSet = new Set(inviteSentIds);
  const inviteAlreadyIdSet = new Set(inviteAlreadyIds);
  const activeParticipant = baggageParticipants.find((participant) => participant.userId === activeParticipantId) || null;
  const activeBaggage = activeTab !== "shared"
    ? (result?.backpacks || []).find((bag) => bag.id.toString() === activeTab)
    : null;
  const canEditActiveBaggage = Boolean(
    user &&
    activeBaggage &&
    canUserEditBaggage(activeBaggage, user.id, result?.backpacks || [])
  );
  const canEditCurrentSection = activeTab === "shared" ? isChecklistParticipant : canEditActiveBaggage;
  const canManageSelectedParticipant = Boolean(
    user &&
    activeParticipant &&
    activeParticipant.userId === user.id
  );
  const canReviewTrip = Boolean(
    user &&
    result &&
    isChecklistParticipant &&
    result.end_date &&
    result.end_date <= new Date().toISOString().slice(0, 10)
  );
  const moveDestinations = sortAllBackpacks(
    (result?.backpacks || []).filter(
      (baggage) =>
        baggage.id !== moveItemDialog?.sourceBackpackId &&
        user &&
        canUserEditBaggage(baggage, user.id, result?.backpacks || [])
    )
  ).map((baggage) => {
    const participant = baggageParticipants.find((entry) => entry.userId === baggage.user_id);
    const ownerLabel = participant?.isCurrentUser
      ? (lang === "en" ? "Mine" : "Мне")
      : participant?.username || baggage.user?.username || (lang === "en" ? "Participant" : "Участнику");
    return {
      id: baggage.id,
      title: baggage.name || getBaggageKindLabel(baggage),
      subtitle: `${ownerLabel} • ${getBaggageMetaLine(baggage)}`,
      isMine: baggage.user_id === user?.id,
    };
  });
  const ownMoveDestinations = moveDestinations.filter((destination) => destination.isMine);
  const otherMoveDestinations = moveDestinations.filter((destination) => !destination.isMine);
  const checklistColumns = viewportWidth <= 600 ? 1 : viewportWidth <= 900 ? 2 : 3;
  const isMobileChecklistView = viewportWidth <= 600;
	  const canMoveQuantityEditorItem = quantityEditor
	    ? (quantityEditor.sectionKey === "shared"
	        ? (result?.backpacks?.length || 0) > 0
	        : (result?.backpacks?.length || 0) > 1)
	    : false;

  useEffect(() => {
    setInviteBusyIds([]);
    setInviteSentIds([]);
    setInviteAlreadyIds([]);
  }, [savedSlug]);

  const confirmResolverRef = React.useRef(null);

  const requestConfirm = React.useCallback(({ title, message, confirmLabel, cancelLabel, tone = "default" }) => (
    new Promise((resolve) => {
      confirmResolverRef.current = resolve;
      setConfirmDialog({
        title,
        message,
        confirmLabel,
        cancelLabel,
        tone,
      });
    })
  ), []);

  const closeConfirmDialog = React.useCallback((result) => {
    if (confirmResolverRef.current) {
      confirmResolverRef.current(result);
      confirmResolverRef.current = null;
    }
    setConfirmDialog(null);
  }, []);

  const handleAuth = (userData, accessToken) => {
    setUser(userData);
    setToken(accessToken);
    localStorage.setItem("user", JSON.stringify(userData));
    localStorage.setItem("token", accessToken);
  };

  useEffect(() => {
    if (user) {
      localStorage.setItem("user", JSON.stringify(user));
    }
  }, [user]);

  useEffect(() => {
    setPackingProfileDraft(normalizePackingProfile(user?.packing_profile || DEFAULT_PACKING_PROFILE));
  }, [user]);

  useEffect(() => {
    const handleResize = () => {
      setViewportWidth(window.innerWidth);
    };

    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    setQuantityEditor(null);
  }, [activeTab, result?.slug]);

  useEffect(() => {
    setRenamingBaggageId(null);
    setRenamingBaggageName("");
  }, [activeParticipantId, activeTab]);

  useEffect(() => {
    if (!quantityEditor || isMobileChecklistView) return undefined;

    const handlePointerDown = (event) => {
      const target = event.target;
      if (
        target.closest(".quantity-editor-popover") ||
        target.closest(".item-progress-trigger")
      ) {
        return;
      }
      setQuantityEditor(null);
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("touchstart", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("touchstart", handlePointerDown);
    };
  }, [isMobileChecklistView, quantityEditor]);

  const handleLogout = React.useCallback(() => {
    setUser(null);
    setToken(null);
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    navigate('/');
  }, [navigate]);

  const authHeaders = React.useMemo(
    () => (token ? { Authorization: `Bearer ${token}` } : {}),
    [token]
  );
  const packingProfile = normalizePackingProfile(user?.packing_profile || DEFAULT_PACKING_PROFILE);
  const packingProfileSummaryParts = [
    ...(packingProfile.gender === "female"
      ? [lang === "en" ? "Female" : "Женский"]
      : packingProfile.gender === "male"
        ? [lang === "en" ? "Male" : "Мужской"]
        : []),
    ...(packingProfile.traveling_with_pet ? [lang === "en" ? "With pet" : "С питомцем"] : []),
    ...(packingProfile.has_allergies ? [lang === "en" ? "Allergies" : "Аллергии"] : []),
  ];
  const hasVisibleSharedItems = false;

  useEffect(() => {
    if (!token || !collaboratorQuery.trim()) {
      setCollaboratorResults((prev) => (prev.length ? [] : prev));
      return undefined;
    }

    const normalizedQuery = collaboratorQuery.trim();
    if (normalizedQuery.length < 2) {
      setCollaboratorResults((prev) => (prev.length ? [] : prev));
      return undefined;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const res = await fetch(`${API_URL}/users/search?q=${encodeURIComponent(normalizedQuery)}`, {
          headers: authHeaders,
          signal: controller.signal,
        });
        if (!res.ok) {
          return;
        }
        const data = await res.json();
        const selectedIds = new Set(selectedCollaborators.map((item) => item.id));
        setCollaboratorResults(
          (data || []).filter((item) => item.id !== user?.id && !selectedIds.has(item.id))
        );
      } catch (e) {
        if (e.name !== "AbortError") {
          console.error("Collaborator search error:", e);
        }
      }
    }, 180);

    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [authHeaders, collaboratorQuery, selectedCollaborators, token, user?.id]);

  useEffect(() => {
    const fetchChecklist = async () => {
      try {
        const requestOptions = authHeaders.Authorization ? { headers: authHeaders } : undefined;
        let res = await fetch(`${API_URL}/checklist/${id}`, requestOptions);
        if (res.status === 401 && authHeaders.Authorization) {
          res = await fetch(`${API_URL}/checklist/${id}`);
        }
        if (!res.ok) throw new Error("Чеклист не найден");
        const data = await res.json();
        setResult(data);
        setSavedSlug(id);
      } catch (e) {
        console.error(e);
        setError("Ошибка при загрузке чеклиста");
      }
    };

    if (id) {
      fetchChecklist();
    }
  }, [authHeaders, id]);

  useEffect(() => {
    if (result && result.items && savedSlug) {
      setCheckedItems(
        buildCheckedItemsMap(
          result.items,
          result.checked_items,
          result.item_quantities || {},
          result.packed_quantities || {}
        )
      );
    }
  }, [result, savedSlug]);

  useEffect(() => {
    if (savedSlug) {
      setRemovedItems(result?.removed_items || []);
    }
  }, [result?.removed_items, savedSlug]);

  useEffect(() => {
    if (!result) return;

    const participants = buildBaggageParticipants(result, user);
    if (participants.length === 0) {
      setActiveParticipantId(null);
      if (activeTab !== "shared") {
        setActiveTab("shared");
      }
      return;
    }

    const stillExists = participants.some((participant) => participant.userId === activeParticipantId);
    if (!stillExists) {
      const preferredParticipant =
        participants.find((participant) => participant.userId === user?.id) || participants[0];
      setActiveParticipantId(preferredParticipant.userId);
      return;
    }

    if (activeTab === "shared") {
      if (hasVisibleSharedItems) return;
      const preferredParticipant =
        participants.find((participant) => participant.userId === activeParticipantId)
        || participants.find((participant) => participant.userId === user?.id)
        || participants[0];
      const fallbackBaggage =
        preferredParticipant?.baggage.find((bp) => bp.is_default) || preferredParticipant?.baggage[0];
      if (fallbackBaggage) {
        setActiveParticipantId(preferredParticipant.userId);
        setActiveTab(fallbackBaggage.id.toString());
      }
      return;
    }

    const activeParticipantGroup = participants.find((participant) => participant.userId === activeParticipantId);
    const baggageStillExists = activeParticipantGroup?.baggage.some((bp) => bp.id.toString() === activeTab);
    if (!baggageStillExists) {
      const fallbackBaggage =
        activeParticipantGroup?.baggage.find((bp) => bp.is_default) || activeParticipantGroup?.baggage[0];
      setActiveTab(fallbackBaggage ? fallbackBaggage.id.toString() : "shared");
    }
  }, [result, user, activeParticipantId, activeTab, hasVisibleSharedItems]);

  useEffect(() => {
    if (location.pathname === "/") {
      setSavedSlug(null);
      setResult(null);
      setDestinations([{ id: 1, city: null, dates: { start: null, end: null } }]);
      setError(null);
    }
  }, [location.pathname]);

  const handleAddDestination = () => {
    setDestinations([
      ...destinations,
      { id: Date.now(), city: null, dates: { start: null, end: null }, transport: "plane" }
    ]);
  };

  const handleRemoveDestination = (id) => {
    if (destinations.length > 1) {
      setDestinations(destinations.filter(d => d.id !== id));
    }
  };

  const updateDestination = (id, field, value) => {
    setDestinations(prev => prev.map(d => {
      if (d.id === id) {
        return { ...d, [field]: value };
      }
      return d;
    }));
  };

  const handleAddBaseItem = () => {
    const normalizedItem = newBaseItem.trim();
    if (!normalizedItem) return;
    setPackingProfileDraft((prev) => ({
      ...prev,
      always_include_items: normalizePackingProfileItems([...prev.always_include_items, normalizedItem]),
    }));
    setNewBaseItem("");
  };

  const handleRemoveBaseItem = (itemToRemove) => {
    setPackingProfileDraft((prev) => ({
      ...prev,
      always_include_items: prev.always_include_items.filter((item) => item !== itemToRemove),
    }));
  };

  const handleSavePackingProfile = async () => {
    if (!authHeaders.Authorization) {
      setShowAuth(true);
      return;
    }

    setPackingProfileSaving(true);
    try {
      const res = await fetch(`${API_URL}/auth/me`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders,
        },
        body: JSON.stringify({ packing_profile: packingProfileDraft }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Не удалось сохранить настройки");
      }
      setUser(data);
      localStorage.setItem("user", JSON.stringify(data));
      setShowPackingModal(false);
    } catch (e) {
      alert(e.message || "Не удалось сохранить настройки");
    } finally {
      setPackingProfileSaving(false);
    }
  };

  const handleSubmit = async () => {
    setError(null);
    setResult(null);
    setSavedSlug(null);

    // Валидация
    const isValid = destinations.every(d => d.city && d.dates.start && d.dates.end);
    if (!isValid) {
      alert("Заполните все города и даты!");
      return;
    }

    try {
      const payload = {
        segments: destinations.map(d => ({
          city: d.city.fullName,
          start_date: d.dates.start,
          end_date: d.dates.end,
          trip_type: options.trip_type,
          transport: d.transport || "plane",
        })),
        gender: packingProfile.gender,
        traveling_with_pet: packingProfile.traveling_with_pet,
        has_allergies: packingProfile.has_allergies,
        participant_user_ids: selectedCollaborators.map((person) => person.id),
        language: lang,
        origin_city: originCity?.fullName || originCity || "",
        return_transport: returnTransport,
      };

      const res = await fetch(`${API_URL}/generate-multi-city`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errorData = await res.json();
        setError(errorData.detail || "Ошибка при генерации списка");
        return;
      }

      const data = await res.json();

      // Проверяем наличие daily_forecast в ответе
      if (!data.daily_forecast) {
        console.warn("daily_forecast отсутствует в ответе сервера", data);
      }

      setResult(data);
      setSavedSlug(data.slug || null);

      if (data?.slug && token && selectedCollaborators.length > 0) {
        await Promise.all(
          selectedCollaborators.map(async (collaborator) => {
            try {
              await fetch(`${API_URL}/checklists/${data.slug}/invite/${collaborator.id}`, {
                method: "POST",
                headers: authHeaders,
              });
            } catch (inviteError) {
              console.error("Invite collaborator error:", inviteError);
            }
          })
        );
      }

      setCollaboratorQuery("");
      setCollaboratorResults([]);
      setSelectedCollaborators([]);
    } catch {
      setError("Ошибка при запросе к серверу");
    }
  };

  const syncChecklist = async (payload) => {
    try {
      if (!authHeaders.Authorization || !savedSlug) return;
      await fetch(`${API_URL}/checklist/${savedSlug}/state`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify(payload)
      });
    } catch (e) { console.error("Checklist sync error:", e); }
  };

  const syncBackpackItems = async (backpackId, payload) => {
    try {
      if (!authHeaders.Authorization) return;
      await fetch(`${API_URL}/backpacks/${backpackId}/state`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify(payload)
      });
    } catch (e) { console.error("Backpack sync error:", e); }
  };

  const handleQuantityStateChange = (item, nextNeededQuantity, nextPackedQuantity) => {
    if (!canEditCurrentSection) return;
    const quantity = Math.max(1, Number(nextNeededQuantity) || 1);
    const packed = Math.max(0, Math.min(quantity, Number(nextPackedQuantity) || 0));

    if (activeTab === "shared") {
      const nextQuantities = setItemQuantityInMap(result?.item_quantities || {}, item, quantity);
      const nextPacked = setPackedQuantityInMap(result?.packed_quantities || {}, item, packed);
      const nextCheckedMap = buildCheckedItemsMap(result?.items || [], result?.checked_items || [], nextQuantities, nextPacked);
      const nextCheckedItems = Object.keys(nextCheckedMap).filter((entry) => nextCheckedMap[entry]);
      setCheckedItems(buildCheckedItemsMap(result?.items || [], nextCheckedItems, nextQuantities, nextPacked));
      setResult((prev) => ({
        ...prev,
        checked_items: nextCheckedItems,
        item_quantities: nextQuantities,
        packed_quantities: nextPacked,
      }));
      syncChecklist({ checked_items: nextCheckedItems, item_quantities: nextQuantities, packed_quantities: nextPacked });
      return;
    }

    setResult((prev) => {
      const next = { ...prev };
      const bp = next.backpacks?.find((bag) => bag.id.toString() === activeTab);
      if (bp) {
        bp.item_quantities = setItemQuantityInMap(bp.item_quantities || {}, item, quantity);
        bp.packed_quantities = setPackedQuantityInMap(bp.packed_quantities || {}, item, packed);
        bp.checked_items = (bp.items || []).filter(
          (existingItem) => getPackedQuantity(bp.packed_quantities || {}, existingItem) >= getItemQuantity(bp.item_quantities || {}, existingItem)
        );
        syncBackpackItems(activeTab, {
          checked_items: bp.checked_items,
          item_quantities: bp.item_quantities,
          packed_quantities: bp.packed_quantities,
        });
      }
      return next;
    });
  };

  const toggleQuantityEditor = (item, neededQuantity, packedQuantity) => {
    const sectionKey = activeTab;
    setQuantityEditor((prev) => {
      if (prev?.item === item && prev?.sectionKey === sectionKey) {
        return null;
      }
      return {
        item,
        sectionKey,
        needed: Math.max(1, Number(neededQuantity) || 1),
        packed: Math.max(0, Math.min(Number(neededQuantity) || 1, Number(packedQuantity) || 0)),
      };
    });
  };

  const updateQuantityEditorDraft = (field, nextValue) => {
    setQuantityEditor((prev) => {
      if (!prev) return prev;
      if (field === "needed") {
        const needed = Math.max(1, Number(nextValue) || 1);
        return {
          ...prev,
          needed,
          packed: Math.min(prev.packed, needed),
        };
      }

      const packed = Math.max(0, Math.min(prev.needed, Number(nextValue) || 0));
      return {
        ...prev,
        packed,
      };
    });
  };

  const applyQuantityEditor = () => {
    if (!quantityEditor) return;
    handleQuantityStateChange(quantityEditor.item, quantityEditor.needed, quantityEditor.packed);
    setQuantityEditor(null);
  };

  const handleQuickPackedChange = (item, delta) => {
    if (!canEditCurrentSection) return;
    const targetNeeded = activeTab === "shared"
      ? getItemQuantity(result?.item_quantities || {}, item)
      : getItemQuantity(
          result?.backpacks?.find((bag) => bag.id.toString() === activeTab)?.item_quantities || {},
          item
        );
    const targetPacked = activeTab === "shared"
      ? getPackedQuantity(result?.packed_quantities || {}, item)
      : getPackedQuantity(
          result?.backpacks?.find((bag) => bag.id.toString() === activeTab)?.packed_quantities || {},
          item
        );
    handleQuantityStateChange(item, targetNeeded, targetPacked + delta);
  };

  const handleCheck = (item) => {
    if (!canEditCurrentSection) return;
    if (activeTab === "shared") {
      const needed = getItemQuantity(result?.item_quantities || {}, item);
      const currentPacked = getPackedQuantity(result?.packed_quantities || {}, item);
      const nextPacked = setPackedQuantityInMap(
        result?.packed_quantities || {},
        item,
        currentPacked >= needed ? 0 : needed
      );
      const nextCheckedItems = (result?.items || []).filter(
        (existingItem) => getPackedQuantity(nextPacked, existingItem) >= getItemQuantity(result?.item_quantities || {}, existingItem)
      );
      const nextCheckedMap = buildCheckedItemsMap(result?.items || [], nextCheckedItems, result?.item_quantities || {}, nextPacked);
      setCheckedItems(nextCheckedMap);
      setResult((prev) => ({ ...prev, checked_items: nextCheckedItems, packed_quantities: nextPacked }));
      syncChecklist({ checked_items: nextCheckedItems, packed_quantities: nextPacked });
    } else {
      setResult(prev => {
        const next = { ...prev };
        const bp = next.backpacks?.find(b => b.id.toString() === activeTab);
        if (bp) {
          const needed = getItemQuantity(bp.item_quantities || {}, item);
          const currentPacked = getPackedQuantity(bp.packed_quantities || {}, item);
          bp.packed_quantities = setPackedQuantityInMap(
            bp.packed_quantities || {},
            item,
            currentPacked >= needed ? 0 : needed
          );
          bp.checked_items = (bp.items || []).filter(
            (existingItem) => getPackedQuantity(bp.packed_quantities || {}, existingItem) >= getItemQuantity(bp.item_quantities || {}, existingItem)
          );
          syncBackpackItems(activeTab, {
            checked_items: bp.checked_items,
            packed_quantities: bp.packed_quantities,
          });
        }
        return next;
      });
    }
  };

  const handleRemoveItem = (item) => {
    if (!canEditCurrentSection) return;
    if (activeTab === "shared") {
      const newRemoved = [...removedItems, item];
      setRemovedItems(newRemoved);
      const nextPacked = setPackedQuantityInMap(result?.packed_quantities || {}, item, 0);
      const nextCheckedItems = (result?.items || []).filter(
        (existingItem) => getPackedQuantity(nextPacked, existingItem) >= getItemQuantity(result?.item_quantities || {}, existingItem)
      );
      setCheckedItems(buildCheckedItemsMap(result?.items || [], nextCheckedItems, result?.item_quantities || {}, nextPacked));
      setResult((prev) => ({ ...prev, checked_items: nextCheckedItems, packed_quantities: nextPacked }));
      syncChecklist({ removed_items: newRemoved, checked_items: nextCheckedItems, packed_quantities: nextPacked });
    } else {
      setResult(prev => {
        const next = { ...prev };
        const bp = next.backpacks?.find(b => b.id.toString() === activeTab);
        if (bp) {
          bp.removed_items = [...bp.removed_items, item];
          bp.packed_quantities = setPackedQuantityInMap(bp.packed_quantities || {}, item, 0);
          bp.checked_items = (bp.items || []).filter(
            (existingItem) => getPackedQuantity(bp.packed_quantities || {}, existingItem) >= getItemQuantity(bp.item_quantities || {}, existingItem)
          );
          syncBackpackItems(activeTab, {
            removed_items: bp.removed_items,
            checked_items: bp.checked_items,
            packed_quantities: bp.packed_quantities,
          });
        }
        return next;
      });
    }
  };

  const resetChecklist = () => {
    if (!canEditCurrentSection) return;
    if (activeTab === "shared") {
      const reset = {};
      result.items.forEach(item => { reset[item] = false; });
      setCheckedItems(reset);
      setResult((prev) => ({ ...prev, checked_items: [], packed_quantities: {} }));
      syncChecklist({ checked_items: [], packed_quantities: {} });
    } else {
      setResult(prev => {
        const next = { ...prev };
        const bp = next.backpacks?.find(b => b.id.toString() === activeTab);
        if (bp) {
          bp.checked_items = [];
          bp.packed_quantities = {};
          syncBackpackItems(activeTab, { checked_items: [], packed_quantities: {} });
        }
        return next;
      });
    }
  };

  const handleAddItem = () => {
    if (!canEditCurrentSection) return;
    const normalizedItem = newItem.trim();
    if (!normalizedItem) return;
    if (activeTab === "shared") {
      if (result.items.includes(normalizedItem)) {
        if (removedItems.includes(normalizedItem)) {
          const nextRemoved = removedItems.filter((existing) => existing !== normalizedItem);
          const nextQuantities = setItemQuantityInMap(
            result?.item_quantities || {},
            normalizedItem,
            getItemQuantity(result?.item_quantities || {}, normalizedItem)
          );
          const nextPacked = setPackedQuantityInMap(
            result?.packed_quantities || {},
            normalizedItem,
            getPackedQuantity(result?.packed_quantities || {}, normalizedItem)
          );
          setRemovedItems(nextRemoved);
          setResult((prev) => ({ ...prev, item_quantities: nextQuantities, packed_quantities: nextPacked }));
          syncChecklist({ removed_items: nextRemoved, item_quantities: nextQuantities, packed_quantities: nextPacked });
        }
        setNewItem("");
        setAddItemMode(false);
        return;
      }
      const newItems = [...result.items, normalizedItem];
      const nextQuantities = setItemQuantityInMap(result?.item_quantities || {}, normalizedItem, 1);
      const nextPacked = setPackedQuantityInMap(result?.packed_quantities || {}, normalizedItem, 0);
      setResult(prev => ({ ...prev, items: newItems, item_quantities: nextQuantities, packed_quantities: nextPacked }));
      syncChecklist({ items: newItems, item_quantities: nextQuantities, packed_quantities: nextPacked });
    } else {
      setResult(prev => {
        const next = { ...prev };
        const bp = next.backpacks?.find(b => b.id.toString() === activeTab);
        if (bp && bp.items.includes(normalizedItem)) {
          if (bp.removed_items.includes(normalizedItem)) {
            bp.removed_items = bp.removed_items.filter((existing) => existing !== normalizedItem);
            bp.item_quantities = setItemQuantityInMap(
              bp.item_quantities || {},
              normalizedItem,
              getItemQuantity(bp.item_quantities || {}, normalizedItem)
            );
            bp.packed_quantities = setPackedQuantityInMap(
              bp.packed_quantities || {},
              normalizedItem,
              getPackedQuantity(bp.packed_quantities || {}, normalizedItem)
            );
            syncBackpackItems(activeTab, {
              removed_items: bp.removed_items,
              item_quantities: bp.item_quantities,
              packed_quantities: bp.packed_quantities
            });
          }
          return next;
        }
        if (bp) {
          bp.items = [...bp.items, normalizedItem];
          bp.item_quantities = setItemQuantityInMap(bp.item_quantities || {}, normalizedItem, 1);
          bp.packed_quantities = setPackedQuantityInMap(bp.packed_quantities || {}, normalizedItem, 0);
          syncBackpackItems(activeTab, { items: bp.items, item_quantities: bp.item_quantities, packed_quantities: bp.packed_quantities });
        }
        return next;
      });
    }
    setNewItem("");
    setAddItemMode(false);
  };

  const openMoveItemDialog = (item, sourceBackpackId = null) => {
    setMoveItemDialog({
      item,
      sourceBackpackId,
      targetBackpackId: null,
    });
  };

  const handleConfirmMoveItem = async () => {
    if (!moveItemDialog?.item || !moveItemDialog?.targetBackpackId || !savedSlug || !authHeaders.Authorization) return;

    setMoveItemBusy(true);
    try {
      const res = await fetch(`${API_URL}/checklists/${savedSlug || id}/transfer-item`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders,
        },
        body: JSON.stringify({
          item: moveItemDialog.item,
          source_backpack_id: moveItemDialog.sourceBackpackId,
          target_backpack_id: moveItemDialog.targetBackpackId,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Не удалось перенести вещь");
      }
      setResult(data);
      setMoveItemDialog(null);
    } catch (e) {
      alert(e.message || "Не удалось перенести вещь");
    } finally {
      setMoveItemBusy(false);
    }
  };

  const selectParticipant = (participantUserId) => {
    setActiveParticipantId(participantUserId);
    setShowBaggageCreator(false);
    setNewBaggageName("");
    const participant = baggageParticipants.find((entry) => entry.userId === participantUserId);
    const fallbackBaggage = participant?.baggage.find((bp) => bp.is_default) || participant?.baggage[0];
    setActiveTab(fallbackBaggage ? fallbackBaggage.id.toString() : "shared");
  };

  const handleCreateBaggage = async () => {
    const name = newBaggageName.trim();
    if (!name || !savedSlug || !activeParticipant || !authHeaders.Authorization) return;

    setBaggageBusy(true);
    try {
      const res = await fetch(`${API_URL}/checklists/${savedSlug || id}/baggage`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({
          user_id: activeParticipant.userId,
          name,
          kind: guessBaggageKind(name),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Не удалось создать багаж");
      }

      setResult((prev) => ({
        ...prev,
        backpacks: sortAllBackpacks([...(prev.backpacks || []), data]),
      }));
      setActiveParticipantId(data.user_id);
      setActiveTab(data.id.toString());
      setNewBaggageName("");
      setShowBaggageCreator(false);
    } catch (e) {
      alert(e.message || "Не удалось создать багаж");
    } finally {
      setBaggageBusy(false);
    }
  };

  const handleDeleteBaggage = async (baggage) => {
    if (!savedSlug || !authHeaders.Authorization) return;
    const confirmed = await requestConfirm({
      title: lang === "en" ? "Delete baggage" : "Удалить багаж",
      message: lang === "en"
        ? `"${baggage.name || "Baggage"}" will be removed from this trip.`
        : `«${baggage.name || "Багаж"}» будет удалён из этой поездки.`,
      confirmLabel: lang === "en" ? "Delete" : "Удалить",
      cancelLabel: lang === "en" ? "Cancel" : "Отмена",
      tone: "danger",
    });
    if (!confirmed) return;

    setBaggageBusy(true);
    try {
      const res = await fetch(`${API_URL}/baggage/${baggage.id}`, {
        method: "DELETE",
        headers: authHeaders,
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Не удалось удалить багаж");
      }

      setResult((prev) => {
        const nextBackpacks = (prev.backpacks || []).filter((bp) => bp.id !== baggage.id);
        return {
          ...prev,
          hidden_sections: (prev.hidden_sections || []).filter((section) => section !== `backpack:${baggage.id}`),
          backpacks: nextBackpacks,
        };
      });

      const participant = baggageParticipants.find((entry) => entry.userId === baggage.user_id);
      const nextBaggage = participant?.baggage.filter((bp) => bp.id !== baggage.id);
      const fallback = nextBaggage?.find((bp) => bp.is_default) || nextBaggage?.[0];
      setActiveTab(fallback ? fallback.id.toString() : "shared");
    } catch (e) {
      alert(e.message || "Не удалось удалить багаж");
    } finally {
      setBaggageBusy(false);
    }
  };

  const handleSetDefaultBaggage = async (baggage) => {
    if (!savedSlug || !authHeaders.Authorization || baggage.is_default) return;

    setBaggageBusy(true);
    try {
      const res = await fetch(`${API_URL}/baggage/${baggage.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({ is_default: true }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Не удалось сделать багаж основным");
      }

      setResult((prev) => ({
        ...prev,
        backpacks: sortAllBackpacks(
          (prev.backpacks || []).map((bp) => (
            bp.user_id === data.user_id
              ? {
                  ...bp,
                  ...(bp.id === data.id ? data : {}),
                  is_default: bp.id === data.id,
                }
              : bp
          ))
        ),
      }));
      setActiveTab(data.id.toString());
    } catch (e) {
      alert(e.message || "Не удалось сделать багаж основным");
    } finally {
      setBaggageBusy(false);
    }
  };

  const startRenameBaggage = (baggage) => {
    setRenamingBaggageId(baggage.id);
    setRenamingBaggageName(baggage.name || "");
  };

  const handleRenameBaggage = async (baggage) => {
    const nextName = renamingBaggageName.trim();
    if (!nextName || !authHeaders.Authorization) return;

    setBaggageBusy(true);
    try {
      const res = await fetch(`${API_URL}/baggage/${baggage.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({
          name: nextName,
          kind: guessBaggageKind(nextName),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Не удалось переименовать багаж");
      }

      setResult((prev) => ({
        ...prev,
        backpacks: sortAllBackpacks((prev.backpacks || []).map((bp) => (bp.id === data.id ? data : bp))),
      }));
      setRenamingBaggageId(null);
      setRenamingBaggageName("");
    } catch (e) {
      alert(e.message || "Не удалось переименовать багаж");
    } finally {
      setBaggageBusy(false);
    }
  };

  const openBaggageAccess = (participant) => {
    const anchorBaggage =
      participant?.baggage?.find((baggage) => baggage.is_default) || participant?.baggage?.[0];
    if (!participant || !anchorBaggage) return;

    setAccessOwner({
      userId: participant.userId,
      displayName: participant.isCurrentUser ? "Мой багаж" : `Багаж ${participant.username}`,
      anchorBackpackId: anchorBaggage.id,
    });
    setAccessEditorIds(getOwnerBaggageEditorIds(result?.backpacks || [], participant.userId, anchorBaggage));
  };

  const handleToggleBaggageEditor = (participantUserId) => {
    setAccessEditorIds((prev) => (
      prev.includes(participantUserId)
        ? prev.filter((id) => id !== participantUserId)
        : [...prev, participantUserId]
    ));
  };

  const handleSaveBaggageAccess = async () => {
    if (!accessOwner || !authHeaders.Authorization) return;

    setBaggageBusy(true);
    try {
      const res = await fetch(`${API_URL}/baggage/${accessOwner.anchorBackpackId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({ editor_user_ids: accessEditorIds }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Не удалось обновить доступ");
      }

      setResult((prev) => ({
        ...prev,
        backpacks: sortAllBackpacks((prev.backpacks || []).map((bp) => (
          bp.user_id === accessOwner.userId
            ? { ...bp, editor_user_ids: data.editor_user_ids || accessEditorIds }
            : bp
        ))),
      }));
      setAccessOwner(null);
      setAccessEditorIds([]);
    } catch (e) {
      alert(e.message || "Не удалось обновить доступ");
    } finally {
      setBaggageBusy(false);
    }
  };

  const addCollaborator = (person) => {
    setSelectedCollaborators((prev) => (
      prev.some((item) => item.id === person.id) ? prev : [...prev, person]
    ));
    setCollaboratorQuery("");
    setCollaboratorResults([]);
  };

  const removeCollaborator = (userId) => {
    setSelectedCollaborators((prev) => prev.filter((item) => item.id !== userId));
  };

  const handleToggleSectionVisibility = async (section) => {
    if (!result || !authHeaders.Authorization) return;

    const isHidden = result.hidden_sections?.includes(section);
    let newHidden = [];
    if (isHidden) {
      newHidden = result.hidden_sections.filter(s => s !== section);
    } else {
      newHidden = [...(result.hidden_sections || []), section];
    }

    try {
      const res = await fetch(`${API_URL}/checklists/${savedSlug || id}/hidden-sections`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({ hidden_sections: newHidden })
      });
      if (res.ok) {
        const data = await res.json();
        setResult(prev => ({ ...prev, hidden_sections: data.hidden_sections }));
      }
    } catch (e) {
      console.error("Error toggling section visibility:", e);
    }
  };

  const handleReviewSaved = (savedReview, removedUserId = null) => {
    setResult((prev) => {
      if (!prev) return prev;
      const remainingReviews = (prev.reviews || []).filter(
        (review) => review.user?.id !== (removedUserId ?? savedReview?.user?.id)
      );
      if (!savedReview) {
        return {
          ...prev,
          reviews: remainingReviews,
        };
      }
      return {
        ...prev,
        reviews: [savedReview, ...remainingReviews].sort(
          (a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0)
        ),
      };
    });
  };

  const handleChecklistUpdated = (updatedChecklist) => {
    if (!updatedChecklist) return;

    const nextSlug = updatedChecklist.slug || savedSlug;
    const nextCheckedItems = buildCheckedItemsMap(
      updatedChecklist.items || [],
      updatedChecklist.checked_items || [],
      updatedChecklist.item_quantities || {},
      updatedChecklist.packed_quantities || {}
    );
    const nextRemovedItems = updatedChecklist.removed_items || [];

    setSavedSlug(nextSlug || null);
    setCheckedItems(nextCheckedItems);
    setRemovedItems(nextRemovedItems);
    setActiveTab("shared");
    setResult(updatedChecklist);
  };

  const formatDate = (isoDate) => {
    const d = new Date(isoDate);
    const day = String(d.getDate()).padStart(2, "0");
    const month = String(d.getMonth() + 1).padStart(2, "0");
    const year = d.getFullYear();
    return `${day}.${month}.${year}`;
  };

  return (
    <>
      {/* Navbar */}
      <nav className="navbar">
        <div className="navbar-logo" onClick={() => navigate("/")}>
          <span>🧳</span><span className="navbar-logo-text">Luggify</span>
        </div>
        <div className="navbar-center navbar-search-desktop">
          <NavbarUserSearch
            lang={lang}
            navigate={navigate}
            currentUsername={user?.username || ""}
          />
        </div>
        <div className="navbar-user">
          <div className="navbar-locale-tools">
            <div className="language-switcher">
              <button
                className={`lang-btn ${lang === "ru" ? "active" : ""}`}
                onClick={() => setLang("ru")}
              >RU</button>
              <button
                className={`lang-btn ${lang === "en" ? "active" : ""}`}
                onClick={() => setLang("en")}
              >EN</button>
            </div>
            <div className="navbar-search-mobile">
              <NavbarUserSearch
                lang={lang}
                navigate={navigate}
                currentUsername={user?.username || ""}
                compact
              />
            </div>
          </div>
          {user ? (
            <>
              <TelegramLinkButton
                user={user}
                token={token}
                onUserUpdate={setUser}
                lang={lang}
              />
              <div className="navbar-profile" onClick={() => navigate("/profile")}>
                <div className="navbar-avatar">
                  {user.avatar && (user.avatar.startsWith("data:image") || user.avatar.startsWith("http")) ? (
                    <img src={user.avatar} alt="Avatar" style={{ width: "100%", height: "100%", borderRadius: "50%", objectFit: "cover" }} />
                  ) : (
                    user.avatar ? user.avatar : user.username.charAt(0).toUpperCase()
                  )}
                </div>
                <span className="navbar-username">{user.username}</span>
              </div>
              <NotificationBell
                authHeaders={authHeaders}
                lang={lang}
                navigate={navigate}
              />
              <button
                className="navbar-logout-btn icon-btn"
                onClick={handleLogout}
                title={t.logout}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                  <polyline points="16 17 21 12 16 7"></polyline>
                  <line x1="21" y1="12" x2="9" y2="12"></line>
                </svg>
              </button>
            </>
          ) : (
            <button className="navbar-login-btn" onClick={() => setShowAuth(true)}>{t.login}</button>
          )}
        </div>
      </nav>

      {showAuth && (
        <AuthModal
          onClose={() => setShowAuth(false)}
          onAuth={handleAuth}
        />
      )}

      <div className="page-wrapper">
        {/* Profile Page */}
        {page === "profile" ? (
          <ProfilePage user={user} token={token} onLogout={handleLogout} onUpdateUser={setUser} lang={lang} />
        ) : (
          <>
            {!result && (
              <>
                <div className="hero">
                  <h2>{t.heroTitle}</h2>
                  <p>{t.heroSubtitle}</p>
                </div>

                <div className="form-card">
                  <div className="origin-dest-block">
                    <div className="origin-row">
                      <div className="form-field" style={{ flex: 1 }}>
                        <CitySelect
                          value={originCity}
                          onSelect={(val) => setOriginCity(val)}
                          lang={lang}
                          label={lang === "ru" ? "Откуда" : "From"}
                        />
                      </div>
                    </div>
                    <div className="route-arrow">↓</div>
                  </div>
                  {destinations.map((dest, index) => (
                    <div key={dest.id} className="destination-row">
                      {destinations.length > 1 && (
                        <div className="destination-header">
                          <span className="destination-number">#{index + 1}</span>
                          <button
                            className="remove-dest-btn"
                            onClick={() => handleRemoveDestination(dest.id)}
                            title="Удалить город"
                          >
                            ×
                          </button>
                        </div>
                      )}
                      <div className="form-field">
                        <CitySelect
                          value={dest.city}
                          onSelect={(val) => updateDestination(dest.id, "city", val)}
                          lang={lang}
                        >
                          {/* Per-destination Transport Selection */}
                          <div className="inline-transport-selector" style={{ background: "transparent", border: "none", padding: 0, gap: "2px" }}>
                            {[
                              { id: "plane", icon: <PlaneIcon style={{ marginRight: 0 }} /> },
                              { id: "train", icon: <TrainIcon style={{ marginRight: 0 }} /> },
                              { id: "car", icon: <CarIcon style={{ marginRight: 0 }} /> },
                              { id: "bus", icon: <BusIcon style={{ marginRight: 0 }} /> },
                            ].map(type => (
                              <button
                                key={type.id}
                                className={`transport-btn ${dest.transport === type.id ? "active" : ""}`}
                                onClick={() => updateDestination(dest.id, "transport", type.id)}
                                title={t[type.id] || type.id}
                                style={{ padding: "4px", fontSize: "1.05rem", minWidth: "24px" }}
                              >
                                {type.icon}
                              </button>
                            ))}
                          </div>
                        </CitySelect>
                      </div>

                      <div className="form-field">
                        <DateRangePicker
                          value={dest.dates}
                          onChange={(val) => updateDestination(dest.id, "dates", val)}
                          lang={lang}
                          minDate={index > 0 ? (destinations[index - 1].dates.end ? new Date(destinations[index - 1].dates.end) : new Date()) : new Date()}
                        />
                      </div>

                      {index < destinations.length - 1 && <div className="destination-divider">↓</div>}
                    </div>
                  ))}

                  <div className="form-actions" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
                    <button className="add-city-btn" onClick={handleAddDestination} style={{ width: "auto" }}>
                      {t.addCity}
                    </button>

                    {/* Return transport selector */}
                    <div className="return-transport-row" style={{ marginTop: 0, paddingTop: 0, borderTop: "none" }}>
                      <label className="section-label" style={{ marginBottom: 0 }}>{t.returnTransport || "Обратно:"}</label>
                      <div className="inline-transport-selector">
                        {[
                          { id: "plane", icon: <PlaneIcon style={{ marginRight: 0 }} /> },
                          { id: "train", icon: <TrainIcon style={{ marginRight: 0 }} /> },
                          { id: "car", icon: <CarIcon style={{ marginRight: 0 }} /> },
                          { id: "bus", icon: <BusIcon style={{ marginRight: 0 }} /> },
                        ].map(type => (
                          <button
                            key={type.id}
                            className={`transport-btn ${returnTransport === type.id ? "active" : ""}`}
                            onClick={() => setReturnTransport(type.id)}
                            title={t[type.id] || type.id}
                          >
                            {type.icon}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="trip-type-selector">
                    <label className="section-label">Тип поездки:</label>
                    <div className="trip-types">
                      {[
                        { id: "vacation", label: t.vacation, icon: <VacationIcon /> },
                        { id: "business", label: t.business, icon: <BusinessIcon /> },
                        { id: "active", label: t.active, icon: <ActiveIcon /> },
                        { id: "beach", label: t.beach, icon: <BeachIcon /> },
                        { id: "winter", label: t.winter, icon: <WinterIcon /> },
                      ].map(type => (
                        <div
                          key={type.id}
                          className={`trip-type-chip ${options.trip_type === type.id ? "active" : ""}`}
                          onClick={() => setOptions({ ...options, trip_type: type.id })}
                        >
                          {type.icon} {type.label}
                        </div>
                      ))}
                    </div>
                  </div>

                  {user && (
                    <div className="packing-profile-summary-card home-setup-card">
                      <div className="home-setup-card-head">
                        <div className="home-setup-card-copy">
                          <span className="home-setup-card-kicker">
                            {lang === "en" ? "Quick start" : "Быстрый старт"}
                          </span>
                          <span className="home-setup-card-title">
                            {lang === "en" ? "Packing settings" : "Настройки сборов"}
                          </span>
                        </div>
                        <button
                          className="packing-profile-summary-btn compact"
                          type="button"
                          onClick={() => setShowPackingModal(true)}
                        >
                          {lang === "en" ? "Configure" : "Настроить"}
                        </button>
                      </div>
                      <div className="packing-profile-summary-tags">
                        {packingProfileSummaryParts.length > 0 ? (
                          packingProfileSummaryParts.map((part) => (
                            <span key={part} className="packing-profile-summary-tag">
                              {part}
                            </span>
                          ))
                        ) : (
                          <span className="packing-profile-summary-empty">
                            {lang === "en" ? "No personal preferences yet" : "Пока без личных параметров"}
                          </span>
                        )}
                        {packingProfile.always_include_items.length > 0 && (
                          <span
                            className="packing-profile-summary-tag accent"
                            title={packingProfile.always_include_items.join(", ")}
                          >
                            {lang === "en"
                              ? `+${packingProfile.always_include_items.length} base items`
                              : `+${packingProfile.always_include_items.length} базовых вещей`}
                          </span>
                        )}
                      </div>
                    </div>
                  )}

                  {user && (
                    <div className="collaborator-picker">
                      <div className="collaborator-picker-panel home-setup-card">
                        <div className="home-setup-card-head">
                          <div className="home-setup-card-copy">
                            <span className="home-setup-card-kicker">
                              {lang === "en" ? "Optional" : "По желанию"}
                            </span>
                            <span className="home-setup-card-title">
                              {lang === "en" ? "Collaborative checklist" : "Совместный чеклист"}
                            </span>
                          </div>
                          {selectedCollaborators.length > 0 && (
                            <span className="home-setup-card-counter">
                              {lang === "en"
                                ? `${selectedCollaborators.length} selected`
                                : `${selectedCollaborators.length} выбрано`}
                            </span>
                          )}
                        </div>
                        {selectedCollaborators.length > 0 && (
                          <div className="collaborator-chip-list">
                            {selectedCollaborators.map((person) => (
                              <button
                                key={person.id}
                                type="button"
                                className="collaborator-chip"
                                onClick={() => removeCollaborator(person.id)}
                                title={lang === "en" ? "Remove" : "Убрать"}
                              >
                                <span className="collaborator-chip-avatar">
                                  {person.avatar ? (
                                    <img src={person.avatar} alt={person.username} />
                                  ) : (
                                    person.username.charAt(0).toUpperCase()
                                  )}
                                </span>
                                <span className="collaborator-chip-name">{person.username}</span>
                                <span className="collaborator-chip-remove">×</span>
                              </button>
                            ))}
                          </div>
                        )}
                        <div className="collaborator-search-shell">
                          <input
                            type="text"
                            className="collaborator-search-input"
                            value={collaboratorQuery}
                            onChange={(e) => setCollaboratorQuery(e.target.value)}
                            placeholder={lang === "en" ? "Find user by username" : "Добавить пользователя по нику"}
                          />
                          {collaboratorResults.length > 0 && (
                            <div className="collaborator-search-results">
                              {collaboratorResults.map((person) => (
                                <button
                                  key={person.id}
                                  type="button"
                                  className="collaborator-search-item"
                                  onClick={() => addCollaborator(person)}
                                >
                                  <span className="collaborator-search-avatar">
                                    {person.avatar ? (
                                      <img src={person.avatar} alt={person.username} />
                                    ) : (
                                      person.username.charAt(0).toUpperCase()
                                    )}
                                  </span>
                                  <span className="collaborator-search-copy">
                                    <strong>{person.username}</strong>
                                    {person.bio && <span>{person.bio}</span>}
                                  </span>
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

                  <div className="form-field generate-field">
                    <button
                      className="generate-btn"
                      onClick={handleSubmit}
                      disabled={false}
                    >
                      {t.generate}
                    </button>
                  </div>
                </div>
              </>
            )}

            {error && <div className="error-message">{error}</div>}

            {result && (
              <div className="results-section">
                <h2 className="checklist-header">
                  <div className="checklist-title-group">
                    <span className="checklist-city-name">{result.city}</span>
                    <span className="checklist-dates">
                      {(() => {
                        const renderPart = (dateStr) => {
                          if (!dateStr) return null;
                          const d = new Date(dateStr);
                          const formatted = d.toLocaleDateString("ru-RU", { day: 'numeric', month: 'long' });
                          const match = formatted.match(/^(\d+)\s+(.+)$/);
                          if (match) {
                            return <><span className="date-num">{match[1]}</span> {match[2]}</>;
                          }
                          return formatted;
                        };
                        return (
                          <>
                            {renderPart(result.start_date || destinations[0]?.dates?.start)}
                            {" — "}
                            {renderPart(result.end_date || destinations[destinations.length - 1]?.dates?.end)}
                          </>
                        );
                      })()}
                    </span>
                  </div>
                  {result.user_id === user?.id && (
                    <button
	                      className="invite-action-btn"
	                      onClick={async () => {
	                        setInviteBusyIds([]);
	                        setShowInviteModal(true);
                        if (user?.username) {
                          fetch(`${API_URL}/users/${user.username}/followers`, { headers: authHeaders })
                            .then(r => r.ok ? r.json() : [])
                            .then(data => setFollowers(data))
                            .catch(e => console.error(e));
                        }
                        if (!result.invite_token) {
                          const res = await fetch(`${API_URL}/checklists/${savedSlug || id}/invite-token`, {
                            method: "POST",
                            headers: authHeaders
                          });
                          if (res.ok) {
                            const data = await res.json();
                            setInviteToken(data.invite_token);
                          }
                        } else {
                          setInviteToken(result.invite_token);
                        }
                      }}
                    >
                      + Пригласить
                    </button>
                  )}
                </h2>

                {(savedSlug || id) && (result.user_id === user?.id || (result.backpacks && result.backpacks.length > 0)) && (
                  <div className="baggage-panel">
                    <div className="baggage-panel-primary">
                      {baggageParticipants.length > 0 && (
                        <div className="participant-switcher">
                          {baggageParticipants.map((participant) => (
                            <button
                              key={participant.userId}
                              className={`participant-chip ${activeParticipantId === participant.userId ? "selected" : ""} ${activeTab !== "shared" && activeParticipantId === participant.userId ? "active" : ""}`}
                              onClick={() => selectParticipant(participant.userId)}
                            >
                              <span className="participant-chip-avatar">
                                {getInitial(participant.isCurrentUser ? "Я" : participant.username)}
                              </span>
                              <span className="participant-chip-body">
                                <span className="participant-chip-name">
                                  {participant.isCurrentUser ? "Я" : participant.username}
                                </span>
                                <span className="participant-chip-meta">
                                  {participant.baggage.length} багажа • {getParticipantVisibleItemCount(participant)} вещей
                                </span>
                              </span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>

                    {activeParticipant && (
                      <div className="baggage-panel-secondary">
                        <div className="baggage-panel-header">
                          <div>
                            <div className="baggage-panel-title">
                              {activeParticipant.isCurrentUser ? "Мой багаж" : `Багаж ${activeParticipant.username}`}
                            </div>
                            <div className="baggage-panel-subtitle">
                              {activeParticipant.baggage.length} багажа • {getParticipantVisibleItemCount(activeParticipant)} вещей
                            </div>
                          </div>
                          <div className="baggage-panel-actions">
                            {canManageSelectedParticipant && activeParticipant.baggage.length > 0 && !showBaggageCreator && (
                              <button
                                className="baggage-create-btn secondary"
                                onClick={() => openBaggageAccess(activeParticipant)}
                                disabled={baggageBusy}
                              >
                                Доступ
                              </button>
                            )}
                            {canManageSelectedParticipant && !showBaggageCreator && (
                              <button
                                className="baggage-create-btn"
                                onClick={() => setShowBaggageCreator(true)}
                                disabled={baggageBusy}
                              >
                                + Багаж
                              </button>
                            )}
                          </div>
                        </div>

                        <div className="baggage-chip-row">
                          {activeParticipant.baggage.length > 0 ? activeParticipant.baggage.map((bp) => (
                            <div
                              key={bp.id}
                              className={`baggage-chip ${activeTab === bp.id.toString() ? "active" : ""}`}
                              onClick={() => setActiveTab(bp.id.toString())}
                            >
                              <div className="baggage-chip-main">
                                <BackpackIcon style={{ marginRight: "6px" }} />
                                <div className="baggage-chip-copy">
                                  <div className="baggage-chip-heading">
                                    {renamingBaggageId === bp.id ? (
                                      <div
                                        className="baggage-rename-row"
                                        onClick={(e) => e.stopPropagation()}
                                      >
                                        <input
                                          className="baggage-rename-input"
                                          value={renamingBaggageName}
                                          onChange={(e) => setRenamingBaggageName(e.target.value)}
                                          onKeyDown={(e) => {
                                            if (e.key === "Enter") handleRenameBaggage(bp);
                                            if (e.key === "Escape") {
                                              setRenamingBaggageId(null);
                                              setRenamingBaggageName("");
                                            }
                                          }}
                                          autoFocus
                                        />
                                        <button
                                          type="button"
                                          className="baggage-rename-btn save"
                                          onClick={() => handleRenameBaggage(bp)}
                                          disabled={baggageBusy || !renamingBaggageName.trim()}
                                        >
                                          OK
                                        </button>
                                        <button
                                          type="button"
                                          className="baggage-rename-btn"
                                          onClick={() => {
                                            setRenamingBaggageId(null);
                                            setRenamingBaggageName("");
                                          }}
                                          disabled={baggageBusy}
                                        >
                                          ×
                                        </button>
                                      </div>
                                    ) : (
                                      <>
                                        <span className="baggage-chip-name">{bp.name || "Багаж"}</span>
                                        {bp.is_default && <span className="baggage-chip-badge">основной</span>}
                                        {bp.user_id === user?.id && (
                                          <button
                                            type="button"
                                            className="baggage-rename-trigger"
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              startRenameBaggage(bp);
                                            }}
                                            title="Переименовать багаж"
                                          >
                                            ✎
                                          </button>
                                        )}
                                      </>
                                    )}
                                  </div>
                                  <span className="baggage-chip-meta">
                                    {getBaggageMetaLine(bp)}
                                  </span>
                                </div>
                              </div>
                              <div className="baggage-chip-actions">
                                {bp.user_id === user?.id && (
                                  <button
                                    className={`baggage-default-toggle ${bp.is_default ? "active" : ""}`}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleSetDefaultBaggage(bp);
                                    }}
                                    title={bp.is_default ? "Основной багаж" : "Сделать основным"}
                                    disabled={baggageBusy || bp.is_default}
                                  >
                                    <span className="baggage-default-toggle-dot" />
                                  </button>
                                )}
                                {bp.user_id === user?.id && (
                                  <button
                                    className={`baggage-chip-action ${result.hidden_sections?.includes(`backpack:${bp.id}`) ? "hidden" : "visible"}`}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleToggleSectionVisibility(`backpack:${bp.id}`);
                                    }}
                                    title={result.hidden_sections?.includes(`backpack:${bp.id}`) ? "Скрыто от других" : "Видно всем"}
                                  >
                                    {result.hidden_sections?.includes(`backpack:${bp.id}`) ? <LockIcon style={{ marginRight: 0 }} /> : <UnlockIcon style={{ marginRight: 0 }} />}
                                  </button>
                                )}
                                {bp.user_id === user?.id && !bp.is_default && (
                                  <button
                                    className="baggage-chip-delete"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleDeleteBaggage(bp);
                                    }}
                                    title="Удалить багаж"
                                    disabled={baggageBusy}
                                  >
                                    ×
                                  </button>
                                )}
                              </div>
                            </div>
                          )) : (
                            <div className="baggage-empty-hint">
                              У этого участника пока нет отдельного багажа.
                            </div>
                          )}
                        </div>

                        {canManageSelectedParticipant && showBaggageCreator && (
                          <div className="baggage-creator">
                            <div className="baggage-creator-presets">
                              {["Чемодан", "Ручная кладь", "Рюкзак"].map((preset) => (
                                <button
                                  key={preset}
                                  className={`baggage-preset-chip ${newBaggageName === preset ? "active" : ""}`}
                                  onClick={() => setNewBaggageName(preset)}
                                  type="button"
                                >
                                  {preset}
                                </button>
                              ))}
                            </div>
                            <div className="baggage-creator-row">
                              <input
                                className="baggage-name-input"
                                type="text"
                                value={newBaggageName}
                                onChange={(e) => setNewBaggageName(e.target.value)}
                                placeholder="Например: Чемодан"
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") {
                                    handleCreateBaggage();
                                  }
                                }}
                                autoFocus
                              />
                              <button
                                className="baggage-confirm-btn"
                                onClick={handleCreateBaggage}
                                disabled={baggageBusy || !newBaggageName.trim()}
                              >
                                Создать
                              </button>
                              <button
                                className="baggage-cancel-btn"
                                onClick={() => {
                                  setShowBaggageCreator(false);
                                  setNewBaggageName("");
                                }}
                                disabled={baggageBusy}
                              >
                                Отмена
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}



                <div className="checklist-card">
                  {(() => {
                    const isSharedHidden = !isChecklistParticipant && result.hidden_sections?.includes('shared');
                    const isBackpacksHidden = result.hidden_sections?.includes('backpacks');

                    if (activeTab === 'shared' && isSharedHidden) {
                      return <div className="section-restricted-msg"><LockIcon /> {result.user?.username || 'Владелец'} ограничил просмотр этого раздела</div>;
                    }
                    if (activeTab !== 'shared') {
                      const bp = result.backpacks?.find((entry) => entry.id.toString() === activeTab);
                      const isThisBpIsHidden = result.hidden_sections?.includes(`backpack:${activeTab}`);
                      const canViewThisBaggage = Boolean(
                        !bp
                          || !isThisBpIsHidden
                          || bp.user_id === user?.id
                      );
                      if ((isBackpacksHidden && result.user_id !== user?.id) || !canViewThisBaggage) {
                        return <div className="section-restricted-msg"><LockIcon /> {(bp?.user?.username || result.user?.username || 'Владелец')} ограничил просмотр этого багажа</div>;
                      }
                    }

                    let targetItems = result.items || [];
                    let targetRemoved = removedItems;
                    let targetChecked = checkedItems;
                    let targetQuantities = normalizeQuantityMap(result.item_quantities || {});
                    let targetPackedQuantities = normalizePackedQuantityMap(result.packed_quantities || {});

                    if (activeTab !== "shared" && result.backpacks) {
                      const bp = result.backpacks.find(b => b.id.toString() === activeTab);
                      if (bp) {
                        targetItems = bp.items || [];
                        targetRemoved = bp.removed_items || [];
                        targetChecked = buildCheckedItemsMap(
                          bp.items || [],
                          bp.checked_items || [],
                          bp.item_quantities || {},
                          bp.packed_quantities || {}
                        );
                        targetQuantities = normalizeQuantityMap(bp.item_quantities || {});
                        targetPackedQuantities = normalizePackedQuantityMap(bp.packed_quantities || {});
                      }
                    }

                    let items = targetItems.filter(item => !targetRemoved.includes(item));

                    if (activeTab === "shared" && result.backpacks) {
                      // Filter out items that are currently in any backpack
                      const allBackpackItems = new Set();
                      result.backpacks.forEach(bp => {
                        if (bp.items) bp.items.forEach(i => allBackpackItems.add(i));
                      });
                      items = items.filter(item => !allBackpackItems.has(item));
                    }

                    const perCol = items.length ? Math.ceil(items.length / checklistColumns) : 0;
                    const cols = items.length
                      ? Array.from({ length: checklistColumns }, (_, i) => items.slice(i * perCol, (i + 1) * perCol))
                      : [];
                    return (
                      <div className="checklist-multicolumn">
                        {items.length === 0 && <div className="empty-state" style={{ padding: "20px", color: "#888" }}>Список пуст.</div>}
                        {cols.map((col, idx) => (
                          <div className="checklist-category" key={idx}>
                            <div className="checklist">
                              {col.map((item) => (
                                (() => {
                                  const quantity = getItemQuantity(targetQuantities, item);
                                  const packedQuantity = getPackedQuantity(targetPackedQuantities, item);
                                  const packedState = `${packedQuantity}/${quantity}`;
                                  const canMoveItem = activeTab === "shared"
                                    ? result?.backpacks?.length > 0
                                    : result?.backpacks?.length > 1;
                                  return (
                                <label
                                  key={item}
                                  className={`checklist-label${targetChecked[item] ? " checked" : ""}${quantityEditor?.item === item && quantityEditor?.sectionKey === activeTab ? " quantity-editor-open" : ""}`}
                                >
                                  <input
                                    type="checkbox"
                                    className="checklist-checkbox"
                                    checked={targetChecked[item] || false}
                                    onChange={() => handleCheck(item)}
                                    disabled={!canEditCurrentSection}
                                  />
                                    <span className="checklist-item-copy">
                                    <span className="checklist-item-text">{item}</span>
                                    {isMobileChecklistView && (
                                      <span className={`checklist-item-meta${packedQuantity >= quantity ? " complete" : packedQuantity > 0 ? " partial" : ""}`}>
                                        {packedState}
                                      </span>
                                    )}
                                  </span>
                                  <span className="item-right-controls">
                                    {!isMobileChecklistView && (
                                      canEditCurrentSection ? (
                                        <button
                                          type="button"
                                          className={`item-progress-badge item-progress-trigger${packedQuantity >= quantity ? " complete" : packedQuantity > 0 ? " partial" : ""}`}
                                          onClick={(e) => {
                                            e.preventDefault();
                                            e.stopPropagation();
                                            toggleQuantityEditor(item, quantity, packedQuantity);
                                          }}
                                        >
                                          {packedState}
                                        </button>
                                      ) : (
                                        <span className={`item-progress-badge${packedQuantity >= quantity ? " complete" : packedQuantity > 0 ? " partial" : ""}`}>
                                          {packedState}
                                        </span>
                                      )
                                    )}
                                    {canEditCurrentSection && (
                                      isMobileChecklistView ? (
                                        <span className="mobile-item-menu-wrap">
                                          <button
                                            type="button"
                                            className="mobile-item-stepper-btn"
                                            title={lang === "en" ? "Pack one less" : "Убрать одну"}
                                            onClick={(e) => {
                                              e.preventDefault();
                                              e.stopPropagation();
                                              handleQuickPackedChange(item, -1);
                                            }}
                                            disabled={packedQuantity <= 0}
                                          >
                                            -1
                                          </button>
                                          <button
                                            type="button"
                                            className="mobile-item-stepper-btn accent"
                                            title={lang === "en" ? "Pack one more" : "Добавить одну"}
                                            onClick={(e) => {
                                              e.preventDefault();
                                              e.stopPropagation();
                                              handleQuickPackedChange(item, 1);
                                            }}
                                            disabled={packedQuantity >= quantity}
                                          >
                                            +1
                                          </button>
                                          <button
                                            type="button"
                                            className={`mobile-item-menu-trigger${quantityEditor?.item === item && quantityEditor?.sectionKey === activeTab ? " active" : ""}`}
                                            title={lang === "en" ? "Open item settings" : "Открыть настройки вещи"}
                                            onClick={(e) => {
                                              e.preventDefault();
                                              e.stopPropagation();
                                              toggleQuantityEditor(item, quantity, packedQuantity);
                                            }}
                                          >
                                            •••
                                          </button>
                                        </span>
                                      ) : (
                                        <span className="item-action-group">
                                          {canMoveItem && (
                                            <button
                                              className="checklist-action-btn"
                                              title={activeTab === "shared" ? "Разложить по багажу" : "Переложить в другой багаж"}
                                              onClick={e => {
                                                e.preventDefault();
                                                openMoveItemDialog(item, activeTab === "shared" ? null : Number(activeTab));
                                              }}
                                              tabIndex={-1}
                                            >
                                              <BackpackIcon style={{ width: '16px', height: '16px', marginRight: 0 }} />
                                            </button>
                                          )}
                                          <button
                                            className="checklist-remove-btn"
                                            title="Удалить"
                                            onClick={e => { e.preventDefault(); handleRemoveItem(item); }}
                                            tabIndex={-1}
                                          >×</button>
                                        </span>
                                      )
                                    )}
                                  </span>
                                  {!isMobileChecklistView && canEditCurrentSection && quantityEditor?.item === item && quantityEditor?.sectionKey === activeTab && (
                                    <div
                                      className="quantity-editor-popover"
                                      onClick={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                      }}
                                      onMouseDown={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                      }}
                                    >
                                      {isMobileChecklistView && <div className="mobile-sheet-handle" />}
                                      <div className="quantity-editor-title">{item}</div>
                                      <div className="quantity-editor-summary">
                                        <div>
                                          <span className="quantity-editor-summary-label">{lang === "en" ? "Packed" : "Собрано"}</span>
                                          <strong>{quantityEditor.packed}/{quantityEditor.needed}</strong>
                                        </div>
                                        <div>
                                          <span className="quantity-editor-summary-label">{lang === "en" ? "Needed" : "Нужно"}</span>
                                          <strong>{quantityEditor.needed}</strong>
                                        </div>
                                      </div>
                                      <div className="quantity-editor-shortcuts">
                                        <button
                                          type="button"
                                          className="quantity-editor-shortcut"
                                          onClick={() => updateQuantityEditorDraft("packed", Math.max(0, quantityEditor.packed - 1))}
                                          disabled={quantityEditor.packed <= 0}
                                        >
                                          -1 {lang === "en" ? "packed" : "собрано"}
                                        </button>
                                        <button
                                          type="button"
                                          className="quantity-editor-shortcut"
                                          onClick={() => updateQuantityEditorDraft("packed", Math.min(quantityEditor.needed, quantityEditor.packed + 1))}
                                          disabled={quantityEditor.packed >= quantityEditor.needed}
                                        >
                                          +1 {lang === "en" ? "packed" : "собрано"}
                                        </button>
                                        <button
                                          type="button"
                                          className="quantity-editor-shortcut accent"
                                          onClick={() => updateQuantityEditorDraft("packed", quantityEditor.needed)}
                                          disabled={quantityEditor.packed >= quantityEditor.needed}
                                        >
                                          {lang === "en" ? "Pack all" : "Собрать всё"}
                                        </button>
                                      </div>
                                      <div className="quantity-editor-row">
                                        <span className="quantity-editor-label">Нужно</span>
                                        <div className="item-quantity-control quantity-editor-control">
                                          <button
                                            type="button"
                                            className="item-quantity-btn"
                                            onClick={() => updateQuantityEditorDraft("needed", Math.max(1, quantityEditor.needed - 1))}
                                            disabled={quantityEditor.needed <= 1}
                                          >
                                            −
                                          </button>
                                          <input
                                            type="number"
                                            min="1"
                                            className="item-quantity-input"
                                            value={quantityEditor.needed}
                                            onChange={(e) => updateQuantityEditorDraft("needed", e.target.value)}
                                          />
                                          <button
                                            type="button"
                                            className="item-quantity-btn"
                                            onClick={() => updateQuantityEditorDraft("needed", quantityEditor.needed + 1)}
                                          >
                                            +
                                          </button>
                                        </div>
                                      </div>
                                      <div className="quantity-editor-row">
                                        <span className="quantity-editor-label">Собрано</span>
                                        <div className="item-quantity-control quantity-editor-control">
                                          <button
                                            type="button"
                                            className="item-quantity-btn"
                                            onClick={() => updateQuantityEditorDraft("packed", Math.max(0, quantityEditor.packed - 1))}
                                            disabled={quantityEditor.packed <= 0}
                                          >
                                            −
                                          </button>
                                          <input
                                            type="number"
                                            min="0"
                                            max={quantityEditor.needed}
                                            className="item-quantity-input"
                                            value={quantityEditor.packed}
                                            onChange={(e) => updateQuantityEditorDraft("packed", e.target.value)}
                                          />
                                          <button
                                            type="button"
                                            className="item-quantity-btn"
                                            onClick={() => updateQuantityEditorDraft("packed", Math.min(quantityEditor.needed, quantityEditor.packed + 1))}
                                            disabled={quantityEditor.packed >= quantityEditor.needed}
                                          >
                                            +
                                          </button>
                                        </div>
                                      </div>
                                      <div className="quantity-editor-actions">
                                        <button
                                          type="button"
                                          className="quantity-editor-btn danger"
                                          onClick={() => {
                                            handleRemoveItem(item);
                                            setQuantityEditor(null);
                                          }}
                                        >
                                          {lang === "en" ? "Remove" : "Удалить"}
                                        </button>
                                        <button
                                          type="button"
                                          className="quantity-editor-btn"
                                          onClick={applyQuantityEditor}
                                        >
                                          Применить
                                        </button>
                                      </div>
                                    </div>
                                  )}
                                </label>
                                  );
                                })()
                              ))}
                            </div>
                          </div>
                        ))}
                </div>
              );
            })()}
            {isMobileChecklistView && canEditCurrentSection && quantityEditor?.sectionKey === activeTab && (
              <div
                className="mobile-quantity-sheet-backdrop"
                onClick={() => setQuantityEditor(null)}
              >
                <section
                  className="mobile-quantity-sheet"
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                  }}
                >
                  <div className="mobile-sheet-handle" />
                  <header className="mobile-quantity-sheet-header">
                    <span>{lang === "en" ? "Item settings" : "Настройка вещи"}</span>
                    <h2>{quantityEditor.item}</h2>
                  </header>
                  <div className="mobile-quantity-sheet-grid">
                    <div>
                      <span>{lang === "en" ? "Packed" : "Собрано"}</span>
                      <strong>{quantityEditor.packed}/{quantityEditor.needed}</strong>
                    </div>
                    <div>
                      <span>{lang === "en" ? "Needed" : "Нужно"}</span>
                      <strong>{quantityEditor.needed}</strong>
                    </div>
                  </div>
                  <div className="mobile-quantity-sheet-actions">
                    <button
                      type="button"
                      onClick={() => updateQuantityEditorDraft("packed", Math.max(0, quantityEditor.packed - 1))}
                      disabled={quantityEditor.packed <= 0}
                    >
                      -1 {lang === "en" ? "packed" : "собрано"}
                    </button>
                    <button
                      type="button"
                      onClick={() => updateQuantityEditorDraft("packed", Math.min(quantityEditor.needed, quantityEditor.packed + 1))}
                      disabled={quantityEditor.packed >= quantityEditor.needed}
                    >
                      +1 {lang === "en" ? "packed" : "собрано"}
                    </button>
                    <button
                      type="button"
                      className="accent"
                      onClick={() => updateQuantityEditorDraft("packed", quantityEditor.needed)}
                      disabled={quantityEditor.packed >= quantityEditor.needed}
                    >
                      {lang === "en" ? "Pack all" : "Собрать всё"}
                    </button>
                  </div>
                  <div className="mobile-quantity-row">
                    <span>{lang === "en" ? "Quantity in list" : "Количество в списке"}</span>
                    <div>
                      <button
                        type="button"
                        onClick={() => updateQuantityEditorDraft("needed", Math.max(1, quantityEditor.needed - 1))}
                        disabled={quantityEditor.needed <= 1}
                      >
                        -
                      </button>
                      <strong>{quantityEditor.needed}</strong>
                      <button
                        type="button"
                        onClick={() => updateQuantityEditorDraft("needed", quantityEditor.needed + 1)}
                      >
                        +
                      </button>
                    </div>
                  </div>
                  <div className="mobile-quantity-sheet-secondary">
                    {canMoveQuantityEditorItem && (
                      <button
                        type="button"
                        onClick={() => {
                          const sourceBackpackId = quantityEditor.sectionKey === "shared"
                            ? null
                            : Number(quantityEditor.sectionKey);
                          setQuantityEditor(null);
                          openMoveItemDialog(quantityEditor.item, sourceBackpackId);
                        }}
                      >
                        {quantityEditor.sectionKey === "shared"
                          ? (lang === "en" ? "Sort into baggage" : "Разложить")
                          : (lang === "en" ? "Move item" : "Переложить")}
                      </button>
                    )}
                    <button
                      type="button"
                      className="danger"
                      onClick={() => {
                        handleRemoveItem(quantityEditor.item);
                        setQuantityEditor(null);
                      }}
                    >
                      {lang === "en" ? "Remove" : "Удалить"}
                    </button>
                  </div>
                  <div className="mobile-quantity-sheet-footer">
                    <button
                      type="button"
                      className="quantity-editor-btn subtle"
                      onClick={() => setQuantityEditor(null)}
                    >
                      {lang === "en" ? "Close" : "Закрыть"}
                    </button>
                    <button
                      type="button"
                      className="quantity-editor-btn"
                      onClick={applyQuantityEditor}
                    >
                      {lang === "en" ? "Apply" : "Применить"}
                    </button>
                  </div>
                </section>
              </div>
            )}

                  <div className="checklist-actions">
                    {canEditCurrentSection && (
                      <>
                        <button className="action-btn" onClick={resetChecklist}>Сбросить отметки</button>
                        <button className="action-btn" onClick={() => setAddItemMode(v => !v)}>
                          {addItemMode ? "Отмена" : "+ Добавить вещь"}
                        </button>
                        {addItemMode && (
                          <>
                            <input
                              className="add-item-input"
                              type="text"
                              value={newItem}
                              onChange={e => setNewItem(e.target.value)}
                              placeholder="Новая вещь"
                              onKeyDown={e => { if (e.key === "Enter") handleAddItem(); }}
                              autoFocus
                            />
                            <button className="action-btn primary" onClick={handleAddItem}>OK</button>
                          </>
                        )}
                      </>
                    )}
                  </div>
                </div>

                {/* Weather Forecast */}
                {result.daily_forecast && result.daily_forecast.length > 0 && (
                  <div className={`forecast-section ${!showForecast ? 'collapsed' : ''}`}>
                    <div className="forecast-header" onClick={() => setShowForecast(!showForecast)}>
                      <h3><span style={{ display: 'flex', alignItems: 'center' }}><WeatherIcon /> {t.forecast}</span></h3>
                      <button className="collapse-toggle">
                        <span className={`chevron ${showForecast ? 'up' : ''}`}>▾</span>
                      </button>
                    </div>

                    {showForecast && (
                      <div className="forecast-content">
                        {Object.entries(
                          result.daily_forecast.reduce((acc, day) => {
                            const cityName = day.city || result.city || "";
                            if (!acc[cityName]) acc[cityName] = [];
                            acc[cityName].push(day);
                            return acc;
                          }, {})
                        ).map(([cityName, days]) => {
                          const forecastRows = viewportWidth >= 1024 ? splitForecastDays(days) : [days];
                          return (
                            <div key={cityName} className="city-forecast-group">
                              {Object.keys(result.daily_forecast.reduce((acc, day) => {
                                const name = day.city || result.city || "";
                                acc[name] = true;
                                return acc;
                              }, {})).length > 1 && (
                                  <h4 className="city-forecast-title">📍 {cityName}</h4>
                                )}
                              <div className={`forecast-grid forecast-grid-count-${days.length}`}>
                                {forecastRows.map((row, rowIndex) => (
                                  <div
                                    key={`${cityName}-${rowIndex}`}
                                    className="forecast-grid-row"
                                    style={viewportWidth >= 1024 ? { "--forecast-grid-row-width": `${getForecastRowWidth(row.length)}px` } : undefined}
                                  >
                                    {row.map((day) => (
                                      <div key={day.date} className={`forecast-card${day.source === "historical" ? " forecast-historical" : ""}`}>
                                        <div className="forecast-date">{formatDate(day.date)}</div>

                                        <img
                                          src={`https://openweathermap.org/img/wn/${day.icon}@2x.png`}
                                          alt={day.condition}
                                          className="forecast-icon"
                                        />
                                        <div className="forecast-conditions">{day.condition}</div>
                                        <div className="forecast-temp">
                                          {day.temp_min.toFixed(1)}° / {day.temp_max.toFixed(1)}°C
                                        </div>
                                        <div className="forecast-details">
                                          {day.humidity != null && <span title="Влажность" style={{ display: 'inline-flex', alignItems: 'center', whiteSpace: 'nowrap' }}><DropletIcon style={{ width: '14px', height: '14px', marginRight: '3px' }} /> {day.humidity}%</span>}
                                          {day.wind_speed != null && <span title="Ветер" style={{ display: 'inline-flex', alignItems: 'center', whiteSpace: 'nowrap' }}><WindIcon style={{ width: '14px', height: '14px', marginRight: '3px' }} /> {day.wind_speed.toFixed(0)} {t.kmh}</span>}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                ))}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}

                {/* Route Timeline (multi-city) */}
                {destinations.length > 1 && result && (
                  <div className="route-timeline">
                    <h3 className="section-title">🗺 {t.routeTitle || "Маршрут"}</h3>
                    <div className="timeline-track">
                      {destinations.map((dest, i) => (
                        <div key={i} className="timeline-stop">
                          <div className="timeline-dot" />
                          {i < destinations.length - 1 && <div className="timeline-line" />}
                          <div className="timeline-info">
                            <div className="timeline-city">{typeof dest.city === "object" ? (dest.city?.name || dest.city?.fullName || "...") : (dest.city || "...")}</div>
                            {dest.dates?.start && (
                              <div className="timeline-dates">
                                {new Date(dest.dates.start).toLocaleDateString("ru-RU", { day: "numeric", month: "short" })}
                                {" — "}
                                {new Date(dest.dates.end).toLocaleDateString("ru-RU", { day: "numeric", month: "short" })}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Itinerary Section */}
                {result && result.start_date && result.end_date && savedSlug && (
                  <div className="itinerary-wrapper">
                    {!isChecklistParticipant && result.hidden_sections?.includes('itinerary') ? (
                      <div className="section-restricted-msg" style={{ background: 'var(--bg-secondary)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}><LockIcon /> {result.user?.username || 'Владелец'} ограничил просмотр плана поездки</div>
                      </div>
                    ) : (
                      <ItinerarySection
                        checklist={result}
                        lang={lang}
                        slug={savedSlug}
                        isOwner={!!isChecklistParticipant}
                        realOwnerId={result.user_id}
                        currentUserId={user?.id}
                        hiddenSections={result.hidden_sections}
                        onToggleVisibility={handleToggleSectionVisibility}
                        requestConfirm={requestConfirm}
                      />
                    )}
                  </div>
                )}

                {result && (
                  <TripReviewsSection
                    checklist={result}
                    user={user}
                    token={token}
                    lang={lang}
                    canReview={canReviewTrip}
                    onReviewSaved={handleReviewSaved}
                    requestConfirm={requestConfirm}
                  />
                )}

                {/* Attractions */}
                {result?.city && (
                  <AttractionsSection city={result.city} lang={lang} compact={isMobileChecklistView} />
                )}

                {/* Flights — only for cities with plane transport */}
                {(() => {
                  if (!result || !result.city) return null;
                  const allCities = result.city.split(" + ").map(c => c.trim());
                  const transports = result.transports || [];
                  // transports array: [to_city0, to_city1, ..., return_transport]
                  // Last element is the return transport
                  const returnTr = transports.length > allCities.length ? transports[transports.length - 1] : (transports.length > 0 ? "plane" : "plane");
                  // Outbound: filter cities where transport is "plane"
                  const outboundCities = transports.length > 0
                    ? allCities.filter((_, i) => (transports[i] || "plane") === "plane")
                    : allCities;
                  // Return: show if return transport is plane, from the last city
                  const lastCity = allCities[allCities.length - 1];
                  const showReturn = returnTr === "plane";
                  // If no outbound and no return — hide section entirely
                  if (outboundCities.length === 0 && !showReturn) return null;
                  // Build the outbound city string
                  const outboundCity = outboundCities.length > 0 ? outboundCities[0] : null;
                  return (
                    <FlightsSection
                      key={"fl-" + (outboundCity || lastCity)}
                      city={outboundCity || lastCity}
                      startDate={result.start_date || destinations[0]?.dates?.start}
                      returnDate={showReturn ? (result.end_date || destinations[destinations.length - 1]?.dates?.end) : null}
                      returnCity={showReturn ? lastCity : null}
                      origin={originCity?.fullName || originCity || result.origin_city || ""}
                      lang={lang}
                      compact={isMobileChecklistView}
                    />
                  );
                })()}

                {/* Hotels */}
                {result && result.city && (
                  <HotelsSection key={"ht-" + result.city} city={result.city} startDate={result.start_date || destinations[0]?.dates?.start} endDate={result.end_date || destinations[destinations.length - 1]?.dates?.end} lang={lang} compact={isMobileChecklistView} />
                )}

                {/* eSIM */}
                {result && result.city && (
                  <EsimSection key={"esim-" + result.city} city={result.city} lang={lang} compact={isMobileChecklistView} />
                )}

              </div>
            )}
          </>
        )}
      </div>

      {showPackingModal && (
        <div className="modal-overlay" onClick={() => {
          setPackingProfileDraft(normalizePackingProfile(user?.packing_profile || DEFAULT_PACKING_PROFILE));
          setNewBaseItem("");
          setShowPackingModal(false);
        }}>
          <div className="modal-content packing-settings-modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => {
              setPackingProfileDraft(normalizePackingProfile(user?.packing_profile || DEFAULT_PACKING_PROFILE));
              setNewBaseItem("");
              setShowPackingModal(false);
            }}>&times;</button>
            <h3>{lang === "en" ? "Packing settings" : "Настройки сборов"}</h3>
            <p className="packing-settings-copy">
              {lang === "en"
                ? "These preferences are applied when a new checklist is generated from the home page."
                : "Эти параметры будут использоваться при создании нового чеклиста с главной страницы."}
            </p>

            <div className="packing-settings-group">
              <span className="packing-settings-label">{lang === "en" ? "Gender" : "Пол"}</span>
              <div className="packing-settings-segmented">
                {[
                  { id: "unspecified", label: lang === "en" ? "Not specified" : "Не указан" },
                  { id: "male", label: lang === "en" ? "Male" : "Мужской" },
                  { id: "female", label: lang === "en" ? "Female" : "Женский" },
                ].map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`packing-settings-pill ${packingProfileDraft.gender === item.id ? "active" : ""}`}
                    onClick={() => setPackingProfileDraft((prev) => ({ ...prev, gender: item.id }))}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="packing-settings-group">
              <span className="packing-settings-label">{lang === "en" ? "Extra factors" : "Дополнительные факторы"}</span>
              <div className="packing-settings-toggles">
                {[
                  {
                    key: "traveling_with_pet",
                    label: lang === "en" ? "Traveling with pet" : "Путешествую с питомцем",
                  },
                  {
                    key: "has_allergies",
                    label: lang === "en" ? "There are allergies" : "Есть аллергии",
                  },
                ].map((item) => (
                  <label key={item.key} className={`packing-settings-toggle ${packingProfileDraft[item.key] ? "active" : ""}`}>
                    <input
                      type="checkbox"
                      className="packing-settings-toggle-input"
                      checked={Boolean(packingProfileDraft[item.key])}
                      onChange={(e) => setPackingProfileDraft((prev) => ({ ...prev, [item.key]: e.target.checked }))}
                    />
                    <span className="packing-settings-toggle-box" aria-hidden="true" />
                    <span>{item.label}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="packing-settings-group">
              <span className="packing-settings-label">{lang === "en" ? "Always add" : "Всегда добавлять"}</span>
              <div className="packing-base-items-editor">
                <div className="packing-base-items-input-row">
                  <input
                    type="text"
                    className="packing-base-items-input"
                    value={newBaseItem}
                    onChange={(e) => setNewBaseItem(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        handleAddBaseItem();
                      }
                    }}
                    placeholder={lang === "en" ? "For example: contact lenses" : "Например: линзы"}
                  />
                  <button type="button" className="packing-base-items-add" onClick={handleAddBaseItem}>
                    {lang === "en" ? "Add" : "Добавить"}
                  </button>
                </div>
                {packingProfileDraft.always_include_items.length > 0 ? (
                  <div className="packing-base-items-list">
                    {packingProfileDraft.always_include_items.map((item) => (
                      <button
                        key={item}
                        type="button"
                        className="packing-base-item-chip"
                        onClick={() => handleRemoveBaseItem(item)}
                        title={lang === "en" ? "Remove item" : "Убрать вещь"}
                      >
                        <span>{item}</span>
                        <span>×</span>
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="packing-base-items-empty">
                    {lang === "en" ? "No personal base items yet" : "Пока нет личных базовых вещей"}
                  </div>
                )}
              </div>
            </div>

            <div className="packing-settings-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  setPackingProfileDraft(normalizePackingProfile(user?.packing_profile || DEFAULT_PACKING_PROFILE));
                  setNewBaseItem("");
                  setShowPackingModal(false);
                }}
                disabled={packingProfileSaving}
              >
                {lang === "en" ? "Cancel" : "Отмена"}
              </button>
              <button type="button" className="btn-primary" onClick={handleSavePackingProfile} disabled={packingProfileSaving}>
                {packingProfileSaving ? "..." : (lang === "en" ? "Save" : "Сохранить")}
              </button>
            </div>
          </div>
        </div>
      )}

      {moveItemDialog && (
        <div className="modal-overlay modal-overlay-lifted" onClick={() => !moveItemBusy && setMoveItemDialog(null)}>
          <div className="modal-content baggage-access-modal item-move-modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => !moveItemBusy && setMoveItemDialog(null)}>&times;</button>
            <h3>{lang === "en" ? "Move item" : "Переложить вещь"}</h3>
            <p className="invite-modal-desc">
              {lang === "en"
                ? `Choose whether to move "${moveItemDialog.item}" to your baggage or assign it to another participant.`
                : `Выбери, куда переложить «${moveItemDialog.item}»: к себе в другой багаж или другому участнику.`}
            </p>
            <div className="baggage-access-list move-destination-groups">
              {ownMoveDestinations.length > 0 && (
                <div className="move-destination-section">
                  <div className="move-destination-title">
                    {lang === "en" ? "Move to my baggage" : "Переложить к себе"}
                  </div>
                  <div className="move-destination-subtitle">
                    {lang === "en" ? "Another suitcase, backpack or bag of yours." : "В другой свой чемодан, рюкзак или сумку."}
                  </div>
                  <div className="baggage-access-list">
                    {ownMoveDestinations.map((destination) => (
                      <button
                        key={destination.id}
                        type="button"
                        className={`baggage-access-item move-destination-item ${moveItemDialog.targetBackpackId === destination.id ? "active" : ""}`}
                        onClick={() => setMoveItemDialog((prev) => ({ ...prev, targetBackpackId: destination.id }))}
                      >
                        <span className="baggage-access-check" aria-hidden="true" />
                        <span className="baggage-access-avatar">
                          {getInitial(destination.title)}
                        </span>
                        <span className="baggage-access-copy">
                          <strong>{destination.title}</strong>
                          <span>{destination.subtitle}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {otherMoveDestinations.length > 0 && (
                <div className="move-destination-section">
                  <div className="move-destination-title">
                    {lang === "en" ? "Give to another participant" : "Передать другому участнику"}
                  </div>
                  <div className="move-destination-subtitle">
                    {lang === "en" ? "Move the item straight into someone else's baggage." : "Сразу переложить вещь в багаж другого человека."}
                  </div>
                  <div className="baggage-access-list">
                    {otherMoveDestinations.map((destination) => (
                      <button
                        key={destination.id}
                        type="button"
                        className={`baggage-access-item move-destination-item ${moveItemDialog.targetBackpackId === destination.id ? "active" : ""}`}
                        onClick={() => setMoveItemDialog((prev) => ({ ...prev, targetBackpackId: destination.id }))}
                      >
                        <span className="baggage-access-check" aria-hidden="true" />
                        <span className="baggage-access-avatar">
                          {getInitial(destination.title)}
                        </span>
                        <span className="baggage-access-copy">
                          <strong>{destination.title}</strong>
                          <span>{destination.subtitle}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {moveDestinations.length === 0 && (
                <div className="packing-base-items-empty">
                  {lang === "en" ? "There is nowhere to move this item yet." : "Пока некуда переложить эту вещь."}
                </div>
              )}
            </div>
            <div className="baggage-access-actions">
              <button className="action-btn" onClick={() => setMoveItemDialog(null)} disabled={moveItemBusy}>
                {lang === "en" ? "Cancel" : "Отмена"}
              </button>
              <button
                className="action-btn primary"
                onClick={handleConfirmMoveItem}
                disabled={moveItemBusy || !moveItemDialog.targetBackpackId}
              >
                {moveItemBusy ? "..." : (lang === "en" ? "Move" : "Переложить")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Модальное окно приглашения */}
      {accessOwner && (
        <div className="modal-overlay modal-overlay-lifted" onClick={() => setAccessOwner(null)}>
          <div className="modal-content baggage-access-modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setAccessOwner(null)}>&times;</button>
            <h3>Доступ к багажу</h3>
            <p className="invite-modal-desc">
              Выбери, кто сможет отмечать, добавлять и удалять вещи во всем разделе «{accessOwner.displayName}».
            </p>
            <div className="baggage-access-list">
              {baggageParticipants
                .filter((participant) => participant.userId !== accessOwner.userId)
                .map((participant) => (
                  <label key={participant.userId} className={`baggage-access-item ${accessEditorIds.includes(participant.userId) ? "active" : ""}`}>
                    <input
                      type="checkbox"
                      className="baggage-access-input"
                      checked={accessEditorIds.includes(participant.userId)}
                      onChange={() => handleToggleBaggageEditor(participant.userId)}
                    />
                    <span className="baggage-access-check" aria-hidden="true" />
                    <span className="baggage-access-avatar">
                      {getInitial(participant.isCurrentUser ? "Я" : participant.username)}
                    </span>
                    <span className="baggage-access-copy">
                      <strong>{participant.isCurrentUser ? "Я" : participant.username}</strong>
                      <span>{participant.baggage.length} багажа</span>
                    </span>
                  </label>
                ))}
            </div>
            <div className="baggage-access-actions">
              <button className="action-btn" onClick={() => setAccessOwner(null)} disabled={baggageBusy}>Закрыть</button>
              <button className="action-btn primary" onClick={handleSaveBaggageAccess} disabled={baggageBusy}>Сохранить доступ</button>
            </div>
          </div>
        </div>
      )}

      {showInviteModal && (
        <div className="modal-overlay modal-overlay-lifted" onClick={() => setShowInviteModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setShowInviteModal(false)}>&times;</button>
            <h3 style={{ marginTop: 0 }}>🔗 Пригласить в путешествие</h3>

            <p className="invite-modal-desc">Ваши подписчики:</p>
            <div className="invite-followers-list">
              {followers.length > 0 ? followers.map(f => {
                const followerId = normalizeUserId(f.id);
                const isAlreadyInChecklist = checklistParticipantIds.has(followerId) || inviteAlreadyIdSet.has(followerId);
                const isInviteBusy = inviteBusyIdSet.has(followerId);
                const isInviteSent = inviteSentIdSet.has(followerId);
                const isInviteDisabled = isAlreadyInChecklist || isInviteBusy || isInviteSent;
                const inviteButtonLabel = isAlreadyInChecklist
                  ? (lang === "en" ? "Already in list" : "Уже в чеклисте")
                  : isInviteSent
                    ? (lang === "en" ? "Sent" : "Отправлено")
                    : isInviteBusy
                      ? (lang === "en" ? "Sending..." : "Отправляем...")
                      : (lang === "en" ? "Invite" : "Пригласить");

                return (
                  <div key={f.id} className="invite-follower-item">
                    <div className="follower-avatar-small">
                      {f.avatar && (f.avatar.startsWith("data:image") || f.avatar.startsWith("http")) ? (
                        <img src={f.avatar} alt="Avatar" />
                      ) : (
                        f.avatar ? f.avatar : f.username.charAt(0).toUpperCase()
                      )}
                    </div>
                    <span className="follower-name">{f.username}</span>
                    <button
                      className="follower-invite-btn"
                      disabled={isInviteDisabled}
	                      onClick={async () => {
	                        if (isInviteDisabled) return;
	                        setInviteBusyIds((prev) => (prev.includes(followerId) ? prev : [...prev, followerId]));
	                        try {
	                          const res = await fetch(`${API_URL}/checklists/${savedSlug || id}/invite/${f.id}`, {
                            method: "POST",
                            headers: authHeaders
	                          });
	                          if (res.status === 409) {
	                            setInviteAlreadyIds((prev) => (prev.includes(followerId) ? prev : [...prev, followerId]));
	                            return;
	                          }
                          if (!res.ok) {
                            const data = await readJsonSafely(res);
                            throw new Error(data?.detail || "Invite failed");
                          }
	                          setInviteSentIds((prev) => (prev.includes(followerId) ? prev : [...prev, followerId]));
	                        } catch (err) {
	                          console.error(err);
	                        } finally {
	                          setInviteBusyIds((prev) => prev.filter((id) => id !== followerId));
	                        }
                      }}
                    >
                      {inviteButtonLabel}
                    </button>
                  </div>
                );
              }) : (
                <div className="empty-subscribers" style={{ textAlign: "center", color: "#666", padding: "20px" }}>У вас пока нет подписчиков</div>
              )}
            </div>

            <p className="invite-modal-desc" style={{ marginTop: "25px" }}>Или отправьте им ссылку для присоединения к чеклисту:</p>
            {inviteToken ? (
              <div className="invite-link-box">
                <input
                  type="text"
                  readOnly
                  value={`${window.location.origin}/join/${inviteToken}`}
                  className="invite-input"
                />
                <button
                  className="copy-btn action-btn primary"
                  onClick={() => {
                    navigator.clipboard.writeText(`${window.location.origin}/join/${inviteToken}`);
                    alert("Ссылка скопирована!");
                  }}
                >Копировать</button>
              </div>
            ) : (
              <div className="loading-spinner" style={{ margin: "20px auto" }}></div>
            )}
          </div>
        </div>
      )}

      {/* AI Assistant Chat Widget */}
      {result && (
        <AIChatWidget
          city={result.destinations?.[0]?.city || result.city}
          startDate={result.destinations?.[0]?.start_date || result.start_date}
          endDate={result.destinations?.[result.destinations?.length - 1]?.end_date || result.end_date}
          avgTemp={result.avg_temp}
          tripType={result.trip_type}
          checklistSlug={savedSlug || result.slug}
          token={token}
          onChecklistUpdated={handleChecklistUpdated}
          language={lang}
        />
      )}

      <ConfirmDialog
        open={Boolean(confirmDialog)}
        title={confirmDialog?.title || ""}
        message={confirmDialog?.message || ""}
        confirmLabel={confirmDialog?.confirmLabel || (lang === "en" ? "Confirm" : "Подтвердить")}
        cancelLabel={confirmDialog?.cancelLabel || (lang === "en" ? "Cancel" : "Отмена")}
        tone={confirmDialog?.tone || "default"}
        onConfirm={() => closeConfirmDialog(true)}
        onCancel={() => closeConfirmDialog(false)}
      />
    </>
  );
};

export default App;
