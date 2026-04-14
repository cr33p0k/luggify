import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import AuthModal from "./AuthModal";
import NavbarUserSearch from "./NavbarUserSearch";
import "./ProfilePage.css";
import "./App.css";
import { pluralizeWord } from "./i18n";
import { LockIcon, UnlockIcon } from "./Icons";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const safeParseJson = (value, fallback = null) => {
    if (!value) return fallback;
    try {
        return JSON.parse(value);
    } catch {
        return fallback;
    }
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

const PublicProfilePage = () => {
    const { username } = useParams();
    const navigate = useNavigate();
    const [profile, setProfile] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [showAuth, setShowAuth] = useState(false);
    
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

    if (loading) return <div className="profile-loading">Загрузка...</div>;
    if (error) return (
        <div className="profile-error">
            <h2>😕 {error}</h2>
            <button className="action-btn" onClick={() => navigate("/")}>На главную</button>
        </div>
    );

    // Followers can see a private profile, just like Instagram
    const canSeeContent = isSelf || profile.is_stats_public || profile.follow_status === "following";
    const publicStatsCards = [
        { key: "checklists", count: profile.checklists?.length || 0, label: getCountNoun(profile.checklists?.length || 0, "checklists") },
        { key: "followers", count: profile.followers_count || 0, label: getCountNoun(profile.followers_count || 0, "followers") },
        { key: "following", count: profile.following_count || 0, label: getCountNoun(profile.following_count || 0, "following") },
    ];

    const travelStatsCards = canSeeContent && profile.stats ? [
        { key: "trips", value: profile.stats.total_trips, label: getCountNoun(profile.stats.total_trips, "trips") },
        { key: "countries", value: profile.stats.unique_countries, label: getCountNoun(profile.stats.unique_countries, "countries") },
        { key: "cities", value: profile.stats.unique_cities, label: getCountNoun(profile.stats.unique_cities, "cities") },
        { key: "days", value: profile.stats.total_days, label: getCountNoun(profile.stats.total_days, "days") },
        { key: "items", value: profile.stats.total_items || 0, label: getCountNoun(profile.stats.total_items || 0, "items") },
    ] : [];

    return (
        <div className="profile-page">
            {/* Full Navbar */}
            <nav className="navbar">
                <div className="navbar-logo" onClick={() => navigate("/")}>
                    <span>🧳</span><span className="navbar-logo-text">Luggify</span>
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

            <div className="profile-header">
                <div className={`profile-main-row ${!canSeeContent ? "no-sidebar" : ""}`}>
                    <div className="profile-avatar">
                        {profile.avatar && (profile.avatar.startsWith("data:image") || profile.avatar.startsWith("http")) ? (
                            <img src={profile.avatar} alt="Avatar" style={{ width: "100%", height: "100%", borderRadius: "50%", objectFit: "cover" }} />
                        ) : (
                            profile.avatar ? profile.avatar : profile.username.charAt(0).toUpperCase()
                        )}
                    </div>

                    <div className="profile-info-block">
                        <div className="profile-name-row">
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
                            </div>
                        </div>

                        <div className="profile-meta-line">
                            <span>{profile.is_stats_public ? "Открытый профиль" : "Закрытый профиль"}</span>
                        </div>

                        {canSeeContent ? (
                            <>
                                {profile.bio && <p className="profile-bio">{profile.bio}</p>}
                                {profile.social_links && Object.keys(profile.social_links).some(k => profile.social_links[k]) && (
                                    <div className="profile-social-icons">
                                        {Object.entries(profile.social_links).map(([net, link]) => {
                                            if (!link) return null;
                                            const href = link.startsWith('http') ? link : (net === 'telegram' ? `https://t.me/${link.replace('@','')}` : (net === 'instagram' ? `https://instagram.com/${link.replace('@','')}` : `https://${link}`));
                                            return (
                                                <a key={net} href={href} target="_blank" rel="noopener noreferrer" className={`social-badge ${net}`} title={net}>
                                                    {renderSocialIcon(net)}
                                                </a>
                                            );
                                        })}
                                    </div>
                                )}
                            </>
                        ) : (
                            <div className="private-profile-notice">
                                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
                                <span>Это закрытый профиль</span>
                            </div>
                        )}

                        {!isSelf && (
                            <div className="profile-action-mt">
                                <button 
                                    className={`action-btn profile-follow-btn ${profile.follow_status === "following" ? "secondary" : profile.follow_status === "requested" ? "secondary" : "primary"}`}
                                    onClick={handleFollowToggle}
                                >
                                    {profile.follow_status === "following" 
                                        ? "Отписаться" 
                                        : profile.follow_status === "requested" 
                                            ? "Отменить запрос" 
                                            : (!profile.is_stats_public ? "Отправить запрос" : "Подписаться")}
                                </button>
                            </div>
                        )}
                    </div>

                    {canSeeContent && (
                        <div className="profile-stats-sidebar">
                            {publicStatsCards.map((item) => (
                                <div key={item.key} className="profile-stat-col">
                                    <span className="profile-stat-count">{item.count}</span>
                                    <span className="profile-stat-string">{item.label}</span>
                                </div>
                            ))}
                        </div>
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
                    <h3 className="profile-section-title">Публичные чеклисты</h3>

                    {profile.checklists.length === 0 ? (
                        <div className="profile-empty-list">
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
                                        {cl.items.length} вещей
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

                    <h3 className="profile-section-title" style={{ marginTop: "1.8rem" }}>Отзывы о поездках</h3>
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
                        <div className="profile-empty-list">
                            <p>Пока нет опубликованных отзывов.</p>
                        </div>
                    )}
                </>
            )}
        </div>
    );
};

export default PublicProfilePage;
