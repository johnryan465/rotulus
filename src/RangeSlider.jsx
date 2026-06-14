import { useState, useEffect, useRef, useCallback } from 'react';

const RangeSlider = ({ min, max, value, onChange }) => {
  const [lower, upper] = value;
  const sliderRef = useRef(null);
  const [activeHandle, setActiveHandle] = useState(null);

  const getPercentage = useCallback((val) => {
    if (max === min) return 0;
    return ((val - min) / (max - min)) * 100;
  }, [min, max]);

  const getValueFromPos = useCallback((clientX) => {
    if (!sliderRef.current) return min;
    const rect = sliderRef.current.getBoundingClientRect();
    const pos = (clientX - rect.left) / rect.width;
    let val = Math.round(pos * (max - min) + min);
    return Math.max(min, Math.min(max, val));
  }, [min, max]);

  useEffect(() => {
    const handleMove = (clientX) => {
      if (!activeHandle) return;
      const val = getValueFromPos(clientX);
      if (activeHandle === 'lower') {
        if (val < upper) onChange([val, upper]);
      } else {
        if (val > lower) onChange([lower, val]);
      }
    };

    const onMouseMove = (e) => handleMove(e.clientX);
    const onTouchMove = (e) => handleMove(e.touches[0].clientX);
    const onEnd = () => setActiveHandle(null);

    if (activeHandle) {
      window.addEventListener('mousemove', onMouseMove);
      window.addEventListener('mouseup', onEnd);
      window.addEventListener('touchmove', onTouchMove);
      window.addEventListener('touchend', onEnd);
    }
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onEnd);
      window.removeEventListener('touchmove', onTouchMove);
      window.removeEventListener('touchend', onEnd);
    };
  }, [activeHandle, lower, upper, onChange, getValueFromPos]);

  const lp = getPercentage(lower);
  const up = getPercentage(upper);

  // Styles defined here to bypass CSS loading issues
  const containerStyle = {
    position: 'relative',
    width: '100%',
    height: '40px',
    userSelect: 'none',
    margin: '8px 0',
    cursor: activeHandle ? 'grabbing' : 'default',
    display: 'flex',
    alignItems: 'center'
  };

  const trackStyle = {
    position: 'absolute',
    width: '100%',
    height: '6px',
    background: 'rgba(0, 0, 0, 0.15)',
    borderRadius: '3px',
    zIndex: 1,
    top: '50%',
    transform: 'translateY(-50%)'
  };

  const highlightStyle = {
    position: 'absolute',
    height: '6px',
    background: '#8b0000', // Rubric Red
    borderRadius: '3px',
    zIndex: 2,
    top: '50%',
    transform: 'translateY(-50%)',
    left: `${lp}%`,
    width: `${up - lp}%`
  };

  const thumbBaseStyle = {
    position: 'absolute',
    width: '24px',
    height: '24px',
    background: '#f4ecd8', // Parchment
    border: '2px solid #8b0000', // Rubric Red
    borderRadius: '50%',
    cursor: 'grab',
    zIndex: 10,
    top: '50%',
    transform: 'translate(-50%, -50%)',
    boxShadow: '0 2px 6px rgba(0,0,0,0.3)',
    transition: 'transform 0.1s ease'
  };

  return (
    <div className="range-container" ref={sliderRef} style={containerStyle} data-slider-v="3">
      <div className="range-track" style={trackStyle} />
      <div className="range-highlight" style={highlightStyle} />
      <div 
        className="range-thumb"
        style={{ ...thumbBaseStyle, left: `${lp}%`, zIndex: activeHandle === 'lower' ? 12 : 11 }}
        onMouseDown={(e) => { e.preventDefault(); setActiveHandle('lower'); }}
        onTouchStart={(e) => { e.preventDefault(); setActiveHandle('lower'); }}
      />
      <div 
        className="range-thumb"
        style={{ ...thumbBaseStyle, left: `${up}%`, zIndex: activeHandle === 'upper' ? 12 : 10 }}
        onMouseDown={(e) => { e.preventDefault(); setActiveHandle('upper'); }}
        onTouchStart={(e) => { e.preventDefault(); setActiveHandle('upper'); }}
      />
    </div>
  );
};

export default RangeSlider;
