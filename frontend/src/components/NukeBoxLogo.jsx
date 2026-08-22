import React from "react";

export function NukeBoxLogo({ size = "md", showText = true, className = "" }) {
  const dim = size === "sm" ? "h-8 w-8" : size === "lg" ? "h-14 w-14" : "h-10 w-10";
  const textSize = size === "sm" ? "text-sm" : size === "lg" ? "text-2xl" : "text-lg";
  const sloganSize = size === "sm" ? "text-[8px]" : size === "lg" ? "text-[11px]" : "text-[9px]";

  return (
    <div className={`flex items-center gap-3 select-none ${className}`}>
      {/* Precision Candlestick Breakout Vector Emblem (Clean without text) */}
      <div className={`relative flex items-center justify-center flex-shrink-0 ${dim}`}>
        <svg
          viewBox="0 0 100 100"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="w-full h-full drop-shadow-[0_0_14px_rgba(6,182,212,0.5)]"
        >
          <defs>
            <linearGradient id="nbBoxGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#00f2fe" />
              <stop offset="45%" stopColor="#2563eb" />
              <stop offset="100%" stopColor="#0f172a" />
            </linearGradient>
            <linearGradient id="nbRimGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#818cf8" stopOpacity="0.4" />
            </linearGradient>
          </defs>

          {/* Rounded Square Box */}
          <rect
            x="6"
            y="6"
            width="88"
            height="88"
            rx="24"
            fill="url(#nbBoxGrad)"
            stroke="url(#nbRimGrad)"
            strokeWidth="2.5"
          />

          {/* Left Candle */}
          <line x1="32" y1="22" x2="32" y2="76" stroke="#ffffff" strokeWidth="3.5" strokeLinecap="round" />
          <rect x="25.5" y="34" width="13" height="30" rx="2" fill="#ffffff" />

          {/* Middle Candle (Tallest) */}
          <line x1="50" y1="14" x2="50" y2="84" stroke="#ffffff" strokeWidth="3.5" strokeLinecap="round" />
          <rect x="43.5" y="24" width="13" height="48" rx="2" fill="#ffffff" />

          {/* Right Candle */}
          <line x1="68" y1="22" x2="68" y2="76" stroke="#ffffff" strokeWidth="3.5" strokeLinecap="round" />
          <rect x="61.5" y="38" width="13" height="26" rx="2" fill="#ffffff" />

          {/* Kinetic Ascending Zigzag Trendline & Arrow */}
          <circle cx="14" cy="54" r="4" fill="#ffffff" />
          <path
            d="M 14 54 L 32 40 L 50 64 L 79 30"
            stroke="#ffffff"
            strokeWidth="5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M 68 28 L 84 25 L 81 41 Z"
            fill="#ffffff"
            stroke="#ffffff"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
        </svg>
      </div>

      {showText && (
        <div className="flex flex-col justify-center">
          <div className="flex items-center gap-1.5 leading-none">
            <span className={`font-black tracking-tight text-white font-sans ${textSize}`}>
              NUKE<span className="bg-gradient-to-r from-cyan-400 via-blue-400 to-indigo-400 bg-clip-text text-transparent">BOX</span>
            </span>
            <span className="rounded-full bg-cyan-500/15 px-1.5 py-0.5 text-[8px] font-black uppercase tracking-widest text-cyan-300 border border-cyan-500/30 font-mono">
              QUANT
            </span>
          </div>
          <span className={`font-extrabold text-cyan-400 tracking-wider font-mono mt-1 uppercase ${sloganSize}`}>
            PRECISION IN EVERY TICK
          </span>
        </div>
      )}
    </div>
  );
}
