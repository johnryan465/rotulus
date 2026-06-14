import React, { useState, useEffect } from 'react';
import { 
  Database, Search, CheckCircle, Download, Image as ImageIcon, 
  BookOpen, UserCheck, RefreshCw, Sliders, ChevronRight, 
  Calendar, MapPin, Edit3, Save, Eye, Check, X, AlertCircle
} from 'lucide-react';

// Helper to determine API base path
const getApiUrl = (path) => {
  const isProd = import.meta.env.PROD;
  // In production (GitHub Pages), we use the static JSON files
  if (isProd) {
    // Mapping dynamic routes to static .json files
    if (path === '/api/rolls') return '/rotulus/api/rolls.json';
    if (path === '/api/travels') return '/rotulus/api/travels.json';
    if (path.startsWith('/api/rolls/')) {
      const id = path.split('/').pop();
      return `/rotulus/api/rolls/${id}.json`;
    }
    return `/rotulus${path}.json`;
  }
  // In development, we use the local FastAPI server via proxy
  return path;
};

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard'); // dashboard, explorer, verification, export
  const [rolls, setRolls] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  
  // Detail views
  const [selectedRollId, setSelectedRollId] = useState(null);
  const [rollDetail, setRollDetail] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  
  // Map states
  const mapInstanceRef = React.useRef(null);
  const [mapRollId, setMapRollId] = useState(null);
  const [travelPath, setTravelPath] = useState([]);
  const [allTravelsData, setAllTravelsData] = useState({});
  
  // Verification pane state
  const [activeVerificationIndex, setActiveVerificationIndex] = useState(0);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [pageBounds, setPageBounds] = useState([]);
  const [naturalDims, setNaturalDims] = useState({ width: 0, height: 0 });
  const [displayDims, setDisplayDims] = useState({ width: 0, height: 0 });
  const [hoveredBox, setHoveredBox] = useState(null);
  const imgRef = React.useRef(null);
  
  // Stats
  const [stats, setStats] = useState({
    total: 0,
    verified: 0,
    unverified: 0,
    percent: 0,
  });

  // Fetch all rolls
  const fetchRolls = async (query = '') => {
    setLoading(true);
    try {
      const url = query ? `/api/rolls?q=${encodeURIComponent(query)}` : '/api/rolls';
      const res = await fetch(url);
      const data = await res.json();
      setRolls(data);
      
      // Calculate stats
      const total = data.length;
      const verified = data.filter(r => r.is_verified).length;
      const unverified = total - verified;
      const percent = total > 0 ? Math.round((verified / total) * 100) : 0;
      setStats({ total, verified, unverified, percent });
    } catch (e) {
      console.error("Failed to fetch rolls:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRolls();
  }, []);

  useEffect(() => {
    if (activeTab !== 'map') return;
    if (rolls.length > 0 && !mapRollId) {
      setMapRollId('all');
    }
  }, [activeTab, rolls]);

  useEffect(() => {
    if (activeTab !== 'map' || !mapRollId) return;

    const fetchTravels = async () => {
      try {
        if (mapRollId === 'all') {
          const res = await fetch(`/rotulus/api/travels.json`);
          const data = await res.json();
          setAllTravelsData(data);

          setTimeout(() => {
            const container = document.getElementById('map-container');
            if (!container) return;

            if (mapInstanceRef.current) {
              mapInstanceRef.current.remove();
              mapInstanceRef.current = null;
            }

            const defaultCenter = [48.8566, 2.3522]; // Paris
            const defaultZoom = 4;

            if (!window.L) return;

            const map = window.L.map('map-container').setView(defaultCenter, defaultZoom);
            mapInstanceRef.current = map;

            window.L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
              attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
              subdomains: 'abcd',
              maxZoom: 20
            }).addTo(map);

            const colors = [
              '#6366f1', '#10b981', '#f59e0b', '#ec4899', '#3b82f6', 
              '#8b5cf6', '#84cc16', '#f97316', '#d946ef', '#06b6d4'
            ];
            let colorIdx = 0;
            const allCoords = [];

            Object.entries(data).forEach(([rId, rInfo]) => {
              const rollTravels = rInfo.travels;
              if (rollTravels.length === 0) return;

              const coords = rollTravels.map(t => t.coords).filter(c => c !== null && c !== undefined);
              allCoords.push(...coords);
              const color = colors[colorIdx % colors.length];
              colorIdx += 1;

              if (coords.length > 1) {
                window.L.polyline(coords, {
                  color: color,
                  weight: 2,
                  opacity: 0.6,
                  dashArray: '3, 6'
                }).addTo(map);
              }

              rollTravels.forEach((loc, index) => {
                if (!loc.coords) return; // Skip marker if no coordinates
                const isOrigin = loc.type === 'origin';
                const marker = window.L.circleMarker(loc.coords, {
                  radius: isOrigin ? 6 : 4,
                  fillColor: color,
                  color: '#ffffff',
                  weight: 1,
                  opacity: 0.8,
                  fillOpacity: 0.8
                }).addTo(map);

                const popupContent = `
                  <div style="color: #0f172a; font-family: sans-serif; padding: 4px; min-width: 150px;">
                    <h4 style="margin: 0 0 4px 0; font-size: 13px; font-weight: bold; color: ${color};">
                      Roll ${rInfo.roll_num} (${isOrigin ? '🚩 Origin' : `📍 Stop ${index}`})
                    </h4>
                    <p style="margin: 0 0 4px 0; font-size: 12px; font-weight: 500;">${loc.name}</p>
                    <p style="margin: 0; font-size: 10px; color: #64748b;">${loc.description}</p>
                  </div>
                `;
                marker.bindPopup(popupContent);
              });
            });

            if (allCoords.length > 0) {
              const bounds = window.L.latLngBounds(allCoords);
              map.fitBounds(bounds, { padding: [50, 50] });
            }
          }, 100);
        } else {
          const res = await fetch(`/api/rolls/${mapRollId}/travels`);
          const data = await res.json();
          setTravelPath(data);

          setTimeout(() => {
            const container = document.getElementById('map-container');
            if (!container) return;

            if (mapInstanceRef.current) {
              mapInstanceRef.current.remove();
              mapInstanceRef.current = null;
            }

            const defaultCenter = [48.8566, 2.3522]; // Paris
            const defaultZoom = 4;

            if (!window.L) return;

            const map = window.L.map('map-container').setView(defaultCenter, defaultZoom);
            mapInstanceRef.current = map;

            window.L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
              attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
              subdomains: 'abcd',
              maxZoom: 20
            }).addTo(map);

            if (data.length > 0) {
              const coords = data.map(t => t.coords).filter(c => c !== null && c !== undefined);

              if (coords.length > 1) {
                window.L.polyline(coords, {
                  color: 'var(--primary)',
                  weight: 3,
                  opacity: 0.8,
                  dashArray: '5, 10'
                }).addTo(map);
              }

              data.forEach((loc, index) => {
                if (!loc.coords) return; // Skip marker if no coordinates
                const isOrigin = loc.type === 'origin';
                const color = isOrigin ? '#6366f1' : '#10b981';

                const marker = window.L.circleMarker(loc.coords, {
                  radius: isOrigin ? 10 : 8,
                  fillColor: color,
                  color: '#ffffff',
                  weight: 2,
                  opacity: 1,
                  fillOpacity: 0.9
                }).addTo(map);

                const popupContent = `
                  <div style="color: #0f172a; font-family: sans-serif; padding: 4px; min-width: 150px;">
                    <h4 style="margin: 0 0 4px 0; font-size: 13px; font-weight: bold; color: ${color};">
                      ${isOrigin ? '🚩 Origin' : `📍 Stop ${index}`}
                    </h4>
                    <p style="margin: 0 0 4px 0; font-size: 12px; font-weight: 500;">${loc.name}</p>
                    <p style="margin: 0; font-size: 10px; color: #64748b;">${loc.description}</p>
                  </div>
                `;

                marker.bindPopup(popupContent);
              });

              if (coords.length > 0) {
                const bounds = window.L.latLngBounds(coords);
                map.fitBounds(bounds, { padding: [50, 50] });
              }
            }
          }, 100);
        }
      } catch (e) {
        console.error("Failed to fetch travels:", e);
      }
    };

    fetchTravels();

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [activeTab, mapRollId]);

  // Fetch page bounds for overlay
  useEffect(() => {
    if (activeTab !== 'verification' || !rollDetail) return;
    
    const fetchBounds = async () => {
      try {
        const pdfMatch = rollDetail.roll.pdf_source.match(/\((\d+)\)/);
        const pdfIdx = pdfMatch ? pdfMatch[1] : 1;
        const pages = rollDetail.roll.pdf_pages.split(',');
        const activePage = pages[activeVerificationIndex] || pages[0] || '3';
        const matchedTitulus = rollDetail.tituli.find(t => t.pdf_page === Number(activePage)) || rollDetail.tituli[0];
        const half = matchedTitulus ? matchedTitulus.pdf_half : 'left';
        
        const res = await fetch(`/api/image/${pdfIdx}/${activePage}/${half}/bounds`);
        const data = await res.json();
        setPageBounds(data);
      } catch (e) {
        console.error("Failed to fetch bounds:", e);
      }
    };
    
    fetchBounds();
  }, [activeTab, rollDetail, activeVerificationIndex]);

  // Fetch detailed roll info
  const fetchRollDetail = async (id) => {
    try {
      const res = await fetch(`/api/rolls/${id}`);
      const data = await res.json();
      setRollDetail(data);
    } catch (e) {
      console.error("Failed to fetch roll details:", e);
    }
  };

  const handleSelectRoll = (id) => {
    setSelectedRollId(id);
    fetchRollDetail(id);
    setIsEditing(false);
    // If we are in explorer, switch to verification view for this roll
    if (activeTab === 'explorer') {
      setActiveTab('verification');
    }
  };

  // Save changes
  const handleSaveRollMetadata = async () => {
    if (!rollDetail) return;
    try {
      const res = await fetch(`/api/rolls/${rollDetail.roll.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          roll_num: rollDetail.roll.roll_num,
          date_str: rollDetail.roll.date_str,
          title: rollDetail.roll.title,
          manuscripts: rollDetail.roll.manuscripts,
        })
      });
      if (res.ok) {
        setIsEditing(false);
        fetchRolls(searchQuery);
      }
    } catch (e) {
      console.error("Failed to save roll metadata:", e);
    }
  };

  const handleSaveTitulus = async (tit_id, title, latin_text) => {
    try {
      const res = await fetch(`/api/tituli/${tit_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, latin_text })
      });
      if (res.ok) {
        fetchRollDetail(selectedRollId);
      }
    } catch (e) {
      console.error("Failed to save titulus:", e);
    }
  };

  const handleSaveEntity = async (ent_id, ent_data) => {
    try {
      const res = await fetch(`/api/entities/${ent_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          normalized_name: ent_data.normalized_name,
          normalized_role: ent_data.normalized_role,
          normalized_dates: ent_data.normalized_dates,
          location_name: ent_data.location_name,
        })
      });
      if (res.ok) {
        fetchRollDetail(selectedRollId);
      }
    } catch (e) {
      console.error("Failed to save entity:", e);
    }
  };

  // Toggle Verification
  const handleToggleVerify = async (id) => {
    try {
      const res = await fetch(`/api/rolls/${id}/verify`, { method: 'POST' });
      const data = await res.json();
      if (rollDetail && rollDetail.roll.id === id) {
        setRollDetail(prev => ({
          ...prev,
          roll: { ...prev.roll, is_verified: data.is_verified }
        }));
      }
      fetchRolls(searchQuery);
    } catch (e) {
      console.error("Failed to toggle verify:", e);
    }
  };

  const triggerSearch = (e) => {
    e.preventDefault();
    fetchRolls(searchQuery);
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Sidebar */}
      <div className="glass-panel" style={{
        width: 'var(--sidebar-width)',
        margin: '16px',
        padding: '24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '24px',
        height: 'calc(100vh - 64px)',
        position: 'sticky',
        top: '16px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Database size={32} color="var(--primary)" />
          <div>
            <h2 style={{ margin: 0, fontSize: '20px', letterSpacing: '0.05em' }}>ANTIGRAVITY</h2>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>MORTUARY ROLLS DB</span>
          </div>
        </div>

        {/* Navigation */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', flex: 1 }}>
          <button 
            className={`btn-secondary ${activeTab === 'dashboard' ? 'glass-panel-interactive' : ''}`}
            style={{ justifyContent: 'flex-start', background: activeTab === 'dashboard' ? 'rgba(99, 102, 241, 0.15)' : 'transparent', borderColor: activeTab === 'dashboard' ? 'var(--primary)' : 'transparent' }}
            onClick={() => setActiveTab('dashboard')}
          >
            <BookOpen size={18} /> Dashboard
          </button>
          
          <button 
            className={`btn-secondary ${activeTab === 'explorer' ? 'glass-panel-interactive' : ''}`}
            style={{ justifyContent: 'flex-start', background: activeTab === 'explorer' ? 'rgba(99, 102, 241, 0.15)' : 'transparent', borderColor: activeTab === 'explorer' ? 'var(--primary)' : 'transparent' }}
            onClick={() => setActiveTab('explorer')}
          >
            <Search size={18} /> Search Explorer
          </button>
          
          <button 
            className={`btn-secondary ${activeTab === 'verification' ? 'glass-panel-interactive' : ''}`}
            style={{ justifyContent: 'flex-start', background: activeTab === 'verification' ? 'rgba(99, 102, 241, 0.15)' : 'transparent', borderColor: activeTab === 'verification' ? 'var(--primary)' : 'transparent' }}
            onClick={() => {
              setActiveTab('verification');
              if (rolls.length > 0 && !selectedRollId) {
                handleSelectRoll(rolls[0].id);
              }
            }}
          >
            <UserCheck size={18} /> Verification Hub
          </button>
          
          <button 
            className={`btn-secondary ${activeTab === 'export' ? 'glass-panel-interactive' : ''}`}
            style={{ justifyContent: 'flex-start', background: activeTab === 'export' ? 'rgba(99, 102, 241, 0.15)' : 'transparent', borderColor: activeTab === 'export' ? 'var(--primary)' : 'transparent' }}
            onClick={() => setActiveTab('export')}
          >
            <Download size={18} /> Export Data
          </button>

          <button 
            className={`btn-secondary ${activeTab === 'map' ? 'glass-panel-interactive' : ''}`}
            style={{ justifyContent: 'flex-start', background: activeTab === 'map' ? 'rgba(99, 102, 241, 0.15)' : 'transparent', borderColor: activeTab === 'map' ? 'var(--primary)' : 'transparent' }}
            onClick={() => setActiveTab('map')}
          >
            <MapPin size={18} /> Travel Map
          </button>
        </div>

        {/* Progress Card */}
        <div className="glass-panel" style={{ padding: '16px', background: 'rgba(255,255,255,0.02)', fontSize: '13px' }}>
          <div style={{ display: 'flex', justifyContent: 'between', marginBottom: '8px', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Verification Progress</span>
            <span style={{ fontWeight: 'bold' }}>{stats.percent}%</span>
          </div>
          <div style={{ width: '100%', height: '6px', background: 'rgba(255,255,255,0.1)', borderRadius: '3px', overflow: 'hidden' }}>
            <div style={{ width: `${stats.percent}%`, height: '100%', background: 'linear-gradient(90deg, var(--primary) 0%, var(--accent) 100%)' }}></div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '12px', fontSize: '11px', color: 'var(--text-muted)' }}>
            <span>Verified: {stats.verified}</span>
            <span>Total: {stats.total}</span>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div style={{ flex: 1, padding: '32px 32px 32px 0', overflowY: 'auto', maxHeight: '100vh' }}>
        
        {/* DASHBOARD TAB */}
        {activeTab === 'dashboard' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
            <div>
              <h1 style={{ fontSize: '32px', marginBottom: '8px' }}>Project Dashboard</h1>
              <p style={{ color: 'var(--text-secondary)', margin: 0 }}>Overview of parsed database records and verification metrics.</p>
            </div>

            {/* Stats Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px' }}>
              <div className="glass-panel" style={{ padding: '24px' }}>
                <span style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>Total Rolls</span>
                <h2 style={{ fontSize: '36px', margin: '8px 0 0 0' }}>{stats.total}</h2>
              </div>
              <div className="glass-panel" style={{ padding: '24px' }}>
                <span style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>Verified Rolls</span>
                <h2 style={{ fontSize: '36px', margin: '8px 0 0 0', color: 'var(--accent)' }}>{stats.verified}</h2>
              </div>
              <div className="glass-panel" style={{ padding: '24px' }}>
                <span style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>Pending Verification</span>
                <h2 style={{ fontSize: '36px', margin: '8px 0 0 0', color: '#fbbf24' }}>{stats.unverified}</h2>
              </div>
              <div className="glass-panel" style={{ padding: '24px' }}>
                <span style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>Completion Rate</span>
                <h2 style={{ fontSize: '36px', margin: '8px 0 0 0', color: 'var(--primary)' }}>{stats.percent}%</h2>
              </div>
            </div>

            {/* Recent / Unverified List */}
            <div className="glass-panel" style={{ padding: '24px' }}>
              <h3 style={{ marginBottom: '16px', fontSize: '18px' }}>Active Mortuary Rolls</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {rolls.slice(0, 10).map(roll => (
                  <div 
                    key={roll.id} 
                    className="glass-panel glass-panel-interactive" 
                    style={{ padding: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
                    onClick={() => handleSelectRoll(roll.id)}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                      <div className="glass-panel" style={{ padding: '10px 14px', background: 'rgba(99, 102, 241, 0.1)', borderColor: 'rgba(99,102,241,0.2)' }}>
                        <span style={{ fontWeight: 'bold', color: 'var(--primary)' }}>N° {roll.roll_num}</span>
                      </div>
                      <div>
                        <h4 style={{ margin: 0, fontSize: '15px' }}>{roll.title || "Untitled Roll"}</h4>
                        <div style={{ display: 'flex', gap: '16px', fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><Calendar size={12} /> {roll.date_str}</span>
                          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><Database size={12} /> PDF: {roll.pdf_source} (p. {roll.pdf_pages})</span>
                        </div>
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <span className={`badge ${roll.is_verified ? 'badge-success' : 'badge-warning'}`}>
                        {roll.is_verified ? 'Verified' : 'Pending'}
                      </span>
                      <ChevronRight size={18} color="var(--text-muted)" />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* SEARCH EXPLORER TAB */}
        {activeTab === 'explorer' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <div>
              <h1 style={{ fontSize: '32px', marginBottom: '8px' }}>Search Explorer</h1>
              <p style={{ color: 'var(--text-secondary)', margin: 0 }}>Advanced full-text search across rolls, tituli, footnotes, and entities.</p>
            </div>

            {/* Search Bar */}
            <form onSubmit={triggerSearch} style={{ display: 'flex', gap: '12px' }}>
              <input 
                type="text" 
                placeholder="Search by name, location, dates, Latin text, manuscripts..." 
                className="input-field"
                style={{ flex: 1 }}
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
              />
              <button type="submit" className="btn-primary">
                <Search size={18} /> Search
              </button>
            </form>

            {/* Search Results */}
            <div className="glass-panel" style={{ padding: '24px' }}>
              {loading ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <div className="skeleton-loader" style={{ height: '40px' }}></div>
                  <div className="skeleton-loader" style={{ height: '40px' }}></div>
                  <div className="skeleton-loader" style={{ height: '40px' }}></div>
                </div>
              ) : rolls.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
                  <AlertCircle size={48} style={{ margin: '0 auto 16px auto', display: 'block' }} />
                  <p>No rolls found matching your query.</p>
                </div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--panel-border)', color: 'var(--text-secondary)', fontSize: '13px' }}>
                        <th style={{ padding: '12px 16px' }}>Roll N°</th>
                        <th style={{ padding: '12px 16px' }}>Date</th>
                        <th style={{ padding: '12px 16px' }}>Title</th>
                        <th style={{ padding: '12px 16px' }}>Source PDF</th>
                        <th style={{ padding: '12px 16px' }}>Status</th>
                        <th style={{ padding: '12px 16px' }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rolls.map(roll => (
                        <tr key={roll.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.02)' }} className="glass-panel-interactive">
                          <td style={{ padding: '16px', fontWeight: 'bold' }}>{roll.roll_num}</td>
                          <td style={{ padding: '16px', color: 'var(--text-secondary)', fontSize: '14px' }}>{roll.date_str}</td>
                          <td style={{ padding: '16px', fontWeight: '500' }}>{roll.title || "Untitled Roll"}</td>
                          <td style={{ padding: '16px', color: 'var(--text-muted)', fontSize: '13px' }}>{roll.pdf_source} (p. {roll.pdf_pages})</td>
                          <td style={{ padding: '16px' }}>
                            <span className={`badge ${roll.is_verified ? 'badge-success' : 'badge-warning'}`}>
                              {roll.is_verified ? 'Verified' : 'Pending'}
                            </span>
                          </td>
                          <td style={{ padding: '16px' }}>
                            <button 
                              className="btn-secondary" 
                              style={{ padding: '6px 12px', fontSize: '12px' }}
                              onClick={() => handleSelectRoll(roll.id)}
                            >
                              Open in Editor
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* VERIFICATION HUB TAB */}
        {activeTab === 'verification' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h1 style={{ fontSize: '32px', marginBottom: '8px' }}>Verification Hub</h1>
                <p style={{ color: 'var(--text-secondary)', margin: 0 }}>Verify parsed rolls against original PDF page scans side-by-side.</p>
              </div>
              
              {/* Roll Selector */}
              <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                <span style={{ fontSize: '14px', color: 'var(--text-muted)' }}>Selected Roll:</span>
                <select 
                  className="input-field" 
                  value={selectedRollId || ''} 
                  onChange={e => handleSelectRoll(Number(e.target.value))}
                  style={{ background: '#0f172a', cursor: 'pointer' }}
                >
                  <option value="" disabled>Select a Roll</option>
                  {rolls.map(r => (
                    <option key={r.id} value={r.id}>
                      N° {r.roll_num} - {r.title ? r.title.substring(0, 40) : "Untitled"}...
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {rollDetail ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr', gap: '24px', height: 'calc(100vh - 200px)' }}>
                
                {/* Left Pane: Image Scan & Footnotes */}
                <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
                  <div style={{ 
                    padding: '16px', 
                    borderBottom: '1px solid var(--panel-border)', 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center',
                    background: 'rgba(255,255,255,0.02)'
                  }}>
                    <span style={{ fontWeight: '500', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <ImageIcon size={18} color="var(--primary)" />
                      PDF Source Scan: {rollDetail.roll.pdf_source} (p. {rollDetail.roll.pdf_pages})
                    </span>
                    
                    {/* Zoom controls */}
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button className="btn-secondary" style={{ padding: '4px 8px' }} onClick={() => setZoomLevel(z => Math.max(0.5, z - 0.2))}>-</button>
                      <span style={{ fontSize: '13px', alignSelf: 'center' }}>{Math.round(zoomLevel * 100)}%</span>
                      <button className="btn-secondary" style={{ padding: '4px 8px' }} onClick={() => setZoomLevel(z => Math.min(2.5, z + 0.2))}>+</button>
                    </div>
                  </div>
                  
                  {/* Dynamic Image Canvas */}
                  <div style={{ 
                    flex: 1, 
                    overflow: 'auto', 
                    background: '#04060a', 
                    display: 'flex', 
                    justifyContent: 'center', 
                    alignItems: 'center',
                    position: 'relative'
                  }}>
                    {/* Heuristically get the PDF Index, Page, and Half for image request */}
                    {(() => {
                      const pdfMatch = rollDetail.roll.pdf_source.match(/\((\d+)\)/);
                      const pdfIdx = pdfMatch ? pdfMatch[1] : 1;
                      const pages = rollDetail.roll.pdf_pages.split(',');
                      const activePage = pages[activeVerificationIndex] || pages[0] || '3';
                      // Try to fetch first titulus of this page/half to determine left/right
                      const matchedTitulus = rollDetail.tituli.find(t => t.pdf_page === Number(activePage)) || rollDetail.tituli[0];
                      const half = matchedTitulus ? matchedTitulus.pdf_half : 'left';
                      
                      const imageUrl = `/api/image/${pdfIdx}/${activePage}/${half}`;
                      
                      const scaleX = naturalDims.width > 0 ? displayDims.width / naturalDims.width : 1;
                      const scaleY = naturalDims.height > 0 ? displayDims.height / naturalDims.height : 1;
                      
                      return (
                        <div style={{
                          position: 'relative',
                          transform: `scale(${zoomLevel})`,
                          transformOrigin: 'center center',
                          transition: 'transform 0.1s ease',
                          display: 'inline-block'
                        }}>
                          <img 
                            ref={imgRef}
                            src={imageUrl} 
                            alt="Scanned manuscript page"
                            onLoad={(e) => {
                              const img = e.target;
                              setNaturalDims({ width: img.naturalWidth, height: img.naturalHeight });
                              setDisplayDims({ width: img.clientWidth, height: img.clientHeight });
                            }}
                            style={{
                              maxWidth: '100%',
                              display: 'block'
                            }} 
                          />
                          {/* Render Bounding Box Overlays */}
                          {pageBounds && pageBounds.map((box, idx) => (
                            <div
                              key={idx}
                              style={{
                                position: 'absolute',
                                left: `${box.x_min * scaleX}px`,
                                top: `${box.y_min * scaleY}px`,
                                width: `${(box.x_max - box.x_min) * scaleX}px`,
                                height: `${(box.y_max - box.y_min) * scaleY}px`,
                                border: hoveredBox === idx ? '2px solid var(--primary)' : '1px solid rgba(99, 102, 241, 0.3)',
                                background: hoveredBox === idx ? 'rgba(99, 102, 241, 0.15)' : 'rgba(99, 102, 241, 0.02)',
                                cursor: 'pointer',
                                transition: 'all 0.15s ease',
                                zIndex: hoveredBox === idx ? 10 : 1
                              }}
                              onMouseEnter={() => setHoveredBox(idx)}
                              onMouseLeave={() => setHoveredBox(null)}
                              title={box.text}
                            />
                          ))}
                          {/* Tooltip for hovered box */}
                          {hoveredBox !== null && pageBounds[hoveredBox] && (
                            <div style={{
                              position: 'absolute',
                              left: `${pageBounds[hoveredBox].x_min * scaleX}px`,
                              top: `${(pageBounds[hoveredBox].y_min * scaleY) - 36}px`,
                              background: '#0f172a',
                              color: '#ffffff',
                              border: '1px solid var(--panel-border)',
                              padding: '6px 12px',
                              borderRadius: '4px',
                              fontSize: '11px',
                              whiteSpace: 'nowrap',
                              zIndex: 100,
                              boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
                              transform: 'translateX(-25%)'
                            }}>
                              {pageBounds[hoveredBox].text} (conf: {Math.round(pageBounds[hoveredBox].confidence * 100)}%)
                            </div>
                          )}
                        </div>
                      );
                    })()}
                  </div>
                  
                  {/* Page Navigation Indicator */}
                  {rollDetail.roll.pdf_pages.split(',').length > 1 && (
                    <div style={{ padding: '12px', display: 'flex', gap: '8px', borderTop: '1px solid var(--panel-border)', justifyContent: 'center' }}>
                      {rollDetail.roll.pdf_pages.split(',').map((p, idx) => (
                        <button 
                          key={idx} 
                          className={`btn-secondary ${activeVerificationIndex === idx ? 'btn-primary' : ''}`}
                          style={{ padding: '6px 12px', fontSize: '12px' }}
                          onClick={() => setActiveVerificationIndex(idx)}
                        >
                          Page {p.strip ? p.strip() : p}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* Right Pane: Editable Structured Content */}
                <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px', overflowY: 'auto' }}>
                  
                  {/* Verification Status Header */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span className={`badge ${rollDetail.roll.is_verified ? 'badge-success' : 'badge-warning'}`}>
                      {rollDetail.roll.is_verified ? 'Verified Record' : 'Requires Verification'}
                    </span>
                    <button 
                      className={`btn-primary`} 
                      style={{ background: rollDetail.roll.is_verified ? '#dc2626' : 'var(--accent)' }}
                      onClick={() => handleToggleVerify(rollDetail.roll.id)}
                    >
                      {rollDetail.roll.is_verified ? <X size={16} /> : <Check size={16} />}
                      {rollDetail.roll.is_verified ? 'Unverify Roll' : 'Verify & Approve'}
                    </button>
                  </div>

                  {/* Roll Metadata Section */}
                  <div className="glass-panel" style={{ padding: '20px', background: 'rgba(255,255,255,0.01)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                      <h3 style={{ margin: 0, fontSize: '16px' }}>Roll Metadata</h3>
                      <button className="btn-secondary" style={{ padding: '4px 8px', fontSize: '12px' }} onClick={() => setIsEditing(!isEditing)}>
                        {isEditing ? 'Cancel' : <><Edit3 size={12} /> Edit</>}
                      </button>
                    </div>
                    
                    {isEditing ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '12px' }}>
                          <input 
                            className="input-field" 
                            value={rollDetail.roll.roll_num} 
                            placeholder="Roll Num" 
                            onChange={e => setRollDetail({
                              ...rollDetail,
                              roll: { ...rollDetail.roll, roll_num: e.target.value }
                            })}
                          />
                          <input 
                            className="input-field" 
                            value={rollDetail.roll.date_str} 
                            placeholder="Date range" 
                            onChange={e => setRollDetail({
                              ...rollDetail,
                              roll: { ...rollDetail.roll, date_str: e.target.value }
                            })}
                          />
                        </div>
                        <input 
                          className="input-field" 
                          value={rollDetail.roll.title} 
                          placeholder="Title" 
                          onChange={e => setRollDetail({
                            ...rollDetail,
                            roll: { ...rollDetail.roll, title: e.target.value }
                          })}
                        />
                        <textarea 
                          className="input-field" 
                          value={rollDetail.roll.manuscripts} 
                          placeholder="Manuscripts" 
                          rows={3}
                          onChange={e => setRollDetail({
                            ...rollDetail,
                            roll: { ...rollDetail.roll, manuscripts: e.target.value }
                          })}
                        />
                        <button className="btn-primary" onClick={handleSaveRollMetadata}>
                          <Save size={16} /> Save Metadata
                        </button>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        <div><strong>Number:</strong> {rollDetail.roll.roll_num}</div>
                        <div><strong>Date:</strong> {rollDetail.roll.date_str}</div>
                        <div><strong>Title:</strong> {rollDetail.roll.title}</div>
                        <div>
                          <strong>Manuscripts:</strong>
                          <pre style={{ margin: '4px 0 0 0', background: 'rgba(0,0,0,0.2)', padding: '8px', borderRadius: '4px', fontSize: '12px', whiteSpace: 'pre-wrap' }}>
                            {rollDetail.roll.manuscripts || "None listed"}
                          </pre>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Tituli Text & Entity Fields */}
                  <div>
                    <h3 style={{ fontSize: '18px', borderBottom: '1px solid var(--panel-border)', paddingBottom: '8px', marginBottom: '16px' }}>Tituli (Latin Contributions)</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                      {rollDetail.tituli.map(tit => (
                        <div key={tit.id} className="glass-panel" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                          <div style={{ fontWeight: 'bold', fontSize: '15px' }} className="title-latin">{tit.title}</div>
                          
                          {/* Latin Text editor */}
                          <textarea 
                            className="input-field" 
                            style={{ fontFamily: 'monospace', fontSize: '13px' }} 
                            value={tit.latin_text} 
                            rows={4}
                            onChange={e => {
                              const updated = rollDetail.tituli.map(t => t.id === tit.id ? { ...t, latin_text: e.target.value } : t);
                              setRollDetail({ ...rollDetail, tituli: updated });
                            }}
                          />
                          <button 
                            className="btn-secondary" 
                            style={{ alignSelf: 'flex-end', padding: '6px 12px', fontSize: '12px' }}
                            onClick={() => handleSaveTitulus(tit.id, tit.title, tit.latin_text)}
                          >
                            Save Titulus Text
                          </button>

                          {/* Parsed Entities for this titulus */}
                          <div style={{ marginTop: '12px' }}>
                            <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 'bold' }}>PARSED HISTORICAL ENTITIES</span>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '8px' }}>
                              {tit.entities && tit.entities.map(ent => (
                                <div key={ent.id} className="glass-panel" style={{ padding: '12px', background: 'rgba(0,0,0,0.15)', fontSize: '13px' }}>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                                    <span>Original: <strong>{ent.original_name}</strong> ({ent.original_title})</span>
                                    <span style={{ color: 'var(--text-muted)' }}>FN: {ent.footnote_num}</span>
                                  </div>
                                  
                                  {/* Normalization form fields */}
                                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '8px' }}>
                                    <input 
                                      className="input-field" 
                                      style={{ padding: '6px 10px', fontSize: '12px' }}
                                      value={ent.normalized_name}
                                      placeholder="Normalized Name"
                                      onChange={e => {
                                        const updatedEntities = tit.entities.map(en => en.id === ent.id ? { ...en, normalized_name: e.target.value } : en);
                                        const updatedTituli = rollDetail.tituli.map(t => t.id === tit.id ? { ...t, entities: updatedEntities } : t);
                                        setRollDetail({ ...rollDetail, tituli: updatedTituli });
                                      }}
                                    />
                                    <input 
                                      className="input-field" 
                                      style={{ padding: '6px 10px', fontSize: '12px' }}
                                      value={ent.normalized_role}
                                      placeholder="Normalized Role"
                                      onChange={e => {
                                        const updatedEntities = tit.entities.map(en => en.id === ent.id ? { ...en, normalized_role: e.target.value } : en);
                                        const updatedTituli = rollDetail.tituli.map(t => t.id === tit.id ? { ...t, entities: updatedEntities } : t);
                                        setRollDetail({ ...rollDetail, tituli: updatedTituli });
                                      }}
                                    />
                                    <input 
                                      className="input-field" 
                                      style={{ padding: '6px 10px', fontSize: '12px' }}
                                      value={ent.normalized_dates}
                                      placeholder="Dates (e.g. 757-762)"
                                      onChange={e => {
                                        const updatedEntities = tit.entities.map(en => en.id === ent.id ? { ...en, normalized_dates: e.target.value } : en);
                                        const updatedTituli = rollDetail.tituli.map(t => t.id === tit.id ? { ...t, entities: updatedEntities } : t);
                                        setRollDetail({ ...rollDetail, tituli: updatedTituli });
                                      }}
                                    />
                                    <input 
                                      className="input-field" 
                                      style={{ padding: '6px 10px', fontSize: '12px' }}
                                      value={ent.location_name}
                                      placeholder="Location (e.g. Noyon)"
                                      onChange={e => {
                                        const updatedEntities = tit.entities.map(en => en.id === ent.id ? { ...en, location_name: e.target.value } : en);
                                        const updatedTituli = rollDetail.tituli.map(t => t.id === tit.id ? { ...t, entities: updatedEntities } : t);
                                        setRollDetail({ ...rollDetail, tituli: updatedTituli });
                                      }}
                                    />
                                  </div>
                                  <button 
                                    className="btn-secondary" 
                                    style={{ padding: '4px 8px', fontSize: '11px', display: 'flex', marginLeft: 'auto' }}
                                    onClick={() => handleSaveEntity(ent.id, ent)}
                                  >
                                    Save Entity Normalizations
                                  </button>
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Footnotes view */}
                  <div>
                    <h3 style={{ fontSize: '18px', borderBottom: '1px solid var(--panel-border)', paddingBottom: '8px', marginBottom: '16px' }}>Footnotes Reference</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {rollDetail.footnotes.map(fn => (
                        <div key={fn.id} style={{ fontSize: '13px', borderBottom: '1px solid rgba(255,255,255,0.01)', paddingBottom: '6px' }}>
                          <span style={{ color: 'var(--primary)', fontWeight: 'bold' }}>{fn.footnote_num}. </span>
                          <span style={{ color: 'var(--text-secondary)' }}>{fn.text}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                </div>
              </div>
            ) : (
              <div className="glass-panel" style={{ padding: '48px', textAlign: 'center', color: 'var(--text-muted)' }}>
                Please select a roll from the dropdown to load editor.
              </div>
            )}
          </div>
        )}

        {/* EXPORT TAB */}
        {activeTab === 'export' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
            <div>
              <h1 style={{ fontSize: '32px', marginBottom: '8px' }}>Export Data</h1>
              <p style={{ color: 'var(--text-secondary)', margin: 0 }}>Download verified mortuary rolls data in standardized research formats.</p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '24px' }}>
              
              <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <h3 style={{ margin: 0 }}>CSV Spreadsheet</h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: '14px', flex: 1 }}>
                  Contains flat rows mapping rolls to tituli and entities. Perfect for loading into Excel, R, or Python Pandas.
                </p>
                <a href="/api/export/csv" className="btn-primary" style={{ textDecoration: 'none', justifyContent: 'center' }}>
                  <Download size={18} /> Download CSV
                </a>
              </div>

              <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <h3 style={{ margin: 0 }}>JSON Format</h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: '14px', flex: 1 }}>
                  Hierarchical structure showing rolls nested with their tituli, parsed entities, and footnotes. Best for digital humanities applications.
                </p>
                <a href="/api/export/json" className="btn-primary" style={{ textDecoration: 'none', justifyContent: 'center' }}>
                  <Download size={18} /> Download JSON
                </a>
              </div>

              <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <h3 style={{ margin: 0 }}>SQLite Database</h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: '14px', flex: 1 }}>
                  Download the raw SQLite relational database file (`rolls.db`) directly to run local queries and scripts.
                </p>
                <a href="/rolls.db" download className="btn-primary" style={{ textDecoration: 'none', justifyContent: 'center' }}>
                  <Download size={18} /> Download rolls.db
                </a>
              </div>

            </div>
          </div>
        )}

        {/* TRAVEL MAP TAB */}
        {activeTab === 'map' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', height: '100%' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h1 style={{ fontSize: '32px', marginBottom: '8px' }}>Travel Map</h1>
                <p style={{ color: 'var(--text-secondary)', margin: 0 }}>Visualize the historical itinerary and visiting stops of each mortuary roll.</p>
              </div>
                    {/* Roll Selector */}
              <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                <span style={{ fontSize: '14px', color: 'var(--text-muted)' }}>Select Roll:</span>
                <select 
                  className="input-field" 
                  value={mapRollId || ''} 
                  onChange={e => setMapRollId(e.target.value === 'all' ? 'all' : Number(e.target.value))}
                  style={{ background: '#0f172a', cursor: 'pointer' }}
                >
                  <option value="all">🌐 All Rolls (Overlay Paths)</option>
                  {rolls.map(r => (
                    <option key={r.id} value={r.id}>Roll {r.roll_num} ({r.date_str})</option>
                  ))}
                </select>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '24px', minHeight: 0 }}>
              {/* Map Container */}
              <div className="glass-panel" style={{ flex: 2, position: 'relative', overflow: 'hidden', height: '600px' }}>
                <div id="map-container" style={{ width: '100%', height: '100%', borderRadius: '12px', background: '#0f172a' }}></div>
              </div>

              {/* Itinerary Steps Panel */}
              <div className="glass-panel" style={{ flex: 1, padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px', overflowY: 'auto', maxHeight: '600px' }}>
                {mapRollId === 'all' ? (
                  <>
                    <h3 style={{ margin: 0, fontSize: '18px', borderBottom: '1px solid var(--panel-border)', paddingBottom: '12px' }}>
                      All Mortuary Rolls
                    </h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {Object.entries(allTravelsData).map(([rId, rInfo]) => {
                        const origin = rInfo.travels.find(t => t.type === 'origin');
                        const stops = rInfo.travels.filter(t => t.type === 'stop');
                        return (
                          <div 
                            key={rId} 
                            className="glass-panel-interactive" 
                            style={{ padding: '12px', borderRadius: '8px', cursor: 'pointer', border: '1px solid var(--panel-border)' }} 
                            onClick={() => setMapRollId(Number(rId))}
                          >
                            <h4 style={{ margin: '0 0 6px 0', fontSize: '14px', fontWeight: 'bold', color: 'var(--primary)' }}>
                              Roll {rInfo.roll_num} ({rInfo.date_str})
                            </h4>
                            <div style={{ fontSize: '11px', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
                              {origin && <span>🚩 {origin.name}</span>}
                              {stops.map((s, idx) => (
                                <span key={idx}> ➔ 📍 {s.name}</span>
                              ))}
                              {!origin && stops.length === 0 && <span style={{ color: 'var(--text-muted)' }}>No travel path</span>}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </>
                ) : (
                  <>
                    <h3 style={{ margin: 0, fontSize: '18px', borderBottom: '1px solid var(--panel-border)', paddingBottom: '12px' }}>
                      Itinerary Stops ({travelPath.length})
                    </h3>
                    {travelPath.length === 0 ? (
                      <div style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)', fontSize: '14px' }}>
                        No travel locations found for this roll.
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', position: 'relative', paddingLeft: '8px' }}>
                        {/* Vertical timeline line */}
                        <div style={{
                          position: 'absolute',
                          left: '19px',
                          top: '12px',
                          bottom: '12px',
                          width: '2px',
                          background: 'rgba(255,255,255,0.06)',
                          zIndex: 0
                        }}></div>

                        {travelPath.map((loc, idx) => {
                          const isOrigin = loc.type === 'origin';
                          return (
                            <div key={idx} style={{ display: 'flex', gap: '16px', zIndex: 1 }}>
                              {/* Timeline dot */}
                              <div style={{
                                width: '24px',
                                height: '24px',
                                borderRadius: '50%',
                                background: isOrigin ? 'var(--primary)' : 'var(--accent)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: '11px',
                                fontWeight: 'bold',
                                border: '4px solid #0f172a',
                                color: '#ffffff',
                                boxShadow: '0 0 10px rgba(0,0,0,0.5)'
                              }}>
                                {isOrigin ? '🚩' : idx}
                              </div>
                              <div style={{ flex: 1 }}>
                                <h4 style={{ margin: 0, fontSize: '14px', fontWeight: 'bold', color: isOrigin ? 'var(--primary)' : 'var(--accent)' }}>
                                  {loc.name}
                                </h4>
                                <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--text-secondary)' }}>
                                  {loc.description}
                                </p>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
