import React from "react";

export function NukeBoxLogo({ size = "md", showText = true, className = "" }) {
  const dim = size === "sm" ? "h-7 w-7" : size === "lg" ? "h-12 w-12" : "h-9 w-9";
  const textSize = size === "sm" ? "text-xs" : size === "lg" ? "text-xl" : "text-sm";

  return (
    <div className={`flex items-center gap-2.5 select-none ${className}`}>
      {/* Precision Geometric Nuclear/Quantum Box Emblem */}
      <div className={`relative flex items-center justify-center ${dim}`}>
        <svg
          viewBox="0 0 44 44"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="w-full h-full drop-shadow-[0_0_12px_rgba(99,102,241,0.45)]"
        >
          <defs>
            <linearGradient id="nbGrad1" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#38bdf8" />
              <stop offset="50%" stopColor="#6366f1" />
              <stop offset="100%" stopColor="#a855f7" />
            </linearGradient>
            <linearGradient id="nbGrad2" x1="100%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#06b6d4" />
              <stop offset="100%" stopColor="#4f46e5" />
            </linearGradient>
            <radialGradient id="nbCoreGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
            </radialGradient>
          </defs>

          {/* Outer Rounded Shield Box */}
          <rect
            x="3"
            y="3"
            width="38"
            height="38"
            rx="11"
            fill="#0f172a"
            stroke="url(#nbGrad1)"
            strokeWidth="1.75"
          />

          {/* Isometric Inner Box Cube */}
          {/* Top Face */}
          <polygon
            points="22,10 32,15.5 22,21 12,15.5"
            fill="url(#nbGrad1)"
            fillOpacity="0.35"
            stroke="#38bdf8"
            strokeWidth="1.2"
          />
          {/* Left Face */}
          <polygon
            points="12,15.5 22,21 22,33 12,27.5"
            fill="url(#nbGrad2)"
            fillOpacity="0.6"
            stroke="#6366f1"
            strokeWidth="1.2"
          />
          {/* Right Face */}
          <polygon
            points="22,21 32,15.5 32,27.5 22,33"
            fill="url(#nbGrad1)"
            fillOpacity="0.85"
            stroke="#a855f7"
            strokeWidth="1.2"
          />

          {/* Central Nuclear Core Energy Orbit */}
          <circle cx="22" cy="21" r="3.5" fill="#ffffff" className="animate-pulse" />
          <circle cx="22" cy="21" r="7" fill="url(#nbCoreGlow)" />

          {/* Kinetic Energy Orbit Ring */}
          <ellipse
            cx="22"
            cy="21"
            rx="14"
            ry="5.5"
            transform="rotate(-25 22 21)"
            stroke="#38bdf8"
            strokeWidth="1"
            strokeDasharray="2 3"
            opacity="0.8"
          />
        </svg>
      </div>

      {showText && (
        <div className="flex flex-col">
          <div className="flex items-center gap-1.5 leading-none">
            <span className={`font-black tracking-tight text-white font-sans ${textSize}`}>
              NUKE<span className="bg-gradient-to-r from-cyan-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent">BOX</span>
            </span>
            <span className="rounded-full bg-indigo-500/20 px-1.5 py-0.5 text-[8px] font-black uppercase tracking-widest text-indigo-300 border border-indigo-500/40 font-mono">
              QUANT
            </span>
          </div>
          <span className="text-[9px] font-semibold text-gray-400 tracking-wider font-mono mt-0.5 uppercase">
            Derivatives Terminal
          </span>
        </div>
      )}
    </div>
  );
}
