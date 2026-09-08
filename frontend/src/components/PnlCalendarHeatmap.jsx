import React, { useMemo, useState } from "react";
import { Calendar, TrendingUp, TrendingDown, ShieldAlert, Award, Info } from "lucide-react";

export function PnlCalendarHeatmap({ dailyBreakdown = {}, liveHistory = [], initialCapital = 1000000 }) {
  const [hoveredDay, setHoveredDay] = useState(null);
  const [selectedYear, setSelectedYear] = useState(2026);

  // Merge DB dailyBreakdown with any live session trades in trade_history
  const dailyStats = useMemo(() => {
    const map = { ...dailyBreakdown };

    for (const t of liveHistory) {
      if (!t.exit_time) continue;
      const dateStr = String(t.exit_time).substring(0, 10);
      if (!map[dateStr]) {
        map[dateStr] = {
          date: dateStr,
          pnl: 0,
          grossPnl: 0,
          charges: 0,
          trades: 0,
          wins: 0,
          losses: 0,
        };
      }
      // If dailyBreakdown didn't already have it, aggregate from tradeHistory
      if (!dailyBreakdown[dateStr]) {
        const net = t.net_pnl != null ? t.net_pnl : (t.realized_pnl || 0);
        map[dateStr].pnl += net;
        map[dateStr].grossPnl += (t.realized_pnl || 0);
        map[dateStr].charges += (t.entry_charges || 0) + (t.exit_charges || 0);
        map[dateStr].trades += 1;
        if (net > 0) map[dateStr].wins += 1;
        else if (net < 0) map[dateStr].losses += 1;
      }
    }
    return map;
  }, [dailyBreakdown, liveHistory]);

  // Generate exact weeks of dates for the selected year
  const { calendarGrid, monthHeaders, totalPnl, winDays, lossDays, bestDay, worstDay } = useMemo(() => {
    const jan1 = new Date(selectedYear, 0, 1);
    const dec31 = new Date(selectedYear, 11, 31);

    // Align start to the preceding Monday
    const startDay = jan1.getDay(); // 0 is Sun, 1 is Mon
    const diffToMon = startDay === 0 ? -6 : 1 - startDay;
    const cur = new Date(jan1);
    cur.setDate(cur.getDate() + diffToMon);

    const weeks = [];
    const monthFirstCol = {};
    let totPnl = 0;
    let wDays = 0;
    let lDays = 0;
    let maxDay = { pnl: 0, date: "N/A" };
    let minDay = { pnl: 0, date: "N/A" };

    let weekIdx = 0;
    while (cur <= dec31 || weeks.length < 52) {
      const weekDays = [];
      for (let d = 0; d < 7; d++) {
        const y = cur.getFullYear();
        const m = cur.getMonth(); // 0 to 11
        const dt = String(cur.getDate()).padStart(2, "0");
        const monthStr = String(m + 1).padStart(2, "0");
        const dateStr = `${y}-${monthStr}-${dt}`;
        const dayOfWeek = cur.getDay(); // 0 is Sun, 1 is Mon... 6 is Sat

        // Track column index where month first appears in current year
        if (y === selectedYear && monthFirstCol[m] === undefined && cur.getDate() <= 7) {
          monthFirstCol[m] = weekIdx;
        }

        const stat = dailyStats[dateStr] || null;
        if (stat && y === selectedYear) {
          totPnl += stat.pnl;
          if (stat.pnl > 0) wDays++;
          else if (stat.pnl < 0) lDays++;
          if (stat.pnl > maxDay.pnl) maxDay = { pnl: stat.pnl, date: dateStr };
          if (stat.pnl < minDay.pnl) minDay = { pnl: stat.pnl, date: dateStr };
        }

        weekDays.push({
          dateStr,
          dayOfWeek,
          month: m,
          isWeekend: dayOfWeek === 0 || dayOfWeek === 6,
          isCurrentYear: y === selectedYear,
          stat,
        });

        cur.setDate(cur.getDate() + 1);
      }
      weeks.push(weekDays);
      weekIdx++;
      if (weeks.length >= 53) break;
    }

    const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const headers = [];
    for (let m = 0; m < 12; m++) {
      if (monthFirstCol[m] !== undefined) {
        headers.push({ name: monthNames[m], colIndex: monthFirstCol[m] });
      }
    }

    return {
      calendarGrid: weeks,
      monthHeaders: headers,
      totalPnl: totPnl,
      winDays: wDays,
      lossDays: lDays,
      bestDay: maxDay,
      worstDay: minDay,
    };
  }, [dailyStats, selectedYear]);

  // Color mapper based on Net Realized P&L
  const getCellBg = (day) => {
    if (!day.isCurrentYear) return "bg-transparent pointer-events-none";
    if (day.isWeekend) return "bg-surface3/20 opacity-30 cursor-default";
    if (!day.stat || day.stat.trades === 0) return "bg-surface3/70 hover:border-accent/40";

    const p = day.stat.pnl;
    if (p >= 5000) return "bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.6)]";
    if (p >= 1500) return "bg-emerald-600";
    if (p > 0) return "bg-emerald-700/90";
    if (p === 0) return "bg-surface3";
    if (p <= -5000) return "bg-rose-600 shadow-[0_0_6px_rgba(225,29,72,0.6)]";
    if (p <= -1500) return "bg-rose-700";
    return "bg-rose-800/90";
  };

  return (
    <div className="rounded-2xl border border-subtle bg-surface p-5 sm:p-6 shadow-sm">
      {/* Header with KPI Metrics */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-subtle/60 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <Calendar className="h-5 w-5 text-accent" />
            <h3 className="text-base font-extrabold text-primary tracking-wide">
              Annual Execution &amp; Net Alpha Matrix
            </h3>
            <span className="rounded-full bg-accent/15 px-2.5 py-0.5 text-[10px] font-bold text-accent">
              GitHub-Style Activity Heatmap
            </span>
          </div>
          <p className="text-xs text-faint mt-1">
            Day-by-day realized P&amp;L ledger across all 44 autonomous strategies
          </p>
        </div>

        {/* Year Selector and Mini KPIs */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-4 text-xs font-mono">
            <div>
              <span className="text-faint text-[10px] block">PROFIT DAYS</span>
              <span className="text-emerald-400 font-bold">{winDays} Days</span>
            </div>
            <div>
              <span className="text-faint text-[10px] block">LOSS DAYS</span>
              <span className="text-rose-400 font-bold">{lossDays} Days</span>
            </div>
            <div>
              <span className="text-faint text-[10px] block">BEST SESSION</span>
              <span className="text-emerald-400 font-bold">
                {bestDay.pnl > 0 ? `+₹${bestDay.pnl.toLocaleString("en-IN", { maximumFractionDigits: 0 })}` : "₹0"}
              </span>
            </div>
          </div>

          <select
            value={selectedYear}
            onChange={(e) => setSelectedYear(Number(e.target.value))}
            className="rounded-xl border border-subtle bg-surface2 px-3 py-1.5 text-xs font-bold text-primary focus:border-accent focus:outline-none"
          >
            <option value={2026}>2026 Active</option>
            <option value={2025}>2025 Replay</option>
          </select>
        </div>
      </div>

      {/* Heatmap Grid */}
      <div className="mt-5 overflow-x-auto pb-2">
        <div className="inline-block min-w-[840px] w-full">
          {/* Days Grid with Aligned Month Labels */}
          <div className="flex gap-1.5">
            {/* Day of Week Labels */}
            <div className="flex flex-col justify-between text-[10px] font-bold text-faint pr-2 py-0.5 h-[112px] mt-6">
              <span>Mon</span>
              <span>Wed</span>
              <span>Fri</span>
            </div>

            {/* 52-53 Week Columns */}
            <div className="flex-1">
              {/* Month Headers perfectly mapped to column offsets */}
              <div className="relative h-5 mb-1.5 text-[11px] font-semibold text-faint">
                {monthHeaders.map((mh, idx) => (
                  <span
                    key={idx}
                    className="absolute"
                    style={{ left: `${(mh.colIndex / calendarGrid.length) * 100}%` }}
                  >
                    {mh.name}
                  </span>
                ))}
              </div>

              {/* Grid Tiles */}
              <div className="flex gap-1">
                {calendarGrid.map((week, wIdx) => (
                  <div key={wIdx} className="flex flex-1 flex-col gap-1">
                    {week.map((day, dIdx) => (
                      <div
                        key={dIdx}
                        onMouseEnter={() => setHoveredDay(day)}
                        onMouseLeave={() => setHoveredDay(null)}
                        className={`h-3.5 w-full rounded-sm transition-all duration-150 cursor-pointer border border-transparent ${getCellBg(day)}`}
                      />
                    ))}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Footer: Interactive Tooltip Hover Card & Legend */}
      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-t border-subtle/50 pt-3">
        {/* Dynamic Hover Details */}
        <div className="text-xs font-mono">
          {hoveredDay && hoveredDay.stat && hoveredDay.stat.trades > 0 ? (
            <div className="flex items-center gap-3">
              <span className="font-bold text-primary">{hoveredDay.dateStr}:</span>
              <span className={hoveredDay.stat.pnl >= 0 ? "text-emerald-400 font-extrabold" : "text-rose-400 font-extrabold"}>
                {hoveredDay.stat.pnl >= 0 ? "+" : ""}₹{hoveredDay.stat.pnl.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} Net
              </span>
              <span className="text-faint">
                ({hoveredDay.stat.trades} Trades · {hoveredDay.stat.wins}W / {hoveredDay.stat.losses}L · Fees: ₹{hoveredDay.stat.charges.toFixed(1)})
              </span>
            </div>
          ) : hoveredDay && hoveredDay.isCurrentYear ? (
            <span className="text-faint">{hoveredDay.dateStr}: No Trades Recorded</span>
          ) : (
            <span className="text-faint flex items-center gap-1">
              <Info className="h-3.5 w-3.5 text-faint" /> Hover over any session block to view trade analytics
            </span>
          )}
        </div>

        {/* Legend */}
        <div className="flex items-center gap-2 text-[10px] text-faint font-semibold">
          <span>Less / Loss</span>
          <span className="h-2.5 w-2.5 rounded-sm bg-rose-600" />
          <span className="h-2.5 w-2.5 rounded-sm bg-rose-800" />
          <span className="h-2.5 w-2.5 rounded-sm bg-surface3" />
          <span className="h-2.5 w-2.5 rounded-sm bg-emerald-700" />
          <span className="h-2.5 w-2.5 rounded-sm bg-emerald-500 shadow-[0_0_4px_rgba(16,185,129,0.5)]" />
          <span>More / Alpha</span>
        </div>
      </div>
    </div>
  );
}

