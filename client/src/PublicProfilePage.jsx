import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import "./ProfilePage.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const PublicProfilePage = () => {
    const { username } = useParams();
    const navigate = useNavigate();
    const [profile, setProfile] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    
    // Auth context
    const token = localStorage.getItem("token");
    const storedUser = localStorage.getItem("user");
    const currentUser = storedUser ? JSON.parse(storedUser) : null;
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
    }, [username]);

    const formatDate = (iso) => {
        const d = new Date(iso);
        return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.${d.getFullYear()}`;
    };

    const handleShare = () => {
        const url = `${window.location.origin}/u/${username}`;
        navigator.clipboard.writeText(url);
        alert("Ссылка скопирована!");
    };

    const handleFollowToggle = async () => {
        if (!token) {
            navigate("/?auth=login"); // or wherever the login trigger is
            return;
        }
        
        try {
            const method = profile.is_following ? "DELETE" : "POST";
            const res = await fetch(`${API_URL}/users/${username}/follow`, {
                method,
                headers: { Authorization: `Bearer ${token}` }
            });
            if (res.ok) {
                setProfile(prev => ({
                    ...prev,
                    is_following: !prev.is_following,
                    followers_count: prev.is_following ? prev.followers_count - 1 : prev.followers_count + 1
                }));
            }
        } catch (e) {
            console.error(e);
        }
    };

    if (loading) return <div className="profile-loading">Загрузка...</div>;
    if (error) return (
        <div className="profile-error">
            <h2>😕 {error}</h2>
            <button className="action-btn" onClick={() => navigate("/")}>На главную</button>
        </div>
    );

    return (
        <div className="profile-page">
            <nav className="navbar" style={{ marginBottom: "2rem", padding: 0 }}>
                <div className="navbar-logo" onClick={() => navigate("/")}>
                    <span>🧳</span> Luggify
                </div>
            </nav>

            <div className="profile-header">
                <div className="profile-top-actions">
                    <button className="top-action-icon" onClick={() => handleShare()} title="Поделиться">
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"></path>
                            <polyline points="16 6 12 2 8 6"></polyline>
                            <line x1="12" y1="2" x2="12" y2="15"></line>
                        </svg>
                    </button>
                </div>

                <div className="profile-main-row">
                    <div className="profile-avatar">
                        {profile.avatar && (profile.avatar.startsWith("data:image") || profile.avatar.startsWith("http")) ? (
                            <img src={profile.avatar} alt="Avatar" style={{ width: "100%", height: "100%", borderRadius: "50%", objectFit: "cover" }} />
                        ) : (
                            profile.avatar ? profile.avatar : profile.username.charAt(0).toUpperCase()
                        )}
                    </div>
                
                    <div className="profile-stats-block">
                        <div className="profile-stat-col">
                            <span className="profile-stat-count">{profile.checklists?.length || 0}</span>
                            <span className="profile-stat-string">Чеклисты</span>
                        </div>
                        <div className="profile-stat-col">
                            <span className="profile-stat-count">{profile.followers_count || 0}</span>
                            <span className="profile-stat-string">Подписчиков</span>
                        </div>
                        <div className="profile-stat-col">
                            <span className="profile-stat-count">{profile.following_count || 0}</span>
                            <span className="profile-stat-string">Подписок</span>
                        </div>
                    </div>
                </div>

                <div className="profile-info-block">
                    <h2>{profile.username}</h2>
                    <p className="profile-bio-date">На Luggify с {formatDate(profile.created_at)}</p>
                    
                    {/* Follow Button */}
                    {!isSelf && (
                        <div className="profile-action-mt">
                            <button 
                                className={`action-btn wide-btn ${profile.is_following ? "secondary" : "primary"}`}
                                onClick={handleFollowToggle}
                            >
                                {profile.is_following ? "Отписаться" : "Подписаться"}
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {profile.is_stats_public && profile.stats && (
                <div className="profile-stats">
                    <div className="stat-item">
                        <span className="stat-val">{profile.stats.total_trips}</span>
                        <span className="stat-lbl">Поездок</span>
                    </div>
                    <div className="stat-item">
                        <span className="stat-val">{profile.stats.unique_countries}</span>
                        <span className="stat-lbl">Стран</span>
                    </div>
                    <div className="stat-item">
                        <span className="stat-val">{profile.stats.unique_cities}</span>
                        <span className="stat-lbl">Городов</span>
                    </div>
                    <div className="stat-item">
                        <span className="stat-val">{profile.stats.total_days}</span>
                        <span className="stat-lbl">Дней</span>
                    </div>
                </div>
            )}

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
                            <div className="preview-city">📍 {cl.city}</div>
                            <div className="preview-dates">
                                {formatDate(cl.start_date)} — {formatDate(cl.end_date)}
                            </div>
                            <div className="preview-temp">
                                {cl.avg_temp > 0 ? "+" : ""}{Math.round(cl.avg_temp)}°C
                            </div>
                            <div className="preview-items">
                                {cl.items.length} вещей
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default PublicProfilePage;
