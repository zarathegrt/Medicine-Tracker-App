import React, { useRef, useState } from 'react';
import './SpotlightCard.css';

/**
 * React Bits - SpotlightCard Component
 * Renders a subtle cursor-following radial glow on mouse movement.
 */
export default function SpotlightCard({
  children,
  className = '',
  spotlightColor = 'rgba(130, 148, 119, 0.12)',
  style = {},
  ...props
}) {
  const cardRef = useRef(null);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [opacity, setOpacity] = useState(0);

  const handleMouseMove = (e) => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    setPosition({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
  };

  const handleMouseEnter = () => {
    setOpacity(1);
  };

  const handleMouseLeave = () => {
    setOpacity(0);
  };

  return (
    <div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={`spotlight-card ${className}`}
      style={style}
      {...props}
    >
      <div
        className="spotlight-layer"
        style={{
          opacity,
          background: `radial-gradient(400px circle at ${position.x}px ${position.y}px, ${spotlightColor}, transparent 70%)`,
        }}
      />
      <div className="spotlight-content">
        {children}
      </div>
    </div>
  );
}
