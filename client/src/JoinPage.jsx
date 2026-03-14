import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

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
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', background: '#0d0d0d', color: '#f0f0f0', fontFamily: 'Inter, sans-serif' }}>
      <h2>🔗 Присоединение...</h2>
      {loading ? (
         <div style={{ marginTop: "20px", width: "40px", height: "40px", border: "4px solid rgba(255, 153, 0, 0.3)", borderTopColor: "#ff9900", borderRadius: "50%", animation: "spin 1s linear infinite" }}>
            <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
         </div>
      ) : (
         <div style={{ marginTop: '20px', color: '#ff4d4d', textAlign: 'center', maxWidth: '400px' }}>
           <p>{error}</p>
           {!localStorage.getItem("token") && (
             <button 
               onClick={() => navigate('/')} 
               style={{ marginTop: '20px', padding: '10px 20px', background: '#ff9900', color: '#0d0d0d', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold' }}
             >
               На главную (Войти)
             </button>
           )}
         </div>
      )}
    </div>
  );
};

export default JoinPage;
