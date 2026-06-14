import React, { useState, useEffect, useRef, useCallback } from 'react';

const RangeSlider = ({ min, max, value, onChange }) => {
  const [lower, upper] = value;
  const sliderRef = useRef(null);
  const [activeHandle, setActiveHandle] = useState(null); // 'lower' or 'upper'

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
  }, [min, max, sliderRef]);

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

  return (
    <div className="range-container" ref={sliderRef}>
      <div className="range-track" />
      <div 
        className="range-highlight" 
        style={{ left: `${lp}%`, width: `${up - lp}%` }} 
      />
      <div 
        className="range-thumb"
        style={{ left: `${lp}%`, zIndex: activeHandle === 'lower' ? 10 : 5 }}
        onMouseDown={(e) => { e.preventDefault(); setActiveHandle('lower'); }}
        onTouchStart={() => setActiveHandle('lower')}
      />
      <div 
        className="range-thumb"
        style={{ left: `${up}%`, zIndex: activeHandle === 'upper' ? 10 : 4 }}
        onMouseDown={(e) => { e.preventDefault(); setActiveHandle('upper'); }}
        onTouchStart={() => setActiveHandle('upper')}
      />
    </div>
  );
};

export default RangeSlider;
