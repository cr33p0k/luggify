import React, { Suspense } from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';

import App from './App.jsx';
import PublicProfilePage from './PublicProfilePage.jsx';
import JoinPage from './JoinPage.jsx';

const TmaApp = React.lazy(() => import('./tma/TmaApp.jsx'));

const tmaFallback = (
  <div style={{
    minHeight: '100vh',
    display: 'grid',
    placeItems: 'center',
    background: '#090908',
    color: '#f4f1ea',
    fontFamily: 'sans-serif'
  }}>
    Luggify
  </div>
);

ReactDOM.createRoot(document.getElementById('root')).render(
  <BrowserRouter>
    <Routes>
      <Route path="/" element={<App />} />
      <Route path="/checklist/:id" element={<App />} />
      <Route path="/profile" element={<App page="profile" />} />
      <Route
        path="/tma"
        element={(
          <Suspense fallback={tmaFallback}>
            <TmaApp />
          </Suspense>
        )}
      />
      <Route path="/u/:username" element={<PublicProfilePage />} />
      <Route path="/join/:token" element={<JoinPage />} />
    </Routes>
  </BrowserRouter>
);
