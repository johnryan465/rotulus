import React, { useState, useEffect } from 'react';
import { 
  Database, Search, Download, Image as ImageIcon, 
  BookOpen, UserCheck, ChevronRight, 
  Calendar, MapPin, Edit3, Save, Check, X, AlertCircle, Menu
} from 'lucide-react';

// Helper to determine API base path
const getApiUrl = (path) => {
  const isProd = import.meta.env.PROD;
  // In production (GitHub Pages), we use the static JSON files
  if (isProd) {
    if (path === '/api/rolls') return '/rotulus/api/rolls.json';
    if (path === '/api/travels') return '/rotulus/api/travels.json';
    
    // Handle /api/rolls/{id}/travels
    if (path.match(/^\/api\/rolls\/\d+\/travels$/)) {
      const parts = path.split('/');
      const id = parts[3];
      return `/rotulus/api/rolls/${id}/travels.json`;
    }
    
    // Handle /api/rolls/{id}
    if (path.match(/^\/api\/rolls\/\d+$/)) {
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
  const [yearFilter, setYearFilter] = useState([600, 1600]);
  const [availableYearRange, setAvailableYearRange] = useState([600, 1600]);
  const [rolls, setRolls] = useState([]);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  
  // Detail views
  const [selectedRollId, setSelectedRollId] = useState(null);
  const [rollDetail, setRollDetail] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  
  // Map states
  const mapInstanceRef = React.useRef(null);
  const [mapRollId, setMapRollId] = useState(null);
  const [stopsFilter, setStopsFilter] = useState(0);
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
      // In production, we fetch all rolls and filter client-side
      const isProd = import.meta.env.PROD;
      const url = getApiUrl('/api/rolls');
      const res = await fetch(url);
      const data = await res.json();
      
      let filteredData = data;
      if (isProd && query) {
        const q = query.toLowerCase();
        filteredData = data.filter(r => 
          (r.title && r.title.toLowerCase().includes(q)) ||
          (r.roll_num && r.roll_num.toString().includes(q)) ||
          (r.date_str && r.date_str.toLowerCase().includes(q))
        );
      }
      setRolls(filteredData);
      
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
    window.gotoRoll = (id) => {
      handleSelectRoll(Number(id));
      setActiveTab('explorer');
    };
    return () => { delete window.gotoRoll; };
  }, [rolls]);

  useEffect(() => {
    if (activeTab !== 'map' || !mapRollId) return;

    const fetchTravels = async () => {
      try {
        if (mapRollId === 'all') {
          const res = await fetch(getApiUrl(`/api/travels`));
          const data = await res.json();
          setAllTravelsData(data);

          // Update available year range
          const allYears = Object.values(data).map(r => r.year).filter(y => y !== null && y !== undefined);
          if (allYears.length > 0) {
            const minYear = Math.min(...allYears);
            const maxYear = Math.max(...allYears);
            setAvailableYearRange([minYear, maxYear]);
          }

          setTimeout(() => {
            const container = document.getElementById('map-container');
            if (!container) {
              console.warn("Map container not found in DOM");
              return;
            }

            if (mapInstanceRef.current) {
              mapInstanceRef.current.remove();
              mapInstanceRef.current = null;
            }

            if (!window.L) {
              console.error("Leaflet (L) not found on window");
              return;
            }

            console.log("Initializing Leaflet map...");
            const southWest = [30, -20];
            const northEast = [72, 45];
            const bounds = [southWest, northEast];

            const map = window.L.map('map-container', {
              scrollWheelZoom: false,
              maxBounds: bounds,
              maxBoundsViscosity: 1.0
            }).setView([48.8566, 2.3522], 4);
            mapInstanceRef.current = map;

            window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
              attribution: '&copy; OpenStreetMap contributors'
            }).addTo(map);

            const colors = [
              '#6366f1', '#10b981', '#f59e0b', '#ec4899', '#3b82f6', 
              '#8b5cf6', '#84cc16', '#f97316', '#d946ef', '#06b6d4'
            ];
            let colorIdx = 0;
            const allCoords = [];

            Object.entries(data).forEach(([rId, rInfo]) => {
              // Filters
              if (rInfo.year && (rInfo.year < yearFilter[0] || rInfo.year > yearFilter[1])) return;
              if (rInfo.num_stops < stopsFilter) return;

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
                  opacity: 0.4,
                  dashArray: '3, 6'
                }).addTo(map);
              }

              rollTravels.forEach((loc, index) => {
                if (!loc.coords) return; 
                const isOrigin = loc.type === 'origin';
                
                if (loc.is_approximate) {
                  // Render as Uncertainty Circle
                  window.L.circle(loc.coords, {
                    radius: 30000, // 30km radius for uncertainty
                    fillColor: color,
                    fillOpacity: 0.1,
                    color: color,
                    weight: 1,
                    dashArray: '5, 5'
                  }).addTo(map).bindPopup(`
                    <div style="color: #0f172a; font-family: sans-serif; padding: 4px;">
                      <h4 style="margin: 0 0 4px 0; font-size: 13px; color: ${color};">
                        Roll ${rInfo.roll_num} [Approximate]
                      </h4>
                      <p style="margin: 0 0 8px 0; font-size: 12px; font-weight: 500;">${loc.name}</p>
                      <button onclick="window.gotoRoll(${rId})" style="background: var(--primary); color: white; border: none; padding: 4px 8px; border-radius: 2px; cursor: pointer; font-size: 11px; width: 100%;">View Scroll Details</button>
                    </div>
                  `, { maxWidth: 200 });
                } else {
                  // Render as Point Marker
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
                      <p style="margin: 0 0 8px 0; font-size: 11px; color: #64748b;">${loc.date_str || ''}</p>
                      <button onclick="window.gotoRoll(${rId})" style="background: var(--primary); color: white; border: none; padding: 4px 8px; border-radius: 2px; cursor: pointer; font-size: 11px; width: 100%;">View Scroll Details</button>
                    </div>
                  `;
                  marker.bindPopup(popupContent);
                }
              });
            });

            if (allCoords.length > 0) {
              const bounds = window.L.latLngBounds(allCoords);
              map.fitBounds(bounds, { padding: [50, 50] });
            }
          }, 100);
        } else {
          const res = await fetch(getApiUrl(`/api/rolls/${mapRollId}/travels`));
          const data = await res.json();
          setTravelPath(data);

          setTimeout(() => {
            const container = document.getElementById('map-container');
            if (!container) {
              console.warn("Map container not found in DOM");
              return;
            }

            if (mapInstanceRef.current) {
              mapInstanceRef.current.remove();
              mapInstanceRef.current = null;
            }

            if (!window.L) {
              console.error("Leaflet (L) not found on window");
              return;
            }

            console.log("Initializing Leaflet map...");
            const southWest = [30, -20];
            const northEast = [72, 45];
            const bounds = [southWest, northEast];

            const map = window.L.map('map-container', {
              scrollWheelZoom: false,
              maxBounds: bounds,
              maxBoundsViscosity: 1.0
            }).setView([48.8566, 2.3522], 4);
            mapInstanceRef.current = map;

            window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
              attribution: '&copy; OpenStreetMap contributors'
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
                    <p style="margin: 0 0 4px 0; font-size: 11px; color: #64748b;">${loc.date_str || ''}</p>
                    <p style="margin: 0; font-size: 10px; color: #94a3b8;">${loc.description}</p>
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
  }, [activeTab, mapRollId, yearFilter, stopsFilter]);

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
        
        const res = await fetch(getApiUrl(`/api/image/${pdfIdx}/${activePage}/${half}/bounds`));
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
      const res = await fetch(getApiUrl(`/api/rolls/${id}`));
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
      const res = await fetch(getApiUrl(`/api/rolls/${rollDetail.roll.id}`), {
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
      const res = await fetch(getApiUrl(`/api/tituli/${tit_id}`), {
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
      const res = await fetch(getApiUrl(`/api/entities/${ent_id}`), {
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
      const res = await fetch(getApiUrl(`/api/rolls/${id}/verify`), { method: 'POST' });
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
    <div className="main-container">
      {/* TOP NAVIGATION */}
      <div className="top-nav">
        <div className="logo-section">
          <BookOpen className="logo-icon" />
          <div className="logo-text">ROTULUS</div>
        </div>
        
        <div className="tabs-nav">
          <button 
            className={`tab-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            Dashboard
          </button>
          <button 
            className={`tab-btn ${activeTab === 'explorer' ? 'active' : ''}`}
            onClick={() => setActiveTab('explorer')}
          >
            Explorer
          </button>
          <button 
            className={`tab-btn ${activeTab === 'map' ? 'active' : ''}`}
            onClick={() => setActiveTab('map')}
          >
            Travel Map
          </button>
          <button 
            className={`tab-btn ${activeTab === 'verification' ? 'active' : ''}`}
            onClick={() => setActiveTab('verification')}
          >
            Verification
          </button>
        </div>

        <div style={{ display: 'flex', gap: '12px' }}>
          <button className="tab-btn" onClick={() => window.open('/rotulus/api/rolls.json', '_blank')}>
            <Download size={16} /> JSON
          </button>
        </div>
      </div>

      <div className="content-area">
        {/* Sidebar - Roll List */}
        {(activeTab === 'explorer' || activeTab === 'verification') && (
          <div className="sidebar">
            <div className="search-container">
              <div style={{ position: 'relative' }}>
                <Search className="search-icon" size={18} />
                <input 
                  type="text" 
                  className="search-input"
                  placeholder="Search rolls..." 
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyUp={(e) => e.key === 'Enter' && fetchRolls(searchQuery)}
                />
              </div>
            </div>

            <div className="roll-list">
              {loading ? (
                <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  Loading documents...
                </div>
              ) : (
                rolls.map(roll => (
                  <div 
                    key={roll.id} 
                    className={`roll-item ${selectedRollId === roll.id ? 'active' : ''}`}
                    onClick={() => {
                      setSelectedRollId(roll.id);
                      fetchRollDetail(roll.id);
                    }}
                  >
                    <div className="roll-num">N° {roll.roll_num}</div>
                    <div style={{ fontSize: '14px', fontWeight: 'bold', marginBottom: '4px' }}>{roll.date_str}</div>
                    <div style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.4' }}>
                      {roll.title.length > 80 ? roll.title.substring(0, 80) + '...' : roll.title}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        <div className="viewer-pane">
          {/* DASHBOARD TAB */}
          {activeTab === 'dashboard' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
              <div>
                <h1 style={{ fontSize: '32px', marginBottom: '8px' }}>Archive Dashboard</h1>
                <p style={{ color: 'var(--text-muted)', margin: 0 }}>Overview of medieval confraternity database and manuscript verification metrics.</p>
              </div>

              {/* Stats Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '24px' }}>
                <div className="glass-panel" style={{ padding: '24px' }}>
                  <span style={{ color: 'var(--text-muted)', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Total Scrolls</span>
                  <h2 style={{ fontSize: '42px', margin: '8px 0 0 0' }}>{stats.total}</h2>
                </div>
                <div className="glass-panel" style={{ padding: '24px' }}>
                  <span style={{ color: 'var(--text-muted)', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Verified Records</span>
                  <h2 style={{ fontSize: '42px', margin: '8px 0 0 0', color: 'var(--primary)' }}>{stats.verified}</h2>
                </div>
                <div className="glass-panel" style={{ padding: '24px' }}>
                  <span style={{ color: 'var(--text-muted)', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Completion</span>
                  <h2 style={{ fontSize: '42px', margin: '8px 0 0 0', color: 'var(--accent)' }}>{stats.percent}%</h2>
                </div>
              </div>

              {/* Recent List */}
              <div className="glass-panel" style={{ padding: '32px' }}>
                <h3 style={{ marginBottom: '24px', fontSize: '20px' }}>Catalogue of Rolls</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {rolls.slice(0, 8).map(roll => (
                    <div 
                      key={roll.id} 
                      className="roll-item active"
                      style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                      onClick={() => handleSelectRoll(roll.id)}
                    >
                      <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
                        <span className="roll-num">N° {roll.roll_num}</span>
                        <div>
                          <h4 style={{ margin: 0, fontSize: '16px' }}>{roll.title || "Untitled Roll"}</h4>
                          <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>{roll.date_str}</span>
                        </div>
                      </div>
                      <ChevronRight size={20} color="var(--accent)" />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* EXPLORER TAB (Metadata & Transcript) */}
          {activeTab === 'explorer' && (
            rollDetail ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
                  <div>
                    <div className="roll-num" style={{ fontSize: '1.2rem' }}>ROLL N° {rollDetail.roll.roll_num}</div>
                    <h1 style={{ margin: '4px 0', fontSize: '2.5rem' }}>{rollDetail.roll.date_str}</h1>
                  </div>
                  <div style={{ display: 'flex', gap: '12px' }}>
                    <button className="tab-btn" onClick={() => setActiveTab('verification')}>View Manuscript</button>
                    <button className="tab-btn active" onClick={() => handleToggleVerify(rollDetail.roll.id)}>
                      {rollDetail.roll.is_verified ? 'Verified ✓' : 'Mark Verified'}
                    </button>
                  </div>
                </div>

                <div className="glass-panel" style={{ padding: '32px' }}>
                  <h3 style={{ marginBottom: '16px' }}>Scholarly Description</h3>
                  <p style={{ fontSize: '1.2rem', lineHeight: '1.6' }}>{rollDetail.roll.title}</p>
                  <div style={{ background: 'rgba(0,0,0,0.03)', padding: '16px', border: '1px solid var(--border)', marginTop: '24px', fontSize: '15px' }}>
                    <strong>Manuscripts:</strong> {rollDetail.roll.manuscripts}
                  </div>
                </div>

                {rollDetail.tituli.map(tit => (
                  <div key={tit.id} className="glass-panel" style={{ padding: '32px' }}>
                    <h3 className="gold-leaf" style={{ marginBottom: '20px', borderBottom: '1px solid var(--border)', paddingBottom: '12px' }}>
                      {tit.location_name ? `Titulus: ${tit.location_name}` : tit.title}
                    </h3>
                    <div className="latin-text">
                      {tit.latin_text}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: 'var(--text-muted)' }}>
                <p>Select a scroll from the sidebar to begin research.</p>
              </div>
            )
          )}

          {/* VERIFICATION TAB (Side-by-side) */}
          {activeTab === 'verification' && (
            rollDetail ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', height: '100%' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h1 style={{ fontSize: '24px' }}>Manuscript Verification: N° {rollDetail.roll.roll_num}</h1>
                  <div style={{ display: 'flex', gap: '12px' }}>
                    <button className="btn-secondary" onClick={() => setZoomLevel(z => Math.max(0.5, z - 0.1))}>Zoom -</button>
                    <button className="btn-secondary" onClick={() => setZoomLevel(z => Math.min(2, z + 0.1))}>Zoom +</button>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '20px', flex: 1, overflow: 'hidden' }}>
                  {/* Left: Image */}
                  <div className="glass-panel" style={{ overflow: 'auto', background: '#000', position: 'relative' }}>
                    {(() => {
                      const pdfMatch = rollDetail.roll.pdf_source.match(/\((\d+)\)/);
                      const pdfIdx = pdfMatch ? pdfMatch[1] : 1;
                      const pages = rollDetail.roll.pdf_pages.split(',');
                      const activePage = pages[activeVerificationIndex]?.trim() || pages[0].trim() || '3';
                      const matchedTitulus = rollDetail.tituli.find(t => t.pdf_page === Number(activePage)) || rollDetail.tituli[0];
                      const half = matchedTitulus ? matchedTitulus.pdf_half : 'left';
                      const imageUrl = `/api/image/${pdfIdx}/${activePage}/${half}`;

                      return (
                        <div style={{ transform: `scale(${zoomLevel})`, transformOrigin: 'top left' }}>
                          <img src={imageUrl} alt="Manuscript" style={{ maxWidth: 'none' }} />
                        </div>
                      );
                    })()}
                  </div>

                  {/* Right: Transcript editor */}
                  <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', overflowY: 'auto', padding: '24px' }}>
                    <h3 style={{ marginBottom: '20px', fontSize: '18px' }}>Transcripts & Footnotes</h3>
                    {rollDetail.tituli.map(tit => (
                      <div key={tit.id} style={{ marginBottom: '32px' }}>
                        <div style={{ fontWeight: 'bold', color: 'var(--primary)', marginBottom: '8px' }}>{tit.title}</div>
                        <textarea 
                          className="search-input"
                          style={{ width: '100%', height: '150px', marginBottom: '12px', fontStyle: 'italic', fontSize: '15px' }}
                          value={tit.latin_text}
                          onChange={(e) => {
                             const updated = rollDetail.tituli.map(t => t.id === tit.id ? { ...t, latin_text: e.target.value } : t);
                             setRollDetail({ ...rollDetail, tituli: updated });
                          }}
                        />
                      </div>
                    ))}
                    
                    <div style={{ marginTop: 'auto', borderTop: '1px solid var(--border)', paddingTop: '20px' }}>
                       <button className="tab-btn active" style={{ width: '100%' }} onClick={() => handleToggleVerify(rollDetail.roll.id)}>
                         {rollDetail.roll.is_verified ? 'Verified' : 'Approve & Save Changes'}
                       </button>
                    </div>
                  </div>
                </div>
                
                {/* Page Navigation */}
                {rollDetail.roll.pdf_pages.split(',').length > 1 && (
                  <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', padding: '12px' }}>
                    {rollDetail.roll.pdf_pages.split(',').map((p, idx) => (
                      <button 
                        key={idx} 
                        className={`tab-btn ${activeVerificationIndex === idx ? 'active' : ''}`}
                        onClick={() => setActiveVerificationIndex(idx)}
                      >
                        Page {p.trim()}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : (
               <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: 'var(--text-muted)' }}>
                <p>Select a scroll from the sidebar to begin verification.</p>
              </div>
            )
          )}

          {/* TRAVEL MAP TAB */}
          {activeTab === 'map' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', minHeight: '800px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h1 style={{ fontSize: '32px', marginBottom: '8px' }}>Historical Itineraries</h1>
                  <p style={{ color: 'var(--text-muted)', margin: 0 }}>Mapping the physical journey of medieval mortuary documents across Europe.</p>
                </div>

                <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                  <select 
                    className="search-input" 
                    style={{ width: '300px', paddingLeft: '12px' }}
                    value={mapRollId || ''} 
                    onChange={e => setMapRollId(e.target.value === 'all' ? 'all' : Number(e.target.value))}
                  >
                    <option value="all">View All Travels (Overlay)</option>
                    {rolls.filter(r => r.id).map(r => (
                      <option key={r.id} value={r.id}>N° {r.roll_num} ({r.date_str})</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Filter Section */}
              {mapRollId === 'all' && (
                <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                  <div className="glass-panel" style={{ padding: '16px 24px', flex: 1, minWidth: '300px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
                      <span style={{ fontSize: '14px', fontWeight: 'bold', fontFamily: 'Cinzel' }}>Time Range: {yearFilter[0]} – {yearFilter[1]}</span>
                      <button 
                        onClick={() => setYearFilter([availableYearRange[0], availableYearRange[1]])}
                        className="tab-btn"
                        style={{ padding: '2px 8px', fontSize: '11px' }}
                      >
                        Reset Filter
                      </button>
                    </div>
                  <div className="range-container" style={{ height: '40px', marginTop: '20px' }}>
                    <div className="range-track" style={{ height: '4px', background: 'var(--paper-dark)', border: '1px solid var(--border)' }}></div>
                    <div 
                      className="range-highlight"
                      style={{
                        position: 'absolute',
                        height: '4px',
                        background: 'var(--primary)',
                        zIndex: 2,
                        borderRadius: '2px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        left: `${((yearFilter[0] - availableYearRange[0]) / (availableYearRange[1] - availableYearRange[0])) * 100}%`,
                        width: `${((yearFilter[1] - yearFilter[0]) / (availableYearRange[1] - availableYearRange[0])) * 100}%`
                      }}
                    ></div>
                    <input 
                      type="range" 
                      min={availableYearRange[0]} 
                      max={availableYearRange[1]} 
                      value={yearFilter[0]} 
                      onChange={e => {
                        const val = Math.min(Number(e.target.value), yearFilter[1] - 10);
                        setYearFilter([val, yearFilter[1]]);
                      }}
                      className="range-input"
                      style={{ zIndex: yearFilter[0] > (availableYearRange[1] - availableYearRange[0]) / 2 ? 5 : 4 }}
                    />
                    <input 
                      type="range" 
                      min={availableYearRange[0]} 
                      max={availableYearRange[1]} 
                      value={yearFilter[1]} 
                      onChange={e => {
                        const val = Math.max(Number(e.target.value), yearFilter[0] + 10);
                        setYearFilter([yearFilter[0], val]);
                      }}
                      className="range-input"
                      style={{ zIndex: 4 }}
                    />
                  </div>

                  </div>

                  <div className="glass-panel" style={{ padding: '16px 24px', width: '250px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span style={{ fontSize: '14px', fontWeight: 'bold', fontFamily: 'Cinzel' }}>Min. Stops</span>
                      <span className="rubric">{stopsFilter}+</span>
                    </div>
                    <input 
                      type="range" 
                      min="0" 
                      max="20" 
                      value={stopsFilter} 
                      onChange={e => setStopsFilter(Number(e.target.value))}
                      style={{ width: '100%', accentColor: 'var(--accent)', cursor: 'pointer' }}
                    />
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                      <span>All</span>
                      <span>Complex only</span>
                    </div>
                  </div>
                </div>
              )}

              <div className="glass-panel" style={{ padding: '12px', height: '700px' }}>
                <div id="map-container" style={{ width: '100%', height: '100%', borderRadius: '4px' }}></div>
              </div>
              
              {mapRollId !== 'all' && travelPath.length > 0 && (
                <div className="glass-panel" style={{ padding: '24px' }}>
                  <h3 style={{ marginBottom: '16px' }}>Stops in Chronological Order</h3>
                  <div style={{ display: 'flex', gap: '20px', overflowX: 'auto', paddingBottom: '12px' }}>
                    {travelPath.map((loc, idx) => (
                      <div key={idx} style={{ minWidth: '200px', padding: '16px', background: 'var(--paper-dark)', border: '1px solid var(--border)' }}>
                        <div className="rubric" style={{ fontSize: '12px', marginBottom: '4px' }}>{idx === 0 ? 'ORIGIN' : `STOP ${idx}`}</div>
                        <div style={{ fontWeight: 'bold' }}>{loc.name}</div>
                        <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>{loc.date_str}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
