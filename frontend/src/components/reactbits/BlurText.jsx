import React, { useEffect, useState } from 'react';
import './BlurText.css';

/**
 * React Bits - BlurText Component
 * Subtle blur-to-sharp staggered text reveal animation.
 */
export default function BlurText({
  text = '',
  delay = 50,
  className = '',
  as: Component = 'span',
}) {
  const [inView, setInView] = useState(false);
  const words = text.split(' ');

  useEffect(() => {
    // Respect reduced motion
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) {
      setInView(true);
      return;
    }

    const timer = setTimeout(() => {
      setInView(true);
    }, 40);

    return () => clearTimeout(timer);
  }, []);

  return (
    <Component className={`blur-text-root ${className}`}>
      {words.map((word, wordIndex) => (
        <span
          key={wordIndex}
          className={`blur-text-word ${inView ? 'animate-in' : ''}`}
          style={{
            transitionDelay: `${wordIndex * delay}ms`,
          }}
        >
          {word}&nbsp;
        </span>
      ))}
    </Component>
  );
}
