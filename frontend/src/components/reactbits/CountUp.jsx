import React, { useEffect, useState, useRef } from 'react';

/**
 * React Bits - CountUp Component
 * Smooth numerical entrance animation with easing and reduced-motion support.
 */
export default function CountUp({
  to = 0,
  from = 0,
  duration = 1.2,
  decimals = 0,
  prefix = '',
  suffix = '',
  className = '',
}) {
  const [value, setValue] = useState(from);
  const prevToRef = useRef(from);
  const animationFrameRef = useRef(null);

  useEffect(() => {
    // Respect user reduced-motion preference
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) {
      setValue(to);
      return;
    }

    const startVal = prevToRef.current;
    const endVal = Number(to) || 0;
    prevToRef.current = endVal;

    if (startVal === endVal) {
      setValue(endVal);
      return;
    }

    const startTime = performance.now();
    const durationMs = duration * 1000;

    const easeOutQuad = (t) => t * (2 - t);

    const updateCounter = (currentTime) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / durationMs, 1);
      const easedProgress = easeOutQuad(progress);
      const current = startVal + (endVal - startVal) * easedProgress;

      setValue(current);

      if (progress < 1) {
        animationFrameRef.current = requestAnimationFrame(updateCounter);
      } else {
        setValue(endVal);
      }
    };

    animationFrameRef.current = requestAnimationFrame(updateCounter);

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [to, duration]);

  const formattedValue = decimals > 0 
    ? Number(value).toFixed(decimals) 
    : Math.round(value).toString();

  return (
    <span className={`count-up ${className}`}>
      {prefix}{formattedValue}{suffix}
    </span>
  );
}
