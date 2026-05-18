import React, { Suspense } from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { resolveInitialTheme } from './appUtils.js';

const App = React.lazy(() => import('./App.jsx'));
const PublicProfilePage = React.lazy(() => import('./PublicProfilePage.jsx'));
const JoinPage = React.lazy(() => import('./JoinPage.jsx'));
const TmaApp = React.lazy(() => import('./tma/TmaApp.jsx'));

const initialTheme = resolveInitialTheme();

if (typeof document !== 'undefined') {
  document.documentElement.dataset.theme = initialTheme;
}

const routeFallback = (
  <div style={{
    minHeight: '100vh',
    display: 'grid',
    placeItems: 'center',
    background: initialTheme === 'light'
      ? 'linear-gradient(180deg, #f8f3eb 0%, #efe6d8 100%)'
      : 'linear-gradient(180deg, #17120d 0%, #0d0a08 100%)',
    color: initialTheme === 'light' ? '#2d241c' : '#f4f1ea',
    fontFamily: '"Manrope", sans-serif'
  }}>
    Luggify
  </div>
);

ReactDOM.createRoot(document.getElementById('root')).render(
  <BrowserRouter>
    <Suspense fallback={routeFallback}>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/checklist/:id" element={<App />} />
        <Route path="/profile" element={<App page="profile" />} />
        <Route path="/tma" element={<TmaApp />} />
        <Route path="/u/:username" element={<PublicProfilePage />} />
        <Route path="/join/:token" element={<JoinPage />} />
      </Routes>
    </Suspense>
  </BrowserRouter>
);

if (import.meta.env.PROD && typeof window !== "undefined" && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}
