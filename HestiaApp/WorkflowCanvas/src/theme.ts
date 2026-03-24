// Dark theme matching Hestia macOS DesignSystem (MacColors)
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
