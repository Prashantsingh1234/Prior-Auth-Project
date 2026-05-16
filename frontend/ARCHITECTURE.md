src/
├── app/                          # Application root — wires providers + router
│   ├── App.tsx                   # Root component: <BrowserRouter><AppProviders><AppRouter>
│   └── router.tsx                # Lazy routes, auth guards, permission guards, Suspense wrappers
│
├── providers/                    # Provider composition layer
│   ├── index.tsx                 # AppProviders: QueryProvider > ThemeProvider > AuthProvider
│   ├── QueryProvider.tsx         # React Query client + DevTools
│   ├── ThemeProvider.tsx         # Applies dark/light class; reacts to system preference
│   └── AuthProvider.tsx          # Token expiry watcher; redirects to /login on expire
│
├── config/                       # Static, import-time configuration
│   ├── app.config.ts             # API base URL, timeouts, upload limits, feature flags, cache TTLs
│   └── routes.config.ts          # ROUTES constants + buildRoute() helper
│
├── types/                        # Shared TypeScript domain models (pure types, no runtime code)
│   ├── index.ts                  # Barrel re-export
│   ├── api.types.ts              # ApiResponse<T>, ApiError, PaginationParams, PaginatedResponse<T>
│   ├── auth.types.ts             # AuthUser, AuthTokens, UserRole, Permission, ROLE_PERMISSIONS
│   ├── case.types.ts             # PACase, CaseListItem, Patient, Provider, ClinicalDocument…
│   ├── review.types.ts           # AuditEvent, ReviewAction, SubmitDecisionPayload…
│   ├── ai.types.ts               # AIWorkflowResult, AIRationale, ReasoningStep, GuardrailResult…
│   └── analytics.types.ts        # PlatformMetrics, TrendPoint, WorkflowLatency, OutcomeDistribution
│
├── schemas/                      # Zod validation schemas (form + API boundary)
│   ├── index.ts
│   ├── auth.schema.ts            # loginSchema → LoginFormData
│   ├── case.schema.ts            # submitCaseSchema, caseFiltersSchema
│   └── review.schema.ts          # decisionSchema, assignSchema, clarificationResponseSchema
│
├── constants/                    # Static lookup tables derived from domain types
│   ├── index.ts
│   ├── case.constants.ts         # STATUS_LABEL/COLOR, PRIORITY_LABEL/COLOR, AI_RECOMMENDATION_COLOR
│   ├── roles.constants.ts        # hasPermission(), ROLE_LABEL, ROLE_COLOR
│   └── ui.constants.ts           # BREAKPOINTS, TRANSITION, TOAST_DURATION, Z_INDEX
│
├── services/                     # API abstraction layer — one file per domain
│   ├── index.ts
│   ├── http.service.ts           # Axios singleton: JWT attach, 401 redirect, error normalisation
│   ├── auth.service.ts           # login, logout, refresh, me
│   ├── cases.service.ts          # list, get, create, uploadDocument, triggerAIProcessing, getAIResult
│   ├── review.service.ts         # approve, deny, escalate, pend, assign, getAuditTrail, getActions
│   └── analytics.service.ts      # getMetrics, getAccuracyTrend, getVolumeTrend, getLatency, getOutcomes
│
├── store/                        # Zustand global state (devtools + persist middleware)
│   ├── index.ts
│   ├── auth.store.ts             # user, tokens, isAuthenticated + can(), hasRole(), hasAnyRole()
│   ├── ui.store.ts               # theme, sidebar, notifications (unreadCount, dismiss), commandOpen
│   └── cases.store.ts            # filters, pagination, activeCase/activeCaseId
│
├── hooks/                        # Cross-feature, reusable React hooks
│   ├── index.ts
│   ├── usePermissions.ts         # can, hasRole, isReviewer, isAdmin, canApprove, canAssign…
│   ├── useDebounce.ts            # Debounce any value by N ms
│   ├── usePagination.ts          # page, pageSize, goToPage, nextPage, prevPage, changeSize
│   ├── useLocalStorage.ts        # Type-safe localStorage get/set/remove
│   └── useErrorHandler.ts        # handleError(ApiError) / handleSuccess() → notification store
│
├── lib/                          # Low-level utilities with no business logic
│   ├── utils.ts                  # cn(), formatDate/DateTime/Relative/Confidence/FileSize, getConfidenceLevel
│   └── queryClient.ts            # Standalone queryClient instance (reused across providers)
│
├── utils/                        # Higher-level utilities composing lib + constants
│   └── index.ts                  # isValidNpi/ICD10/CPT, pick, omit, groupBy, sleep, assertNever
│
├── styles/                       # Global CSS — imported once from main.tsx
│   └── globals.css               # CSS vars (--bg, --surface, --border…), @layer components, dark mode
│
├── components/                   # Shared, feature-agnostic UI building blocks
│   │
│   ├── ui/                       # Headless-style primitives — no business logic
│   │   ├── index.ts
│   │   ├── Button.tsx            # CVA variants: primary|ghost|outline|approve|deny|pend|escalate|danger
│   │   ├── Badge.tsx             # CVA variants: brand|success|warning|danger|violet|sky + dot prop
│   │   ├── Card.tsx              # Card + CardHeader + CardTitle + CardDescription
│   │   ├── Input.tsx             # Input + Textarea with label, hint, error wiring
│   │   ├── Skeleton.tsx          # Skeleton, CardSkeleton, TableRowSkeleton, PageSkeleton
│   │   ├── Spinner.tsx           # Spinner (sm/md/lg) + FullPageSpinner
│   │   └── Alert.tsx             # Alert (info/success/warning/error) with dismiss
│   │
│   ├── layout/                   # App shell and structural boundaries
│   │   ├── index.ts
│   │   ├── AppShell.tsx          # Sidebar + TopBar + <Outlet> with collapse-aware margin
│   │   ├── Sidebar.tsx           # Collapsible nav, animated indicator, HIPAA badge, logout
│   │   ├── TopBar.tsx            # Theme toggle, notification drawer, user avatar
│   │   ├── ErrorBoundary.tsx     # Class component; catches render errors; reset button
│   │   └── SuspenseBoundary.tsx  # <Suspense fallback={<PageSkeleton/>}> wrapper
│   │
│   ├── dashboard/                # Reusable dashboard widgets
│   │   ├── index.ts
│   │   └── MetricCard.tsx        # KPI card: icon, value, label, delta, trend, loading skeleton
│   │
│   ├── review/                   # Shared review-panel primitives (no route awareness)
│   │   └── index.ts
│   │
│   ├── documents/                # Document display primitives
│   │   └── index.ts
│   │
│   ├── ai/                       # AI-specific display components
│   │   ├── index.ts
│   │   └── AIBadge.tsx           # Model ID + tier (SMALL/MEDIUM/LARGE) badge with tier color
│   │
│   ├── metrics/                  # Chart-adjacent metric display
│   │   └── index.ts
│   │
│   ├── charts/                   # Recharts wrappers with project defaults baked in
│   │   └── index.ts              # CHART_COLORS, DEFAULT_TOOLTIP_STYLE, DEFAULT_AXIS_STYLE
│   │
│   ├── policies/                 # Policy criterion display
│   │   ├── index.ts
│   │   └── CriteriaCard.tsx      # MET/NOT_MET/INSUFFICIENT card with evidence and confidence bar
│   │
│   └── audit/                    # Audit timeline primitives
│       ├── index.ts
│       └── TimelineEvent.tsx     # Icon + text + actor + timestamp with connector line
│
├── features/                     # Vertical slices — each owns: types, schemas, hooks, components, pages
│   │
│   ├── auth/                     # Authentication & session
│   │   ├── index.ts              # Public API: LoginPage, LoginForm, useLogin, useLogout
│   │   ├── types/index.ts        # Re-exports from @/types
│   │   ├── schemas/index.ts      # loginSchema
│   │   ├── hooks/
│   │   │   ├── useLogin.ts       # useMutation → authService.login → setAuth → navigate
│   │   │   └── useLogout.ts      # authService.logout → clearAuth → navigate /login
│   │   ├── components/
│   │   │   └── LoginForm.tsx     # Controlled form: email + password + error alert
│   │   └── pages/
│   │       └── LoginPage.tsx     # Split-panel layout, demo accounts, HIPAA notice
│   │
│   ├── cases/                    # Case list & queue management
│   │   ├── index.ts              # Public API: CaseListPage, useCases, useCaseDetail
│   │   ├── types/index.ts
│   │   ├── hooks/
│   │   │   ├── useCases.ts       # useQuery(['cases','list',filters,page]) → casesService.list
│   │   │   └── useCaseDetail.ts  # useQuery(['cases','detail',caseId]) → casesService.get
│   │   ├── components/
│   │   │   └── (CaseQueue, CaseRow, CaseFilters — per review workspace)
│   │   └── pages/
│   │       └── CaseListPage.ts   # ReviewerDashboard + CaseQueue (TanStack Table)
│   │
│   ├── review/                   # Review workspace — 3-panel + decision panel
│   │   ├── index.ts              # Public API: ReviewPage, useReview, useAuditTrail
│   │   ├── types/index.ts
│   │   ├── schemas/index.ts      # decisionSchema
│   │   ├── hooks/
│   │   │   ├── useReview.ts      # approve/deny/escalate/pend/assign mutations + cache invalidation
│   │   │   └── useAuditTrail.ts  # useQuery → reviewService.getAuditTrail
│   │   ├── components/
│   │   │   ├── ReviewWorkspace.tsx   # Animated tab switcher + right-rail actions
│   │   │   ├── DocumentViewer.tsx    # Page nav, zoom, extracted text
│   │   │   ├── ExtractedEntitiesPanel.tsx  # Grouped NER with confidence bars
│   │   │   ├── PolicyCriteriaPanel.tsx     # Criteria checklist, progress bar
│   │   │   ├── RationaleViewer.tsx         # Expandable reasoning chain, caveats
│   │   │   ├── ReviewerActions.tsx         # 4-button decision + Zod-validated rationale
│   │   │   ├── ClarificationResponses.tsx  # Thread UI for AI/reviewer Q&A
│   │   │   └── AuditHistory.tsx            # Timeline events via TimelineEvent
│   │   └── pages/
│   │       └── ReviewPage.ts     # Thin re-export of ReviewWorkspace
│   │
│   ├── ingestion/                # Document upload pipeline
│   │   ├── index.ts              # Public API: UploadZone, useDocumentUpload
│   │   ├── types/index.ts        # UploadFile, UploadStatus
│   │   ├── hooks/
│   │   │   └── useDocumentUpload.ts  # Per-file state + progress + casesService.uploadDocument
│   │   └── components/
│   │       └── UploadZone.tsx    # Drag-and-drop zone + file list + progress bars
│   │
│   ├── reasoning/                # AI rationale display
│   │   ├── index.ts              # Public API: useRationale
│   │   ├── types/index.ts
│   │   └── hooks/
│   │       └── useRationale.ts   # useQuery → casesService.getAIResult
│   │
│   ├── clarifications/           # Clarification request/response thread
│   │   ├── index.ts              # Public API: useClarifications
│   │   ├── types/index.ts
│   │   └── hooks/
│   │       └── useClarifications.ts  # query + respond mutation → /clarifications/:id/respond
│   │
│   ├── analytics/                # AI performance analytics dashboard
│   │   ├── index.ts              # Public API: AnalyticsDashboard, useMetrics, useAccuracyTrend…
│   │   ├── types/index.ts
│   │   ├── hooks/
│   │   │   └── useAnalytics.ts   # useMetrics, useAccuracyTrend, useOutcomes, useLatency
│   │   ├── components/
│   │   │   └── AIAnalyticsDashboard.tsx  # 6 KPIs + 5 Recharts charts
│   │   └── pages/
│   │       └── AnalyticsDashboard.ts  # Re-export
│   │
│   ├── policies/                 # Policy criteria evaluation
│   │   ├── index.ts              # Public API: usePolicyCriteria
│   │   ├── types/index.ts
│   │   └── hooks/
│   │       └── usePolicies.ts    # useQuery → /cases/:id/criteria
│   │
│   ├── audit/                    # Audit trail display
│   │   ├── index.ts              # Public API: useAuditTrail, TimelineEvent
│   │   ├── types/index.ts
│   │   └── hooks/
│   │       └── useAuditTrail.ts  # Delegates to review feature hook
│   │
│   └── monitoring/               # Platform health & system status
│       ├── index.ts              # Public API: SystemStatus, useHealthCheck
│       ├── types/index.ts        # PlatformHealth, ServiceHealth, HealthStatus
│       ├── hooks/
│       │   └── useHealthCheck.ts # useQuery → /health/ready, refetchInterval 30s
│       └── components/
│           └── SystemStatus.tsx  # healthy/degraded/down indicator with icon