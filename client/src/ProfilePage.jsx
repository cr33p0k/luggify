import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./ProfilePage.css";
import { TRANSLATIONS, pluralize, pluralizeWord } from "./i18n";
import { EyeIcon, LockIcon, UnlockIcon, ListIcon, TrophyIcon, BarChartIcon, CheckCircleIcon, XCricleIcon, SparkleIcon, EditIcon } from "./Icons";
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const RANK_TIERS = [
    { id: "novice", icon: "🌱", name_ru: "Новичок", name_en: "Novice", min: 0 },
    { id: "scout", icon: "🧭", name_ru: "Разведчик", name_en: "Scout", min: 140 },
    { id: "traveler", icon: "✈️", name_ru: "Путешественник", name_en: "Traveler", min: 320 },
    { id: "navigator", icon: "🗺️", name_ru: "Навигатор", name_en: "Navigator", min: 580 },
    { id: "pilgrim", icon: "🌍", name_ru: "Пилигрим", name_en: "Pilgrim", min: 900 },
    { id: "trailblazer", icon: "🏔️", name_ru: "Первопроходец", name_en: "Trailblazer", min: 1300 },
    { id: "legend", icon: "👑", name_ru: "Легенда", name_en: "Legend", min: 1700 },
];

const safeParseJson = (value, fallback = null) => {
    if (!value) return fallback;
    try {
        return JSON.parse(value);
    } catch {
        return fallback;
    }
};

const PROFILE_BUNDLE_CACHE_TTL_MS = 2000;
const AVATAR_MAX_SIZE = 1600;
const AVATAR_JPEG_QUALITY = 0.96;
const profileBundleRequestCache = new Map();

const fetchProfileBundleCached = async ({ token, username, failedToLoadChecklists }) => {
    const cacheKey = `${token}:${username || "__self__"}`;
    const now = Date.now();
    const cached = profileBundleRequestCache.get(cacheKey);

    if (cached?.promise) {
        return cached.promise;
    }

    if (cached && now - cached.timestamp < PROFILE_BUNDLE_CACHE_TTL_MS) {
        return cached.data;
    }

    const promise = (async () => {
        const headers = { Authorization: `Bearer ${token}` };

        const resCl = await fetch(`${API_URL}/my-checklists`, { headers });
        if (resCl.status === 401) {
            return { unauthorized: true };
        }
        if (!resCl.ok) {
            throw new Error(failedToLoadChecklists);
        }

        const data = {
            checklists: await resCl.json(),
            stats: null,
            achievements: null,
            feedback: null,
            reviews: [],
            followers: [],
            following: [],
            followRequests: [],
        };

        const resStats = await fetch(`${API_URL}/my-stats`, { headers });
        if (resStats.ok) data.stats = await resStats.json();

        const resAch = await fetch(`${API_URL}/my-achievements`, { headers });
        if (resAch.ok) data.achievements = await resAch.json();

        const resFb = await fetch(`${API_URL}/my-feedback-stats`, { headers });
        if (resFb.ok) data.feedback = await resFb.json();

        const resReviews = await fetch(`${API_URL}/my-trip-reviews`, { headers });
        if (resReviews.ok) data.reviews = await resReviews.json();

        if (username) {
            const resFollowers = await fetch(`${API_URL}/users/${username}/followers`, { headers });
            if (resFollowers.ok) data.followers = await resFollowers.json();

            const resFollowing = await fetch(`${API_URL}/users/${username}/following`, { headers });
            if (resFollowing.ok) data.following = await resFollowing.json();

            const resRequests = await fetch(`${API_URL}/follow-requests`, { headers });
            if (resRequests.ok) data.followRequests = await resRequests.json();
        }

        profileBundleRequestCache.set(cacheKey, {
            data,
            timestamp: Date.now(),
            promise: null,
        });

        return data;
    })().catch((error) => {
        profileBundleRequestCache.delete(cacheKey);
        throw error;
    });

    profileBundleRequestCache.set(cacheKey, {
        data: cached?.data || null,
        timestamp: cached?.timestamp || 0,
        promise,
    });

    return promise;
};

const getCountNoun = (count, key, lang) => {
    const forms = {
        checklists: { ru: ["чеклист", "чеклиста", "чеклистов"], en: ["list", "lists"] },
        followers: { ru: ["подписчик", "подписчика", "подписчиков"], en: ["follower", "followers"] },
        following: { ru: ["подписка", "подписки", "подписок"], en: ["following", "following"] },
        trips: { ru: ["поездка", "поездки", "поездок"], en: ["trip", "trips"] },
        countries: { ru: ["страна", "страны", "стран"], en: ["country", "countries"] },
        cities: { ru: ["город", "города", "городов"], en: ["city", "cities"] },
        days: { ru: ["день", "дня", "дней"], en: ["day", "days"] },
        items: { ru: ["вещь", "вещи", "вещей"], en: ["item", "items"] },
    };
    const value = forms[key];
    if (!value) return "";
    return pluralizeWord(count, value.ru, value.en, lang);
};

const renderSocialIcon = (network) => {
    switch(network) {
        case 'instagram': return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line></svg>;
        case 'telegram': return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>;
        case 'twitter': return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 4s-.7 2.1-2 3.4c1.6 10-9.4 17.3-18 11.6 2.2.1 4.4-.6 6-2C3 15.5.5 9.6 3 5c2.2 2.6 5.6 4.1 9 4-.9-4.2 4-6.6 7-3.8 1.1 0 3-1.2 3-1.2z"></path></svg>;
        case 'linkedin': return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"></path><rect x="2" y="9" width="4" height="12"></rect><circle cx="4" cy="4" r="2"></circle></svg>;
        case 'website': return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>;
        default: return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>;
    }
};

const getSocialHref = (network, link) => {
    if (link.startsWith('http')) return link;
    if (network === 'telegram') return `https://t.me/${link.replace('@','')}`;
    if (network === 'instagram') return `https://instagram.com/${link.replace('@','')}`;
    return `https://${link}`;
};

const getSocialLabel = (network) => {
    const labels = {
        instagram: "Instagram",
        telegram: "Telegram",
        twitter: "Twitter",
        linkedin: "LinkedIn",
        website: "Website",
    };
    return labels[network] || network;
};

const ProfilePage = ({ user, token, onLogout, onUpdateUser, lang = "ru" }) => {
    const t = TRANSLATIONS[lang] || TRANSLATIONS.ru;
    const navigate = useNavigate();
    const [checklists, setChecklists] = useState([]);
    const [reviews, setReviews] = useState([]);
    const [stats, setStats] = useState(null);
    const [achievements, setAchievements] = useState(null);
    const [feedback, setFeedback] = useState(null);
    const [followers, setFollowers] = useState([]);
    const [following, setFollowing] = useState([]);
    const [followRequests, setFollowRequests] = useState([]);
    const [isStatsPublic, setIsStatsPublic] = useState(user?.is_stats_public ?? true);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [activeTab, setActiveTab] = useState("checklists"); // "checklists" | "reviews" | "achievements" | "followers" | "following"
    const [avatar, setAvatar] = useState(user?.avatar || "");
    const [editMode, setEditMode] = useState(false);
    const [bio, setBio] = useState(user?.bio || "");
    const [socialLinks, setSocialLinks] = useState(user?.social_links || {});
    const [saving, setSaving] = useState(false);
    const [isAvatarModalOpen, setIsAvatarModalOpen] = useState(false);
    const [showRankModal, setShowRankModal] = useState(false);
    const [isSocialMenuOpen, setIsSocialMenuOpen] = useState(false);
    const [profileInviteTarget, setProfileInviteTarget] = useState(null);
    const [profileInviteBusySlug, setProfileInviteBusySlug] = useState("");
    const [profileInviteSentSlugs, setProfileInviteSentSlugs] = useState([]);
    const [profileInviteError, setProfileInviteError] = useState("");
    const socialMenuRef = React.useRef(null);
    const bioInputRef = React.useRef(null);
    
    // Check if the current viewer is the owner of this profile
    const currentUserStr = window.localStorage.getItem('user');
    const currentUser = safeParseJson(currentUserStr, null);
    const profileUsername = user?.username || "";
    const isOwner = user && currentUser && user.username === currentUser.username;

    const resizeBioTextarea = (element) => {
        if (!element) return;
        element.style.height = "auto";
        element.style.height = `${Math.min(element.scrollHeight, 150)}px`;
    };

    useEffect(() => {
        if (!token) return;
        let isCancelled = false;

        const fetchData = async () => {
            try {
                const bundle = await fetchProfileBundleCached({
                    token,
                    username: profileUsername,
                    failedToLoadChecklists: t.failedToLoadChecklists,
                });

                if (isCancelled) return;

                if (bundle?.unauthorized) {
                    onLogout();
                    return;
                }

                setChecklists(bundle.checklists || []);
                setStats(bundle.stats);
                setAchievements(bundle.achievements);
                setFeedback(bundle.feedback);
                setReviews(bundle.reviews || []);
                setFollowers(bundle.followers || []);
                setFollowing(bundle.following || []);
                setFollowRequests(bundle.followRequests || []);
            } catch (e) {
                console.error(e);
                if (!isCancelled) {
                    setError(e.message);
                }
            } finally {
                if (!isCancelled) {
                    setLoading(false);
                }
            }
        };
        fetchData();

        return () => {
            isCancelled = true;
        };
    }, [token, profileUsername, onLogout, t.failedToLoadChecklists]);

    useEffect(() => {
        setAvatar(user?.avatar || "");
        setBio(user?.bio || "");
        setSocialLinks(user?.social_links || {});
        setIsStatsPublic(user?.is_stats_public ?? true);
        setIsSocialMenuOpen(false);
    }, [user]);

    useEffect(() => {
        if (!isSocialMenuOpen) return undefined;

        const handlePointerDown = (event) => {
            if (socialMenuRef.current && !socialMenuRef.current.contains(event.target)) {
                setIsSocialMenuOpen(false);
            }
        };

        const handleKeyDown = (event) => {
            if (event.key === "Escape") {
                setIsSocialMenuOpen(false);
            }
        };

        document.addEventListener("pointerdown", handlePointerDown);
        window.addEventListener("keydown", handleKeyDown);
        return () => {
            document.removeEventListener("pointerdown", handlePointerDown);
            window.removeEventListener("keydown", handleKeyDown);
        };
    }, [isSocialMenuOpen]);

    useEffect(() => {
        if (!editMode) return undefined;

        const frameId = window.requestAnimationFrame(() => {
            resizeBioTextarea(bioInputRef.current);
        });

        const handleKeyDown = (event) => {
            if (event.key === "Escape" && !saving) {
                setEditMode(false);
                setBio(user?.bio || "");
                setSocialLinks(user?.social_links || {});
                setIsStatsPublic(user?.is_stats_public ?? true);
            }
        };

        window.addEventListener("keydown", handleKeyDown);
        return () => {
            window.cancelAnimationFrame(frameId);
            window.removeEventListener("keydown", handleKeyDown);
        };
    }, [editMode, bio, saving, user]);

    const formatDate = (iso) => {
        const d = new Date(iso);
        return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.${d.getFullYear()}`;
    };

    const openEditModal = () => {
        setBio(user?.bio || "");
        setSocialLinks(user?.social_links || {});
        setIsStatsPublic(user?.is_stats_public ?? true);
        setEditMode(true);
    };

    const closeEditModal = () => {
        if (saving) return;
        setEditMode(false);
        setBio(user?.bio || "");
        setSocialLinks(user?.social_links || {});
        setIsStatsPublic(user?.is_stats_public ?? true);
    };

    const deleteChecklist = async (e, slug) => {
        e.stopPropagation();
        if (!window.confirm(t.deleteChecklistPrompt)) return;
        try {
            const res = await fetch(`${API_URL}/checklist/${slug}`, {
                method: "DELETE",
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                setChecklists((prev) => prev.filter((c) => c.slug !== slug));
            }
        } catch (e) {
            console.error(e);
        }
    };

    const toggleChecklistPrivacy = async (e, slug, current) => {
        e.stopPropagation();
        try {
            const res = await fetch(`${API_URL}/checklist/${slug}/privacy`, {
                method: "PATCH",
                headers: {
                    Authorization: `Bearer ${token}`,
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ is_public: !current }),
            });
            if (res.ok) {
                setChecklists((prev) =>
                    prev.map((c) =>
                        c.slug === slug ? { ...c, is_public: !current } : c
                    )
                );
            }
        } catch (e) {
            console.error(e);
        }
    };


    const handleSaveProfile = async () => {
        setSaving(true);
        try {
            const res = await fetch(`${API_URL}/auth/me`, {
                method: "PATCH",
                headers: {
                    Authorization: `Bearer ${token}`,
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ bio, social_links: socialLinks, is_stats_public: isStatsPublic }),
            });
            if (res.ok) {
                const updatedUser = await res.json();
                if (onUpdateUser) {
                    onUpdateUser(updatedUser);
                }
                setEditMode(false);
            } else {
                console.error("Failed to update profile");
            }
        } catch (e) {
            console.error(e);
        } finally {
            setSaving(false);
        }
    };

    const fileInputRef = React.useRef(null);

    const handleAvatarClick = () => {
        if (editMode) {
            if (fileInputRef.current) fileInputRef.current.click();
        } else if (avatar && (avatar.startsWith("data:image") || avatar.startsWith("http"))) {
            setIsAvatarModalOpen(true);
        }
    };

    const handleFileChange = (e) => {
        const file = e.target.files?.[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (ev) => {
            const originalDataUrl = typeof ev.target.result === "string" ? ev.target.result : "";
            const img = new Image();
            img.onload = async () => {
                let width = img.width;
                let height = img.height;
                const shouldResize = width > AVATAR_MAX_SIZE || height > AVATAR_MAX_SIZE;
                let dataUrl = originalDataUrl;

                if (shouldResize) {
                    const canvas = document.createElement("canvas");

                    if (width > height) {
                        if (width > AVATAR_MAX_SIZE) {
                            height *= AVATAR_MAX_SIZE / width;
                            width = AVATAR_MAX_SIZE;
                        }
                    } else if (height > AVATAR_MAX_SIZE) {
                        width *= AVATAR_MAX_SIZE / height;
                        height = AVATAR_MAX_SIZE;
                    }

                    canvas.width = Math.round(width);
                    canvas.height = Math.round(height);
                    const ctx = canvas.getContext("2d");

                    if (!ctx) return;

                    ctx.imageSmoothingEnabled = true;
                    ctx.imageSmoothingQuality = "high";
                    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

                    const outputType = file.type === "image/png" ? "image/png" : "image/jpeg";
                    dataUrl = outputType === "image/png"
                        ? canvas.toDataURL(outputType)
                        : canvas.toDataURL(outputType, AVATAR_JPEG_QUALITY);
                }

                try {
                    const res = await fetch(`${API_URL}/auth/avatar`, {
                        method: "PATCH",
                        headers: {
                            Authorization: `Bearer ${token}`,
                            "Content-Type": "application/json",
                        },
                        body: JSON.stringify({ avatar: dataUrl }),
                    });
                    if (res.ok) {
                        setAvatar(dataUrl);
                        if (onUpdateUser) {
                            onUpdateUser({ ...user, avatar: dataUrl });
                        }
                    }
                } catch (err) {
                    console.error(err);
                }
            };
            img.src = ev.target.result;
        };
        reader.readAsDataURL(file);
    };

    const refreshSocialLists = async () => {
        let nextFollowers = followers;
        let nextFollowing = following;

        const resFollowers = await fetch(`${API_URL}/users/${user.username}/followers`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        if (resFollowers.ok) {
            nextFollowers = await resFollowers.json();
            setFollowers(nextFollowers);
        }

        const resFollowing = await fetch(`${API_URL}/users/${user.username}/following`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        if (resFollowing.ok) {
            nextFollowing = await resFollowing.json();
            setFollowing(nextFollowing);
        }

        if (onUpdateUser) {
            onUpdateUser({
                ...user,
                followers_count: nextFollowers.length,
                following_count: nextFollowing.length,
            });
        }

        return { nextFollowers, nextFollowing };
    };

    const handleFollowToggle = async (targetUsername, currentIsFollowing) => {
        try {
            const method = currentIsFollowing ? "DELETE" : "POST";
            const res = await fetch(`${API_URL}/users/${targetUsername}/follow`, {
                method,
                headers: { Authorization: `Bearer ${token}` }
            });
            if (res.ok) {
                await refreshSocialLists();
            }
        } catch (e) {
            console.error(e);
        }
    };

    const handleRemoveFollower = async (targetUsername) => {
        try {
            const res = await fetch(`${API_URL}/users/${user.username}/followers/${targetUsername}`, {
                method: "DELETE",
                headers: { Authorization: `Bearer ${token}` }
            });
            if (res.ok) {
                await refreshSocialLists();
            }
        } catch (e) {
            console.error(e);
        }
    };

    const getSubscriptionMeta = (person, mode) => {
        if (person?.bio) return person.bio;
        if (mode === "followers") {
            return person?.is_following ? t.mutualFollow : t.followsYou;
        }
        return t.youFollow;
    };

    const openProfileInviteModal = (person) => {
        setProfileInviteTarget(person);
        setProfileInviteBusySlug("");
        setProfileInviteSentSlugs([]);
        setProfileInviteError("");
    };

    const closeProfileInviteModal = () => {
        if (profileInviteBusySlug) return;
        setProfileInviteTarget(null);
        setProfileInviteBusySlug("");
        setProfileInviteSentSlugs([]);
        setProfileInviteError("");
    };

    const isUserInChecklist = (checklist, targetUserId) => {
        if (!checklist || !targetUserId) return false;
        if (checklist.user_id === targetUserId) return true;
        return (checklist.backpacks || []).some((backpack) => backpack.user_id === targetUserId);
    };

    const inviteableChecklists = checklists.filter((checklist) => checklist.user_id === user?.id);

    const handleInviteUserToChecklist = async (checklist) => {
        if (!profileInviteTarget?.id || !checklist?.slug) return;
        setProfileInviteBusySlug(checklist.slug);
        setProfileInviteError("");
        try {
            const res = await fetch(`${API_URL}/checklists/${checklist.slug}/invite/${profileInviteTarget.id}`, {
                method: "POST",
                headers: { Authorization: `Bearer ${token}` },
            });

            if (res.ok) {
                setProfileInviteSentSlugs((prev) => (prev.includes(checklist.slug) ? prev : [...prev, checklist.slug]));
                setChecklists((prev) => prev.map((item) => (
                    item.slug === checklist.slug
                        ? {
                            ...item,
                            backpacks: isUserInChecklist(item, profileInviteTarget.id)
                                ? (item.backpacks || [])
                                : [
                                    ...(item.backpacks || []),
                                    { user_id: profileInviteTarget.id },
                                ],
                        }
                        : item
                )));
                return;
            }

            if (res.status === 409) {
                setProfileInviteSentSlugs((prev) => (prev.includes(checklist.slug) ? prev : [...prev, checklist.slug]));
                setChecklists((prev) => prev.map((item) => (
                    item.slug === checklist.slug
                        ? {
                            ...item,
                            backpacks: isUserInChecklist(item, profileInviteTarget.id)
                                ? (item.backpacks || [])
                                : [
                                    ...(item.backpacks || []),
                                    { user_id: profileInviteTarget.id },
                                ],
                        }
                        : item
                )));
                return;
            }

            const data = await res.json().catch(() => null);
            setProfileInviteError(data?.detail || t.errorServer);
        } catch (e) {
            console.error(e);
            setProfileInviteError(t.errorServer);
        } finally {
            setProfileInviteBusySlug("");
        }
    };

    const profileStatsCards = [
        {
            key: "checklists",
            count: checklists.length,
            label: getCountNoun(checklists.length, "checklists", lang),
            onClick: () => setActiveTab("checklists"),
        },
        {
            key: "followers",
            count: followers.length,
            label: getCountNoun(followers.length, "followers", lang),
            onClick: () => setActiveTab("followers"),
        },
        {
            key: "following",
            count: following.length,
            label: getCountNoun(following.length, "following", lang),
            onClick: () => setActiveTab("following"),
        },
    ];

    const followerCount = followers.length;
    const publicChecklistCount = checklists.filter((item) => item.is_public).length;
    const collaborativeChecklistCount = checklists.filter((item) => (item.backpacks || []).length > 0).length;
    const reviewWithPhotoCount = reviews.filter((item) => item.photo).length;

    const pointsBreakdown = [
        {
            id: "checklists",
            label: lang === "en" ? "Created checklists" : "Созданные чеклисты",
            details: `${checklists.length} × 35`,
            points: checklists.length * 35,
        },
        {
            id: "public",
            label: lang === "en" ? "Public checklists" : "Публичные чеклисты",
            details: `${publicChecklistCount} × 10`,
            points: publicChecklistCount * 10,
        },
        {
            id: "reviews",
            label: lang === "en" ? "Trip reviews" : "Отзывы о поездках",
            details: `${reviews.length} × 45`,
            points: reviews.length * 45,
        },
        {
            id: "review-photos",
            label: lang === "en" ? "Review photos" : "Фото в отзывах",
            details: `${reviewWithPhotoCount} × 20`,
            points: reviewWithPhotoCount * 20,
        },
        {
            id: "days",
            label: lang === "en" ? "Travel days" : "Дни в поездках",
            details: `${stats?.total_days || 0} × 3`,
            points: (stats?.total_days || 0) * 3,
        },
        {
            id: "countries",
            label: lang === "en" ? "Visited countries" : "Посещённые страны",
            details: `${stats?.unique_countries || 0} × 18`,
            points: (stats?.unique_countries || 0) * 18,
        },
        {
            id: "cities",
            label: lang === "en" ? "Visited cities" : "Посещённые города",
            details: `${stats?.unique_cities || 0} × 8`,
            points: (stats?.unique_cities || 0) * 8,
        },
        {
            id: "collab",
            label: lang === "en" ? "Shared checklists" : "Совместные чеклисты",
            details: `${collaborativeChecklistCount} × 12`,
            points: collaborativeChecklistCount * 12,
        },
        {
            id: "followers",
            label: lang === "en" ? "Followers" : "Подписчики",
            details: `${followerCount} × 6`,
            points: followerCount * 6,
        },
    ];

    const upcomingPointSources = [
        {
            id: "flight",
            label: lang === "en" ? "Flight booked via app link" : "Покупка билетов по ссылке из приложения",
            reward: "+120",
        },
        {
            id: "hotel",
            label: lang === "en" ? "Hotel booking via app link" : "Бронирование жилья по ссылке из приложения",
            reward: "+180",
        },
        {
            id: "esim",
            label: lang === "en" ? "eSIM purchase via app" : "Покупка eSIM через приложение",
            reward: "+90",
        },
    ];

    const currentRankPoints = pointsBreakdown.reduce((sum, item) => sum + item.points, 0);
    const currentRank = RANK_TIERS.reduce((best, tier) => (
        currentRankPoints >= tier.min ? tier : best
    ), RANK_TIERS[0]);
    const currentRankIndex = RANK_TIERS.findIndex((item) => item.id === currentRank.id);
    const nextRank = currentRankIndex >= 0 ? RANK_TIERS[currentRankIndex + 1] : null;
    const pointsToNextRank = nextRank ? Math.max(nextRank.min - currentRankPoints, 0) : 0;
    const rankProgress = nextRank
        ? Math.min(100, Math.max(0, ((currentRankPoints - currentRank.min) / (nextRank.min - currentRank.min)) * 100))
        : 100;

    const travelStatsCards = stats ? [
        { key: "trips", value: stats.total_trips, label: getCountNoun(stats.total_trips, "trips", lang) },
        { key: "countries", value: stats.unique_countries, label: getCountNoun(stats.unique_countries, "countries", lang) },
        { key: "cities", value: stats.unique_cities, label: getCountNoun(stats.unique_cities, "cities", lang) },
        { key: "days", value: stats.total_days, label: getCountNoun(stats.total_days, "days", lang) },
        { key: "items", value: stats.total_items || 0, label: getCountNoun(stats.total_items || 0, "items", lang) },
    ] : [];
    const isProfileLockedForViewer = !isOwner && !isStatsPublic;
    const visibleSocialLinks = Object.entries(user?.social_links || {}).filter(([, link]) => Boolean(link));
    const primarySocialLinks = visibleSocialLinks.slice(0, 3);
    const hiddenSocialLinks = visibleSocialLinks.slice(3);
    const profileStatsInline = (
        <div className="profile-stats-inline">
            {profileStatsCards.map((item) => (
                <button
                    key={item.key}
                    type="button"
                    className="profile-stat-chip"
                    onClick={item.onClick}
                >
                    <span className="profile-stat-chip-value">{item.count}</span>
                    <span className="profile-stat-chip-label">{item.label}</span>
                </button>
            ))}
        </div>
    );

    return (
        <div className="profile-page">
            <div className="profile-header">
                <div className="profile-main-row profile-main-row-compact">
                    <input
                        type="file"
                        accept="image/*"
                        ref={fileInputRef}
                        style={{ display: "none" }}
                        onChange={handleFileChange}
                    />
                    {!editMode && (
                        <div className="profile-corner-actions">
                            <span className={`profile-visibility-chip ${isStatsPublic ? "public" : "private"}`}>
                                {isStatsPublic ? (lang === "en" ? "Public profile" : "Открытый профиль") : (lang === "en" ? "Private profile" : "Закрытый профиль")}
                            </span>
                            <span
                                className={`profile-corner-status-icon ${isStatsPublic ? "public" : "private"}`}
                                title={isStatsPublic ? (lang === "en" ? "Public profile" : "Открытый профиль") : (lang === "en" ? "Private profile" : "Закрытый профиль")}
                                aria-label={isStatsPublic ? (lang === "en" ? "Public profile" : "Открытый профиль") : (lang === "en" ? "Private profile" : "Закрытый профиль")}
                            >
                                {isStatsPublic ? (
                                    <UnlockIcon style={{ width: "14px", height: "14px", marginRight: 0 }} />
                                ) : (
                                    <LockIcon style={{ width: "14px", height: "14px", marginRight: 0 }} />
                                )}
                            </span>
                            {isOwner && (
                                <button
                                    type="button"
                                    className="profile-settings-icon-button profile-settings-corner-button"
                                    onClick={openEditModal}
                                    title={t.editProfile}
                                    aria-label={t.editProfile}
                                >
                                    <EditIcon style={{ display: "block", marginRight: 0 }} />
                                </button>
                            )}
                        </div>
                    )}
                    <div className="profile-avatar-rail">
                        <div className="profile-avatar-frame">
                            <div className="profile-avatar" onClick={handleAvatarClick} title={editMode ? t.uploadAvatar : ""} style={{ cursor: 'pointer' }}>
                                {avatar && (avatar.startsWith("data:image") || avatar.startsWith("http")) ? (
                                    <img src={avatar} alt="Avatar" className="profile-avatar-image" />
                                ) : (
                                    avatar ? avatar : user.username.charAt(0).toUpperCase()
                                )}
                            </div>
                            {!editMode && (
                                <span
                                    className={`profile-avatar-status-icon ${isStatsPublic ? "public" : "private"}`}
                                    title={isStatsPublic ? (lang === "en" ? "Public profile" : "Открытый профиль") : (lang === "en" ? "Private profile" : "Закрытый профиль")}
                                    aria-label={isStatsPublic ? (lang === "en" ? "Public profile" : "Открытый профиль") : (lang === "en" ? "Private profile" : "Закрытый профиль")}
                                >
                                    {isStatsPublic ? (
                                        <UnlockIcon style={{ width: "12px", height: "12px", marginRight: 0 }} />
                                    ) : (
                                        <LockIcon style={{ width: "12px", height: "12px", marginRight: 0 }} />
                                    )}
                                </span>
                            )}
                        </div>
                        {!editMode && !isProfileLockedForViewer && visibleSocialLinks.length > 0 && (
                            <div className="profile-avatar-socials">
                                {primarySocialLinks.map(([net, link]) => {
                                    const href = getSocialHref(net, link);
                                    return (
                                        <a key={net} href={href} target="_blank" rel="noopener noreferrer" className={`social-badge ${net}`} title={getSocialLabel(net)}>
                                            {renderSocialIcon(net)}
                                        </a>
                                    );
                                })}
                                {hiddenSocialLinks.length > 0 && (
                                    <div className="profile-social-more" ref={socialMenuRef}>
                                        <button
                                            type="button"
                                            className="social-badge profile-social-more-button"
                                            onClick={() => setIsSocialMenuOpen((open) => !open)}
                                            aria-expanded={isSocialMenuOpen}
                                            aria-label={lang === "en" ? "Show more social links" : "Показать остальные соцсети"}
                                        >
                                            +{hiddenSocialLinks.length}
                                        </button>
                                        {isSocialMenuOpen && (
                                            <div className="profile-social-dropdown">
                                                {hiddenSocialLinks.map(([net, link]) => (
                                                    <a
                                                        key={net}
                                                        href={getSocialHref(net, link)}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className={`profile-social-dropdown-link ${net}`}
                                                        onClick={() => setIsSocialMenuOpen(false)}
                                                    >
                                                        {renderSocialIcon(net)}
                                                        <span>{getSocialLabel(net)}</span>
                                                    </a>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>

                    <div className="profile-info-block">
                        <div className="profile-name-row">
                            <div className="profile-identity-block">
                                <div className="profile-title-strip">
                                    <div className="profile-name-heading">
                                        <h2>{user.username}</h2>
                                        <span
                                            className={`profile-name-status-icon ${isStatsPublic ? "public" : "private"}`}
                                            title={isStatsPublic ? (lang === "en" ? "Public profile" : "Открытый профиль") : (lang === "en" ? "Private profile" : "Закрытый профиль")}
                                            aria-label={isStatsPublic ? (lang === "en" ? "Public profile" : "Открытый профиль") : (lang === "en" ? "Private profile" : "Закрытый профиль")}
                                        >
                                            {isStatsPublic ? (
                                                <UnlockIcon style={{ width: "14px", height: "14px", marginRight: 0 }} />
                                            ) : (
                                                <LockIcon style={{ width: "14px", height: "14px", marginRight: 0 }} />
                                            )}
                                        </span>
                                    </div>
                                    <button
                                        type="button"
                                        className="level-badge level-badge-button"
                                        onClick={() => setShowRankModal(true)}
                                    >
                                        {currentRank.icon} {lang === 'en' ? currentRank.name_en : currentRank.name_ru}
                                    </button>
                                </div>

                                <div className={`profile-details-view ${!isProfileLockedForViewer ? "profile-details-view-desktop" : ""}`}>
                                    {isProfileLockedForViewer ? (
                                        <div className="private-profile-notice" style={{marginTop: "1rem", color: "#888", display: "flex", alignItems: "center", gap: "0.5rem"}}>
                                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
                                            <span>{lang === 'en' ? 'This profile is private' : 'Это закрытый профиль'}</span>
                                        </div>
                                    ) : (
                                        <>
                                            {user?.bio && <p className="profile-bio profile-bio-desktop">{user.bio}</p>}
                                        </>
                                    )}
                                </div>
                                {(isOwner || isStatsPublic) && (
                                    <div className="profile-stats-panel profile-stats-panel-mobile">
                                        {profileStatsInline}
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    {(isOwner || isStatsPublic) && (
                        <div className="profile-stats-panel profile-stats-panel-desktop">
                            {profileStatsInline}
                        </div>
                    )}
                    {!isProfileLockedForViewer && user?.bio && (
                        <p className="profile-bio profile-bio-mobile">{user.bio}</p>
                    )}
                </div>

                {(isOwner || isStatsPublic) && travelStatsCards.length > 0 && (
                    <div className="profile-hero-metrics">
                        {travelStatsCards.map((item) => (
                            <div key={item.key} className="profile-hero-metric" data-metric-key={item.key}>
                                <span className="profile-hero-metric-value">{item.value}</span>
                                <span className="profile-hero-metric-label">{item.label}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {editMode && (
                <div className="modal-overlay profile-edit-modal-overlay" onClick={closeEditModal}>
                    <div className="modal-content profile-edit-modal" onClick={(e) => e.stopPropagation()}>
                        <button className="modal-close" onClick={closeEditModal}>×</button>

                        <div className="profile-edit-modal-header">
                            <h3>{t.editProfile}</h3>
                        </div>

                        <button
                            type="button"
                            className="profile-edit-avatar-button"
                            onClick={handleAvatarClick}
                            title={t.uploadAvatar}
                        >
                            <div className="profile-edit-avatar-preview">
                                {avatar && (avatar.startsWith("data:image") || avatar.startsWith("http")) ? (
                                    <img src={avatar} alt="Avatar" className="profile-avatar-image" />
                                ) : (
                                    avatar ? avatar : user.username.charAt(0).toUpperCase()
                                )}
                            </div>
                            <div className="profile-edit-avatar-copy">
                                <strong>{t.uploadAvatar}</strong>
                                <span>
                                    {lang === "en"
                                        ? "Tap to choose a new photo"
                                        : "Нажмите, чтобы выбрать новую фотографию"}
                                </span>
                            </div>
                        </button>

                        <div className="profile-edit-form profile-edit-form-modal">
                            <label className="edit-label">{t.bio}</label>
                            <textarea 
                                ref={bioInputRef}
                                className="edit-input bio-input" 
                                value={bio} 
                                onChange={e => {
                                    setBio(e.target.value);
                                    resizeBioTextarea(e.target);
                                }} 
                                rows={2}
                                placeholder="..."
                            />

                            <label className="edit-label">{t.socialLinks}</label>
                            <div className="social-inputs">
                                {['instagram', 'telegram', 'twitter', 'linkedin', 'website'].map(net => (
                                    <div key={net} className="social-input-wrapper">
                                        <div className="social-input-icon">{renderSocialIcon(net)}</div>
                                        <input 
                                            className="edit-input social-input" 
                                            type="text" 
                                            placeholder={`${net} id`} 
                                            value={socialLinks[net] || ""} 
                                            onChange={e => setSocialLinks({...socialLinks, [net]: e.target.value})}
                                        />
                                    </div>
                                ))}
                            </div>

                            <label className="profile-visibility-toggle">
                                <input
                                    type="checkbox"
                                    checked={!isStatsPublic}
                                    onChange={(e) => setIsStatsPublic(!e.target.checked)}
                                />
                                <span>
                                    {lang === "en"
                                        ? "Private profile"
                                        : "Закрытый профиль"}
                                </span>
                            </label>

                            <div className="edit-actions">
                                <button className="btn-secondary" onClick={closeEditModal}>
                                    {t.cancelEdit}
                                </button>
                                <button className="btn-primary" onClick={handleSaveProfile} disabled={saving}>
                                    {saving ? '...' : t.saveProfile}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {showRankModal && (
                <div className="modal-overlay rank-modal-overlay" onClick={() => setShowRankModal(false)}>
                    <div className="modal-content rank-modal" onClick={(e) => e.stopPropagation()}>
                        <button className="modal-close" onClick={() => setShowRankModal(false)}>×</button>

                        <div className="rank-modal-header">
                            <div className="rank-modal-current">
                                <div className="rank-modal-chip">
                                    <span>{currentRank.icon}</span>
                                    <strong>{lang === 'en' ? currentRank.name_en : currentRank.name_ru}</strong>
                                </div>
                                <div className="rank-modal-points">
                                    <span>{lang === 'en' ? 'Your XP' : 'Ваш опыт'}</span>
                                    <strong>{currentRankPoints}</strong>
                                </div>
                            </div>

                            <div className="rank-modal-progress">
                                <div className="rank-modal-progress-copy">
                                    <strong>
                                        {nextRank
                                            ? (lang === 'en'
                                                ? `${pointsToNextRank} pts to ${nextRank.name_en}`
                                                : `${pointsToNextRank} баллов до ранга «${nextRank.name_ru}»`)
                                            : (lang === 'en' ? 'Maximum rank reached' : 'Максимальный ранг достигнут')}
                                    </strong>
                                    <span>
                                        {lang === 'en'
                                            ? 'Points come from trips, reviews and activity inside the app.'
                                            : 'Баллы начисляются за поездки, отзывы и активность внутри приложения.'}
                                    </span>
                                </div>
                                <div className="rank-modal-progressbar">
                                    <span style={{ width: `${rankProgress}%` }} />
                                </div>
                            </div>
                        </div>

                        <div className="rank-modal-grid">
                            <section className="rank-modal-card">
                                <h4>{lang === 'en' ? 'Rank ladder' : 'Лестница рангов'}</h4>
                                <div className="rank-tier-list">
                                    {RANK_TIERS.map((tier, index) => {
                                        const nextTier = RANK_TIERS[index + 1];
                                        const isActive = tier.id === currentRank.id;
                                        return (
                                            <div key={tier.id} className={`rank-tier-item ${isActive ? 'active' : ''}`}>
                                                <div className="rank-tier-icon">{tier.icon}</div>
                                                <div className="rank-tier-copy">
                                                    <strong>{lang === 'en' ? tier.name_en : tier.name_ru}</strong>
                                                    <span>
                                                        {nextTier
                                                            ? `${tier.min}–${nextTier.min - 1}`
                                                            : `${tier.min}+`}
                                                    </span>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </section>

                            <section className="rank-modal-card">
                                <h4>{lang === 'en' ? 'How points are earned' : 'Как начисляются баллы'}</h4>
                                <div className="rank-points-list">
                                    {pointsBreakdown.map((item) => (
                                        <div key={item.id} className={`rank-points-item ${item.points === 0 ? 'muted' : ''}`}>
                                            <div>
                                                <strong>{item.label}</strong>
                                                <span>{item.details}</span>
                                            </div>
                                            <b>+{item.points}</b>
                                        </div>
                                    ))}
                                </div>
                            </section>
                        </div>

                        <section className="rank-modal-card rank-modal-card-wide">
                            <h4>{lang === 'en' ? 'Soon to be added' : 'Скоро добавим'}</h4>
                            <div className="rank-future-list">
                                {upcomingPointSources.map((item) => (
                                    <div key={item.id} className="rank-future-item">
                                        <span>{item.label}</span>
                                        <strong>{item.reward}</strong>
                                    </div>
                                ))}
                            </div>
                        </section>
                    </div>
                </div>
            )}

            {/* Tabs Navigation */}
            {(isOwner || isStatsPublic) && (
                <div className="profile-tabs">
                    <button
                        className={`profile-tab ${activeTab === "checklists" ? "active" : ""}`}
                        onClick={() => setActiveTab("checklists")}
                    >
                        <span style={{display:'flex',alignItems:'center',justifyContent:'center'}}><ListIcon style={{width:'18px',height:'18px',marginRight:'6px'}}/> {t.profileChecklists}</span>
                    </button>
                    <button
                        className={`profile-tab ${activeTab === "reviews" ? "active" : ""}`}
                        onClick={() => setActiveTab("reviews")}
                    >
                        <span style={{display:'flex',alignItems:'center',justifyContent:'center'}}>★ {lang === 'en' ? 'Reviews' : 'Отзывы'}</span>
                    </button>
                    <button
                        className={`profile-tab ${activeTab === "achievements" ? "active" : ""}`}
                        onClick={() => setActiveTab("achievements")}
                    >
                        <span style={{display:'flex',alignItems:'center',justifyContent:'center'}}><TrophyIcon style={{width:'18px',height:'18px',marginRight:'6px'}}/> {t.profileAchievementsAndStats}</span>
                    </button>
                    <button
                        className={`profile-tab ${activeTab === "followers" ? "active" : ""}`}
                        onClick={() => setActiveTab("followers")}
                    >
                        {t.followersTab}
                    </button>
                    <button
                        className={`profile-tab ${activeTab === "following" ? "active" : ""}`}
                        onClick={() => setActiveTab("following")}
                    >
                        {t.followingTab}
                    </button>
                </div>
            )}

            {/* Achievements & Feedback Tab */}
            {(isOwner || isStatsPublic) && activeTab === "achievements" && (
                <div className="tab-content animations-fade">
                    {achievements && (
                        <div className="achievements-section">
                            <h3 className="profile-section-title">
                                {t.myAchievements}
                                <span className="achievement-counter">{achievements.unlocked_count}/{achievements.achievements.length}</span>
                            </h3>
                            <div className="achievements-grid">
                                {achievements.achievements.map((a) => (
                                    <div key={a.id} className={`achievement-card ${a.unlocked ? "unlocked" : "locked"}`}>
                                        <div className="achievement-icon">{a.icon}</div>
                                        <div className="achievement-name">{lang === 'en' ? a.name_en : a.name_ru}</div>
                                        <div className="achievement-desc">{lang === 'en' ? a.desc_en : a.desc_ru}</div>
                                        <div className="achievement-progress-bar">
                                            <div
                                                className="achievement-progress-fill"
                                                style={{ width: `${a.progress * 100}%` }}
                                            />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {feedback && (feedback.top_removed.length > 0 || feedback.top_added.length > 0) && (
                        <div className="feedback-section">
                            <h3 className="profile-section-title" style={{display:'flex',alignItems:'center'}}><BarChartIcon /> {t.yourPreferences}</h3>
                            <div className="feedback-columns">
                                {feedback.top_added.length > 0 && (
                                    <div className="feedback-col">
                                        <h4 style={{display:'flex',alignItems:'center'}}><CheckCircleIcon style={{color:'var(--success)',width:'18px',height:'18px',marginRight:'6px'}}/> {t.frequentlyAdded}</h4>
                                        {feedback.top_added.map((item, i) => (
                                            <div key={i} className="feedback-item added">
                                                <span>{item.item}</span>
                                                <span className="feedback-count">×{item.count}</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                                {feedback.top_removed.length > 0 && (
                                    <div className="feedback-col">
                                        <h4 style={{display:'flex',alignItems:'center'}}><XCricleIcon style={{color:'var(--error)',width:'18px',height:'18px',marginRight:'6px'}}/> {t.frequentlyRemoved}</h4>
                                        {feedback.top_removed.map((item, i) => (
                                            <div key={i} className="feedback-item removed">
                                                <span>{item.item}</span>
                                                <span className="feedback-count">×{item.count}</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Checklists Tab */}
            {(isOwner || isStatsPublic) && activeTab === "checklists" && (
                <div className="tab-content animations-fade">
                    {loading && <div className="profile-loading">{t.loadingStr}</div>}
                    {error && <div className="profile-error">{error}</div>}

                    {!loading && !error && checklists.length === 0 && (
                        <div className="profile-empty-list">
                            <p>{t.noChecklists}</p>
                            <button className="action-btn primary" onClick={() => navigate("/")} style={{display:'flex',alignItems:'center',justifyContent:'center'}}>
                                <SparkleIcon style={{width:'18px',height:'18px',marginRight:'6px'}}/> {t.createFirstChecklist}
                            </button>
                        </div>
                    )}

                    <div className="checklists-grid">
                        {checklists.map((cl) => {
                            const isOwner = cl.user_id === user?.id;
                            const isShared = !isOwner || (cl.backpacks && cl.backpacks.length > 0);
                            return (
                            <div
                                key={cl.slug}
                                className={`checklist-preview-card${isOwner ? " checklist-preview-card-owned" : ""}`}
                                onClick={() => navigate(`/checklist/${cl.slug}`)}
                            >
                                <div className="card-actions">
                                    {isOwner && (
                                        <>
                                            <button
                                                className={`privacy-btn ${!cl.is_public ? "private" : ""}`}
                                                onClick={(e) => toggleChecklistPrivacy(e, cl.slug, cl.is_public)}
                                                title={cl.is_public ? t.publicStatus : t.hiddenStatus}
                                            >
                                                {cl.is_public ? <EyeIcon style={{marginRight:0}}/> : <LockIcon style={{marginRight:0}}/>}
                                            </button>
                                            <button
                                                className="delete-btn"
                                                onClick={(e) => deleteChecklist(e, cl.slug)}
                                                title={t.deleteChecklistBtn}
                                            >
                                                ✕
                                            </button>
                                        </>
                                    )}
                                </div>
                                <div className="preview-city">
                                    <span className="preview-city-text">{cl.city}</span>
                                </div>
                                <div className="preview-dates">
                                    {formatDate(cl.start_date)} — {formatDate(cl.end_date)}
                                </div>
                                <div className="preview-items">
                                    {pluralize(cl.items.length, ['вещь', 'вещи', 'вещей'], ['item', 'items'], lang)}
                                </div>
                                <div className="preview-temp-row">
                                    <div className="preview-temp">
                                        {cl.avg_temp > 0 ? "+" : ""}{Math.round(cl.avg_temp)}°C
                                    </div>
                                    {isShared && <span className="shared-badge" title={lang === 'en' ? 'Shared checklist' : 'Совместный чеклист'}>👥</span>}
                                </div>
                            </div>
                        );
                        })}
                    </div>
                </div>
            )}

            {(isOwner || isStatsPublic) && activeTab === "reviews" && (
                <div className="tab-content animations-fade">
                    {reviews.length === 0 ? (
                        <div className="profile-empty-list">
                            <p>{lang === 'en' ? 'No trip reviews yet.' : 'Пока нет отзывов о поездках.'}</p>
                        </div>
                    ) : (
                        <div className="profile-reviews-grid">
                            {reviews.map((review) => (
                                <article
                                    key={review.id}
                                    className="profile-review-card"
                                    onClick={() => review.checklist_slug && navigate(`/checklist/${review.checklist_slug}`)}
                                >
                                    <div className="profile-review-meta">
                                        <div>
                                            <div className="profile-review-city">{review.checklist_city || (lang === 'en' ? 'Trip' : 'Поездка')}</div>
                                            <div className="profile-review-dates">
                                                {review.checklist_start_date && review.checklist_end_date
                                                    ? `${formatDate(review.checklist_start_date)} — ${formatDate(review.checklist_end_date)}`
                                                    : ""}
                                            </div>
                                        </div>
                                        <div className="profile-review-rating">
                                            <strong>{review.rating}.0</strong>
                                            <span>{"★".repeat(review.rating)}{"☆".repeat(5 - review.rating)}</span>
                                        </div>
                                    </div>
                                    <p className="profile-review-text">{review.text}</p>
                                    {review.photo && (
                                        <div className="profile-review-photo">
                                            <img src={review.photo} alt="Trip review" />
                                        </div>
                                    )}
                                </article>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Followers Tab */}
            {(isOwner || isStatsPublic) && activeTab === "followers" && (
                <div className="tab-content animations-fade">
                    {/* Sub-tabs: Followers + Requests */}
                    {isOwner && !isStatsPublic && followRequests.length > 0 && (
                        <div className="follow-requests-section">
                            <h3 className="profile-section-title" style={{display: 'flex', alignItems: 'center', gap: '0.5rem'}}>
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="8.5" cy="7" r="4"></circle><line x1="20" y1="8" x2="20" y2="14"></line><line x1="23" y1="11" x2="17" y2="11"></line></svg>
                                {lang === 'en' ? 'Follow Requests' : 'Запросы на подписку'}
                                <span className="achievement-counter">{followRequests.length}</span>
                            </h3>
                            <div className="subscriptions-list">
                                {followRequests.map(req => (
                                    <div key={req.id} className="subscription-card">
                                        <div className="subscription-avatar" onClick={() => navigate(`/u/${req.from_user.username}`)}>
                                            {req.from_user.avatar ? (
                                                <img src={req.from_user.avatar} alt="Avatar" />
                                            ) : (
                                                req.from_user.username.charAt(0).toUpperCase()
                                            )}
                                        </div>
                                        <div className="subscription-info" onClick={() => navigate(`/u/${req.from_user.username}`)}>
                                            <div className="subscription-name">{req.from_user.username}</div>
                                        </div>
                                        <div className="subscription-action" style={{display: 'flex', gap: '0.5rem'}}>
                                            <button 
                                                className="action-btn primary"
                                                onClick={async () => {
                                                    try {
                                                        const res = await fetch(`${API_URL}/follow-requests/${req.id}/accept`, {
                                                            method: 'POST',
                                                            headers: { Authorization: `Bearer ${token}` }
                                                        });
                                                        if (res.ok) {
                                                            setFollowRequests(prev => prev.filter(r => r.id !== req.id));
                                                            await refreshSocialLists();
                                                        }
                                                    } catch(e) { console.error(e); }
                                                }}
                                            >
                                                {lang === 'en' ? 'Accept' : 'Принять'}
                                            </button>
                                            <button 
                                                className="action-btn secondary"
                                                onClick={async () => {
                                                    try {
                                                        const res = await fetch(`${API_URL}/follow-requests/${req.id}/decline`, {
                                                            method: 'POST',
                                                            headers: { Authorization: `Bearer ${token}` }
                                                        });
                                                        if (res.ok) {
                                                            setFollowRequests(prev => prev.filter(r => r.id !== req.id));
                                                        }
                                                    } catch(e) { console.error(e); }
                                                }}
                                            >
                                                {lang === 'en' ? 'Decline' : 'Отклонить'}
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Followers list */}
                    {followers.length === 0 ? (
                        <div className="profile-empty-list">
                            <p>{t.subsEmptyState}</p>
                        </div>
                    ) : (
                        <div className="subscriptions-list">
                            {followers.map(f => (
                                <div key={f.id} className="subscription-card subscription-card-social">
                                    <div className="subscription-avatar" onClick={() => navigate(`/u/${f.username}`)}>
                                        {f.avatar ? (
                                            <img src={f.avatar} alt="Avatar" />
                                        ) : (
                                            f.username.charAt(0).toUpperCase()
                                        )}
                                    </div>
                                    <div className="subscription-info" onClick={() => navigate(`/u/${f.username}`)}>
                                        <div className="subscription-name">{f.username}</div>
                                        <div className="subscription-meta">{getSubscriptionMeta(f, "followers")}</div>
                                    </div>
                                    <div className="subscription-actions" onClick={(e) => e.stopPropagation()}>
                                        <button 
                                            className={`subscription-cta-btn ${f.is_following ? "secondary" : "primary"}`}
                                            onClick={() => {
                                                if (f.is_following) {
                                                    openProfileInviteModal(f);
                                                    return;
                                                }
                                                handleFollowToggle(f.username, false);
                                            }}
                                        >
                                            {f.is_following ? t.inviteBtn : t.followBackBtn}
                                        </button>
                                        <button
                                            type="button"
                                            className="subscription-remove-btn"
                                            title={t.removeFollowerBtn}
                                            aria-label={t.removeFollowerBtn}
                                            onClick={() => handleRemoveFollower(f.username)}
                                        >
                                            ×
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Following Tab */}
            {(isOwner || isStatsPublic) && activeTab === "following" && (
                <div className="tab-content animations-fade">
                    {following.length === 0 ? (
                        <div className="profile-empty-list">
                            <p>{t.subsEmptyState}</p>
                        </div>
                    ) : (
                        <div className="subscriptions-list">
                            {following.map(f => (
                                <div key={f.id} className="subscription-card subscription-card-social">
                                    <div className="subscription-avatar" onClick={() => navigate(`/u/${f.username}`)}>
                                        {f.avatar ? (
                                            <img src={f.avatar} alt="Avatar" />
                                        ) : (
                                            f.username.charAt(0).toUpperCase()
                                        )}
                                    </div>
                                    <div className="subscription-info" onClick={() => navigate(`/u/${f.username}`)}>
                                        <div className="subscription-name">{f.username}</div>
                                        <div className="subscription-meta">{getSubscriptionMeta(f, "following")}</div>
                                    </div>
                                    <div className="subscription-actions" onClick={(e) => e.stopPropagation()}>
                                        <button 
                                            className="subscription-cta-btn secondary"
                                            onClick={() => openProfileInviteModal(f)}
                                        >
                                            {t.inviteBtn}
                                        </button>
                                        <button
                                            type="button"
                                            className="subscription-remove-btn"
                                            title={t.unfollowBtn}
                                            aria-label={t.unfollowBtn}
                                            onClick={() => handleFollowToggle(f.username, true)}
                                        >
                                            ×
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {profileInviteTarget && (
                <div className="modal-overlay profile-invite-modal-overlay" onClick={closeProfileInviteModal}>
                    <div className="modal-content profile-checklist-invite-modal" onClick={(e) => e.stopPropagation()}>
                        <button className="modal-close" onClick={closeProfileInviteModal}>&times;</button>
                        <h3 className="profile-checklist-invite-title">
                            {t.chooseChecklistTitle}: {profileInviteTarget.username}
                        </h3>
                        <p className="invite-modal-desc">{t.chooseChecklistDesc}</p>

                        {profileInviteError && (
                            <div className="profile-invite-error">{profileInviteError}</div>
                        )}

                        {inviteableChecklists.length === 0 ? (
                            <div className="profile-empty-list profile-invite-empty">
                                <p>{t.noChecklistsToInvite}</p>
                            </div>
                        ) : (
                            <div className="profile-invite-checklists">
                                {inviteableChecklists.map((checklist) => {
                                    const alreadyInChecklist = isUserInChecklist(checklist, profileInviteTarget.id);
                                    const inviteSent = profileInviteSentSlugs.includes(checklist.slug);
                                    const disabled = alreadyInChecklist || inviteSent;

                                    return (
                                        <div
                                            key={checklist.slug}
                                            className={`profile-invite-checklist ${disabled ? "disabled" : ""}`}
                                        >
                                            <div className="profile-invite-checklist-copy">
                                                <strong>{checklist.city}</strong>
                                                <span>
                                                    {formatDate(checklist.start_date)} — {formatDate(checklist.end_date)}
                                                </span>
                                            </div>
                                            <button
                                                type="button"
                                                className={`profile-invite-checklist-btn ${disabled ? "disabled" : "primary"}`}
                                                disabled={disabled || profileInviteBusySlug === checklist.slug}
                                                onClick={() => handleInviteUserToChecklist(checklist)}
                                            >
                                                {alreadyInChecklist
                                                    ? t.alreadyInChecklist
                                                    : inviteSent
                                                        ? t.inviteSent
                                                        : profileInviteBusySlug === checklist.slug
                                                            ? "..."
                                                            : t.inviteAction}
                                            </button>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {isAvatarModalOpen && (
                <div className="avatar-modal-overlay" onClick={() => setIsAvatarModalOpen(false)}>
                    <div className="avatar-modal-content" onClick={e => e.stopPropagation()}>
                        <img src={avatar} alt="Avatar Large" className="avatar-modal-img" />
                    </div>
                </div>
            )}
        </div>
    );
};

export default ProfilePage;
