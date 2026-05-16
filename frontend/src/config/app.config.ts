export const APP_CONFIG = {
  name:        'PA Review Platform',
  description: 'AI-Assisted Prior Authorization Review',
  version:     '0.1.0',

  api: {
    baseUrl:        import.meta.env.VITE_API_URL ?? '/api/v1',
    timeout:        30_000,
    retries:        2,
    retryDelay:     500,
  },

  pagination: {
    defaultPageSize: 20,
    pageSizeOptions: [10, 20, 50, 100],
  },

  upload: {
    maxFileSizeMb:    25,
    acceptedMimeTypes: ['application/pdf', 'image/jpeg', 'image/png', 'image/tiff'],
    maxFilesPerCase:  20,
  },

  ai: {
    pollingIntervalMs:  3_000,
    processingTimeoutMs: 120_000,
    confidenceThresholds: {
      high:   0.80,
      medium: 0.65,
    },
  },

  auth: {
    tokenRefreshBufferMs: 60_000,
    sessionTimeoutMs:     8 * 60 * 60 * 1000,
  },

  cache: {
    caseListStaleMs:    30_000,
    caseDetailStaleMs:  10_000,
    metricsStaleMs:     60_000,
    analyticsStaleMs:   5 * 60_000,
  },

  features: {
    enableWebSocket:    import.meta.env.VITE_ENABLE_WS === 'true',
    enableLoadTest:     import.meta.env.VITE_ENABLE_LOAD_TEST === 'true',
    enableDevTools:     import.meta.env.DEV,
  },
} as const

export type AppConfig = typeof APP_CONFIG