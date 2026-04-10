import React, { useState, useRef, useEffect } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function AIChatWidget({ city, startDate, endDate, avgTemp, tripType, language = "ru" }) {
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [suggestions, setSuggestions] = useState([]);
    const messagesEndRef = useRef(null);
    const inputRef = useRef(null);

    useEffect(() => {
        if (isOpen && messages.length === 0) {
            // Load suggestions
            fetch(`${API_URL}/ai/suggestions?language=${language}`)
                .then(r => r.json())
                .then(data => setSuggestions(data.suggestions || []))
                .catch(() => {});
            
            // Add welcome message
            setMessages([{
                role: "ai",
                text: language === "ru" 
                    ? `Привет! 👋 Я ваш AI-помощник для поездки в **${city}**. Спросите меня о ресторанах, достопримечательностях, транспорте или культурных особенностях!`
                    : `Hi! 👋 I'm your AI travel assistant for **${city}**. Ask me about restaurants, sights, transport or cultural tips!`
            }]);
        }
    }, [isOpen, city, language, messages.length]);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    useEffect(() => {
        if (isOpen) {
            inputRef.current?.focus();
        }
    }, [isOpen]);

    const askQuestion = async (question) => {
        if (!question.trim() || loading) return;

        const userMsg = { role: "user", text: question };
        setMessages(prev => [...prev, userMsg]);
        setInput("");
        setLoading(true);

        try {
            const res = await fetch(`${API_URL}/ai/ask`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    city,
                    question,
                    language,
                    start_date: startDate || "",
                    end_date: endDate || "",
                    avg_temp: avgTemp || null,
                    trip_type: tripType || "vacation",
                }),
            });

            const data = await res.json();
            
            setMessages(prev => [...prev, {
                role: "ai",
                text: data.answer || "Не удалось получить ответ"
            }]);

            if (data.suggestions?.length) {
                setSuggestions(data.suggestions);
            }
        } catch {
            setMessages(prev => [...prev, {
                role: "ai",
                text: "⚠️ Ошибка соединения. Попробуйте ещё раз."
            }]);
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        askQuestion(input);
    };

    // Floating button
    if (!isOpen) {
        return (
            <button
                className="ai-fab"
                onClick={() => setIsOpen(true)}
                title={language === "ru" ? "AI-помощник" : "AI Assistant"}
            >
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
                <span className="ai-fab-badge">AI</span>
            </button>
        );
    }

    return (
        <div className="ai-chat-overlay">
            <div className="ai-chat-widget">
                {/* Header */}
                <div className="ai-chat-header">
                    <div className="ai-chat-header-info">
                        <div className="ai-chat-avatar">🤖</div>
                        <div>
                            <div className="ai-chat-title">AI-помощник</div>
                            <div className="ai-chat-subtitle">{city}</div>
                        </div>
                    </div>
                    <button className="ai-chat-close" onClick={() => setIsOpen(false)}>×</button>
                </div>

                {/* Messages */}
                <div className="ai-chat-messages">
                    {messages.map((msg, i) => (
                        <div key={i} className={`ai-msg ${msg.role}`}>
                            <div className="ai-msg-bubble" style={{ whiteSpace: "pre-wrap" }}>
                                {msg.text.split('**').map((part, j) => 
                                    j % 2 === 0 ? part : <strong key={j}>{part}</strong>
                                )}
                            </div>
                        </div>
                    ))}

                    {loading && (
                        <div className="ai-msg ai">
                            <div className="ai-msg-bubble ai-typing">
                                <span /><span /><span />
                            </div>
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>

                {/* Suggestions */}
                {suggestions.length > 0 && messages.length <= 2 && (
                    <div className="ai-suggestions">
                        {suggestions.map((q, i) => (
                            <button
                                key={i}
                                className="ai-suggestion-btn"
                                onClick={() => askQuestion(q)}
                                disabled={loading}
                            >
                                {q}
                            </button>
                        ))}
                    </div>
                )}

                {/* Input */}
                <form className="ai-chat-input-area" onSubmit={handleSubmit}>
                    <input
                        ref={inputRef}
                        className="ai-chat-input"
                        type="text"
                        placeholder={language === "ru" ? "Задайте вопрос о городе..." : "Ask about the city..."}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        disabled={loading}
                    />
                    <button
                        className="ai-chat-send"
                        type="submit"
                        disabled={!input.trim() || loading}
                    >
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                        </svg>
                    </button>
                </form>
            </div>
        </div>
    );
}
