import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./ProfilePage.css";
import { TRANSLATIONS, pluralize } from "./i18n";
import { EyeIcon, LockIcon, ListIcon, TrophyIcon, BarChartIcon, CheckCircleIcon, XCricleIcon, SparkleIcon } from "./Icons";
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const renderSocialIcon = (network) => {
    switch(network) {
        case 'instagram': return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line></svg>;
        case 'telegram': return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>;
        case 'twitter': return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 4s-.7 2.1-2 3.4c1.6 10-9.4 17.3-18 11.6 2.2.1 4.4-.6 6-2C3 15.5.5 9.6 3 5c2.2 2.6 5.6 4.1 9 4-.9-4.2 4-6.6 7-3.8 1.1 0 3-1.2 3-1.2z"></path></svg>;
        case 'linkedin': return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"></path><rect x="2" y="9" width="4" height="12"></rect><circle cx="4" cy="4" r="2"></circle></svg>;
        case 'website': return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>;
        default: return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>;
    }
};

const ProfilePage = ({ user, token, onLogout, onUpdateUser, lang = "ru" }) => {
    const t = TRANSLATIONS[lang] || TRANSLATIONS.ru;
    const navigate = useNavigate();
    const [checklists, setChecklists] = useState([]);
    const [stats, setStats] = useState(null);
    const [achievements, setAchievements] = useState(null);
    const [feedback, setFeedback] = useState(null);
    const [followers, setFollowers] = useState([]);
    const [following, setFollowing] = useState([]);
    const [followRequests, setFollowRequests] = useState([]);
    const [isStatsPublic, setIsStatsPublic] = useState(user?.is_stats_public ?? true);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [activeTab, setActiveTab] = useState("checklists"); // "checklists" | "achievements" | "followers" | "following"
    const [avatar, setAvatar] = useState(user?.avatar || "");
    const [editMode, setEditMode] = useState(false);
    const [bio, setBio] = useState(user?.bio || "");
    const [socialLinks, setSocialLinks] = useState(user?.social_links || {});
    const [saving, setSaving] = useState(false);
    const [isAvatarModalOpen, setIsAvatarModalOpen] = useState(false);
    
    // Check if the current viewer is the owner of this profile
    const currentUserStr = window.localStorage.getItem('user');
    const currentUser = currentUserStr ? JSON.parse(currentUserStr) : null;
    const isOwner = user && currentUser && user.username === currentUser.username;

    useEffect(() => {
        if (!token) return;
        const fetchData = async () => {
            try {
                // Checklists
                const resCl = await fetch(`${API_URL}/my-checklists`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (resCl.status === 401) {
                    onLogout();
                    return;
                }
                if (!resCl.ok) throw new Error(t.failedToLoadChecklists);
                const dataCl = await resCl.json();
                setChecklists(dataCl);

                // Stats
                const resStats = await fetch(`${API_URL}/my-stats`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (resStats.ok) {
                    const dataStats = await resStats.json();
                    setStats(dataStats);
                }

                // Achievements
                const resAch = await fetch(`${API_URL}/my-achievements`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (resAch.ok) {
                    const dataAch = await resAch.json();
                    setAchievements(dataAch);
                }

                // Feedback
                const resFb = await fetch(`${API_URL}/my-feedback-stats`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (resFb.ok) {
                    const dataFb = await resFb.json();
                    setFeedback(dataFb);
                }

                // Followers
                if (user?.username) {
                    const resFollowers = await fetch(`${API_URL}/users/${user.username}/followers`, {
                        headers: { Authorization: `Bearer ${token}` },
                    });
                    if (resFollowers.ok) {
                        setFollowers(await resFollowers.json());
                    }

                    const resFollowing = await fetch(`${API_URL}/users/${user.username}/following`, {
                        headers: { Authorization: `Bearer ${token}` },
                    });
                    if (resFollowing.ok) {
                        setFollowing(await resFollowing.json());
                    }

                    // Follow requests (only for own profile)
                    const resRequests = await fetch(`${API_URL}/follow-requests`, {
                        headers: { Authorization: `Bearer ${token}` },
                    });
                    if (resRequests.ok) {
                        setFollowRequests(await resRequests.json());
                    }
                }
            } catch (e) {
                console.error(e);
                setError(e.message);
            } finally {
                setLoading(false);
            }
        };
        fetchData();

        // Sync privacy state
        if (user) setIsStatsPublic(user.is_stats_public);
    }, [token, user, onLogout, t.failedToLoadChecklists]);

    const formatDate = (iso) => {
        const d = new Date(iso);
        return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.${d.getFullYear()}`;
    };

    const deleteChecklist = async (e, slug) => {
        e.stopPropagation();
        if (!window.confirm(t.deleteChecklistPrompt)) return;
        try {
            const res = await fetch(`${API_URL}/checklist/${slug}`, {
                method: "DELETE",
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                setChecklists((prev) => prev.filter((c) => c.slug !== slug));
            }
        } catch (e) {
            console.error(e);
        }
    };

    const toggleStatsPrivacy = async () => {
        try {
            const res = await fetch(`${API_URL}/auth/privacy`, {
                method: "PATCH",
                headers: {
                    Authorization: `Bearer ${token}`,
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ is_stats_public: !isStatsPublic }),
            });
            if (res.ok) {
                setIsStatsPublic(!isStatsPublic);
                if (onUpdateUser) {
                    onUpdateUser({ ...user, is_stats_public: !isStatsPublic });
                }
            }
        } catch (e) {
            console.error(e);
        }
    };

    const toggleChecklistPrivacy = async (e, slug, current) => {
        e.stopPropagation();
        try {
            const res = await fetch(`${API_URL}/checklist/${slug}/privacy`, {
                method: "PATCH",
                headers: {
                    Authorization: `Bearer ${token}`,
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ is_public: !current }),
            });
            if (res.ok) {
                setChecklists((prev) =>
                    prev.map((c) =>
                        c.slug === slug ? { ...c, is_public: !current } : c
                    )
                );
            }
        } catch (e) {
            console.error(e);
        }
    };


    const handleSaveProfile = async () => {
        setSaving(true);
        try {
            const res = await fetch(`${API_URL}/auth/me`, {
                method: "PATCH",
                headers: {
                    Authorization: `Bearer ${token}`,
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ bio, social_links: socialLinks }),
            });
            if (res.ok) {
                const updatedUser = await res.json();
                if (onUpdateUser) {
                    onUpdateUser(updatedUser);
                }
                setEditMode(false);
            } else {
                console.error("Failed to update profile");
            }
        } catch (e) {
            console.error(e);
        } finally {
            setSaving(false);
        }
    };

    const fileInputRef = React.useRef(null);

    const handleShare = () => {
        const url = `${window.location.origin}/u/${user.username}`;
        navigator.clipboard.writeText(url);
        alert(t.linkCopied);
    };

    const handleAvatarClick = () => {
        if (editMode) {
            if (fileInputRef.current) fileInputRef.current.click();
        } else if (avatar && (avatar.startsWith("data:image") || avatar.startsWith("http"))) {
            setIsAvatarModalOpen(true);
        }
    };

    const handleFileChange = (e) => {
        const file = e.target.files?.[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (ev) => {
            const img = new Image();
            img.onload = async () => {
                const canvas = document.createElement("canvas");
                const MAX_SIZE = 256;
                let width = img.width;
                let height = img.height;

                if (width > height) {
                    if (width > MAX_SIZE) {
                        height *= MAX_SIZE / width;
                        width = MAX_SIZE;
                    }
                } else {
                    if (height > MAX_SIZE) {
                        width *= MAX_SIZE / height;
                        height = MAX_SIZE;
                    }
                }

                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext("2d");
                ctx.drawImage(img, 0, 0, width, height);
                const dataUrl = canvas.toDataURL("image/jpeg", 0.9);

                try {
                    const res = await fetch(`${API_URL}/auth/avatar`, {
                        method: "PATCH",
                        headers: {
                            Authorization: `Bearer ${token}`,
                            "Content-Type": "application/json",
                        },
                        body: JSON.stringify({ avatar: dataUrl }),
                    });
                    if (res.ok) {
                        setAvatar(dataUrl);
                        if (onUpdateUser) {
                            onUpdateUser({ ...user, avatar: dataUrl });
                        }
                    }
                } catch (err) {
                    console.error(err);
                }
            };
            img.src = ev.target.result;
        };
        reader.readAsDataURL(file);
    };

    const handleFollowToggle = async (targetUsername, currentIsFollowing) => {
        try {
            const method = currentIsFollowing ? "DELETE" : "POST";
            const res = await fetch(`${API_URL}/users/${targetUsername}/follow`, {
                method,
                headers: { Authorization: `Bearer ${token}` }
            });
            if (res.ok) {
                // Refresh lists
                const resFollowers = await fetch(`${API_URL}/users/${user.username}/followers`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (resFollowers.ok) setFollowers(await resFollowers.json());

                const resFollowing = await fetch(`${API_URL}/users/${user.username}/following`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (resFollowing.ok) setFollowing(await resFollowing.json());
            }
        } catch (e) {
            console.error(e);
        }
    };

    return (
        <div className="profile-page">
            <div className="profile-header">
                <div className="profile-top-actions">
                    <button className="top-action-icon" onClick={handleShare} title={t.shareString}>
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"></path>
                            <polyline points="16 6 12 2 8 6"></polyline>
                            <line x1="12" y1="2" x2="12" y2="15"></line>
                        </svg>
                    </button>
                    {!editMode && (
                        <button className="top-action-icon" onClick={() => setEditMode(true)} title={t.editProfile}>
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path></svg>
                        </button>
                    )}
                    <button
                        className={`top-action-icon ${!isStatsPublic ? "private" : ""}`}
                        onClick={toggleStatsPrivacy}
                        title={isStatsPublic ? t.statsPublic : t.statsHidden}
                    >
                        {isStatsPublic ? <EyeIcon style={{marginRight:0}}/> : <LockIcon style={{marginRight:0}}/>}
                    </button>
                </div>

                <div className="profile-main-row">
                    <input
                    type="file"
                    accept="image/*"
                    ref={fileInputRef}
                    style={{ display: "none" }}
                    onChange={handleFileChange}
                />
                <div className="profile-avatar" onClick={handleAvatarClick} title={editMode ? t.uploadAvatar : ""} style={{ cursor: 'pointer' }}>
                    {avatar && (avatar.startsWith("data:image") || avatar.startsWith("http")) ? (
                        <img src={avatar} alt="Avatar" style={{ width: "100%", height: "100%", borderRadius: "50%", objectFit: "cover" }} />
                    ) : (
                        avatar ? avatar : user.username.charAt(0).toUpperCase()
                    )}
                </div>
                    
                    <div className="profile-stats-block">
                        <div className="profile-stat-col" onClick={() => setActiveTab("checklists")}>
                            <span className="profile-stat-count">{checklists.length}</span>
                            <span className="profile-stat-string">{lang === 'en' ? 'Lists' : 'Чеклисты'}</span>
                        </div>
                        <div className="profile-stat-col" onClick={() => setActiveTab("followers")}>
                            <span className="profile-stat-count">{user?.followers_count || followers.length}</span>
                            <span className="profile-stat-string">{t.followersStat}</span>
                        </div>
                        <div className="profile-stat-col" onClick={() => setActiveTab("following")}>
                            <span className="profile-stat-count">{user?.following_count || following.length}</span>
                            <span className="profile-stat-string">{t.followingStat}</span>
                        </div>
                    </div>
                </div>

                <div className="profile-info-block">
                    <div className="profile-name-row">
                        <h2>
                            {user.username}
                            {achievements && (
                                <span className="level-badge">
                                    {achievements.level.icon} {lang === 'en' ? achievements.level.name_en : achievements.level.name_ru}
                                </span>
                            )}
                        </h2>
                    </div>

                    {editMode ? (
                        <div className="profile-edit-form">
                            <label className="edit-label">{t.bio}</label>
                            <textarea 
                                className="edit-input bio-input" 
                                value={bio} 
                                onChange={e => setBio(e.target.value)} 
                                rows={3}
                                placeholder="..."
                            />

                            <label className="edit-label">{t.socialLinks}</label>
                            <div className="social-inputs">
                                {['instagram', 'telegram', 'twitter', 'linkedin', 'website'].map(net => (
                                    <div key={net} className="social-input-wrapper">
                                        <div className="social-input-icon">{renderSocialIcon(net)}</div>
                                        <input 
                                            className="edit-input social-input" 
                                            type="text" 
                                            placeholder={`${net} id`} 
                                            value={socialLinks[net] || ""} 
                                            onChange={e => setSocialLinks({...socialLinks, [net]: e.target.value})}
                                        />
                                    </div>
                                ))}
                            </div>

                            <div className="edit-actions">
                                <button className="btn-secondary" onClick={() => {
                                    setEditMode(false);
                                    setBio(user?.bio || "");
                                    setSocialLinks(user?.social_links || {});
                                }}>
                                    {t.cancelEdit}
                                </button>
                                <button className="btn-primary" onClick={handleSaveProfile} disabled={saving}>
                                    {saving ? '...' : t.saveProfile}
                                </button>
                            </div>
                        </div>
                    ) : (
                        <div className="profile-details-view">
                            {(!isOwner && !isStatsPublic) ? (
                                <div className="private-profile-notice" style={{marginTop: "1rem", color: "#888", display: "flex", alignItems: "center", gap: "0.5rem"}}>
                                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
                                    <span>{lang === 'en' ? 'This profile is private' : 'Это закрытый профиль'}</span>
                                </div>
                            ) : (
                                <>
                                    {user?.bio && <p className="profile-bio">{user.bio}</p>}
                                    {user?.social_links && Object.keys(user.social_links).some(k => user.social_links[k]) && (
                                        <div className="profile-social-icons">
                                            {Object.entries(user.social_links).map(([net, link]) => {
                                                if (!link) return null;
                                                const href = link.startsWith('http') ? link : (net === 'telegram' ? `https://t.me/${link.replace('@','')}` : (net === 'instagram' ? `https://instagram.com/${link.replace('@','')}` : `https://${link}`));
                                                return (
                                                    <a key={net} href={href} target="_blank" rel="noopener noreferrer" className={`social-badge ${net}`} title={net}>
                                                        {renderSocialIcon(net)}
                                                    </a>
                                                );
                                            })}
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    )}
                </div>
            </div>

            {/* Statistics Section */}
            {(isOwner || isStatsPublic) && stats && (
                <div className="profile-stats">
                    <div className="stat-item">
                        <span className="stat-val">{stats.total_trips}</span>
                        <span className="stat-lbl">{t.tripsStat}</span>
                    </div>
                    <div className="stat-item">
                        <span className="stat-val">{stats.unique_countries}</span>
                        <span className="stat-lbl">{t.countriesStat}</span>
                    </div>
                    <div className="stat-item">
                        <span className="stat-val">{stats.unique_cities}</span>
                        <span className="stat-lbl">{t.citiesStat}</span>
                    </div>
                    <div className="stat-item">
                        <span className="stat-val">{stats.total_days}</span>
                        <span className="stat-lbl">{t.daysStat}</span>
                    </div>
                </div>
            )}

            {/* Tabs Navigation */}
            {(isOwner || isStatsPublic) && (
                <div className="profile-tabs">
                    <button
                        className={`profile-tab ${activeTab === "checklists" ? "active" : ""}`}
                        onClick={() => setActiveTab("checklists")}
                    >
                        <span style={{display:'flex',alignItems:'center',justifyContent:'center'}}><ListIcon style={{width:'18px',height:'18px',marginRight:'6px'}}/> {t.profileChecklists}</span>
                    </button>
                    <button
                        className={`profile-tab ${activeTab === "achievements" ? "active" : ""}`}
                        onClick={() => setActiveTab("achievements")}
                    >
                        <span style={{display:'flex',alignItems:'center',justifyContent:'center'}}><TrophyIcon style={{width:'18px',height:'18px',marginRight:'6px'}}/> {t.profileAchievementsAndStats}</span>
                    </button>
                    <button
                        className={`profile-tab ${activeTab === "followers" ? "active" : ""}`}
                        onClick={() => setActiveTab("followers")}
                    >
                        {t.followersTab}
                    </button>
                    <button
                        className={`profile-tab ${activeTab === "following" ? "active" : ""}`}
                        onClick={() => setActiveTab("following")}
                    >
                        {t.followingTab}
                    </button>
                </div>
            )}

            {/* Achievements & Feedback Tab */}
            {(isOwner || isStatsPublic) && activeTab === "achievements" && (
                <div className="tab-content animations-fade">
                    {achievements && (
                        <div className="achievements-section">
                            <h3 className="profile-section-title">
                                {t.myAchievements}
                                <span className="achievement-counter">{achievements.unlocked_count}/{achievements.achievements.length}</span>
                            </h3>
                            <div className="achievements-grid">
                                {achievements.achievements.map((a) => (
                                    <div key={a.id} className={`achievement-card ${a.unlocked ? "unlocked" : "locked"}`}>
                                        <div className="achievement-icon">{a.icon}</div>
                                        <div className="achievement-name">{lang === 'en' ? a.name_en : a.name_ru}</div>
                                        <div className="achievement-desc">{lang === 'en' ? a.desc_en : a.desc_ru}</div>
                                        <div className="achievement-progress-bar">
                                            <div
                                                className="achievement-progress-fill"
                                                style={{ width: `${a.progress * 100}%` }}
                                            />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {feedback && (feedback.top_removed.length > 0 || feedback.top_added.length > 0) && (
                        <div className="feedback-section">
                            <h3 className="profile-section-title" style={{display:'flex',alignItems:'center'}}><BarChartIcon /> {t.yourPreferences}</h3>
                            <div className="feedback-columns">
                                {feedback.top_added.length > 0 && (
                                    <div className="feedback-col">
                                        <h4 style={{display:'flex',alignItems:'center'}}><CheckCircleIcon style={{color:'var(--success)',width:'18px',height:'18px',marginRight:'6px'}}/> {t.frequentlyAdded}</h4>
                                        {feedback.top_added.map((item, i) => (
                                            <div key={i} className="feedback-item added">
                                                <span>{item.item}</span>
                                                <span className="feedback-count">×{item.count}</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                                {feedback.top_removed.length > 0 && (
                                    <div className="feedback-col">
                                        <h4 style={{display:'flex',alignItems:'center'}}><XCricleIcon style={{color:'var(--error)',width:'18px',height:'18px',marginRight:'6px'}}/> {t.frequentlyRemoved}</h4>
                                        {feedback.top_removed.map((item, i) => (
                                            <div key={i} className="feedback-item removed">
                                                <span>{item.item}</span>
                                                <span className="feedback-count">×{item.count}</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Checklists Tab */}
            {(isOwner || isStatsPublic) && activeTab === "checklists" && (
                <div className="tab-content animations-fade">
                    {loading && <div className="profile-loading">{t.loadingStr}</div>}
                    {error && <div className="profile-error">{error}</div>}

                    {!loading && !error && checklists.length === 0 && (
                        <div className="profile-empty-list">
                            <p>{t.noChecklists}</p>
                            <button className="action-btn primary" onClick={() => navigate("/")} style={{display:'flex',alignItems:'center',justifyContent:'center'}}>
                                <SparkleIcon style={{width:'18px',height:'18px',marginRight:'6px'}}/> {t.createFirstChecklist}
                            </button>
                        </div>
                    )}

                    <div className="checklists-grid">
                        {checklists.map((cl) => {
                            const isOwner = cl.user_id === user?.id;
                            const isShared = !isOwner || (cl.backpacks && cl.backpacks.length > 0);
                            return (
                            <div
                                key={cl.slug}
                                className="checklist-preview-card"
                                onClick={() => navigate(`/checklist/${cl.slug}`)}
                            >
                                <div className="card-actions">
                                    {isOwner && (
                                        <>
                                            <button
                                                className="delete-btn"
                                                onClick={(e) => deleteChecklist(e, cl.slug)}
                                                title={t.deleteChecklistBtn}
                                            >
                                                ✕
                                            </button>
                                            <button
                                                className={`privacy-btn ${!cl.is_public ? "private" : ""}`}
                                                onClick={(e) => toggleChecklistPrivacy(e, cl.slug, cl.is_public)}
                                                title={cl.is_public ? t.publicStatus : t.hiddenStatus}
                                            >
                                                {cl.is_public ? <EyeIcon style={{marginRight:0}}/> : <LockIcon style={{marginRight:0}}/>}
                                            </button>
                                        </>
                                    )}
                                </div>
                                <div className="preview-city">{cl.city}{isShared && <span className="shared-badge" title={lang === 'en' ? 'Shared checklist' : 'Совместный чеклист'}>👥</span>}</div>
                                <div className="preview-dates">
                                    {formatDate(cl.start_date)} — {formatDate(cl.end_date)}
                                </div>
                                <div className="preview-temp">
                                    {cl.avg_temp > 0 ? "+" : ""}{Math.round(cl.avg_temp)}°C
                                </div>
                                <div className="preview-items">
                                    {pluralize(cl.items.length, ['вещь', 'вещи', 'вещей'], ['item', 'items'], lang)}
                                </div>
                            </div>
                        );
                        })}
                    </div>
                </div>
            )}

            {/* Followers Tab */}
            {(isOwner || isStatsPublic) && activeTab === "followers" && (
                <div className="tab-content animations-fade">
                    {/* Sub-tabs: Followers + Requests */}
                    {isOwner && !isStatsPublic && followRequests.length > 0 && (
                        <div className="follow-requests-section">
                            <h3 className="profile-section-title" style={{display: 'flex', alignItems: 'center', gap: '0.5rem'}}>
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="8.5" cy="7" r="4"></circle><line x1="20" y1="8" x2="20" y2="14"></line><line x1="23" y1="11" x2="17" y2="11"></line></svg>
                                {lang === 'en' ? 'Follow Requests' : 'Запросы на подписку'}
                                <span className="achievement-counter">{followRequests.length}</span>
                            </h3>
                            <div className="subscriptions-list">
                                {followRequests.map(req => (
                                    <div key={req.id} className="subscription-card">
                                        <div className="subscription-avatar" onClick={() => navigate(`/u/${req.from_user.username}`)}>
                                            {req.from_user.avatar ? (
                                                <img src={req.from_user.avatar} alt="Avatar" />
                                            ) : (
                                                req.from_user.username.charAt(0).toUpperCase()
                                            )}
                                        </div>
                                        <div className="subscription-info" onClick={() => navigate(`/u/${req.from_user.username}`)}>
                                            <div className="subscription-name">{req.from_user.username}</div>
                                        </div>
                                        <div className="subscription-action" style={{display: 'flex', gap: '0.5rem'}}>
                                            <button 
                                                className="action-btn primary"
                                                onClick={async () => {
                                                    try {
                                                        const res = await fetch(`${API_URL}/follow-requests/${req.id}/accept`, {
                                                            method: 'POST',
                                                            headers: { Authorization: `Bearer ${token}` }
                                                        });
                                                        if (res.ok) {
                                                            setFollowRequests(prev => prev.filter(r => r.id !== req.id));
                                                            // Refresh followers list
                                                            const resF = await fetch(`${API_URL}/users/${user.username}/followers`, {
                                                                headers: { Authorization: `Bearer ${token}` }
                                                            });
                                                            if (resF.ok) setFollowers(await resF.json());
                                                        }
                                                    } catch(e) { console.error(e); }
                                                }}
                                            >
                                                {lang === 'en' ? 'Accept' : 'Принять'}
                                            </button>
                                            <button 
                                                className="action-btn secondary"
                                                onClick={async () => {
                                                    try {
                                                        const res = await fetch(`${API_URL}/follow-requests/${req.id}/decline`, {
                                                            method: 'POST',
                                                            headers: { Authorization: `Bearer ${token}` }
                                                        });
                                                        if (res.ok) {
                                                            setFollowRequests(prev => prev.filter(r => r.id !== req.id));
                                                        }
                                                    } catch(e) { console.error(e); }
                                                }}
                                            >
                                                {lang === 'en' ? 'Decline' : 'Отклонить'}
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Followers list */}
                    {followers.length === 0 ? (
                        <div className="profile-empty-list">
                            <p>{t.subsEmptyState}</p>
                        </div>
                    ) : (
                        <div className="subscriptions-list">
                            {followers.map(f => (
                                <div key={f.id} className="subscription-card" onClick={() => navigate(`/u/${f.username}`)}>
                                    <div className="subscription-avatar">
                                        {f.avatar ? (
                                            <img src={f.avatar} alt="Avatar" />
                                        ) : (
                                            f.username.charAt(0).toUpperCase()
                                        )}
                                    </div>
                                    <div className="subscription-info">
                                        <div className="subscription-name">{f.username}</div>
                                    </div>
                                    <div className="subscription-action" onClick={(e) => e.stopPropagation()}>
                                        <button 
                                            className={`action-btn ${f.is_following ? "secondary" : "primary"}`}
                                            onClick={() => handleFollowToggle(f.username, f.is_following)}
                                        >
                                            {f.is_following ? t.unfollowBtn : t.followBackBtn}
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Following Tab */}
            {(isOwner || isStatsPublic) && activeTab === "following" && (
                <div className="tab-content animations-fade">
                    {following.length === 0 ? (
                        <div className="profile-empty-list">
                            <p>{t.subsEmptyState}</p>
                        </div>
                    ) : (
                        <div className="subscriptions-list">
                            {following.map(f => (
                                <div key={f.id} className="subscription-card" onClick={() => navigate(`/u/${f.username}`)}>
                                    <div className="subscription-avatar">
                                        {f.avatar ? (
                                            <img src={f.avatar} alt="Avatar" />
                                        ) : (
                                            f.username.charAt(0).toUpperCase()
                                        )}
                                    </div>
                                    <div className="subscription-info">
                                        <div className="subscription-name">{f.username}</div>
                                    </div>
                                    <div className="subscription-action" onClick={(e) => e.stopPropagation()}>
                                        <button 
                                            className="action-btn secondary"
                                            onClick={() => handleFollowToggle(f.username, true)}
                                        >
                                            {t.unfollowBtn}
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {isAvatarModalOpen && (
                <div className="avatar-modal-overlay" onClick={() => setIsAvatarModalOpen(false)}>
                    <div className="avatar-modal-content" onClick={e => e.stopPropagation()}>
                        <img src={avatar} alt="Avatar Large" className="avatar-modal-img" />
                    </div>
                </div>
            )}
        </div>
    );
};

export default ProfilePage;
