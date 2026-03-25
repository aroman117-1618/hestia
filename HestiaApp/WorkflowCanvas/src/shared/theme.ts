// Shared dark theme matching Hestia macOS DesignSystem (MacColors)

// Workflow canvas theme — container, minimap, node status/type colors
export const darkTheme = {
  container: {
    backgroundColor: '#110B03',
    color: '#E4DFD7',
  },
  minimap: {
    backgroundColor: '#0D0802',
    maskColor: 'rgba(235, 223, 209, 0.08)',
    nodeColor: 'rgba(224, 160, 80, 0.6)',
  },
  dotColor: 'rgba(254, 154, 0, 0.08)',
  // Node colors by execution status
  nodeStatus: {
    pending: '#3a3530',
    running: '#E0A050',
    success: '#00D492',
    failed: '#FF6467',
    skipped: 'rgba(235, 223, 209, 0.15)',
  },
  // Node type colors
  nodeType: {
    run_prompt: '#E0A050',    // amber
    call_tool: '#4A9EFF',     // blue
    notify: '#00D492',        // green
    log: 'rgba(235, 223, 209, 0.4)', // muted
    if_else: '#FFB900',       // bright amber
    switch: '#FFB900',        // bright amber
    schedule: '#9B8AFF',      // purple
    manual: '#9B8AFF',        // purple
  },
} as const

// Entity type colors for research canvas (matching MacColors from the Swift design system)
export const nodeColors = {
  entity:     { bg: 'rgba(74,158,255,0.06)',   border: 'rgba(74,158,255,0.15)',   dot: '#4A9EFF' },
  fact:       { bg: 'rgba(0,212,146,0.06)',    border: 'rgba(0,212,146,0.15)',    dot: '#00D492' },
  principle:  { bg: 'rgba(128,80,200,0.06)',   border: 'rgba(128,80,200,0.15)',   dot: '#8050C8' },
  memory:     { bg: 'rgba(228,223,215,0.04)',  border: 'rgba(228,223,215,0.1)',   dot: '#888' },
  annotation: { bg: 'rgba(224,160,80,0.04)',   border: 'rgba(224,160,80,0.1)',    dot: '#E0A050' },
  group:      { bg: 'rgba(224,160,80,0.02)',   border: 'rgba(224,160,80,0.08)',   dot: 'transparent' },
} as const

// Text colors — all UI chrome text must use these, never inline hex strings
export const textColors = {
  primary:     '#E4DFD7',
  secondary:   'rgba(228,223,215,0.5)',
  faint:       'rgba(228,223,215,0.3)',
  placeholder: 'rgba(228,223,215,0.4)',
  accent:      '#E0A050',
} as const
