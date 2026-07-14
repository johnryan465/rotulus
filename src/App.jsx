import { useState, useEffect, useRef } from 'react';
import { 
  Download, BookOpen, ChevronRight
} from 'lucide-react';
import RangeSlider from './RangeSlider';
import './App.css';

// Helper to determine API base path
const getApiUrl = (path) => {
  const isProd = import.meta.env.PROD;
  if (isProd) {
    if (path === '/api/rolls') return '/rotulus/api/rolls.json';
    if (path === '/api/travels') return '/rotulus/api/travels.json';
    if (path.match(/^\/api\/rolls\/\d+\/travels$/)) {
      const parts = path.split('/');
      const id = parts[3];
      return `/rotulus/api/rolls/${id}/travels.json`;
    }
    if (path.match(/^\/api\/rolls\/\d+\/movements$/)) {
      const parts = path.split('/');
      const id = parts[3];
      return `/rotulus/api/rolls/${id}/movements.json`;
    }
    if (path.match(/^\/api\/rolls\/\d+$/)) {
      const id = path.split('/').pop();
      return `/rotulus/api/rolls/${id}.json`;
    }
    return `/rotulus${path}.json`;
  }
  return path;
};

export default function App() {
  const [activeTab, setActiveTab] = useState('map');
  const [yearFilter, setYearFilter] = useState([700, 1500]);
  const [availableYearRange, setAvailableYearRange] = useState([700, 1500]);
  const [rolls, setRolls] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  
  const [selectedRollId, setSelectedRollId] = useState(null);
  const [rollDetail, setRollDetail] = useState(null);
  
  // Map Refs & State
  const mapInstanceRef = useRef(null);
  const mapLayersRef = useRef(null);
  const lastFittedRollId = useRef(null);

  const [mapRollId, setMapRollId] = useState(null);
  const [stopsFilter, setStopsFilter] = useState(0);
  const [travelPath, setTravelPath] = useState([]);
  const [allTravelsData, setAllTravelsData] = useState({});

  // Explorer detail's own embedded per-roll map
  const explorerMapInstanceRef = useRef(null);
  const [explorerTravelPath, setExplorerTravelPath] = useState([]);
  const [rollMovements, setRollMovements] = useState([]);

  // Entities tab state
  const [entityView, setEntityView] = useState('people'); // 'people' | 'locations'
  const [entitiesData, setEntitiesData] = useState([]);
  const [locationsData, setLocationsData] = useState([]);
  const [entitySearch, setEntitySearch] = useState('');
  const [selectedEntity, setSelectedEntity] = useState(null); // { type: 'people'|'locations', name }

  // Verification & Dashboard State
  const [activeVerificationIndex, setActiveVerificationIndex] = useState(0);
  const [zoomLevel] = useState(1);
  const [stats, setStats] = useState({ total: 0, verified: 0, unverified: 0, percent: 0 });

  // Hoisted Functions
  const fetchRollDetail = async (id) => {
    try {
      const res = await fetch(getApiUrl(`/api/rolls/${id}`));
      const data = await res.json();
      setRollDetail(data);
    } catch (e) { console.error("Failed to fetch roll detail:", e); }
    try {
      const res = await fetch(getApiUrl(`/api/rolls/${id}/travels`));
      const data = await res.json();
      setExplorerTravelPath(data);
    } catch (e) { console.error("Failed to fetch roll travels:", e); setExplorerTravelPath([]); }
    try {
      const res = await fetch(getApiUrl(`/api/rolls/${id}/movements`));
      const data = await res.json();
      setRollMovements(data);
    } catch (e) { console.error("Failed to fetch roll movements:", e); setRollMovements([]); }
  };

  // --- HASH ROUTING LOGIC ---
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace('#/', '');
      const parts = hash.split('/');
      const tab = parts[0] || 'map';
      const id = parts[1] ? Number(parts[1]) : null;

      if (['dashboard', 'explorer', 'map', 'entities', 'verification'].includes(tab)) {
        setActiveTab(tab);
        if (id && id !== selectedRollId) {
          setSelectedRollId(id);
          setRollDetail(null);
          setExplorerTravelPath([]);
          setRollMovements([]);
          fetchRollDetail(id);
        }
      }
    };

    window.addEventListener('hashchange', handleHashChange);
    handleHashChange();
    return () => window.removeEventListener('hashchange', handleHashChange);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rolls, selectedRollId]);

  const syncHash = (tab, id = null) => {
    const newHash = id ? `#/${tab}/${id}` : `#/${tab}`;
    if (window.location.hash !== newHash) {
      window.location.hash = newHash;
    }
  };

  const handleTabChange = (tab, id = null) => {
    setActiveTab(tab);
    // Prioritize passed ID
    const targetId = id || (tab === 'explorer' || tab === 'verification' ? selectedRollId : null);
    syncHash(tab, targetId);
  };

  const handleSelectRoll = (id) => {
    if (!id) return;
    setSelectedRollId(id);
    setRollDetail(null);
    setExplorerTravelPath([]);
    setRollMovements([]);
    fetchRollDetail(id);
    // Sync hash if in detail-supporting tab
    if (activeTab === 'explorer' || activeTab === 'verification') {
      syncHash(activeTab, id);
    }
  };

  const fetchRolls = async (query = '') => {
    setLoading(true);
    try {
      const res = await fetch(getApiUrl('/api/rolls'));
      const data = await res.json();
      
      let filteredData = data;
      if (query) {
        const q = query.toLowerCase();
        filteredData = data.filter(r => 
          (r.title && r.title.toLowerCase().includes(q)) ||
          (r.roll_num && r.roll_num.toString().includes(q)) ||
          (r.date_str && r.date_str.toLowerCase().includes(q))
        );
      }
      setRolls(filteredData);
      const total = data.length;
      const verified = data.filter(r => r.is_verified).length;
      setStats({ total, verified, unverified: total - verified, percent: total > 0 ? Math.round((verified / total) * 100) : 0 });
    } catch (e) { console.error("Failed to fetch rolls:", e); } finally { setLoading(false); }
  };

  const handleToggleVerify = async (id) => {
    try {
      const res = await fetch(getApiUrl(`/api/rolls/${id}/verify`), { method: 'POST' });
      const data = await res.json();
      if (rollDetail && rollDetail.roll.id === id) {
        setRollDetail(prev => ({ ...prev, roll: { ...prev.roll, is_verified: data.is_verified } }));
      }
      fetchRolls();
    } catch (e) { console.error("Failed to toggle verification:", e); }
  };

  // Effects
  useEffect(() => { 
    fetchRolls(); 
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (activeTab === 'map' && rolls.length > 0 && !mapRollId) setMapRollId('all');
  }, [activeTab, rolls, mapRollId]);

  useEffect(() => {
    if (activeTab !== 'entities' || entitiesData.length > 0) return;
    (async () => {
      try {
        const [peopleRes, locRes] = await Promise.all([
          fetch(getApiUrl('/api/entities')),
          fetch(getApiUrl('/api/locations')),
        ]);
        setEntitiesData(await peopleRes.json());
        setLocationsData(await locRes.json());
      } catch (e) { console.error("Failed to fetch entities/locations:", e); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  useEffect(() => {
    window.gotoRoll = (rNum) => {
      if (!rNum) return;
      handleSelectRoll(rNum);
      handleTabChange('explorer', rNum);
    };
    return () => { delete window.gotoRoll; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rolls, activeTab, selectedRollId]);

  // Initialize Map Once
  useEffect(() => {
    const container = document.getElementById('map-container');
    if (!container || mapInstanceRef.current || !window.L) return;

    const map = window.L.map('map-container', { 
      scrollWheelZoom: false,
      maxBounds: [[30, -20], [72, 45]],
      maxBoundsViscosity: 1.0
    }).setView([48.8566, 2.3522], 4);
    
    mapInstanceRef.current = map;
    window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap' }).addTo(map);
    mapLayersRef.current = window.L.layerGroup().addTo(map);

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // Fetch Travels Data
  useEffect(() => {
    const fetchTravels = async () => {
      try {
        if (mapRollId === 'all') {
          const res = await fetch(getApiUrl(`/api/travels`));
          const data = await res.json();
          setAllTravelsData(data);

          const allYears = Object.values(data).map(r => r.year).filter(y => y);
          if (allYears.length > 0) {
            const minYear = Math.min(...allYears);
            const maxYear = Math.max(...allYears);
            setAvailableYearRange([minYear, maxYear]);
            setYearFilter(prev => {
              if (prev[0] < minYear || prev[1] > maxYear) {
                return [Math.max(minYear, prev[0]), Math.min(maxYear, prev[1])];
              }
              return prev;
            });
          }
        } else if (mapRollId) {
          const res = await fetch(getApiUrl(`/api/rolls/${mapRollId}/travels`));
          const data = await res.json();
          setTravelPath(data);
        }
      } catch (e) { console.error("Failed to fetch travels:", e); }
    };
    fetchTravels();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapRollId]);

  // Update Map Layers
  useEffect(() => {
    if (!mapLayersRef.current || !window.L) return;
    mapLayersRef.current.clearLayers();

    const colors = ['#8b0000', '#10b981', '#f59e0b', '#b8860b', '#3b82f6'];
    let colorIdx = 0;
    const allCoords = [];

    if (mapRollId === 'all') {
      Object.entries(allTravelsData).forEach(([rId, rInfo]) => {
        if (rInfo.year && (rInfo.year < yearFilter[0] || rInfo.year > yearFilter[1])) return;
        if (rInfo.num_stops < stopsFilter) return;

        const coords = rInfo.travels.map(t => t.coords).filter(c => c);
        if (coords.length === 0) return;
        allCoords.push(...coords);
        const color = colors[colorIdx % colors.length]; colorIdx++;

        if (coords.length > 1) {
          window.L.polyline(coords, { color, weight: 2, opacity: 0.4, dashArray: '3, 6' }).addTo(mapLayersRef.current);
        }

        rInfo.travels.forEach((loc, index) => {
          if (!loc.coords) return;
          const isOrigin = loc.type === 'origin';
          const marker = window.L.circleMarker(loc.coords, { 
            radius: isOrigin ? 7 : 5, 
            fillColor: color, 
            color: '#fff', 
            weight: 2, 
            opacity: 1, 
            fillOpacity: 0.9,
            interactive: true
          }).addTo(mapLayersRef.current);

          // Show name on hover
          marker.bindTooltip(loc.name, { direction: 'top', offset: [0, -5] });

          marker.bindPopup(`
            <div style="font-family: 'Calibri', 'Candara', 'Segoe UI', 'Optima', 'Arial', sans-serif; padding: 4px; min-width: 150px;">
              <h4 style="margin: 0; color: ${color}; font-weight: bold;">Roll N° ${rInfo.roll_num}</h4>
              <div style="font-size: 13px; margin: 4px 0;">${isOrigin ? '🚩 Origin' : `📍 Stop ${index}`}: <b>${loc.name}</b></div>
              <div style="font-size: 12px; color: #666; margin-bottom: 8px;">Total Journey: ${rInfo.num_stops} monasteries</div>
              <button onclick="window.gotoRoll('${rId}')" style="background: var(--primary); color: white; border: none; padding: 6px; cursor: pointer; width: 100%; border-radius: 2px;">View Scroll Details</button>
            </div>
          `);
        });
      });
    } else if (travelPath && travelPath.length > 0) {
      const coords = travelPath.map(t => t.coords).filter(c => c);
      if (coords.length > 0) {
        allCoords.push(...coords);
        if (coords.length > 1) window.L.polyline(coords, { color: '#8b0000', weight: 3, opacity: 0.8, dashArray: '5, 10' }).addTo(mapLayersRef.current);
        travelPath.forEach((loc, index) => {
          if (!loc.coords) return;
          const isOrigin = loc.type === 'origin';
          const marker = window.L.circleMarker(loc.coords, { 
            radius: isOrigin ? 9 : 7, 
            fillColor: isOrigin ? '#8b0000' : '#10b981', 
            color: '#fff', 
            weight: 2, 
            fillOpacity: 1,
            interactive: true
          }).addTo(mapLayersRef.current);

          // Show name on hover
          marker.bindTooltip(loc.name, { direction: 'top', offset: [0, -5] });

          marker.bindPopup(`
            <div style="font-family: 'Calibri', 'Candara', 'Segoe UI', 'Optima', 'Arial', sans-serif; padding: 4px; min-width: 150px;">
              <h4 style="margin: 0; color: ${isOrigin ? '#8b0000' : '#10b981'}; font-weight: bold;">Roll N° ${mapRollId}</h4>
              <div style="font-size: 13px; margin: 4px 0;">${isOrigin ? '🚩 Origin' : `📍 Stop ${index}`}: <b>${loc.name}</b></div>
              <div style="font-size: 12px; color: #666; margin-bottom: 8px;">${loc.date_str || ''}</div>
              <button onclick="window.gotoRoll('${mapRollId}')" style="background: var(--primary); color: white; border: none; padding: 6px; cursor: pointer; width: 100%; border-radius: 2px;">View Scroll Details</button>
            </div>
          `);
        });
      }
    }

    if (allCoords.length > 0 && mapInstanceRef.current && lastFittedRollId.current !== mapRollId) {
      mapInstanceRef.current.fitBounds(window.L.latLngBounds(allCoords), { padding: [50, 50], maxZoom: 10 });
      lastFittedRollId.current = mapRollId;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allTravelsData, travelPath, mapRollId, yearFilter, stopsFilter]);

  useEffect(() => {
    if (activeTab === 'map' && mapInstanceRef.current) {
      setTimeout(() => {
        mapInstanceRef.current.invalidateSize();
      }, 100);
    }
  }, [activeTab]);

  // Explorer detail's embedded per-roll map: torn down and rebuilt fresh
  // for each roll (the container only exists in the DOM while a roll's
  // detail is showing, so there's no persistent instance to update in place
  // like the main map).
  useEffect(() => {
    if (!rollDetail || activeTab !== 'explorer' || !window.L) return;
    const container = document.getElementById('explorer-map-container');
    if (!container) return;

    const map = window.L.map('explorer-map-container', {
      scrollWheelZoom: false,
      maxBounds: [[30, -20], [72, 45]],
      maxBoundsViscosity: 1.0
    }).setView([48.8566, 2.3522], 4);
    explorerMapInstanceRef.current = map;
    window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap' }).addTo(map);
    const layers = window.L.layerGroup().addTo(map);

    const coords = explorerTravelPath.map(t => t.coords).filter(c => c);
    if (coords.length > 1) {
      window.L.polyline(coords, { color: '#8b0000', weight: 3, opacity: 0.8, dashArray: '5, 10' }).addTo(layers);
    }
    explorerTravelPath.forEach((loc, index) => {
      if (!loc.coords) return;
      const isOrigin = loc.type === 'origin';
      const marker = window.L.circleMarker(loc.coords, {
        radius: isOrigin ? 9 : 7,
        fillColor: isOrigin ? '#8b0000' : '#10b981',
        color: '#fff', weight: 2, fillOpacity: 1, interactive: true
      }).addTo(layers);
      marker.bindTooltip(loc.name, { direction: 'top', offset: [0, -5] });
      marker.bindPopup(`<div style="font-family: 'Calibri', 'Candara', 'Segoe UI', 'Optima', 'Arial', sans-serif; padding: 4px; min-width: 130px;">
        <div style="font-size: 13px;">${isOrigin ? '🚩 Origin' : `📍 Stop ${index}`}: <b>${loc.name}</b></div>
        <div style="font-size: 12px; color: #666;">${loc.date_str || ''}</div>
      </div>`);
    });

    if (coords.length > 0) {
      map.fitBounds(window.L.latLngBounds(coords), { padding: [30, 30], maxZoom: 10 });
    }
    setTimeout(() => map.invalidateSize(), 100);

    return () => {
      map.remove();
      explorerMapInstanceRef.current = null;
    };
  }, [rollDetail, explorerTravelPath, activeTab]);

  return (
    <div className="main-container">
      <div className="top-nav">
        <div className="logo-section" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <BookOpen color="var(--primary)" size={28} />
          <div className="logo-text">ROTULUS</div>
        </div>
        <div className="tabs-nav">
          {['dashboard', 'explorer', 'map', 'entities', 'verification'].map(t => (
            <button key={t} className={`tab-btn ${activeTab === t ? 'active' : ''}`} onClick={() => handleTabChange(t)}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
        <button className="tab-btn" onClick={() => window.open('/rotulus/api/rolls.csv', '_blank')}>
          <Download size={16} /> CSV
        </button>
      </div>

      <div className="content-area">
        {(activeTab === 'explorer' || activeTab === 'verification') && (
          <div className="sidebar">
            <div style={{ padding: '16px', borderBottom: '1px solid var(--border)' }}>
              <input type="text" className="search-input" placeholder="Search rolls..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} onKeyUp={(e) => e.key === 'Enter' && fetchRolls(searchQuery)} />
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '12px' }}>
              {loading ? <div style={{ textAlign: 'center', padding: '20px' }}>Loading...</div> :
                rolls.map(roll => (
                  <div key={roll.id} className={`roll-item ${selectedRollId === roll.id ? 'active' : ''}`} onClick={() => handleSelectRoll(roll.id)}>
                    <div className="roll-num">N° {roll.roll_num}</div>
                    <div style={{ fontSize: '14px', fontWeight: 'bold' }}>{roll.date_str}</div>
                    <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>{roll.title.slice(0, 80)}...</div>
                  </div>
                ))
              }
            </div>
          </div>
        )}

        <div className="viewer-pane">
          <div style={{ display: activeTab === 'dashboard' ? 'flex' : 'none', flexDirection: 'column', gap: '32px' }}>
            <h1 style={{ fontSize: '32px' }}>Archive Dashboard</h1>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '24px' }}>
              <div className="glass-panel" style={{ padding: '24px' }}><span>Total Scrolls</span><h2>{stats.total}</h2></div>
              <div className="glass-panel" style={{ padding: '24px' }}><span>Verified Records</span><h2 style={{ color: 'var(--primary)' }}>{stats.verified}</h2></div>
              <div className="glass-panel" style={{ padding: '24px' }}><span>Completion</span><h2 style={{ color: 'var(--accent)' }}>{stats.percent}%</h2></div>
            </div>
            <div className="glass-panel" style={{ padding: '32px' }}>
              <h3>Catalogue of Rolls</h3>
              {rolls.slice(0, 8).map(r => (
                <div key={r.id} className="roll-item active" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }} onClick={() => handleSelectRoll(r.id)}>
                  <div style={{ display: 'flex', gap: '20px' }}>
                    <span className="roll-num">N° {r.roll_num}</span>
                    <div><h4 style={{ margin: 0 }}>{r.title.slice(0, 60)}...</h4><span>{r.date_str}</span></div>
                  </div>
                  <ChevronRight color="var(--accent)" />
                </div>
              ))}
            </div>
          </div>

          <div style={{ display: activeTab === 'explorer' ? 'flex' : 'none', flexDirection: 'column', gap: '32px' }}>
            {rollDetail ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
                <div><div className="roll-num">ROLL N° {rollDetail.roll.roll_num}</div><h1>{rollDetail.roll.date_str}</h1></div>
                
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
                  <div className="glass-panel" style={{ padding: '32px' }}>
                    <h3 style={{ borderBottom: '1px solid var(--primary)', paddingBottom: '8px', marginBottom: '16px' }}>Scholarly Description</h3>
                    <p>{rollDetail.roll.title}</p>
                  </div>
                  <div className="glass-panel" style={{ padding: '32px' }}>
                    <h3 style={{ borderBottom: '1px solid var(--primary)', paddingBottom: '8px', marginBottom: '16px' }}>Current Storage</h3>
                    <p style={{ fontStyle: 'italic', color: 'var(--text-muted)' }}>
                      {rollDetail.roll.manuscripts || "Original manuscript location not specified in catalogue."}
                    </p>
                  </div>
                </div>

                <div className="glass-panel" style={{ padding: '12px' }}>
                  <h3 style={{ padding: '8px 8px 12px', margin: 0 }}>Itinerary</h3>
                  {explorerTravelPath.some(t => t.coords) ? (
                    <div id="explorer-map-container" style={{ width: '100%', height: '360px', borderRadius: '4px' }}></div>
                  ) : (
                    <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
                      No mapped locations for this roll yet.
                    </div>
                  )}
                </div>

                {rollMovements.length > 0 && (
                  <div className="glass-panel" style={{ padding: '32px' }}>
                    <h3 style={{ borderBottom: '1px solid var(--primary)', paddingBottom: '8px', marginBottom: '16px' }}>
                      Movements &amp; Signers
                      {rollMovements.some(m => m.date) && (
                        <span style={{ fontSize: '12px', fontWeight: 'normal', color: 'var(--text-muted)', marginLeft: '8px' }}>
                          (ordered by date where known; undated stops kept near their manuscript position)
                        </span>
                      )}
                    </h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                      {rollMovements.map(m => (
                        <div key={m.titulus_id} style={{ display: 'flex', gap: '16px', borderBottom: '1px solid var(--border)', paddingBottom: '12px' }}>
                          <div style={{ minWidth: '24px', fontWeight: 'bold', color: 'var(--accent)' }}>{m.step + 1}</div>
                          <div style={{ flex: 1 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
                              <strong>{m.location_name || m.title || 'Unknown location'}</strong>
                              {m.date_display && <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>{m.date_display}</span>}
                            </div>
                            {m.entities.length > 0 && (
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '8px' }}>
                                {m.entities.map((e, i) => (
                                  <span key={i} style={{ fontSize: '12px', background: 'var(--paper-dark)', padding: '2px 10px', borderRadius: '12px', border: '1px solid var(--border)' }}>
                                    {e.name || '?'}{e.role ? ` (${e.role})` : ''}{e.dates ? ` — ${e.dates}` : ''}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {rollDetail.tituli.map(t => (
                  <div key={t.id} className="glass-panel" style={{ padding: '32px' }}>
                    <h3 className="gold-leaf">{t.location_name || t.title}</h3>
                    <div className="latin-text">{t.latin_text}</div>
                  </div>
                ))}
              </div>
            ) : selectedRollId ? (
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: 'var(--text-muted)' }}>
                <p>Loading document details...</p>
              </div>
            ) : (
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: 'var(--text-muted)' }}>
                <p>Select a scroll from the sidebar to begin research.</p>
              </div>
            )}
          </div>

          <div style={{ display: activeTab === 'verification' ? 'flex' : 'none', flexDirection: 'column', gap: '24px', height: '100%' }}>
            {rollDetail && (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '20px', flex: 1, overflow: 'hidden' }}>
                  <div className="glass-panel" style={{ overflow: 'auto', background: '#000' }}>
                    {(() => {
                        const pdfIdx = rollDetail.roll.pdf_source.match(/\((\d+)\)/)?.[1] || 1;
                        const pages = rollDetail.roll.pdf_pages.split(',');
                        const p = pages[activeVerificationIndex]?.trim() || '3';
                        return <img src={`/api/image/${pdfIdx}/${p}/left`} style={{ transform: `scale(${zoomLevel})`, transformOrigin: 'top left', maxWidth: 'none' }} alt="manuscript" />;
                    })()}
                  </div>
                  <div className="glass-panel" style={{ padding: '24px', overflowY: 'auto' }}>
                    <h3>Transcripts & Footnotes</h3>
                    {rollDetail.tituli.map(t => <textarea key={t.id} className="search-input" style={{ height: '200px', marginBottom: '20px', fontStyle: 'italic' }} defaultValue={t.latin_text} />)}
                    <button className="tab-btn active" style={{ width: '100%' }} onClick={() => handleToggleVerify(rollDetail.roll.id)}>
                      {rollDetail.roll.is_verified ? 'Verified' : 'Approve & Save Changes'}
                    </button>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', marginTop: '16px' }}>
                  {rollDetail.roll.pdf_pages.split(',').map((p, i) => (
                    <button 
                      key={i} 
                      className={`tab-btn ${activeVerificationIndex === i ? 'active' : ''}`} 
                      onClick={() => setActiveVerificationIndex(i)}
                    >
                      Page {p.trim()}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>

          <div style={{ display: activeTab === 'map' ? 'flex' : 'none', flexDirection: 'column', gap: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h1>Historical Itineraries</h1>
              <select className="search-input" style={{ width: '300px' }} value={mapRollId || ''} onChange={e => setMapRollId(e.target.value === 'all' ? 'all' : Number(e.target.value))}>
                <option value="all">View All Travels</option>
                {rolls.map(r => <option key={r.id} value={r.id}>N° {r.roll_num} ({r.date_str})</option>)}
              </select>
            </div>

            {mapRollId === 'all' && (
              <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                <div className="glass-panel" style={{ padding: '16px 24px', flex: 1, minWidth: '300px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <span style={{ fontFamily: 'Calibri', fontWeight: 'bold' }}>Time Range: {yearFilter[0]} – {yearFilter[1]}</span>
                    <button className="tab-btn" style={{ padding: '2px 8px' }} onClick={() => setYearFilter(availableYearRange)}>Reset</button>
                  </div>
                  <RangeSlider min={availableYearRange[0]} max={availableYearRange[1]} value={yearFilter} onChange={setYearFilter} />
                </div>
                <div className="glass-panel" style={{ padding: '16px 24px', width: '250px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}><span>Min. Stops</span><span className="rubric">{stopsFilter}+</span></div>
                  <input type="range" min="0" max="20" value={stopsFilter} onChange={e => setStopsFilter(Number(e.target.value))} style={{ width: '100%', accentColor: 'var(--primary)' }} />
                </div>
              </div>
            )}
            <div className="glass-panel" style={{ padding: '12px', height: '700px' }}><div id="map-container" style={{ width: '100%', height: '100%', borderRadius: '4px' }}></div></div>

            {mapRollId === 'all' && (
              <div className="glass-panel" style={{ padding: '24px' }}>
                <h3 style={{ marginBottom: '16px', fontSize: '18px' }}>Filtered Catalogue</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '12px' }}>
                  {Object.values(allTravelsData)
                    .filter((r) => {
                      if (r.year && (r.year < yearFilter[0] || r.year > yearFilter[1])) return false;
                      if (r.num_stops < stopsFilter) return false;
                      return true;
                    })
                    .sort((a, b) => {
                      // Robust sort: extract first number from strings like "8-10"
                      const getNum = (s) => parseInt(s.toString().split('-')[0]) || 0;
                      return getNum(a.roll_num) - getNum(b.roll_num);
                    })
                    .map((r) => (
                      <div 
                        key={r.id} 
                        className="roll-item active" 
                        style={{ cursor: 'pointer', padding: '12px' }}
                        onClick={() => window.gotoRoll(r.id)}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div>
                            <div className="roll-num" style={{ fontSize: '14px' }}>N° {r.roll_num}</div>
                            <div style={{ fontWeight: 'bold', fontSize: '13px' }}>{r.date_str} — {r.num_stops} Stops</div>
                            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px', maxWidth: '400px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              Storage: {r.manuscripts || "Not specified"}
                            </div>
                          </div>
                          <ChevronRight size={16} color="var(--accent)" />
                        </div>
                      </div>
                    ))}

                </div>
              </div>
            )}
          </div>

          <div style={{ display: activeTab === 'entities' ? 'flex' : 'none', flexDirection: 'column', gap: '24px', height: '100%' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h1>Entities &amp; Connections</h1>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button className={`tab-btn ${entityView === 'people' ? 'active' : ''}`} onClick={() => { setEntityView('people'); setSelectedEntity(null); setEntitySearch(''); }}>People</button>
                <button className={`tab-btn ${entityView === 'locations' ? 'active' : ''}`} onClick={() => { setEntityView('locations'); setSelectedEntity(null); setEntitySearch(''); }}>Locations</button>
              </div>
            </div>
            <p style={{ color: 'var(--text-muted)', fontSize: '13px', maxWidth: '750px', marginTop: '-12px' }}>
              Aggregated by name across the whole corpus - a common name (e.g. "Bernard") may group
              several distinct historical individuals, not one person. Religious-order affiliation
              isn't extracted as structured data in this corpus, so it isn't shown here.
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.3fr', gap: '24px', flex: 1, minHeight: 0 }}>
              <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', padding: '16px', maxHeight: '650px' }}>
                <input type="text" className="search-input" placeholder={`Search ${entityView}...`}
                       value={entitySearch} onChange={e => setEntitySearch(e.target.value)} style={{ marginBottom: '12px' }} />
                <div style={{ overflowY: 'auto', flex: 1 }}>
                  {(entityView === 'people' ? entitiesData : locationsData).length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-muted)' }}>Loading…</div>
                  ) : (entityView === 'people' ? entitiesData : locationsData)
                    .filter(e => e.name.toLowerCase().includes(entitySearch.toLowerCase()))
                    .slice(0, 300)
                    .map(e => (
                      <div key={e.name} className={`roll-item ${selectedEntity?.name === e.name ? 'active' : ''}`}
                           onClick={() => setSelectedEntity({ type: entityView, name: e.name, data: e })}>
                        <div style={{ fontWeight: 'bold' }}>{e.name}</div>
                        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                          {entityView === 'people'
                            ? `${e.appearance_count} appearance${e.appearance_count !== 1 ? 's' : ''}${e.roles[0] ? ' · ' + e.roles[0] : ''}`
                            : `${e.roll_count} roll${e.roll_count !== 1 ? 's' : ''}`}
                        </div>
                      </div>
                    ))}
                </div>
              </div>
              <div className="glass-panel" style={{ padding: '32px', overflowY: 'auto', maxHeight: '650px' }}>
                {!selectedEntity ? (
                  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: 'var(--text-muted)' }}>
                    <p>Select a {entityView === 'people' ? 'person' : 'location'} to see their connections.</p>
                  </div>
                ) : (
                  <div>
                    <h2 style={{ marginTop: 0 }}>{selectedEntity.data.name}</h2>
                    {selectedEntity.type === 'people' && selectedEntity.data.roles.length > 0 && (
                      <p><strong>Roles seen:</strong> {selectedEntity.data.roles.join(', ')}</p>
                    )}
                    {selectedEntity.type === 'people' && selectedEntity.data.dates.length > 0 && (
                      <p><strong>Dates:</strong> {selectedEntity.data.dates.join('; ')}</p>
                    )}
                    <p><strong>{selectedEntity.type === 'people' ? 'Appears in' : 'Visited by'} {selectedEntity.data.rolls.length} roll{selectedEntity.data.rolls.length !== 1 ? 's' : ''}:</strong></p>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '16px' }}>
                      {selectedEntity.data.rolls.map(r => (
                        <span key={r.id} className="roll-num" style={{ cursor: 'pointer' }} onClick={() => window.gotoRoll(r.id)}>N° {r.roll_num}</span>
                      ))}
                    </div>
                    {selectedEntity.type === 'people' && selectedEntity.data.locations.length > 0 && (
                      <>
                        <p><strong>Associated locations:</strong></p>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '16px' }}>
                          {selectedEntity.data.locations.map(l => (
                            <span key={l} style={{ fontSize: '12px', background: 'var(--paper-dark)', padding: '2px 10px', borderRadius: '12px', border: '1px solid var(--border)' }}>{l}</span>
                          ))}
                        </div>
                      </>
                    )}
                    {selectedEntity.type === 'people' && selectedEntity.data.co_occurring.length > 0 && (
                      <>
                        <p><strong>Named alongside:</strong></p>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                          {selectedEntity.data.co_occurring.map(n => (
                            <span key={n} style={{ fontSize: '12px', background: 'var(--paper-dark)', padding: '2px 10px', borderRadius: '12px', border: '1px solid var(--border)', cursor: 'pointer' }}
                                  onClick={() => {
                                    setEntityView('people'); setEntitySearch('');
                                    const found = entitiesData.find(p => p.name === n);
                                    setSelectedEntity({ type: 'people', name: n, data: found || { name: n, roles: [], dates: [], rolls: [], locations: [], co_occurring: [] } });
                                  }}>
                              {n}
                            </span>
                          ))}
                        </div>
                      </>
                    )}
                    {selectedEntity.type === 'locations' && selectedEntity.data.people.length > 0 && (
                      <>
                        <p><strong>People named here:</strong></p>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                          {selectedEntity.data.people.map(n => (
                            <span key={n} style={{ fontSize: '12px', background: 'var(--paper-dark)', padding: '2px 10px', borderRadius: '12px', border: '1px solid var(--border)', cursor: 'pointer' }}
                                  onClick={() => {
                                    setEntityView('people'); setEntitySearch('');
                                    const found = entitiesData.find(p => p.name === n);
                                    setSelectedEntity({ type: 'people', name: n, data: found || { name: n, roles: [], dates: [], rolls: [], locations: [], co_occurring: [] } });
                                  }}>
                              {n}
                            </span>
                          ))}
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
