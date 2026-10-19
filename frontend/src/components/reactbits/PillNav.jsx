import React, { useRef, useEffect, useState } from 'react';
import './PillNav.css';

/**
 * React Bits - PillNav Component
 * Provides a modern navigation bar with a smooth sliding pill background indicator.
 */
export default function PillNav({ items = [], activeId, onChange, className = '' }) {
  const [indicatorStyle, setIndicatorStyle] = useState({ left: 0, width: 0, opacity: 0 });
  const containerRef = useRef(null);
  const itemRefs = useRef({});

  useEffect(() => {
    const activeEl = itemRefs.current[activeId];
    const container = containerRef.current;

    if (activeEl && container) {
      const containerRect = container.getBoundingClientRect();
      const activeRect = activeEl.getBoundingClientRect();

      setIndicatorStyle({
        left: activeRect.left - containerRect.left,
        width: activeRect.width,
        opacity: 1,
      });
    }
  }, [activeId, items]);

  return (
    <nav className={`pill-nav-container ${className}`} ref={containerRef}>
      <div
        className="pill-nav-indicator"
        style={{
          transform: `translateX(${indicatorStyle.left}px)`,
          width: `${indicatorStyle.width}px`,
          opacity: indicatorStyle.opacity,
        }}
      />
      {items.map((item) => {
        const isActive = activeId === item.id;
        const Icon = item.icon;

        return (
          <button
            key={item.id}
            ref={(el) => (itemRefs.current[item.id] = el)}
            onClick={() => onChange(item.id)}
            className={`pill-nav-item ${isActive ? 'is-active' : ''}`}
            type="button"
            role="tab"
            aria-selected={isActive}
          >
            {Icon && <Icon className="pill-nav-icon" size={17} />}
            <span className="pill-nav-label">{item.label}</span>
            {item.badge !== undefined && (
              <span className={`pill-nav-badge ${isActive ? 'badge-active' : ''}`}>
                {item.badge}
              </span>
            )}
          </button>
        );
      })}
    </nav>
  );
}
