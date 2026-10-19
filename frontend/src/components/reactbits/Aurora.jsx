import React from 'react';
import './Aurora.css';

/**
 * React Bits - Aurora Component
 * Calming, low-opacity ambient gradient glow designed for hero/welcome cards.
 */
export default function Aurora({
  color1 = '#829477',
  color2 = '#E8E2F5',
  color3 = '#D1DDD0',
  opacity = 0.45,
  className = '',
}) {
  return (
    <div
      className={`aurora-container ${className}`}
      style={{
        '--aurora-c1': color1,
        '--aurora-c2': color2,
        '--aurora-c3': color3,
        opacity,
      }}
      aria-hidden="true"
    >
      <div className="aurora-blob aurora-blob-1" />
      <div className="aurora-blob aurora-blob-2" />
      <div className="aurora-blob aurora-blob-3" />
    </div>
  );
}
