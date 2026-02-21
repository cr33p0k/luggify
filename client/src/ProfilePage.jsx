import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./ProfilePage.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const ProfilePage = ({ user, token, onLogout }) => {
    const navigate = useNavigate();
    const [checklists, setChecklists] = useState([]);
    const [stats, setStats] = useState(null);
    const [achievements, setAchievements] = useState(null);
    const [feedback, setFeedback] = useState(null);
    const [isStatsPublic, setIsStatsPublic] = useState(user?.is_stats_public ?? true);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

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
            const res = await fetch(`${API_URL}/my-stats/privacy`, {
                method: "PATCH",
                headers: {
                    Authorization: `Bearer ${token}`,
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ is_stats_public: !isStatsPublic }),
            });
            if (res.ok) {
                setIsStatsPublic(!isStatsPublic);
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

    const handleShare = () => {
        const url = `${window.location.origin}/u/${user.username}`;
        navigator.clipboard.writeText(url);
        alert("Ссылка скопирована!");
    };

    return (
        <div className="profile-page">
            <div className="profile-header">
                <div className="profile-avatar">
                    {user.username.charAt(0).toUpperCase()}
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
                    <p style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                        {checklists.length} {checklists.length === 0 ? "чеклистов" : checklists.length === 1 ? "чеклист" : checklists.length < 5 ? "чеклиста" : "чеклистов"}
                        <button className="share-btn-text" onClick={handleShare}>🔗 Поделиться</button>
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

            {/* Achievements Section */}
            {achievements && (
                <div className="achievements-section">
                    <h3 className="profile-section-title">
                        🏆 Достижения
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

            {/* Feedback Preferences */}
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

            <h3 className="profile-section-title">Мои чеклисты</h3>

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
    );
};

export default ProfilePage;
