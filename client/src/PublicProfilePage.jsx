import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import AuthModal from "./AuthModal";
import NavbarUserSearch from "./NavbarUserSearch";
import "./ProfilePage.css";
import "./App.css";
import { pluralizeWord } from "./i18n";
import { ListIcon, LockIcon, TrophyIcon, UnlockIcon } from "./Icons";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const safeParseJson = (value, fallback = null) => {
    if (!value) return fallback;
    try {
        return JSON.parse(value);
    } catch {
        return fallback;
    }
};

const getChecklistItemCount = (checklist) => {
    const checklistItemsCount = Array.isArray(checklist?.items) ? checklist.items.length : 0;
    const baggageCount = (checklist?.backpacks || []).reduce(
        (sum, backpack) => sum + (Array.isArray(backpack.items) ? backpack.items.length : 0),
        0
    );
    return checklistItemsCount + baggageCount;
};

const renderSocialIcon = (network) => {
    switch(network) {
        case 'instagram': return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line></svg>;
        case 'telegram': return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>;
        case 'twitter': return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 4s-.7 2.1-2 3.4c1.6 10-9.4 17.3-18 11.6 2.2.1 4.4-.6 6-2C3 15.5.5 9.6 3 5c2.2 2.6 5.6 4.1 9 4-.9-4.2 4-6.6 7-3.8 1.1 0 3-1.2 3-1.2z"></path></svg>;
        case 'linkedin': return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"></path><rect x="2" y="9" width="4" height="12"></rect><circle cx="4" cy="4" r="2"></circle></svg>;
        case 'website': return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>;
        default: return '🔗';
    }
};

const getSocialHref = (network, link) => {
    if (link.startsWith("http")) return link;
    if (network === "telegram") return `https://t.me/${link.replace("@", "")}`;
    if (network === "instagram") return `https://instagram.com/${link.replace("@", "")}`;
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

const getCountNoun = (count, key, lang = "ru") => {
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

const getPublicTravelerBadge = (stats) => {
    const totalTrips = Number(stats?.total_trips || 0);
    if (totalTrips >= 15) return "Опытный турист";
    if (totalTrips >= 8) return "Разведчик";
    if (totalTrips >= 3) return "Путешественник";
    return "Новичок";
};

const PublicProfilePage = () => {
    const { username } = useParams();
    const navigate = useNavigate();
    const [profile, setProfile] = useState(null);
    const [followers, setFollowers] = useState([]);
    const [following, setFollowing] = useState([]);
    const [myChecklists, setMyChecklists] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [showAuth, setShowAuth] = useState(false);
    const [activeTab, setActiveTab] = useState("checklists");
    const [profileInviteTarget, setProfileInviteTarget] = useState(null);
    const [profileInviteBusySlug, setProfileInviteBusySlug] = useState("");
    const [profileInviteSentSlugs, setProfileInviteSentSlugs] = useState([]);
    const [profileInviteError, setProfileInviteError] = useState("");
    
    // Auth context
    const token = localStorage.getItem("token");
    const storedUser = localStorage.getItem("user");
    const currentUser = safeParseJson(storedUser, null);
    const isSelf = currentUser && currentUser.username === username;

    useEffect(() => {
        const fetchProfile = async () => {
            try {
                const headers = {};
                if (token) headers.Authorization = `Bearer ${token}`;
                
                const res = await fetch(`${API_URL}/users/${username}`, { headers });
                if (!res.ok) {
                    if (res.status === 404) throw new Error("Пользователь не найден");
                    throw new Error("Ошибка загрузки профиля");
                }
                const data = await res.json();
                setProfile(data);
            } catch (e) {
                setError(e.message);
            } finally {
                setLoading(false);
            }
        };
        fetchProfile();
    }, [username, token]);

    useEffect(() => {
        setActiveTab("checklists");
    }, [username]);

    useEffect(() => {
        if (!profile || !canViewerSeeProfile(profile, currentUser?.username)) {
            setFollowers([]);
            setFollowing([]);
            return;
        }

        let isCancelled = false;

        const fetchSocialLists = async () => {
            try {
                const headers = {};
                if (token) headers.Authorization = `Bearer ${token}`;

                const [followersRes, followingRes] = await Promise.all([
                    fetch(`${API_URL}/users/${username}/followers`, { headers }),
                    fetch(`${API_URL}/users/${username}/following`, { headers }),
                ]);

                if (isCancelled) return;
                if (!followersRes.ok || !followingRes.ok) return;

                const [followersData, followingData] = await Promise.all([
                    followersRes.json(),
                    followingRes.json(),
                ]);

                if (isCancelled) return;
                setFollowers(Array.isArray(followersData) ? followersData : []);
                setFollowing(Array.isArray(followingData) ? followingData : []);
            } catch (e) {
                console.error(e);
            }
        };

        fetchSocialLists();
        return () => {
            isCancelled = true;
        };
    }, [profile, username, token, currentUser?.username]);

    useEffect(() => {
        if (!token) {
            setMyChecklists([]);
            return;
        }

        let isCancelled = false;

        const fetchOwnChecklists = async () => {
            try {
                const res = await fetch(`${API_URL}/my-checklists`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (!res.ok || isCancelled) return;
                const data = await res.json();
                if (isCancelled) return;
                setMyChecklists(Array.isArray(data) ? data : []);
            } catch (e) {
                console.error(e);
            }
        };

        fetchOwnChecklists();
        return () => {
            isCancelled = true;
        };
    }, [token]);

    const formatDate = (iso) => {
        const d = new Date(iso);
        return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.${d.getFullYear()}`;
    };

    const handleFollowToggle = async () => {
        if (!token) {
            setShowAuth(true);
            return;
        }
        
        try {
            const isFollowingOrRequested = profile.follow_status === "following" || profile.follow_status === "requested";
            const method = isFollowingOrRequested ? "DELETE" : "POST";
            const res = await fetch(`${API_URL}/users/${username}/follow`, {
                method,
                headers: { Authorization: `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                if (data.status === "followed") {
                    setProfile(prev => ({
                        ...prev,
                        is_following: true,
                        follow_status: "following",
                        followers_count: prev.followers_count + 1
                    }));
                } else if (data.status === "requested") {
                    setProfile(prev => ({
                        ...prev,
                        follow_status: "requested"
                    }));
                } else if (data.status === "unfollowed" || data.status === "request_cancelled") {
                    setProfile(prev => ({
                        ...prev,
                        is_following: false,
                        follow_status: null,
                        followers_count: data.status === "unfollowed" ? prev.followers_count - 1 : prev.followers_count
                    }));
                }
            }
        } catch (e) {
            console.error(e);
        }
    };

    const handleAuth = (userData, accessToken) => {
        localStorage.setItem("user", JSON.stringify(userData));
        localStorage.setItem("token", accessToken);
        setShowAuth(false);
        window.location.reload();
    };

    const handleLogout = () => {
        localStorage.removeItem("user");
        localStorage.removeItem("token");
        window.location.reload();
    };

    const openProfileInviteModal = () => {
        if (!token) {
            setShowAuth(true);
            return;
        }
        if (!profile?.id) return;

        setProfileInviteTarget({ id: profile.id, username: profile.username });
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

    const inviteableChecklists = myChecklists.filter((checklist) => checklist.user_id === currentUser?.id);

    const handleInviteUserToChecklist = async (checklist) => {
        if (!profileInviteTarget?.id || !checklist?.slug || !token) return;
        setProfileInviteBusySlug(checklist.slug);
        setProfileInviteError("");
        try {
            const res = await fetch(`${API_URL}/checklists/${checklist.slug}/invite/${profileInviteTarget.id}`, {
                method: "POST",
                headers: { Authorization: `Bearer ${token}` },
            });

            if (res.ok || res.status === 409) {
                setProfileInviteSentSlugs((prev) => (prev.includes(checklist.slug) ? prev : [...prev, checklist.slug]));
                setMyChecklists((prev) => prev.map((item) => (
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
            setProfileInviteError(data?.detail || "Не удалось отправить приглашение");
        } catch (e) {
            console.error(e);
            setProfileInviteError("Не удалось отправить приглашение");
        } finally {
            setProfileInviteBusySlug("");
        }
    };

    if (loading) return <div className="profile-loading">Загрузка...</div>;
    if (error) return (
        <div className="profile-error">
            <h2>😕 {error}</h2>
            <button className="action-btn" onClick={() => navigate("/")}>На главную</button>
        </div>
    );

    // Followers can see a private profile, just like Instagram
    const canSeeContent = canViewerSeeProfile(profile, currentUser?.username);
    const publicStatsCards = [
        {
            key: "checklists",
            count: profile.checklists?.length || 0,
            label: getCountNoun(profile.checklists?.length || 0, "checklists"),
            onClick: () => setActiveTab("checklists"),
        },
        {
            key: "followers",
            count: profile.followers_count || 0,
            label: getCountNoun(profile.followers_count || 0, "followers"),
            onClick: () => setActiveTab("followers"),
        },
        {
            key: "following",
            count: profile.following_count || 0,
            label: getCountNoun(profile.following_count || 0, "following"),
            onClick: () => setActiveTab("following"),
        },
    ];

    const travelStatsCards = canSeeContent && profile.stats ? [
        { key: "trips", value: profile.stats.total_trips, label: getCountNoun(profile.stats.total_trips, "trips") },
        { key: "countries", value: profile.stats.unique_countries, label: getCountNoun(profile.stats.unique_countries, "countries") },
        { key: "cities", value: profile.stats.unique_cities, label: getCountNoun(profile.stats.unique_cities, "cities") },
        { key: "days", value: profile.stats.total_days, label: getCountNoun(profile.stats.total_days, "days") },
        { key: "items", value: profile.stats.total_items || 0, label: getCountNoun(profile.stats.total_items || 0, "items") },
    ] : [];

    const visibleSocialLinks = canSeeContent
        ? Object.entries(profile.social_links || {}).filter(([, link]) => Boolean(link))
        : [];

    const profileStatsInline = (
        <div className="profile-stats-inline">
            {publicStatsCards.map((item) => (
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

    const publicBadge = getPublicTravelerBadge(profile.stats);

    const getSubscriptionMeta = (person, mode) => {
        if (person?.bio) return person.bio;
        if (mode === "followers") {
            return person?.is_following ? "Вы подписаны друг на друга" : "Подписан на пользователя";
        }
        return "Вы подписаны";
    };

    return (
        <>
            {/* Full Navbar */}
            <nav className="navbar">
                <div className="navbar-logo" onClick={() => navigate("/")}>
                    <img src="/luggify-logo.svg" alt="" className="navbar-logo-mark" aria-hidden="true" />
                    <span className="navbar-logo-text">LUGGIFY</span>
                </div>
                <div className="navbar-center navbar-search-desktop">
                    <NavbarUserSearch
                        lang="ru"
                        navigate={navigate}
                        currentUsername={currentUser?.username || ""}
                    />
                </div>
                <div className="navbar-user">
                    <div className="navbar-search-mobile">
                        <NavbarUserSearch
                            lang="ru"
                            navigate={navigate}
                            currentUsername={currentUser?.username || ""}
                            compact
                        />
                    </div>
                    {currentUser ? (
                        <>
                            <div className="navbar-profile" onClick={() => navigate("/profile")}>
                                <div className="navbar-avatar">
                                    {currentUser.avatar && (currentUser.avatar.startsWith("data:image") || currentUser.avatar.startsWith("http")) ? (
                                        <img src={currentUser.avatar} alt="Avatar" style={{ width: "100%", height: "100%", borderRadius: "50%", objectFit: "cover" }} />
                                    ) : (
                                        currentUser.avatar ? currentUser.avatar : currentUser.username.charAt(0).toUpperCase()
                                    )}
                                </div>
                                <span className="navbar-username">{currentUser.username}</span>
                            </div>
                            <button
                                className="navbar-logout-btn icon-btn"
                                onClick={handleLogout}
                                title="Выйти"
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
                        <button className="navbar-login-btn" onClick={() => setShowAuth(true)}>Войти</button>
                    )}
                </div>
            </nav>

            {showAuth && (
                <AuthModal
                    onClose={() => setShowAuth(false)}
                    onAuth={handleAuth}
                />
            )}
            <div className="page-wrapper public-profile-shell">
                <div className="profile-page public-profile-page">
                    <div className="profile-header">
                        <div className={`profile-main-row profile-main-row-compact${!canSeeContent ? " no-sidebar" : ""}`}>
                            <div className="profile-corner-actions public-profile-corner-actions">
                                <span className={`profile-visibility-chip ${profile.is_stats_public ? "public" : "private"}`}>
                                    {profile.is_stats_public ? "Открытый профиль" : "Закрытый профиль"}
                                </span>
                                <span
                                    className={`profile-corner-status-icon ${profile.is_stats_public ? "public" : "private"}`}
                                    title={profile.is_stats_public ? "Открытый профиль" : "Закрытый профиль"}
                                    aria-label={profile.is_stats_public ? "Открытый профиль" : "Закрытый профиль"}
                                >
                                    {profile.is_stats_public ? (
                                        <UnlockIcon style={{ width: "14px", height: "14px", marginRight: 0 }} />
                                    ) : (
                                        <LockIcon style={{ width: "14px", height: "14px", marginRight: 0 }} />
                                    )}
                                </span>
                            </div>
                            <div className="profile-avatar-rail">
                                <div className="profile-avatar-frame">
                                    <div className="profile-avatar">
                                        {profile.avatar && (profile.avatar.startsWith("data:image") || profile.avatar.startsWith("http")) ? (
                                            <img src={profile.avatar} alt="Avatar" className="profile-avatar-image" />
                                        ) : (
                                            profile.avatar ? profile.avatar : profile.username.charAt(0).toUpperCase()
                                        )}
                                    </div>
                                    <span
                                        className={`profile-avatar-status-icon ${profile.is_stats_public ? "public" : "private"}`}
                                        title={profile.is_stats_public ? "Открытый профиль" : "Закрытый профиль"}
                                        aria-label={profile.is_stats_public ? "Открытый профиль" : "Закрытый профиль"}
                                    >
                                        {profile.is_stats_public ? (
                                            <UnlockIcon style={{ width: "12px", height: "12px", marginRight: 0 }} />
                                        ) : (
                                            <LockIcon style={{ width: "12px", height: "12px", marginRight: 0 }} />
                                        )}
                                    </span>
                                </div>
                                {visibleSocialLinks.length > 0 && (
                                    <div className="profile-avatar-socials">
                                        {visibleSocialLinks.slice(0, 5).map(([net, link]) => (
                                            <a
                                                key={net}
                                                href={getSocialHref(net, link)}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className={`social-badge ${net}`}
                                                title={getSocialLabel(net)}
                                            >
                                                {renderSocialIcon(net)}
                                            </a>
                                        ))}
                                    </div>
                                )}
                            </div>

                            <div className="profile-info-block">
                                <div className="profile-name-row">
                                    <div className="profile-identity-block">
                                        <div className="profile-title-strip">
                                            <div className="profile-name-heading">
                                                <h2>{profile.username}</h2>
                                                <span
                                                    className={`profile-name-status-icon ${profile.is_stats_public ? "public" : "private"}`}
                                                    title={profile.is_stats_public ? "Открытый профиль" : "Закрытый профиль"}
                                                    aria-label={profile.is_stats_public ? "Открытый профиль" : "Закрытый профиль"}
                                                >
                                                    {profile.is_stats_public ? (
                                                        <UnlockIcon style={{ width: "14px", height: "14px", marginRight: 0 }} />
                                                    ) : (
                                                        <LockIcon style={{ width: "14px", height: "14px", marginRight: 0 }} />
                                                    )}
                                                </span>
                                            </div>
                                            {canSeeContent && (
                                                <span className="level-badge public-profile-badge">
                                                    {publicBadge}
                                                </span>
                                            )}
                                        </div>

                                        <div className={`profile-details-view ${canSeeContent ? "profile-details-view-desktop" : ""}`}>
                                            {canSeeContent ? (
                                                <>
                                                    {profile.bio && <p className="profile-bio">{profile.bio}</p>}
                                                </>
                                            ) : (
                                                <div className="private-profile-notice">
                                                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
                                                    <span>Это закрытый профиль</span>
                                                </div>
                                            )}
                                        </div>

                                        {canSeeContent && (
                                            <div className="profile-stats-panel profile-stats-panel-mobile">
                                                {profileStatsInline}
                                            </div>
                                        )}

                                        {!isSelf && (
                                            <div className="profile-action-mt profile-action-mt-compact public-profile-action-row">
                                                <button
                                                    className={`action-btn profile-follow-btn profile-follow-btn-public ${profile.follow_status === "following" ? "secondary" : profile.follow_status === "requested" ? "secondary" : "primary"}`}
                                                    onClick={handleFollowToggle}
                                                >
                                                    {profile.follow_status === "following"
                                                        ? "Отписаться"
                                                        : profile.follow_status === "requested"
                                                            ? "Отменить запрос"
                                                            : (!profile.is_stats_public ? "Отправить запрос" : "Подписаться")}
                                                </button>
                                                <button
                                                    type="button"
                                                    className="action-btn secondary profile-follow-btn profile-follow-btn-public public-profile-invite-btn"
                                                    onClick={openProfileInviteModal}
                                                >
                                                    Пригласить
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>

                            {canSeeContent && (
                                <div className="profile-stats-panel profile-stats-panel-desktop">
                                    {profileStatsInline}
                                </div>
                            )}

                            {canSeeContent && profile.bio && (
                                <p className="profile-bio profile-bio-mobile">{profile.bio}</p>
                            )}
                        </div>

                        {travelStatsCards.length > 0 && (
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

                    {canSeeContent && (
                        <>
                            <div className="profile-tabs public-profile-tabs">
                                <button
                                    className={`profile-tab ${activeTab === "checklists" ? "active" : ""}`}
                                    onClick={() => setActiveTab("checklists")}
                                >
                                    <span style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
                                        <ListIcon style={{ width: "18px", height: "18px", marginRight: "6px" }} />
                                        Чеклисты
                                    </span>
                                </button>
                                <button
                                    className={`profile-tab ${activeTab === "reviews" ? "active" : ""}`}
                                    onClick={() => setActiveTab("reviews")}
                                >
                                    <span style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
                                        ★ Отзывы
                                    </span>
                                </button>
                                <button
                                    className={`profile-tab ${activeTab === "achievements" ? "active" : ""}`}
                                    onClick={() => setActiveTab("achievements")}
                                >
                                    <span style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
                                        <TrophyIcon style={{ width: "18px", height: "18px", marginRight: "6px" }} />
                                        Достижения и статистика
                                    </span>
                                </button>
                                <button
                                    className={`profile-tab ${activeTab === "followers" ? "active" : ""}`}
                                    onClick={() => setActiveTab("followers")}
                                >
                                    <span style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
                                        Подписчики
                                    </span>
                                </button>
                                <button
                                    className={`profile-tab ${activeTab === "following" ? "active" : ""}`}
                                    onClick={() => setActiveTab("following")}
                                >
                                    <span style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
                                        Подписки
                                    </span>
                                </button>
                            </div>

                            {activeTab === "checklists" && (
                                <div className="tab-content animations-fade">
                                    {profile.checklists.length === 0 ? (
                                        <div className="profile-empty-list public-profile-empty">
                                            <p>Пользователь скрыл свои чеклисты или пока ничего не создал.</p>
                                        </div>
                                    ) : (
                                        <div className="checklists-grid">
                                            {profile.checklists.map((cl) => (
                                                <div
                                                    key={cl.slug}
                                                    className="checklist-preview-card"
                                                    onClick={() => navigate(`/checklist/${cl.slug}`)}
                                                >
                                                    <div className="preview-city">
                                                        <span className="preview-city-text">{cl.city}</span>
                                                    </div>
                                                    <div className="preview-dates">
                                                        {formatDate(cl.start_date)} — {formatDate(cl.end_date)}
                                                    </div>
                                                    <div className="preview-items">
                                                        {getChecklistItemCount(cl)} {getCountNoun(getChecklistItemCount(cl), "items", "ru")}
                                                    </div>
                                                    <div className="preview-temp-row">
                                                        <div className="preview-temp">
                                                            {cl.avg_temp > 0 ? "+" : ""}{Math.round(cl.avg_temp)}°C
                                                        </div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}

                            {activeTab === "reviews" && (
                                <div className="tab-content animations-fade">
                                    {profile.reviews?.length ? (
                                        <div className="profile-reviews-grid">
                                            {profile.reviews.map((review) => (
                                                <article
                                                    key={review.id}
                                                    className="profile-review-card"
                                                    onClick={() => review.checklist_slug && navigate(`/checklist/${review.checklist_slug}`)}
                                                >
                                                    <div className="profile-review-meta">
                                                        <div>
                                                            <div className="profile-review-city">{review.checklist_city || "Поездка"}</div>
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
                                    ) : (
                                        <div className="profile-empty-list public-profile-empty">
                                            <p>Пока нет опубликованных отзывов.</p>
                                        </div>
                                    )}
                                </div>
                            )}

                            {activeTab === "achievements" && (
                                <div className="tab-content animations-fade">
                                    {travelStatsCards.length > 0 && (
                                        <div className="public-profile-stats-grid">
                                            {travelStatsCards.map((item) => (
                                                <div key={item.key} className="profile-hero-metric public-profile-stat-card" data-metric-key={item.key}>
                                                    <span className="profile-hero-metric-value">{item.value}</span>
                                                    <span className="profile-hero-metric-label">{item.label}</span>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                    {(profile.bio || visibleSocialLinks.length > 0) && (
                                        <div className="public-profile-about-card">
                                            <h3 className="profile-section-title public-profile-about-title">О профиле</h3>
                                            {profile.bio && <p className="profile-bio public-profile-about-bio">{profile.bio}</p>}
                                            {visibleSocialLinks.length > 0 && (
                                                <div className="public-profile-socials">
                                                    {visibleSocialLinks.map(([net, link]) => (
                                                        <a
                                                            key={net}
                                                            href={getSocialHref(net, link)}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                            className={`social-badge ${net}`}
                                                            title={getSocialLabel(net)}
                                                        >
                                                            {renderSocialIcon(net)}
                                                        </a>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            )}

                            {activeTab === "followers" && (
                                <div className="tab-content animations-fade">
                                    {followers.length === 0 ? (
                                        <div className="profile-empty-list public-profile-empty">
                                            <p>Пока нет подписчиков.</p>
                                        </div>
                                    ) : (
                                        <div className="subscriptions-list">
                                            {followers.map((person) => (
                                                <div key={person.id} className="subscription-card subscription-card-social">
                                                    <div className="subscription-avatar" onClick={() => navigate(`/u/${person.username}`)}>
                                                        {person.avatar ? (
                                                            <img src={person.avatar} alt="Avatar" />
                                                        ) : (
                                                            person.username.charAt(0).toUpperCase()
                                                        )}
                                                    </div>
                                                    <div className="subscription-info" onClick={() => navigate(`/u/${person.username}`)}>
                                                        <div className="subscription-name">{person.username}</div>
                                                        <div className="subscription-meta">{getSubscriptionMeta(person, "followers")}</div>
                                                    </div>
                                                    <div className="subscription-actions" onClick={(e) => e.stopPropagation()}>
                                                        <button
                                                            type="button"
                                                            className="subscription-cta-btn primary"
                                                            onClick={() => navigate(person.username === currentUser?.username ? "/profile" : `/u/${person.username}`)}
                                                        >
                                                            Открыть
                                                        </button>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}

                            {activeTab === "following" && (
                                <div className="tab-content animations-fade">
                                    {following.length === 0 ? (
                                        <div className="profile-empty-list public-profile-empty">
                                            <p>Пока нет подписок.</p>
                                        </div>
                                    ) : (
                                        <div className="subscriptions-list">
                                            {following.map((person) => (
                                                <div key={person.id} className="subscription-card subscription-card-social">
                                                    <div className="subscription-avatar" onClick={() => navigate(`/u/${person.username}`)}>
                                                        {person.avatar ? (
                                                            <img src={person.avatar} alt="Avatar" />
                                                        ) : (
                                                            person.username.charAt(0).toUpperCase()
                                                        )}
                                                    </div>
                                                    <div className="subscription-info" onClick={() => navigate(`/u/${person.username}`)}>
                                                        <div className="subscription-name">{person.username}</div>
                                                        <div className="subscription-meta">{getSubscriptionMeta(person, "following")}</div>
                                                    </div>
                                                    <div className="subscription-actions" onClick={(e) => e.stopPropagation()}>
                                                        <button
                                                            type="button"
                                                            className="subscription-cta-btn primary"
                                                            onClick={() => navigate(person.username === currentUser?.username ? "/profile" : `/u/${person.username}`)}
                                                        >
                                                            Открыть
                                                        </button>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}
                        </>
                    )}
                </div>
            </div>

            {profileInviteTarget && (
                <div className="modal-overlay profile-invite-modal-overlay" onClick={closeProfileInviteModal}>
                    <div className="modal-content profile-checklist-invite-modal" onClick={(e) => e.stopPropagation()}>
                        <button className="modal-close" onClick={closeProfileInviteModal}>&times;</button>
                        <h3 className="profile-checklist-invite-title">
                            Куда пригласить: {profileInviteTarget.username}
                        </h3>
                        <p className="invite-modal-desc">Выберите один из своих чеклистов, куда хотите пригласить пользователя.</p>

                        {profileInviteError && (
                            <div className="profile-invite-error">{profileInviteError}</div>
                        )}

                        {inviteableChecklists.length === 0 ? (
                            <div className="profile-empty-list profile-invite-empty">
                                <p>У вас пока нет своих чеклистов для приглашения.</p>
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
                                                    ? "Уже в чеклисте"
                                                    : inviteSent
                                                        ? "Приглашение отправлено"
                                                        : profileInviteBusySlug === checklist.slug
                                                            ? "..."
                                                            : "Пригласить"}
                                            </button>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </>
    );
};

const canViewerSeeProfile = (profile, viewerUsername) => {
    if (!profile) return false;
    return profile.username === viewerUsername || profile.is_stats_public || profile.follow_status === "following";
};

export default PublicProfilePage;
