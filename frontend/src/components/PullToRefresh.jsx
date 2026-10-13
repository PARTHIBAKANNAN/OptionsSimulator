import { useState, useRef, useEffect } from "react";
import { RefreshCw, Check } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const PULL_THRESHOLD = 65; // px of pull needed to trigger refresh
const MAX_PULL = 90; // maximum visual pull distance

export function PullToRefresh({ onRefresh, children }) {
  const [pullDistance, setPullDistance] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  const startYRef = useRef(0);
  const isPullingRef = useRef(false);
  const hasVibratedRef = useRef(false);

  const handleTouchStart = (e) => {
    // Only allow pull-to-refresh if user is at the very top of the scroll
    if (window.scrollY <= 0 && !isRefreshing) {
      startYRef.current = e.touches[0].clientY;
      isPullingRef.current = true;
      hasVibratedRef.current = false;
    }
  };

  const handleTouchMove = (e) => {
    if (!isPullingRef.current || isRefreshing) return;

    const currentY = e.touches[0].clientY;
    const diff = currentY - startYRef.current;

    // Only handle downward drag when scroll is at the top
    if (diff > 0 && window.scrollY <= 0) {
      // Resistance curve: diminishing returns as user pulls further
      const distance = Math.min(diff * 0.45, MAX_PULL);
      setPullDistance(distance);

      // Light haptic feedback once threshold is crossed
      if (distance >= PULL_THRESHOLD && !hasVibratedRef.current) {
        hasVibratedRef.current = true;
        if (navigator.vibrate) {
          try {
            navigator.vibrate(20);
          } catch {
            // ignore if blocked by browser policy
          }
        }
      } else if (distance < PULL_THRESHOLD) {
        hasVibratedRef.current = false;
      }
    } else {
      setPullDistance(0);
    }
  };

  const handleTouchEnd = async () => {
    if (!isPullingRef.current) return;
    isPullingRef.current = false;

    if (pullDistance >= PULL_THRESHOLD && !isRefreshing) {
      setIsRefreshing(true);
      setPullDistance(55); // Hold at indicator height while refreshing

      try {
        if (onRefresh) {
          await Promise.all([
            onRefresh(),
            new Promise((resolve) => setTimeout(resolve, 600)), // minimum pleasant animation duration
          ]);
        }
        setIsSuccess(true);
        if (navigator.vibrate) {
          try {
            navigator.vibrate([15, 30]);
          } catch {
            // ignore
          }
        }
        await new Promise((resolve) => setTimeout(resolve, 400));
      } catch (err) {
        console.error("Pull-to-refresh failed:", err);
      } finally {
        setIsSuccess(false);
        setIsRefreshing(false);
        setPullDistance(0);
      }
    } else {
      setPullDistance(0);
    }
  };

  const progress = Math.min(pullDistance / PULL_THRESHOLD, 1);
  const isTriggerable = pullDistance >= PULL_THRESHOLD;

  return (
    <div
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      className="relative w-full"
    >
      {/* Pull indicator floating badge */}
      <AnimatePresence>
        {(pullDistance > 10 || isRefreshing) && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{
              opacity: 1,
              y: pullDistance,
              transition: { type: "spring", stiffness: 350, damping: 25 },
            }}
            exit={{ opacity: 0, y: -20, transition: { duration: 0.2 } }}
            className="fixed top-14 left-0 right-0 z-50 flex justify-center pointer-events-none"
          >
            <div
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-full border shadow-lg backdrop-blur-md transition-all ${
                isSuccess
                  ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                  : isTriggerable || isRefreshing
                  ? "bg-accent/20 text-accent border-accent/40 scale-105"
                  : "bg-surface/90 text-muted border-subtle"
              }`}
            >
              {isSuccess ? (
                <>
                  <Check className="h-4 w-4 text-emerald-400 animate-scale-in" />
                  <span className="text-xs font-bold text-emerald-400">Updated</span>
                </>
              ) : (
                <>
                  <RefreshCw
                    className={`h-4 w-4 transition-transform ${
                      isRefreshing ? "animate-spin text-accent" : ""
                    }`}
                    style={{
                      transform: isRefreshing ? undefined : `rotate(${progress * 180}deg)`,
                    }}
                  />
                  <span className="text-xs font-semibold">
                    {isRefreshing
                      ? "Refreshing data..."
                      : isTriggerable
                      ? "Release to refresh"
                      : "Pull to refresh"}
                  </span>
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Content with subtle translateY resistance */}
      <div
        style={{
          transform: pullDistance > 0 ? `translateY(${pullDistance * 0.4}px)` : "none",
          transition: isPullingRef.current ? "none" : "transform 0.25s ease-out",
        }}
      >
        {children}
      </div>
    </div>
  );
}
