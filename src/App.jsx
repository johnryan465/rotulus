import React, { useState, useEffect, useRef } from 'react';
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
  };

  const handleSelectRoll = (id) => {
    setSelectedRollId(id);
    setRollDetail(null);
    fetchRollDetail(id);
  };

  const fetchRolls = async (query = '') => {
    setLoading(true);
    try {
      const isProd = import.meta.env.PROD;
      const res = await fetch(getApiUrl('/api/rolls'));
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
    window.gotoRoll = (id) => {
      if (!id) return;
      handleSelectRoll(Number(id));
      setActiveTab('explorer');
    };
    return () => { delete window.gotoRoll; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rolls]);

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

          marker.on('click', (e) => {
            window.L.DomEvent.stopPropagation(e);
            window.gotoRoll(rId);
          });

          marker.bindPopup(`
            <div style="font-family: 'Calibri', 'Candara', 'Segoe UI', 'Optima', 'Arial', sans-serif; padding: 4px; min-width: 150px;">
              <h4 style="margin: 0; color: ${color}; font-weight: bold;">Roll N° ${rInfo.roll_num}</h4>
              <div style="font-size: 13px; margin: 4px 0;">${isOrigin ? '🚩 Origin' : `📍 Stop ${index}`}: <b>${loc.name}</b></div>
              <button onclick="window.gotoRoll('${rId}')" style="background: var(--primary); color: white; border: none; padding: 6px; cursor: pointer; width: 100%; border-radius: 2px;">View Scroll Details</button>
            </div>
          `);
        });
      });
    } else {
      const coords = travelPath.map(t => t.coords).filter(c => c);
      if (coords.length > 0) {
        allCoords.push(...coords);
        if (coords.length > 1) window.L.polyline(coords, { color: 'var(--primary)', weight: 3, opacity: 0.8, dashArray: '5, 10' }).addTo(mapLayersRef.current);
        travelPath.forEach((loc) => {
          if (!loc.coords) return;
          window.L.circleMarker(loc.coords, { radius: loc.type === 'origin' ? 9 : 7, fillColor: loc.type === 'origin' ? '#8b0000' : '#10b981', color: '#fff', weight: 2, fillOpacity: 1 }).addTo(mapLayersRef.current)
            .bindPopup(`<strong>${loc.name}</strong><br/>${loc.date_str || ''}`);
        });
      }
    }

    if (allCoords.length > 0 && mapInstanceRef.current && lastFittedRollId.current !== mapRollId) {
      mapInstanceRef.current.fitBounds(window.L.latLngBounds(allCoords), { padding: [50, 50] });
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

  return (
    <div className="main-container">
      <div className="top-nav">
        <div className="logo-section" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <BookOpen color="var(--primary)" size={28} />
          <div className="logo-text">ROTULUS</div>
        </div>
        <div className="tabs-nav">
          {['dashboard', 'explorer', 'map', 'verification'].map(t => (
            <button key={t} className={`tab-btn ${activeTab === t ? 'active' : ''}`} onClick={() => setActiveTab(t)}>
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
                <div className="glass-panel" style={{ padding: '32px' }}>
                  <h3>Scholarly Description</h3><p>{rollDetail.roll.title}</p>
                  <div style={{ marginTop: '24px', background: 'rgba(0,0,0,0.03)', padding: '16px' }}>Manuscripts: {rollDetail.roll.manuscripts}</div>
                </div>
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
                  {Object.entries(allTravelsData)
                    .filter(([, r]) => {
                      if (r.year && (r.year < yearFilter[0] || r.year > yearFilter[1])) return false;
                      if (r.num_stops < stopsFilter) return false;
                      return true;
                    })
                    .sort((a, b) => Number(a[1].roll_num) - Number(b[1].roll_num))
                    .map(([id, r]) => (
                      <div 
                        key={id} 
                        className="roll-item active" 
                        style={{ cursor: 'pointer', padding: '12px' }}
                        onClick={() => window.gotoRoll(id)}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div>
                            <div className="roll-num" style={{ fontSize: '14px' }}>N° {r.roll_num}</div>
                            <div style={{ fontWeight: 'bold', fontSize: '13px' }}>{r.year} AD</div>
                          </div>
                          <ChevronRight size={16} color="var(--accent)" />
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
