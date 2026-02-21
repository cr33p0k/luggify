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

    useEffect(() => {
        const fetchProfile = async () => {
            try {
                const res = await fetch(`${API_URL}/users/${username}`);
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
                <div className="profile-avatar">
                    {profile.username.charAt(0).toUpperCase()}
                </div>
                <div className="profile-info">
                    <h2>{profile.username}</h2>
                    <p>На Luggify с {formatDate(profile.created_at)}</p>
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
