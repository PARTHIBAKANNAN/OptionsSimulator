import React from "react";

export function NukeBoxLogo({ size = "md", showText = true, className = "" }) {
  const logoUrl = `${import.meta.env.BASE_URL}assets/nukebox_logo.png`;
  
  const dim = size === "sm" ? "h-8 w-8" : size === "lg" ? "h-14 w-14" : "h-10 w-10";
  const textSize = size === "sm" ? "text-xs" : size === "lg" ? "text-xl" : "text-sm";
  const sloganSize = size === "sm" ? "text-[8px]" : size === "lg" ? "text-[11px]" : "text-[9px]";

  return (
    <div className={`flex items-center gap-2.5 select-none ${className}`}>
      {/* Official Candlestick Breakout Logo Emblem */}
      <div className={`relative flex items-center justify-center rounded-xl overflow-hidden shadow-md shadow-cyan-500/20 ${dim}`}>
        <img
          src={logoUrl}
          alt="NUKEBOX Logo"
          className="h-full w-full object-cover rounded-xl"
          onError={(e) => {
            e.target.style.display = "none";
          }}
        />
      </div>

      {showText && (
        <div className="flex flex-col">
          <div className="flex items-center gap-1.5 leading-none">
            <span className={`font-black tracking-tight text-white font-sans ${textSize}`}>
              NUKE<span className="bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">BOX</span>
            </span>
            <span className="rounded-full bg-cyan-500/15 px-1.5 py-0.5 text-[8px] font-black uppercase tracking-widest text-cyan-300 border border-cyan-500/30 font-mono">
              QUANT
            </span>
          </div>
          <span className={`font-extrabold text-cyan-400 tracking-wider font-mono mt-0.5 uppercase ${sloganSize}`}>
            PRECISION IN EVERY TICK
          </span>
        </div>
      )}
    </div>
  );
}
