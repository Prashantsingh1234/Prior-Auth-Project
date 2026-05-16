import { create } from 'zustand'
import type { ExtractedEntity, PolicyCriterion } from '@/api/types'

interface ReviewState {
  // Entity highlighting — syncs DocumentViewer ↔ ExtractedEntitiesPanel
  highlightedEntityId: string | null
  highlightedChunkId: string | null
  setHighlightedEntity: (entityId: string | null) => void
  setHighlightedChunk: (chunkId: string | null) => void

  // Document viewer state
  currentPage: number
  totalPages: number
  zoom: number
  setCurrentPage: (page: number) => void
  setTotalPages: (total: number) => void
  setZoom: (zoom: number) => void

  // Expanded entity/criterion tracking
  expandedEntityIds: Set<string>
  toggleEntityExpanded: (id: string) => void

  // Panel visibility (for mobile / focus mode)
  showDocumentPanel: boolean
  showEntitiesPanel: boolean
  showActionsPanel: boolean
  togglePanel: (panel: 'document' | 'entities' | 'actions') => void

  // Active action modal
  activeModal: 'approve' | 'deny' | 'pend' | 'escalate' | 'note' | null
  setActiveModal: (modal: ReviewState['activeModal']) => void
}

export const useReviewStore = create<ReviewState>()((set) => ({
  highlightedEntityId: null,
  highlightedChunkId: null,
  setHighlightedEntity: (id) => set({ highlightedEntityId: id }),
  setHighlightedChunk: (id) => set({ highlightedChunkId: id }),

  currentPage: 1,
  totalPages: 1,
  zoom: 1.0,
  setCurrentPage: (page) => set({ currentPage: page }),
  setTotalPages: (total) => set({ totalPages: total }),
  setZoom: (zoom) => set({ zoom: Math.max(0.5, Math.min(3.0, zoom)) }),

  expandedEntityIds: new Set(),
  toggleEntityExpanded: (id) =>
    set((state) => {
      const next = new Set(state.expandedEntityIds)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return { expandedEntityIds: next }
    }),

  showDocumentPanel: true,
  showEntitiesPanel: true,
  showActionsPanel: true,
  togglePanel: (panel) =>
    set((state) => ({
      showDocumentPanel: panel === 'document' ? !state.showDocumentPanel : state.showDocumentPanel,
      showEntitiesPanel: panel === 'entities' ? !state.showEntitiesPanel : state.showEntitiesPanel,
      showActionsPanel:  panel === 'actions'  ? !state.showActionsPanel  : state.showActionsPanel,
    })),

  activeModal: null,
  setActiveModal: (modal) => set({ activeModal: modal }),
}))
