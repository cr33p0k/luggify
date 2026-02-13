import React, { useState } from "react";
import "./AuthModal.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function AuthModal({ onClose, onAuth }) {
    const [tab, setTab] = useState("login"); // "login" | "register"
    const [email, setEmail] = useState("");
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError("");
        setLoading(true);

        try {
            const url =
                tab === "login"
                    ? `${API_URL}/auth/login`
                    : `${API_URL}/auth/register`;

            const body =
                tab === "login"
                    ? { email, password }
                    : { email, username, password };

            const res = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });

            const data = await res.json();

            if (!res.ok) {
                setError(data.detail || "Ошибка авторизации");
                setLoading(false);
                return;
            }

            // Сохраняем токен и данные пользователя
            localStorage.setItem("token", data.access_token);
            localStorage.setItem("user", JSON.stringify(data.user));
            onAuth(data.user, data.access_token);
            onClose();
        } catch (err) {
            setError("Ошибка сети. Проверьте подключение.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="auth-overlay" onClick={onClose}>
            <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
                <button className="auth-close" onClick={onClose}>
                    ×
                </button>

                <div className="auth-tabs">
                    <button
                        className={`auth-tab ${tab === "login" ? "active" : ""}`}
                        onClick={() => { setTab("login"); setError(""); }}
                    >
                        Вход
                    </button>
                    <button
                        className={`auth-tab ${tab === "register" ? "active" : ""}`}
                        onClick={() => { setTab("register"); setError(""); }}
                    >
                        Регистрация
                    </button>
                </div>

                <form className="auth-form" onSubmit={handleSubmit}>
                    <div className="auth-field">
                        <label>Email</label>
                        <input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="example@mail.com"
                            required
                            autoComplete="email"
                        />
                    </div>

                    {tab === "register" && (
                        <div className="auth-field">
                            <label>Имя пользователя</label>
                            <input
                                type="text"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                placeholder="username"
                                required
                                autoComplete="username"
                            />
                        </div>
                    )}

                    <div className="auth-field">
                        <label>Пароль</label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="••••••••"
                            required
                            minLength={4}
                            autoComplete={tab === "login" ? "current-password" : "new-password"}
                        />
                    </div>

                    {error && <div className="auth-error">{error}</div>}

                    <button className="auth-submit" type="submit" disabled={loading}>
                        {loading
                            ? "Загрузка..."
                            : tab === "login"
                                ? "Войти"
                                : "Зарегистрироваться"}
                    </button>
                </form>
            </div>
        </div>
    );
}
