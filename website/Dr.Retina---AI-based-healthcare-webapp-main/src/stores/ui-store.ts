"use client";

import { create } from "zustand";

/**
 * Shared CLIENT-ONLY UI state (sidebar, viewer settings, workflow UI).
 * NEVER authentication, authorization, or domain truth — those live in
 * the session layer / backend / TanStack Query respectively.
 */
interface UiState {
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  activeHotspotId: string | null;
  setActiveHotspotId: (id: string | null) => void;
}

export const useUiStore = create<UiState>((set) => ({
  sidebarOpen: true,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  activeHotspotId: null,
  setActiveHotspotId: (id) => set({ activeHotspotId: id }),
}));
