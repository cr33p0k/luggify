import React, { useEffect, useRef, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const TELEGRAM_BOT_USERNAME = import.meta.env.VITE_TELEGRAM_BOT_USERNAME || "luggify_bot";
const TELEGRAM_WIDGET_SRC = "https://telegram.org/js/telegram-widget.js?22";

const isLocalTelegramLoginHost = () => {
    if (typeof window === "undefined") return false;
    const host = window.location.hostname;
    if (!host) return true;
    if (host === "localhost" || host === "127.0.0.1" || host === "::1") return true;
    if (/^10\./.test(host)) return true;
    if (/^192\.168\./.test(host)) return true;
    if (/^172\.(1[6-9]|2\d|3[0-1])\./.test(host)) return true;
    return false;
};

export default function AuthModal({ onClose, onAuth }) {
    const [tab, setTab] = useState("login"); // "login" | "register"
    const [email, setEmail] = useState("");
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");
    const [loading, setLoading] = useState(false);
    const [telegramLoading, setTelegramLoading] = useState(false);
    const localTelegramWidgetBlocked = isLocalTelegramLoginHost();

    // Email verification state
    const [showVerification, setShowVerification] = useState(false);
    const [verificationCode, setVerificationCode] = useState("");
    const [pendingUser, setPendingUser] = useState(null);
    const [pendingToken, setPendingToken] = useState(null);

    // Device verification state
    const [showDeviceVerification, setShowDeviceVerification] = useState(false);
    const [rememberDevice, setRememberDevice] = useState(true);

    const getDeviceId = () => {
        let id = localStorage.getItem("device_id");
        if (!id) {
            id = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 15);
            localStorage.setItem("device_id", id);
        }
        return id;
    };
    const deviceId = getDeviceId();

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError("");
        setSuccess("");
        setLoading(true);

        try {
            const url =
                tab === "login"
                    ? `${API_URL}/auth/login`
                    : `${API_URL}/auth/register`;

            const body =
                tab === "login"
                    ? { email, password, device_id: deviceId, user_agent: navigator.userAgent }
                    : { email, username, password };

            const res = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });

            const data = await res.json();

            if (!res.ok && res.status !== 202) {
                setError(data.detail || "Ошибка авторизации");
                setLoading(false);
                return;
            }

            if (res.status === 202 && data.status === "verification_required") {
                setShowDeviceVerification(true);
                setSuccess(data.message);
                setLoading(false);
                return;
            }

            if (tab === "register") {
                // Show verification screen
                setPendingUser(data.user);
                setPendingToken(data.access_token);
                setShowVerification(true);
                if (data.email_delivery_failed) {
                    setError(
                        data.message ||
                        "Аккаунт создан, но письмо пока не отправлено. Проверьте настройки почты сервера и нажмите 'Отправить ещё раз'."
                    );
                } else {
                    setSuccess(data.message || "Код подтверждения отправлен на " + email);
                }
            } else {
                // Login — directly authenticate
                localStorage.setItem("token", data.access_token);
                localStorage.setItem("user", JSON.stringify(data.user));
                onAuth(data.user, data.access_token);
                onClose();
            }
        } catch {
            setError("Ошибка сети. Проверьте подключение.");
        } finally {
            setLoading(false);
        }
    };

    const handleVerify = async (e) => {
        e.preventDefault();
        setError("");
        setSuccess("");
        setLoading(true);

        try {
            const res = await fetch(`${API_URL}/auth/verify-email`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, code: verificationCode, device_id: deviceId, user_agent: navigator.userAgent }),
            });

            const data = await res.json();

            if (!res.ok) {
                setError(data.detail || "Ошибка верификации");
                setLoading(false);
                return;
            }

            // Verification successful — log the user in
            if (pendingToken && pendingUser) {
                const updatedUser = { ...pendingUser, is_email_verified: true };
                localStorage.setItem("token", pendingToken);
                localStorage.setItem("user", JSON.stringify(updatedUser));
                onAuth(updatedUser, pendingToken);
                onClose();
            }
        } catch {
            setError("Ошибка сети");
        } finally {
            setLoading(false);
        }
    };

    const handleResend = async () => {
        setError("");
        setSuccess("");
        setLoading(true);

        try {
            const res = await fetch(`${API_URL}/auth/resend-code`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email }),
            });

            const data = await res.json();

            if (!res.ok) {
                setError(data.detail || "Не удалось отправить код");
            } else {
                setSuccess("Код отправлен повторно на " + email);
            }
        } catch {
            setError("Ошибка сети");
        } finally {
            setLoading(false);
        }
    };

    const handleSkipVerification = () => {
        // Allow user to skip and log in without verifying
        if (pendingToken && pendingUser) {
            localStorage.setItem("token", pendingToken);
            localStorage.setItem("user", JSON.stringify(pendingUser));
            onAuth(pendingUser, pendingToken);
            onClose();
        }
    };

    const handleVerifyDevice = async (e) => {
        e.preventDefault();
        setError("");
        setSuccess("");
        setLoading(true);

        try {
            const res = await fetch(`${API_URL}/auth/verify-device-login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    email,
                    password,
                    code: verificationCode,
                    device_id: deviceId,
                    remember_device: rememberDevice,
                    user_agent: navigator.userAgent
                }),
            });

            const data = await res.json();

            if (!res.ok) {
                setError(data.detail || "Ошибка верификации устройства");
                setLoading(false);
                return;
            }

            localStorage.setItem("token", data.access_token);
            localStorage.setItem("user", JSON.stringify(data.user));
            onAuth(data.user, data.access_token);
            onClose();
        } catch {
            setError("Ошибка сети");
        } finally {
            setLoading(false);
        }
    };

    const inputRefs = useRef([]);
    const telegramWidgetRef = useRef(null);
    const telegramAuthHandlerRef = useRef(null);

    const handlePinChange = (index, value) => {
        const digit = value.replace(/\D/g, '');
        if (!digit && value !== '') return;

        const newCode = verificationCode.split('');
        while(newCode.length < 6) newCode.push('');

        newCode[index] = digit;

        const result = newCode.join('').substring(0, 6);
        setVerificationCode(result);

        // Advance focus
        if (digit && index < 5 && inputRefs.current[index + 1]) {
            inputRefs.current[index + 1].focus();
        }
    };

    const handlePinKeyDown = (index, e) => {
        if (e.key === 'Backspace' && !verificationCode[index] && index > 0) {
            inputRefs.current[index - 1].focus();
        }
    };

    const handlePinPaste = (e) => {
        e.preventDefault();
        const pastedData = e.clipboardData.getData('text/plain').replace(/\D/g, '').substring(0, 6);
        if (pastedData) {
            setVerificationCode(pastedData);
            const focusIndex = Math.min(pastedData.length, 5);
            if (inputRefs.current[focusIndex]) {
                inputRefs.current[focusIndex].focus();
            }
        }
    };

    const handleTelegramAuth = async (telegramUser) => {
        if (!telegramUser) return;

        setError("");
        setSuccess("");
        setTelegramLoading(true);

        try {
            const res = await fetch(`${API_URL}/auth/telegram`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    tg_id: String(telegramUser.id),
                    first_name: telegramUser.first_name,
                    last_name: telegramUser.last_name,
                    username: telegramUser.username,
                    photo_url: telegramUser.photo_url,
                    auth_date: String(telegramUser.auth_date || ""),
                    hash: telegramUser.hash,
                }),
            });

            const data = await res.json();
            if (!res.ok) {
                setError(data.detail || "Не удалось войти через Telegram");
                return;
            }

            localStorage.setItem("token", data.access_token);
            localStorage.setItem("user", JSON.stringify(data.user));
            onAuth(data.user, data.access_token);
            onClose();
        } catch {
            setError("Ошибка Telegram-авторизации. Попробуйте ещё раз.");
        } finally {
            setTelegramLoading(false);
        }
    };

    telegramAuthHandlerRef.current = handleTelegramAuth;

    useEffect(() => {
        window.onTelegramAuthLuggify = (telegramUser) => {
            telegramAuthHandlerRef.current?.(telegramUser);
        };
        return () => {
            delete window.onTelegramAuthLuggify;
        };
    }, []);

    useEffect(() => {
        if (showVerification || showDeviceVerification || !telegramWidgetRef.current || localTelegramWidgetBlocked) return;

        const container = telegramWidgetRef.current;
        container.innerHTML = "";

        const script = document.createElement("script");
        script.async = true;
        script.src = TELEGRAM_WIDGET_SRC;
        script.setAttribute("data-telegram-login", TELEGRAM_BOT_USERNAME);
        script.setAttribute("data-size", "large");
        script.setAttribute("data-radius", "12");
        script.setAttribute("data-userpic", "false");
        script.setAttribute("data-request-access", "write");
        script.setAttribute("data-lang", "ru");
        script.setAttribute("data-onauth", "onTelegramAuthLuggify(user)");

        container.appendChild(script);

        return () => {
            container.innerHTML = "";
        };
    }, [showVerification, showDeviceVerification, tab, localTelegramWidgetBlocked]);

    // Verification screen
    if (showVerification || showDeviceVerification) {
        return (
            <div className="auth-overlay" onClick={onClose}>
                <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
                    <button className="auth-close" onClick={onClose}>×</button>

                    <div className="auth-title">
                        <span>{showDeviceVerification ? "Новое устройство" : "📧 Подтверждение"}</span>
                    </div>

                    <p className="auth-verify-copy">
                        {showDeviceVerification ? (
                            <>
                                Мы отправили новый код на<br/>
                                <strong className="auth-verify-email">{email}</strong><br/>
                                Введите его для входа.
                            </>
                        ) : (
                            <>
                                Мы отправили код подтверждения на<br/>
                                <strong className="auth-verify-email">{email}</strong>
                            </>
                        )}
                    </p>

                    <form className="auth-form" onSubmit={showDeviceVerification ? handleVerifyDevice : handleVerify}>
                        <div className="auth-pin-row">
                            {[0, 1, 2, 3, 4, 5].map((idx) => (
                                <input
                                    key={idx}
                                    ref={(el) => (inputRefs.current[idx] = el)}
                                    type="text"
                                    inputMode="numeric"
                                    className="auth-input auth-pin-input"
                                    maxLength={1}
                                    value={verificationCode[idx] || ''}
                                    onChange={(e) => handlePinChange(idx, e.target.value)}
                                    onKeyDown={(e) => handlePinKeyDown(idx, e)}
                                    onPaste={handlePinPaste}
                                    autoFocus={idx === 0}
                                    required={idx === 0}
                                />
                            ))}
                        </div>

                        {showDeviceVerification && (
                            <label className="auth-remember-device">
                                <input
                                    type="checkbox"
                                    checked={rememberDevice}
                                    onChange={(e) => setRememberDevice(e.target.checked)}
                                />
                                Запомнить это устройство
                            </label>
                        )}

                        {error && <div className="auth-error" style={{ marginTop: '12px' }}>{error}</div>}
                        {success && <div className="auth-success" style={{ marginTop: '12px' }}>{success}</div>}

                        <button
                            className="auth-submit"
                            type="submit"
                            disabled={loading || verificationCode.length !== 6}
                            style={{ marginTop: '16px' }}
                        >
                            {loading ? "Проверка..." : "Подтвердить"}
                        </button>

                        <div className="auth-secondary-actions">
                            <button
                                className="auth-secondary-btn accent"
                                type="button"
                                onClick={handleResend}
                                disabled={loading}
                            >
                                Отправить ещё раз
                            </button>
                            <button
                                className="auth-secondary-btn ghost"
                                type="button"
                                onClick={showDeviceVerification ? () => setShowDeviceVerification(false) : handleSkipVerification}
                            >
                                {showDeviceVerification ? 'К логину' : 'Пропустить'}
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        );
    }

    return (
        <div className="auth-overlay" onClick={onClose}>
            <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
                <button className="auth-close" onClick={onClose}>×</button>

                <div className="auth-title">
                    <span>🧳 Luggify</span>
                </div>

                <div className="auth-tabs">
                    <button
                        className={`auth-tab ${tab === "login" ? "active" : ""}`}
                        onClick={() => { setTab("login"); setError(""); setSuccess(""); }}
                    >
                        Вход
                    </button>
                    <button
                        className={`auth-tab ${tab === "register" ? "active" : ""}`}
                        onClick={() => { setTab("register"); setError(""); setSuccess(""); }}
                    >
                        Регистрация
                    </button>
                </div>

                <div className="auth-telegram-block">
                    <div className="auth-telegram-label">
                        {tab === "login" ? "Войти через Telegram" : "Продолжить через Telegram"}
                    </div>
                    <div className="auth-telegram-widget-shell">
                        {localTelegramWidgetBlocked ? (
                            <div className="auth-telegram-local-fallback">
                                <div className="auth-telegram-soon-icon">✈️</div>
                                <div className="auth-telegram-soon-text">Скоро</div>
                            </div>
                        ) : (
                            <div ref={telegramWidgetRef} className="auth-telegram-widget" />
                        )}
                    </div>
                    {!localTelegramWidgetBlocked && (
                        <div className="auth-telegram-hint">
                            Быстрый вход без почты и пароля.
                        </div>
                    )}
                </div>

                <div className="auth-divider">
                    <span>или</span>
                </div>

                <form className="auth-form" onSubmit={handleSubmit}>
                    <input
                        className="auth-input"
                        type="email"
                        placeholder="Email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                        autoFocus
                    />
                    {tab === "register" && (
                        <input
                            className="auth-input"
                            type="text"
                            placeholder="Имя пользователя"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            required
                        />
                    )}
                    <input
                        className="auth-input"
                        type="password"
                        placeholder="Пароль"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                    />
                    {error && <div className="auth-error">{error}</div>}
                    {success && <div className="auth-success">{success}</div>}
                    <button className="auth-submit" type="submit" disabled={loading || telegramLoading}>
                        {(loading || telegramLoading)
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
