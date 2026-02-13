import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./ProfilePage.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const ProfilePage = ({ user, token, onLogout }) => {
    const navigate = useNavigate();
    const [checklists, setChecklists] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        if (!token) return;
        const fetchChecklists = async () => {
            try {
                const res = await fetch(`${API_URL}/my-checklists`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (!res.ok) throw new Error("Не удалось загрузить чеклисты");
                const data = await res.json();
                setChecklists(data);
            } catch (e) {
                console.error(e);
                setError(e.message);
            } finally {
                setLoading(false);
            }
        };
        fetchChecklists();
    }, [token]);

    const formatDate = (iso) => {
        const d = new Date(iso);
        return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.${d.getFullYear()}`;
    };

    if (!user) {
        return (
            <div className="profile-empty">
                <h2>Вы не авторизованы</h2>
                <p>Войдите, чтобы видеть сохранённые чеклисты</p>
            </div>
        );
    }

    const deleteChecklist = async (e, slug) => {
        e.stopPropagation();
        if (!window.confirm("Вы уверены, что хотите удалить этот чеклист?")) return;

        try {
            const res = await fetch(`${API_URL}/checklist/${slug}`, {
                method: "DELETE",
                headers: { Authorization: `Bearer ${token}` },
            });

            if (res.status === 204 || res.ok) {
                setChecklists((prev) => prev.filter((cl) => cl.slug !== slug));
            } else {
                alert("Не удалось удалить чеклист");
            }
        } catch (error) {
            console.error("Ошибка при удалении:", error);
            alert("Ошибка при удалении");
        }
    };

    return (
        <div className="profile-page">
            <div className="profile-header">
                <div className="profile-avatar">
                    {user.username.charAt(0).toUpperCase()}
                </div>
                <div className="profile-info">
                    <h2>{user.username}</h2>
                    <p>{checklists.length} {checklists.length === 1 ? "чеклист" : checklists.length < 5 ? "чеклиста" : "чеклистов"}</p>
                </div>
            </div>

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
                        <button
                            className="delete-btn"
                            onClick={(e) => deleteChecklist(e, cl.slug)}
                            title="Удалить чеклист"
                        >
                            ✕
                        </button>
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
