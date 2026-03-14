import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./ProfilePage.css";
import { TRANSLATIONS, pluralize } from "./i18n";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const ProfilePage = ({ user, token, onLogout, onUpdateUser, lang = "ru" }) => {
    const t = TRANSLATIONS[lang] || TRANSLATIONS.ru;
    const navigate = useNavigate();
    const [checklists, setChecklists] = useState([]);
    const [stats, setStats] = useState(null);
    const [achievements, setAchievements] = useState(null);
    const [feedback, setFeedback] = useState(null);
    const [followers, setFollowers] = useState([]);
    const [following, setFollowing] = useState([]);
    const [isStatsPublic, setIsStatsPublic] = useState(user?.is_stats_public ?? true);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [activeTab, setActiveTab] = useState("checklists"); // "checklists" | "achievements" | "followers" | "following"
    const [avatar, setAvatar] = useState(user?.avatar || "");

    useEffect(() => {
        if (!token) return;
        const fetchData = async () => {
            try {
                // Checklists
                const resCl = await fetch(`${API_URL}/my-checklists`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (resCl.status === 401) {
                    onLogout();
                    return;
                }
                if (!resCl.ok) throw new Error(t.failedToLoadChecklists);
                const dataCl = await resCl.json();
                setChecklists(dataCl);

                // Stats
                const resStats = await fetch(`${API_URL}/my-stats`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (resStats.ok) {
                    const dataStats = await resStats.json();
                    setStats(dataStats);
                }

                // Achievements
                const resAch = await fetch(`${API_URL}/my-achievements`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (resAch.ok) {
                    const dataAch = await resAch.json();
                    setAchievements(dataAch);
                }

                // Feedback
                const resFb = await fetch(`${API_URL}/my-feedback-stats`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (resFb.ok) {
                    const dataFb = await resFb.json();
                    setFeedback(dataFb);
                }

                // Followers
                if (user?.username) {
                    const resFollowers = await fetch(`${API_URL}/users/${user.username}/followers`, {
                        headers: { Authorization: `Bearer ${token}` },
                    });
                    if (resFollowers.ok) {
                        setFollowers(await resFollowers.json());
                    }

                    const resFollowing = await fetch(`${API_URL}/users/${user.username}/following`, {
                        headers: { Authorization: `Bearer ${token}` },
                    });
                    if (resFollowing.ok) {
                        setFollowing(await resFollowing.json());
                    }
                }
            } catch (e) {
                console.error(e);
                setError(e.message);
            } finally {
                setLoading(false);
            }
        };
        fetchData();

        // Sync privacy state
        if (user) setIsStatsPublic(user.is_stats_public);
    }, [token, user]);

    const formatDate = (iso) => {
        const d = new Date(iso);
        return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.${d.getFullYear()}`;
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

    const toggleStatsPrivacy = async () => {
        try {
            const res = await fetch(`${API_URL}/auth/privacy`, {
                method: "PATCH",
                headers: {
                    Authorization: `Bearer ${token}`,
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ is_stats_public: !isStatsPublic }),
            });
            if (res.ok) {
                setIsStatsPublic(!isStatsPublic);
                if (onUpdateUser) {
                    onUpdateUser({ ...user, is_stats_public: !isStatsPublic });
                }
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

    const fileInputRef = React.useRef(null);

    const handleShare = () => {
        const url = `${window.location.origin}/u/${user.username}`;
        navigator.clipboard.writeText(url);
        alert(t.linkCopied);
    };

    const handleAvatarClick = () => {
        if (fileInputRef.current) fileInputRef.current.click();
    };

    const handleFileChange = (e) => {
        const file = e.target.files?.[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (ev) => {
            const img = new Image();
            img.onload = async () => {
                const canvas = document.createElement("canvas");
                const MAX_SIZE = 256;
                let width = img.width;
                let height = img.height;

                if (width > height) {
                    if (width > MAX_SIZE) {
                        height *= MAX_SIZE / width;
                        width = MAX_SIZE;
                    }
                } else {
                    if (height > MAX_SIZE) {
                        width *= MAX_SIZE / height;
                        height = MAX_SIZE;
                    }
                }

                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext("2d");
                ctx.drawImage(img, 0, 0, width, height);
                const dataUrl = canvas.toDataURL("image/jpeg", 0.9);

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

    const handleFollowToggle = async (targetUsername, currentIsFollowing) => {
        try {
            const method = currentIsFollowing ? "DELETE" : "POST";
            const res = await fetch(`${API_URL}/users/${targetUsername}/follow`, {
                method,
                headers: { Authorization: `Bearer ${token}` }
            });
            if (res.ok) {
                // Refresh lists
                const resFollowers = await fetch(`${API_URL}/users/${user.username}/followers`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (resFollowers.ok) setFollowers(await resFollowers.json());

                const resFollowing = await fetch(`${API_URL}/users/${user.username}/following`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (resFollowing.ok) setFollowing(await resFollowing.json());
            }
        } catch (e) {
            console.error(e);
        }
    };

    return (
        <div className="profile-page">
            <div className="profile-header">
                <div className="profile-top-actions">
                    <button className="top-action-icon" onClick={handleShare} title={t.shareString}>
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"></path>
                            <polyline points="16 6 12 2 8 6"></polyline>
                            <line x1="12" y1="2" x2="12" y2="15"></line>
                        </svg>
                    </button>
                    <button
                        className={`top-action-icon ${!isStatsPublic ? "private" : ""}`}
                        onClick={toggleStatsPrivacy}
                        title={isStatsPublic ? t.statsPublic : t.statsHidden}
                    >
                        {isStatsPublic ? "👁️" : "🔒"}
                    </button>
                </div>

                <div className="profile-main-row">
                    <input
                    type="file"
                    accept="image/*"
                    ref={fileInputRef}
                    style={{ display: "none" }}
                    onChange={handleFileChange}
                />
                <div className="profile-avatar" onClick={handleAvatarClick} title={t.uploadAvatar}>
                    {avatar && (avatar.startsWith("data:image") || avatar.startsWith("http")) ? (
                        <img src={avatar} alt="Avatar" style={{ width: "100%", height: "100%", borderRadius: "50%", objectFit: "cover" }} />
                    ) : (
                        avatar ? avatar : user.username.charAt(0).toUpperCase()
                    )}
                </div>
                    
                    <div className="profile-stats-block">
                        <div className="profile-stat-col" onClick={() => setActiveTab("checklists")}>
                            <span className="profile-stat-count">{checklists.length}</span>
                            <span className="profile-stat-string">{lang === 'en' ? 'Lists' : 'Чеклисты'}</span>
                        </div>
                        <div className="profile-stat-col" onClick={() => setActiveTab("followers")}>
                            <span className="profile-stat-count">{user?.followers_count || followers.length}</span>
                            <span className="profile-stat-string">{t.followersStat}</span>
                        </div>
                        <div className="profile-stat-col" onClick={() => setActiveTab("following")}>
                            <span className="profile-stat-count">{user?.following_count || following.length}</span>
                            <span className="profile-stat-string">{t.followingStat}</span>
                        </div>
                    </div>
                </div>

                <div className="profile-info-block">
                    <h2>
                        {user.username}
                        {achievements && (
                            <span className="level-badge">
                                {achievements.level.icon} {lang === 'en' ? achievements.level.name_en : achievements.level.name_ru}
                            </span>
                        )}
                    </h2>
                </div>
            </div>

            {/* Statistics Section */}
            {stats && (
                <div className={`profile-stats ${!isStatsPublic ? "opacity-50" : ""}`}>
                    <div className="stat-item">
                        <span className="stat-val">{stats.total_trips}</span>
                        <span className="stat-lbl">{t.tripsStat}</span>
                    </div>
                    <div className="stat-item">
                        <span className="stat-val">{stats.unique_countries}</span>
                        <span className="stat-lbl">{t.countriesStat}</span>
                    </div>
                    <div className="stat-item">
                        <span className="stat-val">{stats.unique_cities}</span>
                        <span className="stat-lbl">{t.citiesStat}</span>
                    </div>
                    <div className="stat-item">
                        <span className="stat-val">{stats.total_days}</span>
                        <span className="stat-lbl">{t.daysStat}</span>
                    </div>
                </div>
            )}

            {/* Tabs Navigation */}
            <div className="profile-tabs">
                <button
                    className={`profile-tab ${activeTab === "checklists" ? "active" : ""}`}
                    onClick={() => setActiveTab("checklists")}
                >
                    {t.profileChecklists}
                </button>
                <button
                    className={`profile-tab ${activeTab === "achievements" ? "active" : ""}`}
                    onClick={() => setActiveTab("achievements")}
                >
                    {t.profileAchievementsAndStats}
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

            {/* Achievements & Feedback Tab */}
            {activeTab === "achievements" && (
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
                            <h3 className="profile-section-title">{t.yourPreferences}</h3>
                            <div className="feedback-columns">
                                {feedback.top_added.length > 0 && (
                                    <div className="feedback-col">
                                        <h4>{t.frequentlyAdded}</h4>
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
                                        <h4>{t.frequentlyRemoved}</h4>
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
            {activeTab === "checklists" && (
                <div className="tab-content animations-fade">
                    {loading && <div className="profile-loading">{t.loadingStr}</div>}
                    {error && <div className="profile-error">{error}</div>}

                    {!loading && !error && checklists.length === 0 && (
                        <div className="profile-empty-list">
                            <p>{t.noChecklists}</p>
                            <button className="action-btn primary" onClick={() => navigate("/")}>
                                {t.createFirstChecklist}
                            </button>
                        </div>
                    )}

                    <div className="checklists-grid">
                        {checklists.map((cl) => {
                            const isOwner = cl.user_id === user?.id;
                            return (
                            <div
                                key={cl.slug}
                                className="checklist-preview-card"
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
                                                {cl.is_public ? "👁️" : "🔒"}
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
                                <div className="preview-city">{cl.city}{!isOwner && <span className="shared-badge" title={lang === 'en' ? 'Shared checklist' : 'Совместный чеклист'}>👥</span>}</div>
                                <div className="preview-dates">
                                    {formatDate(cl.start_date)} — {formatDate(cl.end_date)}
                                </div>
                                <div className="preview-temp">
                                    {cl.avg_temp > 0 ? "+" : ""}{Math.round(cl.avg_temp)}°C
                                </div>
                                <div className="preview-items">
                                    {pluralize(cl.items.length, ['вещь', 'вещи', 'вещей'], ['item', 'items'], lang)}
                                </div>
                            </div>
                        );
                        })}
                    </div>
                </div>
            )}

            {/* Followers Tab */}
            {activeTab === "followers" && (
                <div className="tab-content animations-fade">
                    {followers.length === 0 ? (
                        <div className="profile-empty-list">
                            <p>{t.subsEmptyState}</p>
                        </div>
                    ) : (
                        <div className="subscriptions-list">
                            {followers.map(f => (
                                <div key={f.id} className="subscription-card" onClick={() => navigate(`/u/${f.username}`)}>
                                    <div className="subscription-avatar">
                                        {f.avatar ? (
                                            <img src={f.avatar} alt="Avatar" />
                                        ) : (
                                            f.username.charAt(0).toUpperCase()
                                        )}
                                    </div>
                                    <div className="subscription-info">
                                        <div className="subscription-name">{f.username}</div>
                                    </div>
                                    <div className="subscription-action" onClick={(e) => e.stopPropagation()}>
                                        <button 
                                            className={`action-btn ${f.is_following ? "secondary" : "primary"}`}
                                            onClick={() => handleFollowToggle(f.username, f.is_following)}
                                        >
                                            {f.is_following ? t.unfollowBtn : t.followBackBtn}
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Following Tab */}
            {activeTab === "following" && (
                <div className="tab-content animations-fade">
                    {following.length === 0 ? (
                        <div className="profile-empty-list">
                            <p>{t.subsEmptyState}</p>
                        </div>
                    ) : (
                        <div className="subscriptions-list">
                            {following.map(f => (
                                <div key={f.id} className="subscription-card" onClick={() => navigate(`/u/${f.username}`)}>
                                    <div className="subscription-avatar">
                                        {f.avatar ? (
                                            <img src={f.avatar} alt="Avatar" />
                                        ) : (
                                            f.username.charAt(0).toUpperCase()
                                        )}
                                    </div>
                                    <div className="subscription-info">
                                        <div className="subscription-name">{f.username}</div>
                                    </div>
                                    <div className="subscription-action" onClick={(e) => e.stopPropagation()}>
                                        <button 
                                            className="action-btn secondary"
                                            onClick={() => handleFollowToggle(f.username, true)}
                                        >
                                            {t.unfollowBtn}
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default ProfilePage;
