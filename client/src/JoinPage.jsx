import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import './JoinPage.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const JoinPage = () => {
  const { token } = useParams();
  const navigate = useNavigate();
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const handleJoin = async () => {
      const authToken = localStorage.getItem("token");
      if (!authToken) {
        setError("Пожалуйста, войдите в аккаунт или зарегистрируйтесь, чтобы присоединиться к чеклисту.");
        setLoading(false);
        return;
      }

      try {
        const res = await fetch(`${API_URL}/join/${token}`, {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${authToken}`
          }
        });

        if (!res.ok) {
          const data = await res.json();
          throw new Error(data.detail || "Неверная ссылка или ошибка сервера");
        }

        const data = await res.json();
        navigate(`/checklist/${data.slug}`);
      } catch (err) {
        setError(err.message);
        setLoading(false);
      }
    };

    handleJoin();
  }, [token, navigate]);

  return (
    <div className="join-page">
      <div className="join-card">
        <div className="join-badge">🔗</div>
        <h2 className="join-title">Присоединение к чеклисту</h2>
        <p className="join-subtitle">
          {loading
            ? 'Проверяем приглашение и подключаем поездку к вашему аккаунту.'
            : 'Не удалось автоматически присоединить вас к поездке.'}
        </p>

        {loading ? (
          <div className="join-spinner" aria-label="Загрузка" />
        ) : (
          <div className="join-error-block">
            <p className="join-error-text">{error}</p>
            {!localStorage.getItem("token") && (
              <button
                className="join-action-btn"
                onClick={() => navigate('/')}
              >
                На главную и войти
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default JoinPage;
