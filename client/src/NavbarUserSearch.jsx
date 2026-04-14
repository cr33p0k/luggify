import React, { useEffect, useRef, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const NavbarUserSearch = ({ lang = "ru", navigate, currentUsername = "", compact = false }) => {
    const [query, setQuery] = useState("");
    const [results, setResults] = useState([]);
    const [isOpen, setIsOpen] = useState(false);
    const [loading, setLoading] = useState(false);
    const rootRef = useRef(null);
    const inputRef = useRef(null);

    useEffect(() => {
        const handleOutsideClick = (event) => {
            if (rootRef.current && !rootRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        };

        document.addEventListener("mousedown", handleOutsideClick);
        return () => document.removeEventListener("mousedown", handleOutsideClick);
    }, []);

    useEffect(() => {
        const trimmed = query.trim();
        if (trimmed.length < 1) {
            setResults([]);
            return;
        }

        const controller = new AbortController();
        const timer = setTimeout(async () => {
            setLoading(true);
            try {
                const res = await fetch(`${API_URL}/users/search?q=${encodeURIComponent(trimmed)}`, {
                    signal: controller.signal,
                });
                if (!res.ok) {
                    throw new Error("search_failed");
                }
                const data = await res.json();
                setResults(data);
                setIsOpen(true);
            } catch (e) {
                if (e.name !== "AbortError") {
                    console.error(e);
                    setResults([]);
                }
            } finally {
                setLoading(false);
            }
        }, 180);

        return () => {
            controller.abort();
            clearTimeout(timer);
        };
    }, [query]);

    useEffect(() => {
        if (compact && isOpen) {
            requestAnimationFrame(() => {
                inputRef.current?.focus();
            });
        }
    }, [compact, isOpen]);

    const openProfile = (username) => {
        setQuery("");
        setResults([]);
        setIsOpen(false);
        navigate(username === currentUsername ? "/profile" : `/u/${username}`);
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        const trimmed = query.trim();
        if (!trimmed) return;

        const exactMatch = results.find((item) => item.username.toLowerCase() === trimmed.toLowerCase());
        if (exactMatch) {
            openProfile(exactMatch.username);
            return;
        }

        navigate(`/u/${trimmed}`);
        setQuery("");
        setIsOpen(false);
    };

    const searchForm = (
        <form className={`navbar-search-form ${compact ? "compact" : ""}`} onSubmit={handleSubmit}>
            <svg className="navbar-search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onFocus={() => {
                    if (compact || results.length) setIsOpen(true);
                }}
                className="navbar-search-input"
                placeholder={lang === "en" ? "Search username" : "Поиск по нику"}
            />
        </form>
    );

    const searchDropdown = isOpen && (loading || query.trim().length > 0) ? (
        <div className="navbar-search-dropdown">
            {loading ? (
                <div className="navbar-search-empty">
                    {lang === "en" ? "Searching..." : "Ищем..."}
                </div>
            ) : results.length ? (
                results.map((item) => (
                    <button
                        key={item.id}
                        type="button"
                        className="navbar-search-result"
                        onClick={() => openProfile(item.username)}
                    >
                        <div className="navbar-search-avatar">
                            {item.avatar && (item.avatar.startsWith("data:image") || item.avatar.startsWith("http")) ? (
                                <img src={item.avatar} alt={item.username} style={{ width: "100%", height: "100%", objectFit: "cover", borderRadius: "50%" }} />
                            ) : (
                                item.username.charAt(0).toUpperCase()
                            )}
                        </div>
                        <div className="navbar-search-copy">
                            <strong>{item.username}</strong>
                            <span>{item.bio || (lang === "en" ? "Open profile" : "Открыть профиль")}</span>
                        </div>
                    </button>
                ))
            ) : (
                <div className="navbar-search-empty">
                    {lang === "en" ? "No users found" : "Никого не нашли"}
                </div>
            )}
        </div>
    ) : null;

    if (compact) {
        return (
            <div className="navbar-search compact" ref={rootRef}>
                <button
                    type="button"
                    className={`navbar-search-toggle ${isOpen ? "active" : ""}`}
                    onClick={() => setIsOpen((open) => !open)}
                    aria-label={lang === "en" ? "Search users" : "Поиск пользователей"}
                    title={lang === "en" ? "Search users" : "Поиск пользователей"}
                >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <circle cx="11" cy="11" r="8"></circle>
                        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                    </svg>
                </button>
                {isOpen && (
                    <div className="navbar-search-panel">
                        {searchForm}
                        {searchDropdown}
                    </div>
                )}
            </div>
        );
    }

    return (
        <div className="navbar-search" ref={rootRef}>
            {searchForm}
            {searchDropdown}
        </div>
    );
};

export default NavbarUserSearch;
