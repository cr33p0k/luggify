import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./ProfilePage.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const ProfilePage = ({ user, token, onLogout, onUpdateUser }) => {
    const navigate = useNavigate();
    const [checklists, setChecklists] = useState([]);
    const [stats, setStats] = useState(null);
    const [achievements, setAchievements] = useState(null);
    const [feedback, setFeedback] = useState(null);
    const [isStatsPublic, setIsStatsPublic] = useState(user?.is_stats_public ?? true);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [activeTab, setActiveTab] = useState("checklists"); // "checklists" | "achievements"
    const [avatar, setAvatar] = useState(user?.avatar || "");

    useEffect(() => {
        if (!token) return;
        const fetchData = async () => {
            try {
                // Checklists
                const resCl = await fetch(`${API_URL}/my-checklists`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (!resCl.ok) throw new Error("Не удалось загрузить чеклисты");
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
        if (!window.confirm("Удалить чеклист?")) return;
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
        alert("Ссылка скопирована!");
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

    return (
        <div className="profile-page">
            <div className="profile-header">
                <input
                    type="file"
                    accept="image/*"
                    ref={fileInputRef}
                    style={{ display: "none" }}
                    onChange={handleFileChange}
                />
                <div className="profile-avatar" onClick={handleAvatarClick} title="Загрузить аватарку">
                    {avatar && (avatar.startsWith("data:image") || avatar.startsWith("http")) ? (
                        <img src={avatar} alt="Avatar" style={{ width: "100%", height: "100%", borderRadius: "50%", objectFit: "cover" }} />
                    ) : (
                        avatar ? avatar : user.username.charAt(0).toUpperCase()
                    )}
                </div>
                <div className="profile-info">
                    <h2>
                        {user.username}
                        {achievements && (
                            <span className="level-badge">
                                {achievements.level.icon} {achievements.level.name_ru}
                            </span>
                        )}
                    </h2>
                    <p className="profile-stats-summary">
                        <span>{checklists.length} {checklists.length === 0 ? "чеклистов" : checklists.length === 1 ? "чеклист" : checklists.length < 5 ? "чеклиста" : "чеклистов"}</span>
                        <span className="dot-separator">•</span>
                        <button className="share-btn-enhanced" onClick={handleShare}>
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"></path>
                                <polyline points="16 6 12 2 8 6"></polyline>
                                <line x1="12" y1="2" x2="12" y2="15"></line>
                            </svg>
                            Поделиться
                        </button>
                    </p>
                </div>
                <button
                    className={`privacy-toggle-btn ${!isStatsPublic ? "private" : ""}`}
                    onClick={toggleStatsPrivacy}
                    title={isStatsPublic ? "Статистика видна всем" : "Статистика скрыта"}
                >
                    {isStatsPublic ? "👁️" : "🔒"}
                </button>
            </div>

            {/* Statistics Section */}
            {stats && (
                <div className={`profile-stats ${!isStatsPublic ? "opacity-50" : ""}`}>
                    <div className="stat-item">
                        <span className="stat-val">{stats.total_trips}</span>
                        <span className="stat-lbl">Поездок</span>
                    </div>
                    <div className="stat-item">
                        <span className="stat-val">{stats.unique_countries}</span>
                        <span className="stat-lbl">Стран</span>
                    </div>
                    <div className="stat-item">
                        <span className="stat-val">{stats.unique_cities}</span>
                        <span className="stat-lbl">Городов</span>
                    </div>
                    <div className="stat-item">
                        <span className="stat-val">{stats.total_days}</span>
                        <span className="stat-lbl">Дней</span>
                    </div>
                </div>
            )}

            {/* Tabs Navigation */}
            <div className="profile-tabs">
                <button
                    className={`profile-tab ${activeTab === "checklists" ? "active" : ""}`}
                    onClick={() => setActiveTab("checklists")}
                >
                    📝 Чеклисты
                </button>
                <button
                    className={`profile-tab ${activeTab === "achievements" ? "active" : ""}`}
                    onClick={() => setActiveTab("achievements")}
                >
                    🏆 Достижения и статистика
                </button>
            </div>

            {/* Achievements & Feedback Tab */}
            {activeTab === "achievements" && (
                <div className="tab-content animations-fade">
                    {achievements && (
                        <div className="achievements-section">
                            <h3 className="profile-section-title">
                                Мои достижения
                                <span className="achievement-counter">{achievements.unlocked_count}/{achievements.achievements.length}</span>
                            </h3>
                            <div className="achievements-grid">
                                {achievements.achievements.map((a) => (
                                    <div key={a.id} className={`achievement-card ${a.unlocked ? "unlocked" : "locked"}`}>
                                        <div className="achievement-icon">{a.icon}</div>
                                        <div className="achievement-name">{a.name_ru}</div>
                                        <div className="achievement-desc">{a.desc_ru}</div>
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
                            <h3 className="profile-section-title">📊 Ваши предпочтения</h3>
                            <div className="feedback-columns">
                                {feedback.top_added.length > 0 && (
                                    <div className="feedback-col">
                                        <h4>✅ Часто добавляете</h4>
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
                                        <h4>❌ Часто удаляете</h4>
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
                    {loading && <div className="profile-loading">Загрузка...</div>}
                    {error && <div className="profile-error">{error}</div>}

                    {!loading && !error && checklists.length === 0 && (
                        <div className="profile-empty-list">
                            <p>У вас пока нет сохранённых чеклистов</p>
                            <button className="action-btn primary" onClick={() => navigate("/")}>
                                ✨ Создать первый чеклист
                            </button>
                        </div>
                    )}

                    <div className="checklists-grid">
                        {checklists.map((cl) => (
                            <div
                                key={cl.slug}
                                className="checklist-preview-card"
                                onClick={() => navigate(`/checklist/${cl.slug}`)}
                            >
                                <div className="card-actions">
                                    <button
                                        className={`privacy-btn ${!cl.is_public ? "private" : ""}`}
                                        onClick={(e) => toggleChecklistPrivacy(e, cl.slug, cl.is_public)}
                                        title={cl.is_public ? "Публичный" : "Скрытый"}
                                    >
                                        {cl.is_public ? "👁️" : "🔒"}
                                    </button>
                                    <button
                                        className="delete-btn"
                                        onClick={(e) => deleteChecklist(e, cl.slug)}
                                        title="Удалить чеклист"
                                    >
                                        ✕
                                    </button>
                                </div>
                                <div className="preview-city">📍 {cl.city}</div>
                                <div className="preview-dates">
                                    {formatDate(cl.start_date)} — {formatDate(cl.end_date)}
                                </div>
                                <div className="preview-temp">
                                    {cl.avg_temp > 0 ? "+" : ""}{Math.round(cl.avg_temp)}°C
                                </div>
                                <div className="preview-items">
                                    {cl.items.length} {cl.items.length === 1 ? "вещь" : cl.items.length < 5 ? "вещи" : "вещей"}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default ProfilePage;
