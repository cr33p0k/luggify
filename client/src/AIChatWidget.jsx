import React, { useState, useRef, useEffect } from "react";
import { API_URL } from "./appUtils";

const CHECKLIST_COMMAND_RE = /(?:^|\b)(добав(?:ь|ить|им)?|убер(?:и|ать|ем)?|удал(?:и|ить|им)?|отмет(?:ь|ить|им)?|сними?\s+отметк|перемест(?:и|ить|им)?|перелож(?:и|ить|им)?|перенес(?:и|ти|ем)?|созда(?:й|ть|дим)\s+(?:багаж|чемодан|рюкзак)|rename|add|remove|delete|mark|unmark|move|transfer|create\s+(?:baggage|bag|backpack|carry-on))/i;
const CHECKLIST_CONTINUATION_RE = /^\s*(?:и\s+)?(?:ещ[её]|еще|тоже|also|and)\b/i;
const EXPENSE_COMMAND_RE = /(?:\b(?:бюджет|расход|расходы|траты?|трату|потрат|остат|сэконом|expense|expenses|budget|spent|remaining|save money)\b|\d+(?:[.,]\d+)?\s*(?:₽|руб|рублей|рубля|евро|eur|€|доллар(?:ов|а)?|бакс(?:ов|а)?|usd|[a-zA-Z]{3}|\$)(?=$|\s|[.,;:!?]))/i;
const RESTAURANT_COMMAND_RE = /(?:ресторан|кафе|бар|поесть|позавтрак|пообед|поужин|еда|обед|ужин|завтрак|\b(?:restaurant|cafe|bar|food|lunch|dinner|breakfast)\b)/i;
const FULL_DAY_PLAN_RE = /(?:насыщ|полностью|полный\s+день|целый\s+день|день\s+целиком|распланир(?:уй|овать).{0,32}день|(?:перв|втор|трет|1|2|3).{0,16}день|full\s+day|rich\s+day|whole\s+day|day\s+plan)/i;
const HELP_COMMAND_RE = /^\s*(?:помощь|help|\/help)\s*$/i;
const RESTAURANT_BLOCKLIST_KEY = "luggify_hidden_restaurants_v1";
const AI_CHAT_SESSION_PREFIX = "luggify_ai_chat_session_v1";
const AI_CHAT_SESSION_MAX_MESSAGES = 40;
const CUSTOM_RESTAURANT_CHOICE = "__custom_restaurant__";
const SHOULD_RENDER_DIRECT_ACTION_CARDS = false;

const getHumanFriendlyDate = (dateStr, language = "ru") => {
    if (!dateStr) return "";
    try {
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return dateStr;
        return d.toLocaleDateString(language === "ru" ? "ru-RU" : "en-US", { day: 'numeric', month: 'long' });
    } catch {
        return dateStr;
    }
};

const getBagOwnerName = (bag, tripProfile, language = "ru") => {
    if (!tripProfile || !bag) return "";
    
    // Check if it's a child's bag
    if (bag.child_profile_id) {
        const child = (tripProfile.child_profiles || []).find(c => c.id === bag.child_profile_id);
        if (child) return child.first_name || (language === "ru" ? "Ребёнок" : "Child");
    }
    
    // Check if it's the main user's bag
    if (bag.user_id === tripProfile.user_id) {
        return language === "ru" ? "Мой" : "My";
    }

    // Shared list or fallback
    if (bag.id === "shared") return language === "ru" ? "Общий" : "Shared";

    return "";
};

const AI_EXPENSE_CURRENCIES = ["RUB", "USD", "EUR"];

const AI_EXPENSE_CATEGORIES = [
    { id: "food", ru: "Еда", en: "Food" },
    { id: "transport", ru: "Транспорт", en: "Transport" },
    { id: "tickets", ru: "Билеты", en: "Tickets" },
    { id: "hotel", ru: "Жильё", en: "Accommodation" },
    { id: "entertainment", ru: "Развлечения", en: "Entertainment" },
    { id: "shopping", ru: "Покупки", en: "Shopping" },
    { id: "other", ru: "Другое", en: "Other" },
];

const getAiExpenseCategoryLabel = (category, language = "ru") => {
    const item = AI_EXPENSE_CATEGORIES.find((entry) => entry.id === category);
    return item?.[language] || item?.ru || category || "";
};

const formatRestaurantDistance = (meters, language = "ru") => {
    const value = Number(meters);
    if (!Number.isFinite(value) || value <= 0) return "";
    if (value < 1000) return language === "ru" ? `${Math.round(value)} м` : `${Math.round(value)} m`;
    const km = (value / 1000).toFixed(1);
    return language === "ru" ? `${km} км` : `${km} km`;
};

const getRestaurantDisplayDescription = (description) => {
    const text = String(description || "").trim();
    if (!text) return "";
    if (/^(подходит для|вариант для|good for|lunch option|dinner option)/i.test(text)) return "";
    if (/\b\d+(?:[.,]\d+)?\s*(?:м|км|m|km)\s+(?:от точки|from the point)/i.test(text)) return "";
    if (/формат:|style:|еда:|cuisine:/i.test(text)) return text.replace(/(?:^|\.\s*)(?:формат|style|еда|cuisine):\s*/i, "").trim();
    return text;
};

const getRestaurantBlockKey = (option) => (
    String(option?.option_id || option?.name || "").trim().toLowerCase()
);

const getMealTitlePrefix = (proposal, group, language = "ru") => {
    const base = String(group?.meal_label || proposal?.title || "").split("·")[0].trim();
    const normalized = base.toLowerCase();
    if (/завтрак|breakfast/.test(normalized)) return language === "ru" ? "Завтрак" : "Breakfast";
    if (/обед|lunch/.test(normalized)) return language === "ru" ? "Обед" : "Lunch";
    if (/ужин|dinner/.test(normalized)) return language === "ru" ? "Ужин" : "Dinner";
    return base || (language === "ru" ? "Приём пищи" : "Meal");
};

const loadHiddenRestaurantKeys = () => {
    try {
        const parsed = JSON.parse(localStorage.getItem(RESTAURANT_BLOCKLIST_KEY) || "[]");
        return Array.isArray(parsed) ? parsed.filter(Boolean) : [];
    } catch {
        return [];
    }
};

const saveHiddenRestaurantKeys = (keys) => {
    try {
        localStorage.setItem(RESTAURANT_BLOCKLIST_KEY, JSON.stringify(Array.from(new Set(keys)).slice(-200)));
    } catch {
        // Ignore storage failures; the current chat still hides the card.
    }
};

const buildAiChatSessionKey = (checklistSlug, city, language) => (
    `${AI_CHAT_SESSION_PREFIX}:${checklistSlug || "trip"}:${city || "unknown"}:${language || "ru"}`
);

const loadAiChatSession = (sessionKey) => {
    try {
        const parsed = JSON.parse(sessionStorage.getItem(sessionKey) || "{}");
        return {
            messages: Array.isArray(parsed.messages) ? parsed.messages : [],
            lastCommandContext: parsed.lastCommandContext || null,
        };
    } catch {
        return { messages: [], lastCommandContext: null };
    }
};

const saveAiChatSession = (sessionKey, messages, lastCommandContext) => {
    try {
        const trimmedMessages = (Array.isArray(messages) ? messages : [])
            .slice(-AI_CHAT_SESSION_MAX_MESSAGES);
        sessionStorage.setItem(sessionKey, JSON.stringify({
            messages: trimmedMessages,
            lastCommandContext: lastCommandContext || null,
            updatedAt: Date.now(),
        }));
    } catch {
        // Session storage can be unavailable in private modes.
    }
};

const buildAssistantHelpText = (language = "ru", hasChecklist = false) => {
    if (language === "en") {
        const checklistBlock = hasChecklist
            ? "\n\n**Packing**\nWhat is left to pack?\nAdd water to backpack\nAdd 2 t-shirts per day\nMove all tech to carry-on\nMake the list lighter"
            : "";
        return `**Plan**\nEasy plan for tomorrow\nRich plan for the third day\nPlan without museums\nOptimize route\n\n**Events**\nMove museum to evening\nShift the day one hour later\nCheck time overlaps\n\n**Expenses**\nSet daily limit 50 EUR\nAdd 25 EUR for museum\nSplit 60 EUR dinner by 3\nShow expenses by category\n\n**Food**\nWhere should I eat nearby?\nFind dinner near the last stop\n\n**Weather**\nWhat should I change because of rain?${checklistBlock}`;
    }
    const checklistBlock = hasChecklist
        ? "\n\n**Вещи**\nЧто осталось собрать?\nДобавь воду в рюкзак\nДобавь по 2 футболки на каждый день\nПереложи всю технику в ручную кладь\nСделай список легче"
        : "";
    return `**План**\nЛёгкий план на завтра\nНасыщенный план на третий день\nПлан без музеев\nОптимизируй маршрут\n\n**События**\nПеренеси музей на вечер\nСдвинь весь день на час позже\nПроверь пересечения по времени\n\n**Траты**\nПоставь дневной лимит 50 EUR\nДобавь 25 EUR на музей\nРаздели 60 EUR ужин на троих\nПокажи траты по категориям\n\n**Еда**\nГде поесть рядом?\nНайди ужин рядом с последней точкой\n\n**Погода**\nЧто поменять в плане из-за дождя?${checklistBlock}`;
};

const isFoodPlanProposal = (proposal) => {
    if (String(proposal?.event_type || "").toLowerCase() === "food") return true;
    const title = String(proposal?.title || "").toLowerCase();
    return /^(завтрак|обед|ужин|breakfast|lunch|dinner)\b/.test(title.trim());
};

const shouldKeepFoodProposalInPlan = (question, proposal) => {
    if (!isFoodPlanProposal(proposal)) return true;
    const normalizedQuestion = String(question || "").toLowerCase();
    const foodWasRequested = FULL_DAY_PLAN_RE.test(question) || RESTAURANT_COMMAND_RE.test(question) || /завтрак|обед|ужин|поесть|покушать|еда|breakfast|lunch|dinner|eat|food/i.test(normalizedQuestion);
    if (!foodWasRequested) return false;
    return true;
};

const hasValidCoords = (proposal) => (
    Number.isFinite(Number(proposal?.lat)) && Number.isFinite(Number(proposal?.lng))
);

const getMealLabel = (proposal, language = "ru") => {
    const text = [proposal?.title, proposal?.description, proposal?.reason].join(" ").toLowerCase();
    if (/завтрак|breakfast/.test(text)) return language === "ru" ? "Завтрак" : "Breakfast";
    if (/обед|lunch/.test(text)) return language === "ru" ? "Обед" : "Lunch";
    if (/ужин|dinner/.test(text)) return language === "ru" ? "Ужин" : "Dinner";
    const dayPart = String(proposal?.day_part || "").toLowerCase();
    if (dayPart === "morning") return language === "ru" ? "Завтрак" : "Breakfast";
    if (dayPart === "day" || dayPart === "afternoon") return language === "ru" ? "Обед" : "Lunch";
    if (dayPart === "evening") return language === "ru" ? "Ужин" : "Dinner";
    return language === "ru" ? "Еда" : "Food";
};

const getMealType = (proposal) => {
    const text = [proposal?.title, proposal?.description, proposal?.reason].join(" ").toLowerCase();
    if (/завтрак|breakfast/.test(text)) return "breakfast";
    if (/обед|lunch/.test(text)) return "lunch";
    if (/ужин|dinner/.test(text)) return "dinner";
    const dayPart = String(proposal?.day_part || "").toLowerCase();
    if (dayPart === "morning") return "breakfast";
    if (dayPart === "day" || dayPart === "afternoon") return "lunch";
    if (dayPart === "evening") return "dinner";
    return null;
};

const getMealDefinition = (proposal) => {
    const mealType = getMealType(proposal);
    if (!mealType) return null;
    return MEAL_DEFINITIONS.find((meal) => meal.meal_type === mealType) || null;
};

const normalizePlanProposalForDisplay = (proposal, language = "ru") => {
    if (!isFoodPlanProposal(proposal)) return proposal;
    const mealDefinition = getMealDefinition(proposal);
    if (!mealDefinition) return proposal;
    return {
        ...proposal,
        title: proposal.title || mealDefinition[language] || mealDefinition.ru,
        display_time: null,
        meal_type: mealDefinition.meal_type,
        event_type: proposal?.event_type || "food",
    };
};

const sortPlanProposals = (proposals) => (
    (Array.isArray(proposals) ? proposals : [])
        .slice()
        .sort((first, second) => {
            const firstDate = String(first?.event_date || "");
            const secondDate = String(second?.event_date || "");
            if (firstDate !== secondDate) return firstDate.localeCompare(secondDate);
            return getProposalMinutes(first) - getProposalMinutes(second);
        })
);

const buildTripDateList = (startDate, endDate) => {
    if (!startDate) return [];
    const start = new Date(`${startDate}T00:00:00`);
    const end = endDate ? new Date(`${endDate}T00:00:00`) : start;
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) return [startDate];
    const dates = [];
    const cursor = new Date(start);
    while (cursor <= end && dates.length < 7) {
        dates.push(cursor.toISOString().slice(0, 10));
        cursor.setDate(cursor.getDate() + 1);
    }
    return dates;
};

const shouldUseWholeTripForMeals = (question) => {
    const text = String(question || "").toLowerCase();
    return /кажд(?:ый|ого|ом)\s+день|оба\s+дня|пару\s+дней|два\s+дня|2\s+дня|12\s*(?:и|-|—)\s*13|every\s+day|both\s+days|two\s+days/.test(text);
};

const MEAL_DEFINITIONS = [
    {
        meal_type: "breakfast",
        day_part: "morning",
        time: "09:00",
        display_time_ru: "06:00-12:00",
        display_time_en: "06:00-12:00",
        ru: "Завтрак",
        en: "Breakfast",
    },
    {
        meal_type: "lunch",
        day_part: "day",
        time: "13:00",
        display_time_ru: "12:00-17:00",
        display_time_en: "12:00-17:00",
        ru: "Обед",
        en: "Lunch",
    },
    {
        meal_type: "dinner",
        day_part: "evening",
        time: "19:00",
        display_time_ru: "17:00-00:00",
        display_time_en: "17:00-00:00",
        ru: "Ужин",
        en: "Dinner",
    },
];

const addDaysIso = (startDate, offset) => {
    if (!startDate) return null;
    const date = new Date(`${startDate}T00:00:00`);
    if (Number.isNaN(date.getTime())) return null;
    date.setDate(date.getDate() + offset);
    return date.toISOString().slice(0, 10);
};

const getProposalMinutes = (proposal) => {
    const match = String(proposal?.time || "").match(/^(\d{2}):(\d{2})$/);
    if (match) return (Number(match[1]) * 60) + Number(match[2]);
    const dayPart = String(proposal?.day_part || "").toLowerCase();
    if (dayPart === "morning") return 9 * 60;
    if (dayPart === "evening") return 19 * 60;
    return 13 * 60;
};

const getRequestedMealDates = (question, proposals, startDate, endDate) => {
    const normalizedQuestion = String(question || "").toLowerCase();
    if (shouldUseWholeTripForMeals(question)) {
        const dates = buildTripDateList(startDate, endDate);
        if (dates.length > 0) return dates;
    }

    const ordinalOffsets = [
        { offset: 0, re: /(?:перв(?:ый|ого|ом)|1(?:й|ый)?|first).{0,16}день|day\s*1|first\s+day/i },
        { offset: 1, re: /(?:втор(?:ой|ого|ом)|2(?:й|ой)?|second).{0,16}день|day\s*2|second\s+day/i },
        { offset: 2, re: /(?:трет(?:ий|ьего|ьем)|3(?:й|ий)?|third).{0,16}день|day\s*3|third\s+day/i },
    ];
    const ordinal = ordinalOffsets.find((entry) => entry.re.test(normalizedQuestion));
    if (ordinal && startDate) {
        const date = addDaysIso(startDate, ordinal.offset);
        if (date) return [date];
    }

    const proposalDates = Array.from(new Set(
        (Array.isArray(proposals) ? proposals : [])
            .map((proposal) => proposal?.event_date)
            .filter(Boolean)
    ));
    if (proposalDates.length > 0) return proposalDates.slice(0, 3);

    return [startDate || null];
};

const findMealAnchor = (proposals, eventDate, mealType) => {
    const sameDayStops = (Array.isArray(proposals) ? proposals : [])
        .filter((proposal) => proposal?.event_date === eventDate && hasValidCoords(proposal) && !isFoodPlanProposal(proposal))
        .sort((first, second) => getProposalMinutes(first) - getProposalMinutes(second));
    if (sameDayStops.length === 0) return null;
    if (mealType === "breakfast") return sameDayStops[0];
    if (mealType === "dinner") return sameDayStops[sameDayStops.length - 1];

    const lunchTarget = 13 * 60;
    return sameDayStops
        .slice()
        .sort((first, second) => Math.abs(getProposalMinutes(first) - lunchTarget) - Math.abs(getProposalMinutes(second) - lunchTarget))[0] || sameDayStops[0];
};

const buildRestaurantSearchPayloads = (question, planProposals, language, startDate = null, endDate = null) => {
    const proposals = Array.isArray(planProposals) ? planProposals : [];
    const payloads = [];
    const addPayload = (payload) => {
        const key = `${payload.event_date || ""}|${payload.meal_type || payload.meal_label || ""}`;
        if (payloads.some((existing) => `${existing.event_date || ""}|${existing.meal_type || existing.meal_label || ""}` === key)) return;
        payloads.push(payload);
    };

    proposals.forEach((foodProposal, foodIndex) => {
        if (!isFoodPlanProposal(foodProposal)) return;
        const mealType = getMealType(foodProposal);
        const sameDayBefore = proposals
            .slice(0, foodIndex)
            .reverse()
            .find((proposal) => proposal.event_date === foodProposal.event_date && hasValidCoords(proposal));
        const sameDayAny = proposals.find((proposal) => proposal.event_date === foodProposal.event_date && hasValidCoords(proposal));
        const anchor = sameDayBefore || sameDayAny;
        const basePayload = {
            language,
            event_date: foodProposal.event_date || anchor?.event_date || null,
            time: foodProposal.time || null,
            day_part: foodProposal.day_part || "day",
            meal_type: mealType,
            radius_meters: 1200,
            limit: 5,
            meal_label: getMealLabel(foodProposal, language),
            plan_proposal_id: foodProposal.proposal_id || null,
        };
        if (anchor) {
            addPayload({
                ...basePayload,
                lat: Number(anchor.lat),
                lng: Number(anchor.lng),
            });
        }
    });

    if (FULL_DAY_PLAN_RE.test(question)) {
        const dates = getRequestedMealDates(question, proposals, startDate, endDate);
        dates.forEach((eventDate, dayIndex) => {
            MEAL_DEFINITIONS.forEach((meal) => {
                const anchor = findMealAnchor(proposals, eventDate, meal.meal_type);
                const matchingProposal = proposals.find(p => p.event_date === eventDate && isFoodPlanProposal(p) && getMealType(p) === meal.meal_type);
                addPayload({
                    language,
                    event_date: eventDate,
                    time: meal.time,
                    day_part: meal.day_part,
                    meal_type: meal.meal_type,
                    radius_meters: 1200,
                    limit: 5,
                    meal_label: dates.length > 1 && eventDate
                        ? `${meal[language] || meal.ru} · ${new Date(`${eventDate}T00:00:00`).toLocaleDateString(language === "ru" ? "ru-RU" : "en-US", { day: "numeric", month: "short" })}`
                        : meal[language] || meal.ru,
                    plan_proposal_id: matchingProposal ? matchingProposal.proposal_id : `meal-${dayIndex}-${meal.meal_type}`,
                    ...(anchor ? { lat: Number(anchor.lat), lng: Number(anchor.lng) } : {}),
                });
            });
        });
    }

    if (payloads.length > 0) return payloads.slice(0, 9);

    if (RESTAURANT_COMMAND_RE.test(question)) {
        const normalizedQuestion = String(question || "").toLowerCase();
        const requestedMeals = [];
        if (/завтрак|позавтрак|breakfast/.test(normalizedQuestion)) {
            requestedMeals.push({
                meal_type: "breakfast",
                day_part: "morning",
                time: "09:00",
                meal_label: language === "ru" ? "Завтрак" : "Breakfast",
            });
        }
        if (/обед|пообед|lunch/.test(normalizedQuestion)) {
            requestedMeals.push({
                meal_type: "lunch",
                day_part: "day",
                time: "13:00",
                meal_label: language === "ru" ? "Обед" : "Lunch",
            });
        }
        if (/ужин|поужин|dinner/.test(normalizedQuestion)) {
            requestedMeals.push({
                meal_type: "dinner",
                day_part: "evening",
                time: "19:00",
                meal_label: language === "ru" ? "Ужин" : "Dinner",
            });
        }
        if (requestedMeals.length > 0) {
            const dates = shouldUseWholeTripForMeals(question) ? buildTripDateList(startDate, endDate) : [startDate || null];
            return dates.flatMap((eventDate, dayIndex) => (
                requestedMeals.map((meal) => ({
                    language,
                    event_date: eventDate,
                    radius_meters: 1200,
                    limit: 5,
                    ...meal,
                    meal_label: dates.length > 1 && eventDate
                        ? `${meal.meal_label} · ${new Date(`${eventDate}T00:00:00`).toLocaleDateString(language === "ru" ? "ru-RU" : "en-US", { day: "numeric", month: "short" })}`
                        : meal.meal_label,
                    plan_proposal_id: `meal-${dayIndex}-${meal.meal_type}`,
                }))
            )).slice(0, 6);
        }
        return [{
            language,
            event_date: startDate || null,
            radius_meters: 1200,
            limit: 5,
            meal_label: language === "ru" ? "Места рядом" : "Nearby places",
        }];
    }

    return [];
};

const AIChatDropdown = ({ options, value, onChange, disabled }) => {
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef(null);

    useEffect(() => {
        if (!isOpen) return;
        const handlePointerDown = (event) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        };
        document.addEventListener("mousedown", handlePointerDown);
        document.addEventListener("touchstart", handlePointerDown);
        return () => {
            document.removeEventListener("mousedown", handlePointerDown);
            document.removeEventListener("touchstart", handlePointerDown);
        };
    }, [isOpen]);

    const selectedOption = options.find(o => o.value === value) || options[0] || {};

    return (
        <div className="trip-settings-field" ref={dropdownRef} style={{ width: '100%', opacity: disabled ? 0.5 : 1, pointerEvents: disabled ? 'none' : 'auto', position: 'relative' }}>
            <button
                type="button"
                className={`trip-settings-dropdown-trigger ${isOpen ? "open" : ""}`}
                style={{ minHeight: '40px', padding: '0.45rem 0.8rem', borderRadius: '10px' }}
                onClick={() => setIsOpen(!isOpen)}
                disabled={disabled}
            >
                <span className="trip-settings-dropdown-value" style={{ flex: 1, textAlign: 'left', fontSize: '0.85rem' }}>
                    {selectedOption.label}
                </span>
                <span className="trip-settings-chevron" aria-hidden="true">▾</span>
            </button>
            {isOpen && (
                <div className="trip-settings-dropdown-menu" style={{ width: '100%', zIndex: 10, borderRadius: '10px', marginTop: '4px' }}>
                    {options.map((item) => {
                        const isSelected = value === item.value;
                        return (
                            <button
                                key={item.value}
                                type="button"
                                className={`trip-settings-dropdown-option ${isSelected ? "active" : ""}`}
                                style={{ padding: '0.5rem 0.8rem', fontSize: '0.85rem' }}
                                onClick={() => {
                                    onChange(item.value);
                                    setIsOpen(false);
                                }}
                            >
                                <span className="trip-settings-dropdown-label" style={{ whiteSpace: 'nowrap' }}>{item.label}</span>
                            </button>
                        );
                    })}
                </div>
            )}
        </div>
    );
};

const AIChatPlanBuilder = ({ startDate, endDate, events, language, onCancel, onSubmit }) => {
    const dates = buildTripDateList(startDate, endDate);
    const eventDates = new Set((events || []).map(e => e.event_date).filter(Boolean));
    const defaultDate = dates.find(d => !eventDates.has(d)) || dates[0] || "";
    
    const [selectedDate, setSelectedDate] = useState(defaultDate);
    const [density, setDensity] = useState("сбалансированный");

    const hasEvents = eventDates.has(selectedDate);

    const handleSubmit = () => {
        if (!selectedDate || hasEvents) return;
        const displayDate = getHumanFriendlyDate(selectedDate, language);
        const prompt = language === "ru" 
            ? `Составь ${density} план на ${displayDate} (${selectedDate})`
            : `Create a ${density === "сбалансированный" ? "balanced" : density === "лёгкий" ? "light" : "rich"} plan for ${displayDate} (${selectedDate})`;
        onSubmit(prompt);
    };


    return (
        <div className="ai-plan-card" style={{ width: '100%', maxWidth: '440px', flexDirection: 'column', gap: '8px', marginTop: '8px', padding: '16px', background: 'var(--surface-strong, rgba(255, 255, 255, 0.04))', borderRadius: '14px', border: '1px solid var(--border-subtle, rgba(255, 153, 0, 0.15))' }}>
            <div className="ai-plan-card-title" style={{ fontSize: '0.9rem', marginBottom: '8px' }}>
                {language === "ru" ? "📝 Составить план" : "📝 Create plan"}
            </div>
            
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', flex: '1 1 120px' }}>
                    <label style={{ fontSize: '0.75rem', color: '#9d9d9d', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{language === "ru" ? "Дата" : "Date"}</label>
                    <AIChatDropdown 
                        options={dates.length > 0 ? dates.map(d => ({
                            value: d,
                            label: `${getHumanFriendlyDate(d, language)} ${eventDates.has(d) ? (language === "ru" ? "(уже есть план)" : "(has events)") : ""}`
                        })) : [{ value: "", label: language === "ru" ? "Даты не указаны" : "No dates set" }]}
                        value={selectedDate}
                        onChange={setSelectedDate}
                    />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', flex: '1 1 140px' }}>
                    <label style={{ fontSize: '0.75rem', color: '#9d9d9d', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{language === "ru" ? "Насыщенность" : "Density"}</label>
                    <AIChatDropdown 
                        options={[
                            { value: "лёгкий", label: language === "ru" ? "Лёгкий" : "Light" },
                            { value: "сбалансированный", label: language === "ru" ? "Сбалансированный" : "Balanced" },
                            { value: "насыщенный", label: language === "ru" ? "Насыщенный" : "Rich" }
                        ]}
                        value={density}
                        onChange={setDensity}
                        disabled={hasEvents}
                    />
                </div>
            </div>

            {hasEvents && (
                <div style={{ fontSize: '0.75rem', color: '#ffae42', marginTop: '8px', lineHeight: 1.4 }}>
                    {language === "ru" 
                        ? "На эту дату уже есть план или события. Вы можете задать вопрос ассистенту, чтобы их изменить."
                        : "There are already events for this date. Ask the assistant to modify them."}
                </div>
            )}

            <div style={{ display: 'flex', gap: '8px', marginTop: '12px', justifyContent: 'flex-end' }}>
                <button type="button" className="ai-apply-plan-btn" style={{ background: 'transparent', color: '#b8b8b8', border: '1px solid rgba(255,255,255,0.1)' }} onClick={onCancel}>
                    {language === "ru" ? "Отмена" : "Cancel"}
                </button>
                <button type="button" className="ai-apply-plan-btn" disabled={hasEvents || !selectedDate} onClick={handleSubmit}>
                    {language === "ru" ? "Создать" : "Create"}
                </button>
            </div>
        </div>
    );
};

const AIChatExpenseBuilder = ({ language, onSubmit, onCancel, dates, localCurrency }) => {
    const [title, setTitle] = useState("");
    const [amount, setAmount] = useState("");
    
    const currencyOptions = Array.from(new Set([...AI_EXPENSE_CURRENCIES, localCurrency].filter(Boolean)));
    const [currency, setCurrency] = useState(currencyOptions.includes("RUB") ? "RUB" : currencyOptions[0]);
    const [category, setCategory] = useState("other");
    const [date, setDate] = useState(dates[0] || "");

    const handleSubmit = () => {
        if (!title.trim() || !amount) return;
        const displayDate = getHumanFriendlyDate(date, language);
        const prompt = language === "ru"
            ? `Добавь трату: ${title}, ${amount} ${currency}, категория ${getAiExpenseCategoryLabel(category, "ru")}${date ? ` на ${displayDate} (${date})` : ""}`
            : `Add expense: ${title}, ${amount} ${currency}, category ${getAiExpenseCategoryLabel(category, "en")}${date ? ` on ${displayDate} (${date})` : ""}`;
        onSubmit(prompt);
    };

    return (
        <div className="ai-plan-card" style={{ width: '100%', maxWidth: '440px', flexDirection: 'column', gap: '8px', marginTop: '8px', padding: '16px', background: 'var(--surface-strong, rgba(255, 255, 255, 0.04))', borderRadius: '14px', border: '1px solid var(--border-subtle, rgba(255, 153, 0, 0.15))' }}>
            <div className="ai-plan-card-title" style={{ fontSize: '0.9rem', marginBottom: '8px' }}>
                {language === "ru" ? "💰 Добавить трату" : "💰 Add expense"}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <input
                    className="ai-plan-edit-input ai-plan-edit-input-full"
                    type="text"
                    placeholder={language === "ru" ? "На что потратили?" : "What did you spend on?"}
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                />
                <div style={{ display: 'flex', gap: '8px' }}>
                    <input
                        className="ai-plan-edit-input"
                        style={{ flex: 1 }}
                        type="number"
                        placeholder={language === "ru" ? "Сумма" : "Amount"}
                        value={amount}
                        onChange={(e) => setAmount(e.target.value)}
                    />
                    <div style={{ flex: 1, minWidth: '90px' }}>
                        <AIChatDropdown
                            options={currencyOptions.map(c => ({ value: c, label: c }))}
                            value={currency}
                            onChange={setCurrency}
                        />
                    </div>
                </div>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <div style={{ flex: 1, minWidth: '120px' }}>
                        <AIChatDropdown
                            options={AI_EXPENSE_CATEGORIES.map(c => ({ value: c.id, label: language === "ru" ? c.ru : c.en }))}
                            value={category}
                            onChange={setCategory}
                        />
                    </div>
                    {dates.length > 0 && (
                        <div style={{ flex: 1, minWidth: '120px' }}>
                            <AIChatDropdown
                                options={dates.map(d => ({ value: d, label: getHumanFriendlyDate(d, language) }))}
                                value={date}
                                onChange={setDate}
                            />
                        </div>
                    )}
                </div>
            </div>
            <div style={{ display: 'flex', gap: '8px', marginTop: '12px', justifyContent: 'flex-end' }}>
                <button type="button" className="ai-apply-plan-btn" style={{ background: 'transparent', color: '#b8b8b8', border: '1px solid rgba(255,255,255,0.1)' }} onClick={onCancel}>
                    {language === "ru" ? "Отмена" : "Cancel"}
                </button>
                <button type="button" className="ai-apply-plan-btn" disabled={!title.trim() || !amount} onClick={handleSubmit}>
                    {language === "ru" ? "Добавить" : "Add"}
                </button>
            </div>
        </div>
    );
};

const AIChatPackingBuilder = ({ language, onSubmit, onCancel, backpacks, tripProfile, hiddenSections, isAdmin, currentUserId }) => {
    const [item, setItem] = useState("");
    const [quantity, setQuantity] = useState("1");
    
    // Filter out restricted bags
    const validBags = (backpacks || []).filter(bag => {
        if (isAdmin) return true;
        if (hiddenSections?.includes(`backpack:${bag.id}`)) {
            // If it's my own bag, I should see it even if it's hidden from others
            return bag.user_id === currentUserId;
        }
        return true;
    });

    // Group valid bags by owner
    const ownersMap = new Map();
    
    validBags.forEach(bag => {
        let id, label;
        if (bag.child_profile_id) {
            const child = (tripProfile?.child_profiles || []).find(c => c.id === bag.child_profile_id);
            id = bag.child_profile_id;
            label = child?.name || (language === 'ru' ? 'Ребёнок' : 'Child');
        } else {
            id = bag.user_id;
            if (bag.user_id === currentUserId) {
                label = language === 'ru' ? 'Я' : 'Me';
            } else {
                label = bag.user?.username || `User ${bag.user_id}`;
            }
        }
        
        if (!ownersMap.has(id)) {
            ownersMap.set(id, { id, label, bags: [] });
        }
        ownersMap.get(id).bags.push(bag);
    });

    const owners = Array.from(ownersMap.values());

    const [selectedOwnerId, setSelectedOwnerId] = useState(owners[0]?.id || "");
    
    const ownerBags = (owners.find(o => o.id === selectedOwnerId)?.bags || []);

    const [selectedBagId, setSelectedBagId] = useState(ownerBags[0]?.id || "");

    // Re-select bag if owner changes
    useEffect(() => {
        if (ownerBags.length > 0) {
            setSelectedBagId(ownerBags[0].id);
        } else {
            setSelectedBagId("");
        }
    }, [selectedOwnerId]);

    const handleSubmit = () => {
        if (!item.trim() || !selectedBagId) return;
        const bag = validBags.find(b => b.id === selectedBagId);
        const owner = owners.find(o => o.id === selectedOwnerId);
        const bagBaseName = bag ? (bag.name || (language === "ru" ? "багаж" : "bag")) : (language === "ru" ? "багаж" : "bag");
        const bagName = owner ? `${owner.label} ${bagBaseName}` : bagBaseName;

        const prompt = language === "ru"
            ? `Добавь ${quantity} ${item} в ${bagName}`
            : `Add ${quantity} ${item} to ${bagName}`;
        onSubmit(prompt);
    };

    const getBagLabel = (bag) => {
        if (!bag) return language === "ru" ? "Общий список" : "Shared list";
        const owner = getBagOwnerName(bag, tripProfile, language);
        const name = bag.name || (language === "ru" ? "Багаж" : "Bag");
        return owner ? `${name} (${owner})` : name;
    };

    return (
        <div className="ai-plan-card" style={{ width: '100%', maxWidth: '440px', flexDirection: 'column', gap: '8px', marginTop: '8px', padding: '16px', background: 'var(--surface-strong, rgba(255, 255, 255, 0.04))', borderRadius: '14px', border: '1px solid var(--border-subtle, rgba(255, 153, 0, 0.15))' }}>
            <div className="ai-plan-card-title" style={{ fontSize: '0.9rem', marginBottom: '8px' }}>
                {language === "ru" ? "🎒 Добавить вещь" : "🎒 Add item"}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ display: 'flex', gap: '8px' }}>
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        <input
                            className="ai-plan-edit-input ai-plan-edit-input-full"
                            type="text"
                            placeholder={language === "ru" ? "Что нужно взять?" : "What to pack?"}
                            value={item}
                            onChange={(e) => setItem(e.target.value)}
                        />
                    </div>
                    <div style={{ width: '70px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        <input
                            className="ai-plan-edit-input"
                            style={{ width: '100%', textAlign: 'center' }}
                            type="number"
                            min="1"
                            value={quantity}
                            onChange={(e) => setQuantity(e.target.value)}
                        />
                    </div>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        <label style={{ fontSize: '0.65rem', color: '#9d9d9d', textTransform: 'uppercase' }}>{language === "ru" ? "Пользователь" : "User"}</label>
                        <AIChatDropdown
                            options={owners.map(o => ({ value: o.id, label: o.label }))}
                            value={selectedOwnerId}
                            onChange={setSelectedOwnerId}
                        />
                    </div>
                    {ownerBags.length > 0 && (
                        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
                            <label style={{ fontSize: '0.65rem', color: '#9d9d9d', textTransform: 'uppercase' }}>{language === "ru" ? "Багаж" : "Bag"}</label>
                            <AIChatDropdown
                                options={ownerBags.map(b => ({ value: b.id, label: b.name || (language === "ru" ? "Багаж" : "Bag") }))}
                                value={selectedBagId}
                                onChange={setSelectedBagId}
                                disabled={ownerBags.length <= 1}
                            />
                        </div>
                    )}
                </div>
                {owners.length === 0 && (
                    <div style={{ fontSize: '0.75rem', color: '#ffae42', marginTop: '4px' }}>
                        {language === "ru" ? "У вас пока нет багажа. Сначала создайте чемодан или рюкзак." : "No baggage found. Please create a bag first."}
                    </div>
                )}
            </div>
            <div style={{ display: 'flex', gap: '8px', marginTop: '12px', justifyContent: 'flex-end' }}>
                <button type="button" className="ai-apply-plan-btn" style={{ background: 'transparent', color: '#b8b8b8', border: '1px solid rgba(255,255,255,0.1)' }} onClick={onCancel}>
                    {language === "ru" ? "Отмена" : "Cancel"}
                </button>
                <button type="button" className="ai-apply-plan-btn" disabled={!item.trim() || !selectedBagId} onClick={handleSubmit}>
                    {language === "ru" ? "Добавить" : "Add"}
                </button>
            </div>
        </div>
    );
};

const AIChatEventBuilder = ({ language, onSubmit, onCancel, dates }) => {
    const [title, setTitle] = useState("");
    const [time, setTime] = useState("12:00");
    const [date, setDate] = useState(dates[0] || "");
    const [address, setAddress] = useState("");

    const handleSubmit = () => {
        if (!title.trim() || !date) return;
        const displayDate = getHumanFriendlyDate(date, language);
        const prompt = language === "ru"
            ? `Добавь событие: ${title} на ${displayDate} (${date}) в ${time}${address ? `, адрес: ${address}` : ""}`
            : `Add event: ${title} on ${displayDate} (${date}) at ${time}${address ? `, address: ${address}` : ""}`;
        onSubmit(prompt);
    };

    return (
        <div className="ai-plan-card" style={{ width: '100%', maxWidth: '440px', flexDirection: 'column', gap: '8px', marginTop: '8px', padding: '16px', background: 'var(--surface-strong, rgba(255, 255, 255, 0.04))', borderRadius: '14px', border: '1px solid var(--border-subtle, rgba(255, 153, 0, 0.15))' }}>
            <div className="ai-plan-card-title" style={{ fontSize: '0.9rem', marginBottom: '8px' }}>
                {language === "ru" ? "🗓️ Добавить событие" : "🗓️ Add event"}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <input
                    className="ai-plan-edit-input ai-plan-edit-input-full"
                    type="text"
                    placeholder={language === "ru" ? "Название события" : "Event title"}
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                />
                <div style={{ display: 'flex', gap: '8px' }}>
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        <label style={{ fontSize: '0.65rem', color: '#9d9d9d', textTransform: 'uppercase' }}>{language === "ru" ? "Дата" : "Date"}</label>
                        <AIChatDropdown
                            options={dates.map(d => ({ value: d, label: getHumanFriendlyDate(d, language) }))}
                            value={date}
                            onChange={setDate}
                        />
                    </div>
                    <div style={{ width: '100px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        <label style={{ fontSize: '0.65rem', color: '#9d9d9d', textTransform: 'uppercase' }}>{language === "ru" ? "Время" : "Time"}</label>
                        <input
                            className="ai-plan-edit-input"
                            style={{ width: '100%' }}
                            type="time"
                            value={time}
                            onChange={(e) => setTime(e.target.value)}
                        />
                    </div>
                </div>
                <input
                    className="ai-plan-edit-input ai-plan-edit-input-full"
                    type="text"
                    placeholder={language === "ru" ? "Место или адрес (опционально)" : "Place or address (optional)"}
                    value={address}
                    onChange={(e) => setAddress(e.target.value)}
                />
            </div>
            <div style={{ display: 'flex', gap: '8px', marginTop: '12px', justifyContent: 'flex-end' }}>
                <button type="button" className="ai-apply-plan-btn" style={{ background: 'transparent', color: '#b8b8b8', border: '1px solid rgba(255,255,255,0.1)' }} onClick={onCancel}>
                    {language === "ru" ? "Отмена" : "Cancel"}
                </button>
                <button type="button" className="ai-apply-plan-btn" disabled={!title.trim() || !date} onClick={handleSubmit}>
                    {language === "ru" ? "Добавить" : "Add"}
                </button>
            </div>
        </div>
    );
};

export default function AIChatWidget({
    city,
    startDate,
    endDate,
    avgTemp,
    tripType,
    tripProfile = null,
    checklistSlug = null,
    token = null,
    onChecklistUpdated = null,
    onPlanApplied = null,
    language = "ru",
    isAdmin = false,
    events = [],
    backpacks = [],
    hiddenSections = [],
    localCurrency = null,
    currentUserId = null,
}) {
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [lastCommandContext, setLastCommandContext] = useState(null);
    const [applyingPlanMessageIndex, setApplyingPlanMessageIndex] = useState(null);
    const [applyingChangeMessageIndex, setApplyingChangeMessageIndex] = useState(null);
    const [applyingExpenseMessageIndex, setApplyingExpenseMessageIndex] = useState(null);
    const [applyingPackingMessageIndex, setApplyingPackingMessageIndex] = useState(null);
    const [hiddenRestaurantKeys, setHiddenRestaurantKeys] = useState(() => loadHiddenRestaurantKeys());
    const [openRestaurantDropdownKey, setOpenRestaurantDropdownKey] = useState(null);
    const [isCommandsMenuOpen, setIsCommandsMenuOpen] = useState(false);
    const messagesEndRef = useRef(null);
    const inputRef = useRef(null);
    const lastMessageCountRef = useRef(0);
    const chatSessionKey = buildAiChatSessionKey(checklistSlug, city, language);

    const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};

    const shouldAttemptChecklistCommand = (question) => {
        const normalized = String(question || "").trim();
        if (!normalized || !token || !checklistSlug) return false;
        if (EXPENSE_COMMAND_RE.test(normalized)) return false;
        if (CHECKLIST_COMMAND_RE.test(normalized)) return true;
        if (lastCommandContext && CHECKLIST_CONTINUATION_RE.test(normalized)) return true;
        return false;
    };

    useEffect(() => {
        const savedSession = loadAiChatSession(chatSessionKey);
        if (savedSession.messages.length > 0) {
            setMessages(savedSession.messages);
            setLastCommandContext(savedSession.lastCommandContext);
            return;
        }
        setMessages([{
                role: "ai",
                text: language === "ru" 
                    ? (
                        checklistSlug
                            ? `Привет! Я AI-помощник для поездки в **${city}**. Помогу с планом дня, вещами, едой, погодой и тратами. Напишите **Помощь**, чтобы увидеть примеры.`
                            : `Привет! Я AI-помощник для поездки в **${city}**. Помогу с маршрутом, едой, погодой и городскими советами. Напишите **Помощь**, чтобы увидеть примеры.`
                    )
                    : (
                        checklistSlug
                            ? `Hi! I'm your AI travel assistant for **${city}**. I can help with day plans, packing, food, weather, and expenses. Type **Help** to see examples.`
                            : `Hi! I'm your AI travel assistant for **${city}**. I can help with routes, food, weather, and city tips. Type **Help** to see examples.`
                    )
        }]);
        setLastCommandContext(null);
    }, [chatSessionKey, city, checklistSlug, language]);

    useEffect(() => {
        if (messages.length > 0) {
            saveAiChatSession(chatSessionKey, messages, lastCommandContext);
        }
    }, [chatSessionKey, messages, lastCommandContext]);

    useEffect(() => {
        if (messages.length > lastMessageCountRef.current) {
            messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
        }
        lastMessageCountRef.current = messages.length;
    }, [messages.length]);

    useEffect(() => {
        if (isOpen) {
            inputRef.current?.focus();
        }
    }, [isOpen]);

    useEffect(() => {
        const handleOutsideClick = (e) => {
            if (isCommandsMenuOpen && !e.target.closest('.ai-commands-dropdown-container')) {
                setIsCommandsMenuOpen(false);
            }
        };
        document.addEventListener('mousedown', handleOutsideClick);
        return () => document.removeEventListener('mousedown', handleOutsideClick);
    }, [isCommandsMenuOpen]);

    const clearChat = () => {
        setMessages([{
            role: "ai",
            text: language === "ru"
                ? `Чат очищен. Чем могу помочь?`
                : `Chat cleared. How can I help?`,
        }]);
        setLastCommandContext(null);
        try {
            sessionStorage.removeItem(chatSessionKey);
        } catch {
            // Session storage can fail in restricted browser modes.
        }
    };

    const askTravelQuestion = async (question) => {
        const parseResponse = async (res) => {
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                return {
                    answer: data?.detail || (language === "ru" ? "Ассистент временно недоступен." : "Assistant is temporarily unavailable."),
                    suggestions: [],
                };
            }
            return data;
        };

        if (checklistSlug) {
            const res = await fetch(`${API_URL}/checklists/${checklistSlug}/assistant/ask`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...authHeaders,
                },
                body: JSON.stringify({
                    question,
                    language,
                }),
            });
            return parseResponse(res);
        }

        const res = await fetch(`${API_URL}/ai/ask`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                city,
                question,
                language,
                start_date: startDate || "",
                end_date: endDate || "",
                avg_temp: avgTemp || null,
                trip_type: tripType || "vacation",
                trip_profile: tripProfile || null,
            }),
        });

        return parseResponse(res);
    };

    const normalizeExpenseProposalsForApply = (proposals) => (
        (Array.isArray(proposals) ? proposals : [])
            .map((proposal) => ({
                ...proposal,
                title: (proposal.title || "").trim() || null,
                category: (proposal.category || "other").trim() || "other",
                amount: proposal.amount == null || proposal.amount === "" ? null : Number(proposal.amount),
                budget_amount: proposal.budget_amount == null || proposal.budget_amount === "" ? null : Number(proposal.budget_amount),
                daily_budget_amount: proposal.daily_budget_amount == null || proposal.daily_budget_amount === "" ? null : Number(proposal.daily_budget_amount),
                currency: (proposal.currency || "RUB").trim().toUpperCase(),
                base_currency: proposal.base_currency ? proposal.base_currency.trim().toUpperCase() : null,
                expense_date: proposal.expense_date || null,
                note: (proposal.note || "").trim() || null,
            }))
            .filter((proposal) => (
                proposal.action === "set_budget"
                    ? proposal.budget_amount !== null
                    : proposal.action === "set_daily_budget"
                        ? proposal.daily_budget_amount !== null
                        : proposal.title && proposal.amount !== null
            ))
    );

    const applyExpenseProposalsDirectly = async (proposals) => {
        const selectedProposals = normalizeExpenseProposalsForApply(proposals);
        if (!checklistSlug || !token || selectedProposals.length === 0) return null;
        const res = await fetch(`${API_URL}/checklists/${checklistSlug}/assistant/apply-expenses`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...authHeaders,
            },
            body: JSON.stringify({ proposals: selectedProposals }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            throw new Error(data?.detail || (language === "ru" ? "Не удалось применить траты." : "Could not apply expenses."));
        }
        if (data?.checklist && onChecklistUpdated) {
            onChecklistUpdated(data.checklist);
        }
        return data;
    };

    const askQuestion = async (question) => {
        if (!question.trim() || loading) return;

        const userMsg = { role: "user", text: question };
        setMessages(prev => [...prev, userMsg]);
        setInput("");

        if (HELP_COMMAND_RE.test(question)) {
            setMessages(prev => [...prev, {
                role: "ai",
                text: buildAssistantHelpText(language, Boolean(checklistSlug)),
            }]);
            return;
        }

        setLoading(true);

        try {
            if (shouldAttemptChecklistCommand(question)) {
                try {
                    const commandResponse = await fetch(`${API_URL}/checklists/${checklistSlug}/ai-command`, {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            ...authHeaders,
                        },
                        body: JSON.stringify({
                            command: question,
                            language,
                            command_context: lastCommandContext,
                        }),
                    });

                    if (commandResponse.ok) {
                        const commandData = await commandResponse.json();
                        if (commandData.recognized_action_request) {
                            if (commandData.applied && commandData.checklist && onChecklistUpdated) {
                                onChecklistUpdated(commandData.checklist);
                            }
                            setLastCommandContext(commandData.command_context || null);
                            setMessages(prev => [...prev, {
                                role: "ai",
                                text: commandData.message || (language === "ru" ? "Чеклист обновлён." : "Checklist updated."),
                            }]);
                            setLoading(false);
                            return;
                        }
                    }
                } catch (commandError) {
                    console.error("Checklist AI command failed:", commandError);
                }
            }

            const data = await askTravelQuestion(question);
            let restaurantGroups = [];
            const planProposals = sortPlanProposals(
                (Array.isArray(data.plan_proposals) ? data.plan_proposals : [])
                    .filter((proposal) => shouldKeepFoodProposalInPlan(question, proposal))
                    .map((proposal) => normalizePlanProposalForDisplay(proposal, language))
            );
            const restaurantSearchPayloads = buildRestaurantSearchPayloads(question, planProposals, language, startDate, endDate);
            if (checklistSlug && token && restaurantSearchPayloads.length > 0) {
                const settledGroups = await Promise.all(restaurantSearchPayloads.map(async (payload) => {
                    try {
                        const restaurantRes = await fetch(`${API_URL}/checklists/${checklistSlug}/assistant/restaurant-options`, {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json",
                                ...authHeaders,
                            },
                            body: JSON.stringify(payload),
                        });
                        const restaurantData = await restaurantRes.json().catch(() => ({}));
                        if (!restaurantRes.ok) return null;
                        const hiddenKeys = new Set(loadHiddenRestaurantKeys());
                        return {
                            ...restaurantData,
                            options: Array.isArray(restaurantData.options)
                                ? restaurantData.options.filter((option) => !hiddenKeys.has(getRestaurantBlockKey(option)))
                                : [],
                            meal_label: payload.meal_label,
                            plan_proposal_id: payload.plan_proposal_id || null,
                        };
                    } catch (restaurantError) {
                        console.error("Restaurant options failed:", restaurantError);
                        return null;
                    }
                }));
                restaurantGroups = settledGroups.filter(Boolean);
            }
            const expenseProposals = Array.isArray(data.expense_proposals) ? data.expense_proposals : [];
            const packingRecommendations = Array.isArray(data.packing_recommendations) ? data.packing_recommendations : [];
            let answerText = data.answer || "Не удалось получить ответ";
            if (expenseProposals.length > 0) {
                try {
                    const applyData = await applyExpenseProposalsDirectly(expenseProposals);
                    if (applyData) {
                        answerText = language === "ru"
                            ? `Добавил в траты: ${applyData.applied_count} ${applyData.applied_count === 1 ? "запись" : "записи"}.`
                            : `Added ${applyData.applied_count} expense update${applyData.applied_count === 1 ? "" : "s"}.`;
                    }
                } catch (expenseError) {
                    answerText = expenseError?.message || (language === "ru" ? "Не удалось применить траты." : "Could not apply expenses.");
                }
            }

            setMessages(prev => [...prev, {
                role: "ai",
                text: answerText,
                planProposals,
                selectedProposalIds: planProposals.map((proposal) => proposal.proposal_id),
                appliedProposalIds: [],
                eventChangeProposals: Array.isArray(data.event_change_proposals) ? data.event_change_proposals : [],
                selectedChangeProposalIds: Array.isArray(data.event_change_proposals)
                    ? data.event_change_proposals.map((proposal) => proposal.proposal_id)
                    : [],
                appliedChangeProposalIds: [],
                expenseProposals: [],
                selectedExpenseProposalIds: Array.isArray(data.expense_proposals)
                    ? data.expense_proposals.map((proposal) => proposal.proposal_id)
                    : [],
                appliedExpenseProposalIds: [],
                packingRecommendations: [],
                selectedPackingRecommendationIds: packingRecommendations.length > 0
                    ? packingRecommendations.map((recommendation, index) => recommendation.recommendation_id || recommendation.item || `packing-${index}`)
                    : [],
                appliedPackingRecommendationIds: [],
                dailyBrief: data.daily_brief || null,
                restaurantGroups,
                restaurantOptions: Array.isArray(restaurantGroups[0]?.options) ? restaurantGroups[0].options : [],
                restaurantContext: restaurantGroups[0] || null,
            }]);
            setLastCommandContext(data.command_context || null);
        } catch {
            setMessages(prev => [...prev, {
                role: "ai",
                text: "⚠️ Ошибка соединения. Попробуйте ещё раз."
            }]);
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        askQuestion(input);
    };

    const toggleProposalSelection = (messageIndex, proposalId) => {
        setMessages((prev) => prev.map((message, index) => {
            if (index !== messageIndex) return message;
            const currentSelected = Array.isArray(message.selectedProposalIds) ? message.selectedProposalIds : [];
            const nextSelected = currentSelected.includes(proposalId)
                ? currentSelected.filter((id) => id !== proposalId)
                : [...currentSelected, proposalId];
            return { ...message, selectedProposalIds: nextSelected };
        }));
    };

    const updateProposalDraft = (messageIndex, proposalId, field, value) => {
        setMessages((prev) => prev.map((message, index) => {
            if (index !== messageIndex) return message;
            const nextPlanProposals = (message.planProposals || []).map((proposal) => (
                proposal.proposal_id === proposalId
                    ? { ...proposal, [field]: value }
                    : proposal
            ));
            return { ...message, planProposals: nextPlanProposals };
        }));
    };

    const updateRestaurantSelection = (messageIndex, groupIndex, value) => {
        const key = getRestaurantSkipKey(messageIndex, groupIndex);
        setOpenRestaurantDropdownKey(null);
        setMessages((prev) => prev.map((message, index) => (
            index === messageIndex
                ? {
                    ...message,
                    restaurantSelections: {
                        ...(message.restaurantSelections || {}),
                        [key]: value,
                    },
                }
                : message
        )));
    };

    const resolveRestaurantSelection = (message, messageIndex, group, groupIndex) => {
        const key = getRestaurantSkipKey(messageIndex, groupIndex);
        const availableOptions = (Array.isArray(group?.options) ? group.options : [])
            .filter((option) => !hiddenRestaurantKeys.includes(getRestaurantBlockKey(option)));
        const storedValue = message?.restaurantSelections?.[key];
        const storedOption = availableOptions.find((option) => option.option_id === storedValue) || null;
        const selectedValue = storedValue === CUSTOM_RESTAURANT_CHOICE
            ? CUSTOM_RESTAURANT_CHOICE
            : (storedOption?.option_id || availableOptions[0]?.option_id || CUSTOM_RESTAURANT_CHOICE);
        const selectedOption = selectedValue === CUSTOM_RESTAURANT_CHOICE
            ? null
            : (storedOption || availableOptions[0] || null);
        return { key, selectedValue, selectedOption };
    };

    const buildProposalForApply = (proposal, message, messageIndex) => {
        const groups = (message?.restaurantGroups || [])
            .map((group, groupIndex) => ({ group, groupIndex }))
            .filter(({ group }) => group?.plan_proposal_id && group.plan_proposal_id === proposal.proposal_id);
        const restaurantGroup = groups[0];
        const baseProposal = {
            ...proposal,
            event_date: proposal.event_date,
            time: proposal.time || restaurantGroup?.group?.time || null,
            title: (proposal.title || "").trim(),
            address: (proposal.address || "").trim() || null,
            description: (proposal.description || "").trim() || null,
        };
        if (!restaurantGroup) return baseProposal;

        const { selectedValue, selectedOption } = resolveRestaurantSelection(
            message,
            messageIndex,
            restaurantGroup.group,
            restaurantGroup.groupIndex,
        );
        if (selectedValue === CUSTOM_RESTAURANT_CHOICE || !selectedOption) {
            return {
                ...baseProposal,
                event_type: "food",
                day_part: restaurantGroup.group?.day_part || proposal.day_part || "day",
            };
        }

        const mealPrefix = getMealTitlePrefix(proposal, restaurantGroup.group, language);
        return {
            ...baseProposal,
            time: restaurantGroup.group?.time || baseProposal.time,
            title: `${mealPrefix} в ${selectedOption.name}`.trim(),
            address: selectedOption.address || baseProposal.address,
            description: selectedOption.description || baseProposal.description,
            lat: selectedOption.lat,
            lng: selectedOption.lng,
            place_source: selectedOption.source || "geoapify",
            event_type: "food",
            day_part: restaurantGroup.group?.day_part || proposal.day_part || "day",
            duration_minutes: proposal.duration_minutes || 75,
            travel_buffer_minutes: proposal.travel_buffer_minutes || 15,
        };
    };

    const toggleChangeProposalSelection = (messageIndex, proposalId) => {
        setMessages((prev) => prev.map((message, index) => {
            if (index !== messageIndex) return message;
            const currentSelected = Array.isArray(message.selectedChangeProposalIds) ? message.selectedChangeProposalIds : [];
            const nextSelected = currentSelected.includes(proposalId)
                ? currentSelected.filter((id) => id !== proposalId)
                : [...currentSelected, proposalId];
            return { ...message, selectedChangeProposalIds: nextSelected };
        }));
    };

    const updateChangeProposalDraft = (messageIndex, proposalId, field, value) => {
        setMessages((prev) => prev.map((message, index) => {
            if (index !== messageIndex) return message;
            const nextProposals = (message.eventChangeProposals || []).map((proposal) => (
                proposal.proposal_id === proposalId
                    ? { ...proposal, [field]: value }
                    : proposal
            ));
            return { ...message, eventChangeProposals: nextProposals };
        }));
    };

    const toggleExpenseProposalSelection = (messageIndex, proposalId) => {
        setMessages((prev) => prev.map((message, index) => {
            if (index !== messageIndex) return message;
            const currentSelected = Array.isArray(message.selectedExpenseProposalIds) ? message.selectedExpenseProposalIds : [];
            const nextSelected = currentSelected.includes(proposalId)
                ? currentSelected.filter((id) => id !== proposalId)
                : [...currentSelected, proposalId];
            return { ...message, selectedExpenseProposalIds: nextSelected };
        }));
    };

    const updateExpenseProposalDraft = (messageIndex, proposalId, field, value) => {
        setMessages((prev) => prev.map((message, index) => {
            if (index !== messageIndex) return message;
            const nextProposals = (message.expenseProposals || []).map((proposal) => (
                proposal.proposal_id === proposalId
                    ? { ...proposal, [field]: value }
                    : proposal
            ));
            return { ...message, expenseProposals: nextProposals };
        }));
    };

    const getPackingRecommendationId = (recommendation, index) => (
        recommendation?.recommendation_id || recommendation?.item || `packing-${index}`
    );

    const togglePackingRecommendationSelection = (messageIndex, recommendationId) => {
        setMessages((prev) => prev.map((message, index) => {
            if (index !== messageIndex) return message;
            const currentSelected = Array.isArray(message.selectedPackingRecommendationIds) ? message.selectedPackingRecommendationIds : [];
            const nextSelected = currentSelected.includes(recommendationId)
                ? currentSelected.filter((id) => id !== recommendationId)
                : [...currentSelected, recommendationId];
            return { ...message, selectedPackingRecommendationIds: nextSelected };
        }));
    };

    const updatePackingRecommendationDraft = (messageIndex, recommendationId, field, value) => {
        setMessages((prev) => prev.map((message, index) => {
            if (index !== messageIndex) return message;
            const nextRecommendations = (message.packingRecommendations || []).map((recommendation, recIndex) => (
                getPackingRecommendationId(recommendation, recIndex) === recommendationId
                    ? { ...recommendation, [field]: value }
                    : recommendation
            ));
            return { ...message, packingRecommendations: nextRecommendations };
        }));
    };

    const applySelectedPlanProposals = async (messageIndex) => {
        const message = messages[messageIndex];
        const selectedIds = Array.isArray(message?.selectedProposalIds) ? message.selectedProposalIds : [];
        const selectedProposals = (message?.planProposals || [])
            .filter((proposal) => selectedIds.includes(proposal.proposal_id))
            .map((proposal) => buildProposalForApply(proposal, message, messageIndex))
            .filter((proposal) => proposal.title);
        if (!checklistSlug || !token || selectedProposals.length === 0) return;

        setApplyingPlanMessageIndex(messageIndex);
        try {
            const res = await fetch(`${API_URL}/checklists/${checklistSlug}/assistant/apply-plan`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...authHeaders,
                },
                body: JSON.stringify({
                    proposals: selectedProposals,
                }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                throw new Error(data?.detail || (language === "ru" ? "Не удалось применить план." : "Could not apply the plan."));
            }

            if (data?.checklist && onChecklistUpdated) {
                onChecklistUpdated(data.checklist);
            }
            if (Array.isArray(data?.created_event_ids) && onPlanApplied) {
                onPlanApplied(data.created_event_ids);
            }

            setMessages((prev) => prev.map((currentMessage, index) => {
                if (index !== messageIndex) return currentMessage;
                return {
                    ...currentMessage,
                    appliedProposalIds: [
                        ...(currentMessage.appliedProposalIds || []),
                        ...selectedProposals.map((proposal) => proposal.proposal_id),
                    ],
                    selectedProposalIds: [],
                };
            }));

            setMessages((prev) => [...prev, {
                role: "ai",
                text: language === "ru"
                    ? `Добавил в маршрут ${data.applied_count} ${data.applied_count === 1 ? "событие" : data.applied_count < 5 ? "события" : "событий"}.`
                    : `Added ${data.applied_count} event${data.applied_count === 1 ? "" : "s"} to the itinerary.`,
            }]);
        } catch (error) {
            setMessages((prev) => [...prev, {
                role: "ai",
                text: error?.message || (language === "ru" ? "Не удалось применить выбранные пункты плана." : "Could not apply the selected plan items."),
            }]);
        } finally {
            setApplyingPlanMessageIndex(null);
        }
    };

    const applySelectedEventChanges = async (messageIndex) => {
        const message = messages[messageIndex];
        const selectedIds = Array.isArray(message?.selectedChangeProposalIds) ? message.selectedChangeProposalIds : [];
        const selectedProposals = (message?.eventChangeProposals || [])
            .filter((proposal) => selectedIds.includes(proposal.proposal_id))
            .map((proposal) => ({
                ...proposal,
                event_date: proposal.event_date || null,
                time: proposal.time || null,
                title: (proposal.title || "").trim() || null,
                address: (proposal.address || "").trim() || null,
                description: (proposal.description || "").trim() || null,
                reason: (proposal.reason || "").trim() || null,
            }));
        if (!checklistSlug || !token || selectedProposals.length === 0) return;

        setApplyingChangeMessageIndex(messageIndex);
        try {
            const res = await fetch(`${API_URL}/checklists/${checklistSlug}/assistant/apply-event-changes`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...authHeaders,
                },
                body: JSON.stringify({ proposals: selectedProposals }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                throw new Error(data?.detail || (language === "ru" ? "Не удалось применить изменения маршрута." : "Could not apply itinerary changes."));
            }
            if (data?.checklist && onChecklistUpdated) {
                onChecklistUpdated(data.checklist);
            }
            if (onPlanApplied) {
                onPlanApplied([
                    ...(Array.isArray(data.created_event_ids) ? data.created_event_ids : []),
                    ...(Array.isArray(data.updated_event_ids) ? data.updated_event_ids : []),
                    ...(Array.isArray(data.deleted_event_ids) ? data.deleted_event_ids : []),
                ]);
            }
            setMessages((prev) => prev.map((currentMessage, index) => {
                if (index !== messageIndex) return currentMessage;
                return {
                    ...currentMessage,
                    appliedChangeProposalIds: [
                        ...(currentMessage.appliedChangeProposalIds || []),
                        ...selectedProposals.map((proposal) => proposal.proposal_id),
                    ],
                    selectedChangeProposalIds: [],
                };
            }));
            setMessages((prev) => [...prev, {
                role: "ai",
                text: language === "ru"
                    ? `Применил ${data.applied_count} изменений к маршруту.`
                    : `Applied ${data.applied_count} itinerary changes.`,
            }]);
        } catch (error) {
            setMessages((prev) => [...prev, {
                role: "ai",
                text: error?.message || (language === "ru" ? "Не удалось применить изменения маршрута." : "Could not apply itinerary changes."),
            }]);
        } finally {
            setApplyingChangeMessageIndex(null);
        }
    };

    const applySelectedExpenseProposals = async (messageIndex) => {
        const message = messages[messageIndex];
        const selectedIds = Array.isArray(message?.selectedExpenseProposalIds) ? message.selectedExpenseProposalIds : [];
        const selectedProposals = normalizeExpenseProposalsForApply(
            (message?.expenseProposals || []).filter((proposal) => selectedIds.includes(proposal.proposal_id))
        );
        if (!checklistSlug || !token || selectedProposals.length === 0) return;

        setApplyingExpenseMessageIndex(messageIndex);
        try {
            const res = await fetch(`${API_URL}/checklists/${checklistSlug}/assistant/apply-expenses`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...authHeaders,
                },
                body: JSON.stringify({ proposals: selectedProposals }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                throw new Error(data?.detail || (language === "ru" ? "Не удалось применить траты." : "Could not apply expenses."));
            }
            if (data?.checklist && onChecklistUpdated) {
                onChecklistUpdated(data.checklist);
            }
            setMessages((prev) => prev.map((currentMessage, index) => {
                if (index !== messageIndex) return currentMessage;
                return {
                    ...currentMessage,
                    appliedExpenseProposalIds: [
                        ...(currentMessage.appliedExpenseProposalIds || []),
                        ...selectedProposals.map((proposal) => proposal.proposal_id),
                    ],
                    selectedExpenseProposalIds: [],
                };
            }));
            setMessages((prev) => [...prev, {
                role: "ai",
                text: language === "ru"
                    ? `Применил ${data.applied_count} ${data.applied_count === 1 ? "изменение" : "изменения"} по тратам.`
                    : `Applied ${data.applied_count} expense update${data.applied_count === 1 ? "" : "s"}.`,
            }]);
        } catch (error) {
            setMessages((prev) => [...prev, {
                role: "ai",
                text: error?.message || (language === "ru" ? "Не удалось применить траты." : "Could not apply expenses."),
            }]);
        } finally {
            setApplyingExpenseMessageIndex(null);
        }
    };

    const applySelectedPackingRecommendations = async (messageIndex) => {
        const message = messages[messageIndex];
        const selectedIds = Array.isArray(message?.selectedPackingRecommendationIds) ? message.selectedPackingRecommendationIds : [];
        const selectedRecommendations = (message?.packingRecommendations || [])
            .filter((recommendation, index) => selectedIds.includes(getPackingRecommendationId(recommendation, index)))
            .map((recommendation) => ({
                ...recommendation,
                item: (recommendation.item || "").trim(),
                reason: (recommendation.reason || "").trim() || (language === "ru" ? "Предложено ассистентом" : "Suggested by assistant"),
                target_section: (recommendation.target_section || "").trim() || null,
                quantity: recommendation.quantity == null || recommendation.quantity === "" ? null : Number(recommendation.quantity),
            }))
            .filter((recommendation) => recommendation.item);
        if (!checklistSlug || !token || selectedRecommendations.length === 0) return;

        setApplyingPackingMessageIndex(messageIndex);
        try {
            const res = await fetch(`${API_URL}/checklists/${checklistSlug}/assistant/apply-packing-recommendations`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...authHeaders,
                },
                body: JSON.stringify({
                    recommendations: selectedRecommendations,
                    language,
                }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                throw new Error(data?.detail || (language === "ru" ? "Не удалось применить вещи." : "Could not apply packing changes."));
            }
            if (data?.checklist && onChecklistUpdated) {
                onChecklistUpdated(data.checklist);
            }
            setMessages((prev) => prev.map((currentMessage, index) => {
                if (index !== messageIndex) return currentMessage;
                return {
                    ...currentMessage,
                    appliedPackingRecommendationIds: [
                        ...(currentMessage.appliedPackingRecommendationIds || []),
                        ...selectedRecommendations.map((recommendation, recIndex) => getPackingRecommendationId(recommendation, recIndex)),
                    ],
                    selectedPackingRecommendationIds: [],
                };
            }));
            setMessages((prev) => [...prev, {
                role: "ai",
                text: language === "ru"
                    ? `Применил ${data.applied_count} ${data.applied_count === 1 ? "изменение" : "изменения"} по вещам.`
                    : `Applied ${data.applied_count} packing update${data.applied_count === 1 ? "" : "s"}.`,
            }]);
        } catch (error) {
            setMessages((prev) => [...prev, {
                role: "ai",
                text: error?.message || (language === "ru" ? "Не удалось применить предложения по вещам." : "Could not apply packing suggestions."),
            }]);
        } finally {
            setApplyingPackingMessageIndex(null);
        }
    };

    const getRestaurantSkipKey = (messageIndex, groupIndex) => `${messageIndex}-${groupIndex}`;

    const openRestaurantMap = (event, mapUrl) => {
        if (!mapUrl) return;
        event.preventDefault();
        window.open(mapUrl, "_blank", "noopener,noreferrer");
    };

    const hideRestaurantOption = (messageIndex, option) => {
        const key = getRestaurantBlockKey(option);
        if (!key) return;
        setHiddenRestaurantKeys((current) => {
            const next = Array.from(new Set([...current, key]));
            saveHiddenRestaurantKeys(next);
            return next;
        });
        setMessages((prev) => prev.map((message, index) => {
            if (index !== messageIndex) return message;
            const nextGroups = (message.restaurantGroups || []).map((group) => ({
                ...group,
                options: (group.options || []).filter((item) => getRestaurantBlockKey(item) !== key),
            }));
            const nextContext = message.restaurantContext
                ? {
                    ...message.restaurantContext,
                    options: (message.restaurantContext.options || []).filter((item) => getRestaurantBlockKey(item) !== key),
                }
                : message.restaurantContext;
            return {
                ...message,
                restaurantGroups: nextGroups,
                restaurantContext: nextContext,
                restaurantOptions: (message.restaurantOptions || []).filter((item) => getRestaurantBlockKey(item) !== key),
            };
        }));
    };


    const renderRestaurantGroup = (msg, messageIndex, group, groupIndex, inline = false) => {
        const availableOptions = (Array.isArray(group?.options) ? group.options : [])
            .filter((option) => !hiddenRestaurantKeys.includes(getRestaurantBlockKey(option)));
        if (availableOptions.length === 0 && !group?.message) return null;
        const { selectedValue, selectedOption } = resolveRestaurantSelection(msg, messageIndex, group, groupIndex);
        const selectedDescription = getRestaurantDisplayDescription(selectedOption?.description);
        const isCustom = selectedValue === CUSTOM_RESTAURANT_CHOICE;
        const dropdownKey = getRestaurantSkipKey(messageIndex, groupIndex);
        const dropdownOpen = openRestaurantDropdownKey === dropdownKey;
        const selectedDistance = formatRestaurantDistance(selectedOption?.distance_meters, language);
        const selectedLabel = selectedOption
            ? `${selectedOption.name}${selectedDistance ? ` · ${selectedDistance}` : ""}`
            : (language === "ru" ? "Выберу сам" : "I will choose myself");

        return (
            <div className={inline ? "ai-restaurant-inline" : ""} key={`${group?.meal_label || "places"}-${groupIndex}`}>
                {group?.message && (
                    <div className="ai-restaurant-note">{group.message}</div>
                )}
                {availableOptions.length > 0 && (
                    <div className="ai-restaurant-selector">
                        <div className="ai-restaurant-heading">
                            <strong>{language === "ru" ? "Заведение" : "Place"}</strong>
                            <span>{language === "ru" ? "Выберите вариант для сохранения" : "Choose what to save"}</span>
                        </div>
                        <div className="ai-restaurant-dropdown">
                            <button
                                type="button"
                                className={`ai-restaurant-select-button ${dropdownOpen ? "open" : ""}`}
                                onClick={() => setOpenRestaurantDropdownKey((current) => (
                                    current === dropdownKey ? null : dropdownKey
                                ))}
                            >
                                <span>{selectedValue === availableOptions[0]?.option_id ? `${language === "ru" ? "Лучший: " : "Best: "}${selectedLabel}` : selectedLabel}</span>
                                <span className="ai-restaurant-select-chevron">⌄</span>
                            </button>
                            {dropdownOpen && (
                                <div className="ai-restaurant-menu">
                                    {availableOptions.map((option, optionIndex) => {
                                        const distance = formatRestaurantDistance(option.distance_meters, language);
                                        const isActive = selectedValue === option.option_id;
                                        return (
                                            <button
                                                type="button"
                                                key={option.option_id}
                                                className={`ai-restaurant-menu-item ${isActive ? "active" : ""}`}
                                                onClick={() => updateRestaurantSelection(messageIndex, groupIndex, option.option_id)}
                                            >
                                                <strong>{option.name}</strong>
                                                <span>
                                                    {[optionIndex === 0 ? (language === "ru" ? "Лучший вариант" : "Best option") : option.category, distance]
                                                        .filter(Boolean)
                                                        .join(" · ")}
                                                </span>
                                            </button>
                                        );
                                    })}
                                    <button
                                        type="button"
                                        className={`ai-restaurant-menu-item ${isCustom ? "active" : ""}`}
                                        onClick={() => updateRestaurantSelection(messageIndex, groupIndex, CUSTOM_RESTAURANT_CHOICE)}
                                    >
                                        <strong>{language === "ru" ? "Выберу сам" : "I will choose myself"}</strong>
                                        <span>{language === "ru" ? "Открою поля названия, описания и адреса" : "Show custom name, description, and address fields"}</span>
                                    </button>
                                </div>
                            )}
                        </div>
                        {selectedOption && (
                            <div className="ai-restaurant-selected-summary">
                                <div>
                                    <strong>{selectedOption.name}</strong>
                                    <span>
                                        {[selectedOption.category, formatRestaurantDistance(selectedOption.distance_meters, language)]
                                            .filter(Boolean)
                                            .join(" · ")}
                                    </span>
                                </div>
                                {isAdmin && (
                                    <button
                                        type="button"
                                        className="ai-restaurant-hide"
                                        onClick={() => hideRestaurantOption(messageIndex, selectedOption)}
                                    >
                                        {language === "ru" ? "Не работает" : "Closed"}
                                    </button>
                                )}
                            </div>
                        )}
                        {selectedDescription && (
                            <div className="ai-restaurant-card-description">{selectedDescription}</div>
                        )}
                        {selectedOption?.address && selectedOption?.map_url && (
                            <a
                                href={selectedOption.map_url}
                                target="_blank"
                                rel="noreferrer"
                                className="ai-restaurant-address"
                                onClick={(event) => openRestaurantMap(event, selectedOption.map_url)}
                            >
                                <span>📍</span>
                                {selectedOption.address}
                            </a>
                        )}
                        {isCustom && (
                            <div className="ai-restaurant-custom-note">
                                {language === "ru"
                                    ? "Заполните название, адрес и заметку выше. Сохранится как выбранный приём пищи."
                                    : "Fill in the title, address, and note above. It will be saved as this meal."}
                            </div>
                        )}
                    </div>
                )}
            </div>
        );
    };

    // Floating button
    if (!isOpen) {
        return (
            <button
                className="ai-fab"
                onClick={() => setIsOpen(true)}
                title={language === "ru" ? "AI-помощник" : "AI Assistant"}
            >
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
                <span className="ai-fab-badge">AI</span>
            </button>
        );
    }

    return (
        <div className="ai-chat-overlay">
            <div className="ai-chat-widget">
                {/* Header */}
                <div className="ai-chat-header">
                    <div className="ai-chat-header-info">
                        <div className="ai-chat-avatar">🤖</div>
                        <div>
                            <div className="ai-chat-title">AI-помощник</div>
                            <div className="ai-chat-subtitle">{city}</div>
                        </div>
                    </div>
                    <button className="ai-chat-close" onClick={() => setIsOpen(false)}>×</button>
                </div>

                {/* Messages */}
                <div className="ai-chat-messages">
                    {messages.map((msg, i) => (
                        <div key={i} className={`ai-msg ${msg.role}`}>
                            <div className="ai-msg-content">
                                {msg.isPlanBuilder ? (
                                    <AIChatPlanBuilder
                                        startDate={startDate}
                                        endDate={endDate}
                                        events={events}
                                        language={language}
                                        onCancel={() => {
                                            setMessages(prev => prev.filter((_, idx) => idx !== i));
                                        }}
                                        onSubmit={(prompt) => {
                                            setMessages(prev => prev.filter((_, idx) => idx !== i));
                                            askQuestion(prompt);
                                        }}
                                    />
                                ) : msg.isExpenseBuilder ? (
                                    <AIChatExpenseBuilder
                                        language={language}
                                        localCurrency={localCurrency}
                                        dates={buildTripDateList(startDate, endDate)}
                                        onCancel={() => {
                                            setMessages(prev => prev.filter((_, idx) => idx !== i));
                                        }}
                                        onSubmit={(prompt) => {
                                            setMessages(prev => prev.filter((_, idx) => idx !== i));
                                            askQuestion(prompt);
                                        }}
                                    />
                                ) : msg.isPackingBuilder ? (
                                    <AIChatPackingBuilder
                                        language={language}
                                        backpacks={backpacks}
                                        tripProfile={tripProfile}
                                        hiddenSections={hiddenSections}
                                        isAdmin={isAdmin}
                                        currentUserId={currentUserId}
                                        onCancel={() => {
                                            setMessages(prev => prev.filter((_, idx) => idx !== i));
                                        }}
                                        onSubmit={(prompt) => {
                                            setMessages(prev => prev.filter((_, idx) => idx !== i));
                                            askQuestion(prompt);
                                        }}
                                    />
                                ) : msg.isEventBuilder ? (
                                    <AIChatEventBuilder
                                        language={language}
                                        dates={buildTripDateList(startDate, endDate)}
                                        onCancel={() => {
                                            setMessages(prev => prev.filter((_, idx) => idx !== i));
                                        }}
                                        onSubmit={(prompt) => {
                                            setMessages(prev => prev.filter((_, idx) => idx !== i));
                                            askQuestion(prompt);
                                        }}
                                    />
                                ) : (
                                    <div className="ai-msg-bubble" style={{ whiteSpace: "pre-wrap" }}>
                                        {msg.text.split('**').map((part, j) =>
                                            j % 2 === 0 ? part : <strong key={j}>{part}</strong>
                                        )}
                                    </div>
                                )}
                                {msg.role === "ai" && Array.isArray(msg.planProposals) && msg.planProposals.length > 0 && (
                                    <div className="ai-plan-proposals">
                                        {msg.planProposals.map((proposal) => {
                                            const isSelected = (msg.selectedProposalIds || []).includes(proposal.proposal_id);
                                            const isApplied = (msg.appliedProposalIds || []).includes(proposal.proposal_id);
                                            const proposalRestaurantGroups = (msg.restaurantGroups || [])
                                                .map((group, groupIndex) => ({ group, groupIndex }))
                                                .filter(({ group }) => group?.plan_proposal_id && group.plan_proposal_id === proposal.proposal_id);
                                            const restaurantSelection = proposalRestaurantGroups[0]
                                                ? resolveRestaurantSelection(
                                                    msg,
                                                    i,
                                                    proposalRestaurantGroups[0].group,
                                                    proposalRestaurantGroups[0].groupIndex,
                                                )
                                                : null;
                                            const showDraftFields = isSelected && !isApplied && (
                                                proposalRestaurantGroups.length === 0
                                                || restaurantSelection?.selectedValue === CUSTOM_RESTAURANT_CHOICE
                                            );
                                            return (
                                                <div
                                                    key={proposal.proposal_id}
                                                    className={`ai-plan-card ${isApplied ? "applied" : ""} ${proposalRestaurantGroups.length > 0 ? "meal-choice" : ""}`}
                                                >
                                                    <input
                                                        type="checkbox"
                                                        checked={isApplied || isSelected}
                                                        disabled={isApplied || applyingPlanMessageIndex === i}
                                                        onChange={() => toggleProposalSelection(i, proposal.proposal_id)}
                                                    />
                                                    <div className="ai-plan-card-body">
                                                        <div className="ai-plan-card-head">
                                                            <strong>{proposal.display_time || proposal.time || (language === "ru" ? "Без точного времени" : "Anytime")}</strong>
                                                        </div>
                                                        <div className="ai-plan-card-title">{proposal.title}</div>
                                                        {proposal.address && <div className="ai-plan-card-meta">{proposal.address}</div>}
                                                        {proposal.description && <div className="ai-plan-card-meta">{proposal.description}</div>}
                                                        {showDraftFields && (
                                                            <div className="ai-plan-edit-grid">
                                                                <input
                                                                    className="ai-plan-edit-input"
                                                                    type="text"
                                                                    inputMode="numeric"
                                                                    pattern="[0-9]{2}:[0-9]{2}"
                                                                    placeholder="HH:MM"
                                                                    value={proposal.time || ""}
                                                                    onChange={(event) => {
                                                                        let v = event.target.value.replace(/[^0-9:]/g, "");
                                                                        if (v.length >= 3 && !v.includes(":")) {
                                                                            v = v.slice(0, 2) + ":" + v.slice(2);
                                                                        }
                                                                        updateProposalDraft(i, proposal.proposal_id, "time", v.slice(0, 5));
                                                                    }}
                                                                    style={{ maxWidth: '80px', textAlign: 'center' }}
                                                                />
                                                                <input
                                                                    className="ai-plan-edit-input ai-plan-edit-input-full"
                                                                    type="text"
                                                                    value={proposal.title || ""}
                                                                    placeholder={language === "ru" ? "Название события" : "Event title"}
                                                                    onChange={(event) => updateProposalDraft(i, proposal.proposal_id, "title", event.target.value)}
                                                                />
                                                                <input
                                                                    className="ai-plan-edit-input ai-plan-edit-input-full"
                                                                    type="text"
                                                                    value={proposal.address || ""}
                                                                    placeholder={language === "ru" ? "Место или адрес" : "Place or address"}
                                                                    onChange={(event) => updateProposalDraft(i, proposal.proposal_id, "address", event.target.value)}
                                                                />
                                                                <textarea
                                                                    className="ai-plan-edit-input ai-plan-edit-input-full ai-plan-edit-textarea"
                                                                    rows="3"
                                                                    value={proposal.description || ""}
                                                                    placeholder={language === "ru" ? "Короткая заметка" : "Short note"}
                                                                    onChange={(event) => updateProposalDraft(i, proposal.proposal_id, "description", event.target.value)}
                                                                />
                                                            </div>
                                                        )}
                                                        {proposalRestaurantGroups.length > 0 && (
                                                            <div className="ai-plan-restaurant-slot">
                                                                {proposalRestaurantGroups.map(({ group, groupIndex }) => (
                                                                    renderRestaurantGroup(msg, i, group, groupIndex, true)
                                                                ))}
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            );
                                        })}
                                        {checklistSlug && token && (
                                            <button
                                                className="ai-apply-plan-btn"
                                                disabled={(msg.selectedProposalIds || []).length === 0 || applyingPlanMessageIndex === i}
                                                onClick={() => applySelectedPlanProposals(i)}
                                            >
                                                {applyingPlanMessageIndex === i
                                                    ? (language === "ru" ? "Добавляю..." : "Adding...")
                                                    : (language === "ru" ? "Добавить выбранное в маршрут" : "Add selected to itinerary")}
                                            </button>
                                        )}
                                    </div>
                                )}
                                {msg.role === "ai" && Array.isArray(msg.eventChangeProposals) && msg.eventChangeProposals.length > 0 && (
                                    <div className="ai-plan-proposals">
                                        {msg.eventChangeProposals.map((proposal) => {
                                            const isSelected = (msg.selectedChangeProposalIds || []).includes(proposal.proposal_id);
                                            const isApplied = (msg.appliedChangeProposalIds || []).includes(proposal.proposal_id);
                                            const isDelete = proposal.action === "delete";
                                            return (
                                                <div
                                                    key={proposal.proposal_id}
                                                    className={`ai-plan-card ${isApplied ? "applied" : ""} ${isDelete ? "danger" : ""}`}
                                                >
                                                    <input
                                                        type="checkbox"
                                                        checked={isApplied || isSelected}
                                                        disabled={isApplied || applyingChangeMessageIndex === i}
                                                        onChange={() => toggleChangeProposalSelection(i, proposal.proposal_id)}
                                                    />
                                                    <div className="ai-plan-card-body">
                                                        <div className="ai-plan-card-head">
                                                            <strong>{isDelete ? (language === "ru" ? "Удалить" : "Delete") : (proposal.time || (language === "ru" ? "Обновить" : "Update"))}</strong>
                                                            <span>#{proposal.target_event_id}</span>
                                                        </div>
                                                        <div className="ai-plan-card-title">{proposal.title || (language === "ru" ? "Изменение события" : "Event change")}</div>
                                                        {proposal.reason && <div className="ai-plan-card-meta">{proposal.reason}</div>}
                                                        {isSelected && !isApplied && !isDelete && (
                                                            <div className="ai-plan-edit-grid">
                                                                <input
                                                                    className="ai-plan-edit-input"
                                                                    type="date"
                                                                    value={proposal.event_date || ""}
                                                                    onChange={(event) => updateChangeProposalDraft(i, proposal.proposal_id, "event_date", event.target.value)}
                                                                />
                                                                <input
                                                                    className="ai-plan-edit-input"
                                                                    type="time"
                                                                    value={proposal.time || ""}
                                                                    onChange={(event) => updateChangeProposalDraft(i, proposal.proposal_id, "time", event.target.value)}
                                                                />
                                                                <input
                                                                    className="ai-plan-edit-input ai-plan-edit-input-full"
                                                                    type="text"
                                                                    value={proposal.title || ""}
                                                                    placeholder={language === "ru" ? "Новое название" : "New title"}
                                                                    onChange={(event) => updateChangeProposalDraft(i, proposal.proposal_id, "title", event.target.value)}
                                                                />
                                                                <input
                                                                    className="ai-plan-edit-input ai-plan-edit-input-full"
                                                                    type="text"
                                                                    value={proposal.address || ""}
                                                                    placeholder={language === "ru" ? "Новое место или адрес" : "New place or address"}
                                                                    onChange={(event) => updateChangeProposalDraft(i, proposal.proposal_id, "address", event.target.value)}
                                                                />
                                                                <textarea
                                                                    className="ai-plan-edit-input ai-plan-edit-input-full ai-plan-edit-textarea"
                                                                    rows="3"
                                                                    value={proposal.description || ""}
                                                                    placeholder={language === "ru" ? "Обновлённая заметка" : "Updated note"}
                                                                    onChange={(event) => updateChangeProposalDraft(i, proposal.proposal_id, "description", event.target.value)}
                                                                />
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            );
                                        })}
                                        {checklistSlug && token && (
                                            <button
                                                className="ai-apply-plan-btn"
                                                disabled={(msg.selectedChangeProposalIds || []).length === 0 || applyingChangeMessageIndex === i}
                                                onClick={() => applySelectedEventChanges(i)}
                                            >
                                                {applyingChangeMessageIndex === i
                                                    ? (language === "ru" ? "Применяю..." : "Applying...")
                                                    : (language === "ru" ? "Применить выбранные изменения" : "Apply selected changes")}
                                            </button>
                                        )}
                                    </div>
                                )}
                                {SHOULD_RENDER_DIRECT_ACTION_CARDS && msg.role === "ai" && Array.isArray(msg.expenseProposals) && msg.expenseProposals.length > 0 && (
                                    <div className="ai-plan-proposals">
                                        {msg.expenseProposals.map((proposal) => {
                                            const isSelected = (msg.selectedExpenseProposalIds || []).includes(proposal.proposal_id);
                                            const isApplied = (msg.appliedExpenseProposalIds || []).includes(proposal.proposal_id);
                                            const isBudget = proposal.action === "set_budget";
                                            const isDailyBudget = proposal.action === "set_daily_budget";
                                            return (
                                                <div
                                                    key={proposal.proposal_id}
                                                    className={`ai-plan-card ${isApplied ? "applied" : ""}`}
                                                >
                                                    <input
                                                        type="checkbox"
                                                        checked={isApplied || isSelected}
                                                        disabled={isApplied || applyingExpenseMessageIndex === i}
                                                        onChange={() => toggleExpenseProposalSelection(i, proposal.proposal_id)}
                                                    />
                                                    <div className="ai-plan-card-body">
                                                        <div className="ai-plan-card-head">
                                                            <strong>
                                                                {isBudget
                                                                    ? (language === "ru" ? "Бюджет" : "Budget")
                                                                    : isDailyBudget
                                                                        ? (language === "ru" ? "Дневной лимит" : "Daily limit")
                                                                        : (language === "ru" ? "Трата" : "Expense")}
                                                            </strong>
                                                            <span>{proposal.currency || proposal.base_currency || "RUB"}</span>
                                                        </div>
                                                        <div className="ai-plan-card-title">
                                                            {isBudget
                                                                ? `${language === "ru" ? "Бюджет поездки" : "Trip budget"}: ${proposal.budget_amount ?? ""} ${proposal.base_currency || proposal.currency || "RUB"}`
                                                                : isDailyBudget
                                                                    ? `${language === "ru" ? "Лимит на день" : "Daily limit"}: ${proposal.daily_budget_amount ?? ""} ${proposal.base_currency || proposal.currency || "RUB"}`
                                                                    : `${proposal.title || (language === "ru" ? "Трата" : "Expense")}: ${proposal.amount ?? ""} ${proposal.currency || "RUB"}`}
                                                        </div>
                                                        {!isBudget && !isDailyBudget && proposal.category && <div className="ai-plan-card-meta">{getAiExpenseCategoryLabel(proposal.category, language)}</div>}
                                                        {isSelected && !isApplied && (
                                                            <div className="ai-plan-edit-grid">
                                                                {isBudget || isDailyBudget ? (
                                                                    <>
                                                                        <input
                                                                            className="ai-plan-edit-input"
                                                                            type="number"
                                                                            min="0"
                                                                            value={isDailyBudget ? (proposal.daily_budget_amount ?? "") : (proposal.budget_amount ?? "")}
                                                                            placeholder={isDailyBudget ? (language === "ru" ? "Лимит на день" : "Daily limit") : (language === "ru" ? "Бюджет" : "Budget")}
                                                                            onChange={(event) => updateExpenseProposalDraft(i, proposal.proposal_id, isDailyBudget ? "daily_budget_amount" : "budget_amount", event.target.value)}
                                                                        />
                                                                        <select
                                                                            className="ai-plan-edit-input"
                                                                            value={proposal.base_currency || proposal.currency || "RUB"}
                                                                            onChange={(event) => updateExpenseProposalDraft(i, proposal.proposal_id, "base_currency", event.target.value)}
                                                                        >
                                                                            {AI_EXPENSE_CURRENCIES.map((currency) => <option key={currency} value={currency}>{currency}</option>)}
                                                                        </select>
                                                                    </>
                                                                ) : (
                                                                    <>
                                                                        <input
                                                                            className="ai-plan-edit-input"
                                                                            type="date"
                                                                            value={proposal.expense_date || ""}
                                                                            onChange={(event) => updateExpenseProposalDraft(i, proposal.proposal_id, "expense_date", event.target.value)}
                                                                        />
                                                                        <input
                                                                            className="ai-plan-edit-input"
                                                                            type="number"
                                                                            min="0"
                                                                            value={proposal.amount ?? ""}
                                                                            placeholder={language === "ru" ? "Сумма" : "Amount"}
                                                                            onChange={(event) => updateExpenseProposalDraft(i, proposal.proposal_id, "amount", event.target.value)}
                                                                        />
                                                                        <select
                                                                            className="ai-plan-edit-input"
                                                                            value={proposal.currency || "RUB"}
                                                                            onChange={(event) => updateExpenseProposalDraft(i, proposal.proposal_id, "currency", event.target.value)}
                                                                        >
                                                                            {AI_EXPENSE_CURRENCIES.map((currency) => <option key={currency} value={currency}>{currency}</option>)}
                                                                        </select>
                                                                        <select
                                                                            className="ai-plan-edit-input"
                                                                            value={proposal.category || "other"}
                                                                            onChange={(event) => updateExpenseProposalDraft(i, proposal.proposal_id, "category", event.target.value)}
                                                                        >
                                                                            {AI_EXPENSE_CATEGORIES.map((category) => (
                                                                                <option key={category.id} value={category.id}>{category[language] || category.ru}</option>
                                                                            ))}
                                                                        </select>
                                                                        <input
                                                                            className="ai-plan-edit-input ai-plan-edit-input-full"
                                                                            type="text"
                                                                            value={proposal.title || ""}
                                                                            placeholder={language === "ru" ? "Название траты" : "Expense title"}
                                                                            onChange={(event) => updateExpenseProposalDraft(i, proposal.proposal_id, "title", event.target.value)}
                                                                        />
                                                                        <textarea
                                                                            className="ai-plan-edit-input ai-plan-edit-input-full ai-plan-edit-textarea"
                                                                            rows="2"
                                                                            value={proposal.note || ""}
                                                                            placeholder={language === "ru" ? "Заметка" : "Note"}
                                                                            onChange={(event) => updateExpenseProposalDraft(i, proposal.proposal_id, "note", event.target.value)}
                                                                        />
                                                                    </>
                                                                )}
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            );
                                        })}
                                        {checklistSlug && token && (
                                            <button
                                                className="ai-apply-plan-btn"
                                                disabled={(msg.selectedExpenseProposalIds || []).length === 0 || applyingExpenseMessageIndex === i}
                                                onClick={() => applySelectedExpenseProposals(i)}
                                            >
                                                {applyingExpenseMessageIndex === i
                                                    ? (language === "ru" ? "Применяю..." : "Applying...")
                                                    : (language === "ru" ? "Применить к тратам" : "Apply to expenses")}
                                            </button>
                                        )}
                                    </div>
                                )}
                                {SHOULD_RENDER_DIRECT_ACTION_CARDS && msg.role === "ai" && Array.isArray(msg.packingRecommendations) && msg.packingRecommendations.length > 0 && (
                                    <div className="ai-plan-proposals">
                                        {msg.packingRecommendations.map((recommendation, recommendationIndex) => {
                                            const recommendationId = getPackingRecommendationId(recommendation, recommendationIndex);
                                            const isSelected = (msg.selectedPackingRecommendationIds || []).includes(recommendationId);
                                            const isApplied = (msg.appliedPackingRecommendationIds || []).includes(recommendationId);
                                            const actionLabel = {
                                                add: language === "ru" ? "Добавить" : "Add",
                                                remove: language === "ru" ? "Убрать" : "Remove",
                                                move_to_carry_on: language === "ru" ? "В ручную кладь" : "Move to carry-on",
                                                keep: language === "ru" ? "Оставить" : "Keep",
                                            }[recommendation.suggested_action] || (language === "ru" ? "Вещь" : "Packing");
                                            return (
                                                <div
                                                    key={recommendationId}
                                                    className={`ai-plan-card ${isApplied ? "applied" : ""}`}
                                                >
                                                    <input
                                                        type="checkbox"
                                                        checked={isApplied || isSelected}
                                                        disabled={isApplied || applyingPackingMessageIndex === i}
                                                        onChange={() => togglePackingRecommendationSelection(i, recommendationId)}
                                                    />
                                                    <div className="ai-plan-card-body">
                                                        <div className="ai-plan-card-head">
                                                            <strong>{actionLabel}</strong>
                                                            {recommendation.target_section && <span>{recommendation.target_section}</span>}
                                                        </div>
                                                        <div className="ai-plan-card-title">
                                                            {recommendation.item}
                                                            {recommendation.quantity ? ` × ${recommendation.quantity}` : ""}
                                                        </div>
                                                        {recommendation.reason && <div className="ai-plan-card-meta">{recommendation.reason}</div>}
                                                        {isSelected && !isApplied && (
                                                            <div className="ai-plan-edit-grid">
                                                                <input
                                                                    className="ai-plan-edit-input ai-plan-edit-input-full"
                                                                    type="text"
                                                                    value={recommendation.item || ""}
                                                                    placeholder={language === "ru" ? "Вещь" : "Item"}
                                                                    onChange={(event) => updatePackingRecommendationDraft(i, recommendationId, "item", event.target.value)}
                                                                />
                                                                <input
                                                                    className="ai-plan-edit-input"
                                                                    type="number"
                                                                    min="1"
                                                                    max="99"
                                                                    value={recommendation.quantity ?? ""}
                                                                    placeholder={language === "ru" ? "Количество" : "Quantity"}
                                                                    onChange={(event) => updatePackingRecommendationDraft(i, recommendationId, "quantity", event.target.value)}
                                                                />
                                                                <input
                                                                    className="ai-plan-edit-input"
                                                                    type="text"
                                                                    value={recommendation.target_section || ""}
                                                                    placeholder={language === "ru" ? "Багаж" : "Bag"}
                                                                    onChange={(event) => updatePackingRecommendationDraft(i, recommendationId, "target_section", event.target.value)}
                                                                />
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            );
                                        })}
                                        {checklistSlug && token && (
                                            <button
                                                className="ai-apply-plan-btn"
                                                disabled={(msg.selectedPackingRecommendationIds || []).length === 0 || applyingPackingMessageIndex === i}
                                                onClick={() => applySelectedPackingRecommendations(i)}
                                            >
                                                {applyingPackingMessageIndex === i
                                                    ? (language === "ru" ? "Применяю..." : "Applying...")
                                                    : (language === "ru" ? "Применить к вещам" : "Apply to packing")}
                                            </button>
                                        )}
                                    </div>
                                )}
                                {msg.role === "ai" && (Array.isArray(msg.restaurantGroups) ? msg.restaurantGroups.length > 0 : msg.restaurantContext) && (
                                    (() => {
                                        if (Array.isArray(msg.planProposals) && msg.planProposals.length > 0) {
                                            return null;
                                        }
                                        const groups = Array.isArray(msg.restaurantGroups) && msg.restaurantGroups.length > 0
                                            ? msg.restaurantGroups
                                            : [msg.restaurantContext];
                                        const attachedProposalIds = new Set((msg.planProposals || []).map((proposal) => proposal.proposal_id).filter(Boolean));
                                        const looseGroups = groups
                                            .map((group, groupIndex) => ({ group, groupIndex }))
                                            .filter(({ group }) => !group?.plan_proposal_id || !attachedProposalIds.has(group.plan_proposal_id));
                                        if (looseGroups.length === 0) return null;
                                        return (
                                            <div className="ai-restaurant-proposals">
                                                {looseGroups.map(({ group, groupIndex }) => renderRestaurantGroup(msg, i, group, groupIndex))}
                                            </div>
                                        );
                                    })()
                                )}
                            </div>
                        </div>
                    ))}

                    {loading && (
                        <div className="ai-msg ai">
                            <div className="ai-msg-bubble ai-typing">
                                <span /><span /><span />
                            </div>
                        </div>
                    )}

                    {messages.length === 1 && !loading && (
                        <div className="ai-suggestions-hint" style={{ fontSize: '0.75rem', color: '#888', textAlign: 'center', marginTop: '16px' }}>
                            {language === "ru" ? "Вы можете использовать меню слева от поля ввода для готовых команд." : "You can use the menu on the left of the input for quick commands."}
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>

                {/* Input */}

                <form className="ai-chat-input-area" onSubmit={handleSubmit}>
                    <div className="ai-commands-dropdown-container" style={{ position: 'relative' }}>
                        <button
                            type="button"
                            className="ai-commands-toggle-btn"
                            onClick={() => setIsCommandsMenuOpen(!isCommandsMenuOpen)}
                            title={language === "ru" ? "Готовые команды" : "Quick commands"}
                        >
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <circle cx="12" cy="12" r="10"></circle>
                                <path d="M12 16v-4"></path>
                                <path d="M12 8h.01"></path>
                            </svg>
                        </button>
                        
                        {isCommandsMenuOpen && (
                            <div className="ai-commands-menu-popup">
                                {[
                                    { label: language === "ru" ? "Составить план" : "Create plan", action: "PLAN_BUILDER" },
                                    { label: language === "ru" ? "Вещи" : "Packing", action: "PACKING_BUILDER" },
                                    { label: language === "ru" ? "Траты" : "Expenses", action: "EXPENSE_BUILDER" },
                                    { label: language === "ru" ? "События" : "Events", action: "EVENT_BUILDER" },
                                ].map((action) => (
                                    <button
                                        key={action.label}
                                        type="button"
                                        className="ai-command-menu-item"
                                        disabled={loading}
                                        onClick={() => {
                                            setIsCommandsMenuOpen(false);
                                            if (action.action === "PLAN_BUILDER") {
                                                setMessages(prev => [...prev, { role: "ai", isPlanBuilder: true }]);
                                            } else if (action.action === "PACKING_BUILDER") {
                                                setMessages(prev => [...prev, { role: "ai", isPackingBuilder: true }]);
                                            } else if (action.action === "EXPENSE_BUILDER") {
                                                setMessages(prev => [...prev, { role: "ai", isExpenseBuilder: true }]);
                                            } else if (action.action === "EVENT_BUILDER") {
                                                setMessages(prev => [...prev, { role: "ai", isEventBuilder: true }]);
                                            } else {
                                                askQuestion(action.prompt);
                                            }
                                        }}
                                    >
                                        {action.label}
                                    </button>
                                ))}
                                <div style={{ borderTop: '1px solid var(--border-subtle, rgba(255,153,0,0.12))', margin: '4px 0' }} />
                                <button
                                    type="button"
                                    className="ai-command-menu-item"
                                    onClick={() => { setIsCommandsMenuOpen(false); clearChat(); }}
                                >
                                    {language === "ru" ? "Очистить чат" : "Clear chat"}
                                </button>
                            </div>
                        )}
                    </div>
                    <input
                        ref={inputRef}
                        className="ai-chat-input"
                        type="text"
                        placeholder={
                            checklistSlug
                                ? (language === "ru" ? "Ваш вопрос..." : "Your question...")
                                : (language === "ru" ? "Ваш вопрос..." : "Your question...")
                        }
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        disabled={loading}
                    />
                    <button
                        className="ai-chat-send"
                        type="submit"
                        disabled={!input.trim() || loading}
                    >
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                        </svg>
                    </button>
                </form>
            </div>
        </div>
    );
}
