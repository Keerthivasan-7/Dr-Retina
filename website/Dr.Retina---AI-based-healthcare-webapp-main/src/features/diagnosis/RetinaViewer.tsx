"use client";

import * as React from "react";
import { Activity, CheckCircle2, X } from "lucide-react";
import { cn } from "@/lib/utils/cn";

interface Hotspot {
  id: string;
  title: string;
  label: string;
  x: string;
  y: string;
  xNum: number;
  yNum: number;
  side: "left" | "right";
  status: string;
  desc: string;
}

const HOTSPOTS: Hotspot[] = [
  {
    id: "optic-disc",
    title: "Optic Disc Assessment",
    label: "Optic",
    x: "28%",
    y: "48%",
    xNum: 0.28,
    yNum: 0.48,
    side: "left",
    status: "Normal CDR 0.35",
    desc: "Optic nerve head boundary segmentation & cup-to-disc ratio analysis for secondary glaucoma triage.",
  },
  {
    id: "macula",
    title: "Macular Zone & Fovea",
    label: "Macular",
    x: "62%",
    y: "52%",
    xNum: 0.62,
    yNum: 0.52,
    side: "right",
    status: "High Sensitivity Zone",
    desc: "Deep learning assessment for diabetic macular edema (DME) and hard exudates in central vision.",
  },
  {
    id: "superior-arcade",
    title: "Superior Vascular Arcade",
    label: "Superior",
    x: "46%",
    y: "22%",
    xNum: 0.46,
    yNum: 0.22,
    side: "right",
    status: "Vessel Caliber 1:1",
    desc: "Arteriovenous ratio (AVR) calculation and automated microaneurysm cluster identification.",
  },
  {
    id: "inferior-arcade",
    title: "Inferior Arcade & Triage",
    label: "Inferior",
    x: "42%",
    y: "78%",
    xNum: 0.42,
    yNum: 0.78,
    side: "left",
    status: "AI Quad-Scan Clear",
    desc: "Four-quadrant automated lesion detection adhering to International Clinical DR Grading standard.",
  },
];

/**
 * Interactive fundus viewer. Isolated client-only island: uses window resize
 * listeners and measured DOM geometry. Dynamically imported by the landing
 * page so its JS is never shipped to dashboard routes.
 */
export function RetinaViewer() {
  const [activeHotspot, setActiveHotspot] = React.useState<Hotspot | null>(null);
  const circleRef = React.useRef<HTMLDivElement>(null);
  const [circleSize, setCircleSize] = React.useState({ width: 440, height: 440 });

  React.useEffect(() => {
    const updateSize = () => {
      if (circleRef.current) {
        const rect = circleRef.current.getBoundingClientRect();
        setCircleSize({ width: rect.width, height: rect.height });
      }
    };
    updateSize();
    window.addEventListener("resize", updateSize);
    return () => window.removeEventListener("resize", updateSize);
  }, []);

  const connector = React.useMemo(() => {
    if (!activeHotspot) return null;
    const hotspotX = circleSize.width * activeHotspot.xNum;
    const hotspotY = circleSize.height * activeHotspot.yNum;
    const cardEdgeX =
      activeHotspot.side === "left" ? -32 : circleSize.width + 32;
    return { x1: cardEdgeX, y1: hotspotY, x2: hotspotX, y2: hotspotY, hotspotX, hotspotY, cardEdgeX };
  }, [activeHotspot, circleSize]);

  return (
    <div className="relative w-full max-w-5xl mx-auto flex flex-col items-center justify-center py-4 select-none">
      <div
        ref={circleRef}
        className="relative w-full max-w-72 sm:max-w-none sm:w-96 sm:h-96 md:w-[440px] md:h-[440px] aspect-square flex items-center justify-center"
      >
        <div className="absolute inset-0 rounded-full bg-gradient-to-tr from-brand-500/20 via-cyan-400/15 to-blue-400/20 blur-3xl transform -rotate-12 animate-pulse-slow pointer-events-none" />
        <div className="relative w-full h-full rounded-full p-5 sm:p-6 bg-gradient-to-b from-slate-900/5 to-slate-900/10 backdrop-blur-sm border border-brand-500/20 shadow-2xl flex items-center justify-center overflow-hidden">
          <div className="relative w-full h-full rounded-full bg-gradient-to-br from-[#3d1008] via-[#7a2010] to-[#4a1508] shadow-inner flex items-center justify-center overflow-hidden border border-orange-900/40">
            <div className="absolute inset-0 bg-[linear-gradient(to_right,#c0521510_1px,transparent_1px),linear-gradient(to_bottom,#c0521510_1px,transparent_1px)] bg-[size:24px_24px]" />
            <div className="absolute inset-0 rounded-full bg-[radial-gradient(circle_at_38%_50%,rgba(220,100,30,0.75)_0%,rgba(160,50,10,0.60)_25%,rgba(80,15,5,0.80)_60%,rgba(30,5,2,0.95)_100%)]" />
            <svg className="absolute inset-0 w-full h-full opacity-90 pointer-events-none" viewBox="0 0 400 400" fill="none" aria-hidden="true">
              <defs>
                <radialGradient id="opticGlow" cx="0.5" cy="0.5" r="0.5" fx="0.5" fy="0.5">
                  <stop offset="0%" stopColor="#fff8e1" stopOpacity="1" />
                  <stop offset="30%" stopColor="#ffcc80" stopOpacity="0.85" />
                  <stop offset="65%" stopColor="#f97316" stopOpacity="0.45" />
                  <stop offset="100%" stopColor="#7c2d12" stopOpacity="0" />
                </radialGradient>
                <radialGradient id="maculaGlow" cx="0.5" cy="0.5" r="0.5" fx="0.5" fy="0.5">
                  <stop offset="0%" stopColor="#1c0700" stopOpacity="0.85" />
                  <stop offset="50%" stopColor="#7c2d12" stopOpacity="0.35" />
                  <stop offset="100%" stopColor="#c2410c" stopOpacity="0" />
                </radialGradient>
                <radialGradient id="lesion1" cx="0.5" cy="0.5" r="0.5">
                  <stop offset="0%" stopColor="#fde68a" stopOpacity="0.35" />
                  <stop offset="100%" stopColor="#f97316" stopOpacity="0" />
                </radialGradient>
                <radialGradient id="lesion2" cx="0.5" cy="0.5" r="0.5">
                  <stop offset="0%" stopColor="#fef3c7" stopOpacity="0.28" />
                  <stop offset="100%" stopColor="#c2410c" stopOpacity="0" />
                </radialGradient>
                <radialGradient id="choroid" cx="0.5" cy="0.5" r="0.5">
                  <stop offset="0%" stopColor="#dc6820" stopOpacity="0.55" />
                  <stop offset="55%" stopColor="#9a3412" stopOpacity="0.30" />
                  <stop offset="100%" stopColor="#3d0f04" stopOpacity="0" />
                </radialGradient>
              </defs>
              <circle cx="200" cy="200" r="200" fill="url(#choroid)" />
              <circle cx="135" cy="200" r="36" fill="url(#opticGlow)" />
              <circle cx="135" cy="200" r="20" fill="#fff8e1" fillOpacity="0.55" />
              <circle cx="135" cy="200" r="9" fill="#fffde7" fillOpacity="0.90" />
              <ellipse cx="255" cy="205" rx="30" ry="26" fill="url(#maculaGlow)" />
              <circle cx="255" cy="205" r="3.5" fill="#fff8e1" fillOpacity="0.55" />
              <path d="M135 200 C 148 162, 172 128, 228 98 C 278 72, 335 80, 375 115" stroke="#b91c1c" strokeWidth="4" strokeLinecap="round" opacity="0.90" />
              <path d="M135 200 C 152 168, 192 138, 248 122 C 305 108, 358 132, 390 168" stroke="#dc2626" strokeWidth="2.4" strokeLinecap="round" opacity="0.75" />
              <path d="M228 98 C 248 82, 278 62, 318 55" stroke="#ef4444" strokeWidth="1.8" strokeLinecap="round" opacity="0.60" />
              <path d="M248 122 C 270 105, 305 90, 340 88" stroke="#f87171" strokeWidth="1.4" strokeLinecap="round" opacity="0.50" />
              <path d="M135 200 C 148 238, 172 272, 228 302 C 278 328, 335 320, 375 285" stroke="#b91c1c" strokeWidth="4" strokeLinecap="round" opacity="0.90" />
              <path d="M135 200 C 152 232, 192 262, 248 278 C 305 292, 358 268, 390 232" stroke="#dc2626" strokeWidth="2.4" strokeLinecap="round" opacity="0.75" />
              <path d="M228 302 C 248 318, 278 338, 318 345" stroke="#ef4444" strokeWidth="1.8" strokeLinecap="round" opacity="0.60" />
              <path d="M135 200 C 100 185, 68 178, 22 188" stroke="#991b1b" strokeWidth="2.2" strokeLinecap="round" opacity="0.65" />
              <path d="M135 200 C 100 215, 68 222, 22 212" stroke="#991b1b" strokeWidth="2.2" strokeLinecap="round" opacity="0.65" />
              <path d="M220 165 C 238 152, 255 148, 268 155" stroke="#f87171" strokeWidth="1.2" strokeLinecap="round" opacity="0.45" />
              <path d="M220 240 C 238 252, 255 258, 268 252" stroke="#f87171" strokeWidth="1.2" strokeLinecap="round" opacity="0.45" />
              <circle cx="300" cy="145" r="18" fill="url(#lesion1)" />
              <circle cx="180" cy="260" r="14" fill="url(#lesion2)" />
              <circle cx="320" cy="260" r="12" fill="url(#lesion1)" />
            </svg>
            <div className="absolute inset-x-0 h-1 bg-gradient-to-r from-transparent via-cyan-400 to-transparent shadow-[0_0_15px_#22d3ee] animate-scan pointer-events-none" />
            {HOTSPOTS.map((spot) => {
              const isSelected = activeHotspot?.id === spot.id;
              return (
                <div key={spot.id} style={{ left: spot.x, top: spot.y }} className="absolute -translate-x-1/2 -translate-y-1/2 cursor-pointer group z-10">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setActiveHotspot(isSelected ? null : spot);
                    }}
                    aria-expanded={isSelected}
                    aria-label={`${spot.title} details`}
                    className="relative flex items-center justify-center"
                  >
                    <span className={cn("absolute w-8 h-8 rounded-full animate-ping", isSelected ? "bg-cyan-300/60" : "bg-brand-400/30")} />
                    <span className={cn("w-6 h-6 rounded-full border-2 flex items-center justify-center shadow-lg transition-all duration-200 transform group-hover:scale-125", isSelected ? "bg-cyan-400 border-white scale-125 ring-4 ring-brand-400/40 shadow-cyan-400/50" : "bg-slate-900/80 border-brand-300 text-brand-300")}>
                      <span className="w-2 h-2 rounded-full bg-white" />
                    </span>
                  </button>
                  <div className={cn("absolute left-1/2 -translate-x-1/2 top-7 whitespace-nowrap px-2.5 py-0.5 rounded-full backdrop-blur-md border text-[10px] font-semibold shadow-md flex items-center gap-1 transition-all", isSelected ? "bg-brand-600 text-white border-brand-300 scale-105 shadow-brand-600/30" : "bg-slate-900/85 text-brand-200 border-brand-500/40")}>
                    <span className={cn("w-1.5 h-1.5 rounded-full", isSelected ? "bg-white" : "bg-brand-400")} />
                    {spot.label}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {activeHotspot && connector && (
          <svg className="absolute inset-0 w-full h-full pointer-events-none overflow-visible hidden xl:block z-20" style={{ width: circleSize.width, height: circleSize.height }} aria-hidden="true">
            <line x1={connector.x1} y1={connector.y1} x2={connector.x2} y2={connector.y2} stroke="#2563eb" strokeWidth="2" strokeDasharray="4 3" className="animate-pulse" />
            <circle cx={connector.hotspotX} cy={connector.hotspotY} r="4.5" fill="#2563eb" stroke="#ffffff" strokeWidth="2" />
            <circle cx={connector.cardEdgeX} cy={connector.y1} r="3.5" fill="#2563eb" />
          </svg>
        )}

        {activeHotspot && (
          <div className={cn("hidden xl:block absolute top-1/2 -translate-y-1/2 z-30 w-64 animate-fade-in", activeHotspot.side === "left" ? "right-[calc(100%+36px)]" : "left-[calc(100%+36px)]")} style={{ top: `${activeHotspot.yNum * 100}%` }}>
            <HotspotCard hotspot={activeHotspot} onClose={() => setActiveHotspot(null)} />
          </div>
        )}
      </div>

      {activeHotspot && (
        <div className="block xl:hidden mt-6 w-full max-w-sm px-2 animate-fade-in z-20">
          <HotspotCard hotspot={activeHotspot} onClose={() => setActiveHotspot(null)} />
        </div>
      )}
    </div>
  );
}

function HotspotCard({ hotspot, onClose }: { hotspot: Hotspot; onClose: () => void }) {
  return (
    <div className="bg-white/95 backdrop-blur-md border border-brand-200/90 shadow-xl shadow-brand-950/5 rounded-2xl p-4 text-left text-slate-800 relative">
      <div className="flex items-start justify-between gap-2 pb-2 mb-2 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-brand-50 text-brand-700 border border-brand-100 flex items-center justify-center flex-shrink-0">
            <Activity className="w-3.5 h-3.5 text-brand-600" aria-hidden="true" />
          </div>
          <h4 className="text-xs font-bold text-slate-900 tracking-tight leading-snug">{hotspot.title}</h4>
        </div>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors p-0.5 rounded-md hover:bg-slate-100 flex-shrink-0" aria-label="Close panel">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
      <div className="mb-2">
        <span className="inline-block text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-brand-50 text-brand-800 border border-brand-200/80">{hotspot.status}</span>
      </div>
      <p className="text-xs text-slate-600 leading-relaxed">{hotspot.desc}</p>
      <div className="mt-3 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
        <span className="flex items-center gap-1 font-medium text-brand-600">
          <CheckCircle2 className="w-3 h-3 text-brand-500" aria-hidden="true" />
          <span>AI Segmented</span>
        </span>
        <span className="text-[10px] text-slate-400 font-normal">ICDR Protocol</span>
      </div>
    </div>
  );
}
