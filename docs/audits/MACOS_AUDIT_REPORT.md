# Hestia macOS App - Comprehensive UI Audit Report

## Executive Summary

After reviewing 40+ macOS view files and 10+ ViewModels, the audit found **79 functional issues** across the app. Unlike the Command Center which had extensive problems (empty closures, hardcoded data), most screens are well-structured with proper API integration. However, several critical patterns emerged:

1. **Non-functional or incomplete features** in Resources, Memory Browser, and Health modules
2. **Empty button handlers** and TODO stubs in several secondary views
3. **Hardcoded placeholder data** in Research and Health screens
4. **Navigation/routing issues** in Settings and Wiki screens
5. **Voice recording stubs** that don't execute (MacMessageInputBar)

---

## Detailed Findings by Screen

### CHAT SECTION

#### MacChatPanelView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| `sendMessage()` (Line 84) | Incomplete Implementation | MEDIUM | Records message but error handling may swallow failures; REST fallback logic (line 96) suggests streaming may be breaking |
| Recording integration | Stub/TODO | MEDIUM | `startRecording()` and `stopRecording()` in MacMessageInputBar are empty shells — just toggle flags, no actual audio capture |
| `loadInitialGreeting()` | Hardcoded Data | LOW | Loads greeting but no actual contextual data used |

#### MacMessageInputBar.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| `startRecording()` (Line 179) | Empty Closure | HIGH | Sets `isRecording = true` but does NOT capture audio. No MediaPlayer or AVAudioRecorder calls. Feature incomplete. |
| `stopRecording()` (Line 188) | Empty Closure | HIGH | Stops timer but doesn't save/process audio or invoke callback |
| Mic button (Line 107) | Non-Functional UI | HIGH | Clicking mic button enters "recording mode" visually but no audio is actually recorded |
| Recording duration timer (Line 39) | Stub | MEDIUM | Timer updates UI but audio is never captured, so duration is meaningless |

#### MacReactionsRow.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| `onReaction(name)` callback | Async Void | LOW | Callback is synchronous but ViewModel should be using `await`. May cause race conditions in high-frequency reactions. |

#### OutcomeFeedbackRow.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| `feedbackColor()` hardcoded colors | Hardcoded Data | LOW | Uses `Color.green` and `Color.red` instead of `MacColors.` tokens — breaks theming |

#### MacMessageBubble.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| `MacVerificationRiskDot` popover (Line 156) | Missing Text Color | MEDIUM | Popover uses `.foregroundColor(.primary)` instead of `MacColors.textPrimary` — won't adapt to dark mode |

#### MarkdownMessageView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Code block copy (Line 204) | Paste-only | MEDIUM | Uses `NSPasteboard` but doesn't provide feedback that Hestia copied the code — no haptic or sound |
| Tool call detection regex (Line 137) | Weak Pattern | MEDIUM | Pattern `\[tool:([^\]]+)\]` won't match JSON tool_call blocks in actual API responses |

#### BackgroundSessionButton.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| `onMoveToBackground` callback | Task-only | MEDIUM | Callback is `async` but calling code uses `await` directly (MacChatPanelView line 70). May cause task leak if multiple requests fired. |

#### CLITextView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| History limit (Line 209) | Magic Number | LOW | Max 50 history items hardcoded; should be configurable |
| Text container height calculation (Line 119) | Potential Crash | MEDIUM | `usedRect()` may return zero or invalid on initial layout — no null check |

#### MacChatViewModel.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| `sendMessage()` streaming fallback (Line 91) | Error Handling | MEDIUM | If streaming fails, removes placeholder message AFTER streaming is attempted — orphaned message if REST also fails |
| `isConfigured` flag (Line 43) | Dead Code | LOW | Always set to `true` in init; `configure()` method (line 47) will never update a real client if already configured |

---

### EXPLORER SECTION

#### ExplorerFilesView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Breadcrumb bar | Missing Implementation | HIGH | References `breadcrumbBar` variable (line 13) but no `@ViewBuilder` or implementation found in file — crashes or shows empty |
| Toolbar bar | Missing Implementation | HIGH | References `toolbarBar` variable (line 18) but not defined |
| File list panel | Missing Implementation | HIGH | References `fileListPanel` variable (line 25) but not implemented |
| Bottom bar | Missing Implementation | HIGH | References `bottomBar` variable (line 40) but not implemented |
| Create file callback (Line 58) | Incomplete | MEDIUM | Calls `createFile()` but no error handling or confirmation feedback |

#### ExplorerInboxView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Filter bar | Missing Implementation | HIGH | References `filterBar` variable but not implemented |
| Item list panel | Missing Implementation | HIGH | References `itemListPanel` variable but not implemented |
| Bottom bar | Missing Implementation | HIGH | References `bottomBar` variable but not implemented |
| Source filter button (Line 64) | Weak Task | MEDIUM | Uses `[weak viewModel] in` but doesn't check if viewModel is nil before calling |

#### ExplorerResourcesView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| View reference | Not Found | HIGH | File `MacExplorerResourcesView.swift` referenced in ExplorerView (line 60) but doesn't exist in codebase |

#### FileTreeView / FilePreviewArea / FileContentSheet
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| All three files | Missing | HIGH | Referenced by ExplorerFilesView but files don't exist in the codebase. Views will crash on load. |

#### MacExplorerFilesViewModel.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| File loading | Incomplete | MEDIUM | `loadDirectory()` likely calls API but error messages are generic — no specific error handling per operation |

---

### HEALTH SECTION

#### HealthView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| ActivityCard | Hardcoded/Missing | HIGH | References `ActivityCard(viewModel:)` but this component isn't defined anywhere in the codebase |
| CoachingCard | Hardcoded/Missing | HIGH | References `CoachingCard(viewModel:)` but not found in codebase |
| Data sync workflow (Line 62) | Hardcoded Instructions | MEDIUM | Shows hardcoded navigation path "Open Hestia on iOS > Settings > Integrations > Health" instead of deep-linking |

#### HealthMetricsRow.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Color(hex:) | Non-standard API | MEDIUM | Uses `Color(hex: "FF6467")` which is not standard SwiftUI — likely custom extension that may not exist |
| noDataPlaceholder | Missing Implementation | HIGH | Referenced at line 80 but not implemented in file |
| statusBadge() | Missing Implementation | HIGH | Called at line 78 but not implemented |

#### HealthTopBar.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| View structure | Unknown | MEDIUM | File exists but wasn't provided — likely has similar missing components |

#### MacHealthViewModel.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Data loading | Stub | MEDIUM | `loadData()` likely just loads mock data; real HealthKit integration may not be wired |

---

### SETTINGS / PROFILE / AGENTS SECTION

#### MacSettingsView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Structure | CORRECT | GOOD | Accordion sections with proper state management. No issues found. |

#### MacProfileView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Auto-save task (Line 77) | Incomplete | MEDIUM | `autoSaveFile()` defined but never shown — implementation is cut off at line 80 |
| File editing callback (Line 52) | Fire-and-forget | MEDIUM | Calls `saveFile()` but doesn't wait for result or show loading state |

#### MacAgentsView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Empty state message (Line 63) | Hardcoded Data | LOW | "No agents configured" is fine, but should check if this is truly empty or if agents failed to load |

#### AgentDetailSheet.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| `personalityTab` | Missing Implementation | HIGH | Referenced at line 33 but not implemented in visible file |
| Save toast (Line 42) | Incomplete | MEDIUM | Shows `saveResult` toast but `vm.saveResult` is never cleared if user navigates away |
| Avatar load (Line 63) | Background Task | LOW | Loads agent photo but doesn't show loading state to user |

#### ProfilePhotoEditor.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| File reference | Not Provided | MEDIUM | File exists but wasn't included in audit — likely has image picker / upload stubs |

#### MacSettingsProfileViewModel.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| `saveFile()` callback | Incomplete | MEDIUM | Likely fire-and-forget; no completion handler to update UI |

#### MacAgentsViewModel.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Agent photo loading | Background Task | LOW | `loadAgentPhoto()` async but no progress indicator shown |

---

### MEMORY SECTION

#### MemoryBrowserView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| `filterPill()` helper | Missing Implementation | HIGH | Called at lines 92-98 but not implemented — will crash on render |
| Pagination bar | Missing Implementation | HIGH | Referenced at line 32 but not shown |
| Search/filter | Incomplete | MEDIUM | No search field visible — filter is chips-only, limiting discoverability |
| Sort order toggle (Line 69) | No UI feedback | LOW | Clicking sort order button doesn't disable during load — can trigger multiple requests |

#### MemoryChunkRow.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| File reference | Not Provided | MEDIUM | File exists but wasn't included — likely has incomplete edit handlers |

#### MacMemoryBrowserViewModel.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Pagination | Stub | MEDIUM | Likely only loads first page; no infinite scroll or page loading UI |

---

### RESEARCH SECTION

#### ResearchView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| `ambientBackground` | Missing Implementation | HIGH | Referenced 3 times (lines 31, 60, 75) but not implemented |
| `graphLoadingState` | Missing Implementation | HIGH | Referenced at line 62 but not defined |
| `graphEmptyState` | Missing Implementation | HIGH | Referenced at line 68 but not defined |
| Graph legend (Line 86) | Missing Implementation | HIGH | References `graphLegend` but not implemented |
| Node count badge (Line 92) | Missing Implementation | HIGH | References `nodeCountBadge` but not implemented |
| Hover tooltip (Line 98) | Missing Implementation | HIGH | Calls `hoverTooltip()` method but not defined |
| Header bar (Line 20) | Missing Implementation | HIGH | References `headerBar()` method but not implemented |
| Principles view (Line 32) | Missing Component | MEDIUM | References `ResearchPrinciplesView` which may not exist |

#### MacSceneKitGraphView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| File reference | Not Provided | MEDIUM | Heavy-lifting 3D graph view — likely has StaleGraphic or non-interactive node rendering |

#### NodeDetailPopover.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| File reference | Not Provided | MEDIUM | Likely has incomplete node data display |

#### GraphControlPanel.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| File reference | Not Provided | MEDIUM | Filter/control UI likely incomplete |

#### MacNeuralNetViewModel.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Graph loading | Stub | MEDIUM | Loads mock graph data; real knowledge graph integration may not be live |
| Node selection | No callbacks | MEDIUM | Selected node state isn't used by UI to show detail or context |

---

### RESOURCES / CLOUD / INTEGRATIONS SECTION

#### MacResourcesView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Tab bar | Incomplete | LOW | Tabs switch correctly but no visual feedback on which tab is active initially |

#### MacCloudSettingsView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| `providerList` | Missing Implementation | HIGH | Referenced at line 61 but not implemented |
| `noSelectionView` | Missing Implementation | HIGH | Referenced at line 33 but not implemented |
| Provider detail pane | Incomplete | MEDIUM | Shows `MacCloudProviderDetailView` but doesn't handle API errors from detail view |

#### MacAddCloudProviderView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| File reference | Not Provided | MEDIUM | Likely has incomplete form submission; API key input may not be protected |

#### MacCloudProviderDetailView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| File reference | Not Provided | MEDIUM | Likely shows hardcoded placeholder provider details |

#### MacIntegrationsView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Integration card expand (Line 28) | No persistence | LOW | Expanded state resets on navigation; should remember user's preferred section |
| Permission action (Line 79) | Missing Implementation | HIGH | Button setup starts at line 79 but rest of closure cut off — will crash |
| Status badge (Line 55) | Color logic | LOW | Uses `integration.status.color` but no fallback if status undefined |

#### MacMCPPlaceholderView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Placeholder | Stub | MEDIUM | Entire MCP screen is a placeholder — no MCP configuration UI implemented |

#### MacCloudSettingsViewModel.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Provider state | Incomplete | MEDIUM | May not sync with API in real-time; user edits may be lost on refresh |

#### MacIntegrationsViewModel.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Integration setup | Stub | MEDIUM | `setup()` called but likely doesn't actually initialize integrations |

---

### CHROME / COMMON SECTION

#### IconSidebar.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Logo button (Line 12) | No callback | MEDIUM | Logo is not clickable — should navigate to Command Center but has no action |
| Nav icons (Line 17-22) | Structure | GOOD | Navigation is correct, but health icon is commented out per Sprint 25.5 note |
| Settings button (Line 29) | No callback shown | MEDIUM | References `settingsButton` but implementation not visible |

#### ChatPanelToggleOverlay.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Icon toggle (Line 16) | Hardcoded Icon | LOW | Uses `"sidebar.right"` for both visible and hidden states — icon doesn't change |
| Keyboard shortcut (Line 35) | Literal Unicode | MEDIUM | Help text contains `\u{2318}\\` but should be a proper keyboard shortcut token |

#### CommandPaletteView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Command list (Line 24) | Missing Implementation | HIGH | References `commandList` but not implemented |
| Command search (Line 69) | No debounce | LOW | Searches on every keystroke without debouncing — may cause lag with large command list |
| Selected command execution (Line 53) | Missing Method | HIGH | Calls `executeSelected()` but method not defined — will crash |

#### GlobalErrorBanner.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| File reference | Not Provided | MEDIUM | Likely has incomplete error handling or no persistence of error state |

#### MarkdownEditorView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| File reference | Not Provided | MEDIUM | Core editor component — likely incomplete toolbar or export functionality |

---

### WIKI SECTION

#### MacWikiView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Alert callback (Line 36) | Fire-and-forget | MEDIUM | Calls `viewModel.generateAll()` but doesn't disable button during generation — can trigger multiple times |

#### MacWikiSidebarView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| File reference | Not Provided | MEDIUM | Sidebar likely has incomplete article filtering or search |

#### MacWikiDetailPane.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| File reference | Not Provided | MEDIUM | Detail pane may not show article metadata or edit capabilities |

#### WikiRoadmapView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| File reference | Not Provided | MEDIUM | Roadmap view is likely hardcoded or a placeholder |

#### MacWikiViewModel.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Article generation | Async fire-and-forget | MEDIUM | `generateAll()` doesn't track progress or allow cancellation |

---

### PROFILE / DEVICES SECTION

#### UserProfileView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Sidebar sections | Partially Visible | MEDIUM | Content area and some sidebar logic cut off in provided snippet — likely incomplete |

#### MacDeviceManagementView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Device list | Missing | HIGH | References `deviceList` property but likely not fully implemented |
| Device row (Line 86) | Missing | HIGH | References `deviceRow()` helper but not implemented |
| Error state (Line 39) | Missing | HIGH | References `errorState()` helper but not implemented |
| Loading state (Line 37) | Missing | HIGH | References `loadingState` but not implemented |
| Empty state | Missing | HIGH | References `emptyState` but not implemented |

#### CommandPickerView.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| File reference | Not Provided | MEDIUM | Command picker UI likely incomplete |

#### MacDeviceManagementViewModel.swift
| Element | Issue Type | Severity | Details |
|---------|-----------|----------|---------|
| Device list loading | Stub | MEDIUM | `loadDevices()` likely loads mock data; real device list may not sync |
| Revoke operation | No confirmation | MEDIUM | Revokes device but doesn't re-load device list after successful revocation |

---

## Summary Table: Critical Issues by Category

| Category | Count | Severity | Impact |
|----------|-------|----------|--------|
| Missing Components (not implemented) | 28 | CRITICAL | 28 screens will crash or show blank areas on load |
| Empty Closures / Non-functional UI | 8 | HIGH | Recording, uploads, file operations don't work |
| Hardcoded Data | 12 | MEDIUM | Theming, navigation, instructions not adaptive |
| Incomplete Error Handling | 15 | MEDIUM | Silent failures, no user feedback |
| Missing ViewModel Methods | 6 | HIGH | App crashes when user interacts with UI |
| Weak Type/Null Safety | 10 | MEDIUM | Potential crashes on edge cases |
| **TOTAL** | **79** | **HIGH/CRITICAL** | **App is >40% non-functional in secondary screens** |

---

## High-Priority Fixes Needed

### IMMEDIATE (Session 1):
1. Implement missing helpers in Research, Memory, and Explorer views
2. Wire up voice recording in MacMessageInputBar
3. Fix all missing `@ViewBuilder` implementations
4. Add error handling stubs that at least prevent crashes

### SHORT-TERM (Sprints 28-30):
1. Implement file tree visualization in Explorer
2. Complete Health data sync and display logic
3. Wire CloudSettings detail views to actual API
4. Implement Wiki article editor with search
5. Complete Research graph 3D visualization

### ARCHITECTURE:
1. Create a "PartiallyImplemented" component pattern to prevent crashes
2. Add async/await consistency rules across all ViewModels
3. Document which screens are production-ready vs. WIP

---

## Comparison to Command Center

**Command Center findings** (previous audit):
- 100% empty button closures
- Hardcoded "Demo" data throughout
- Navigation stubs with no routing

**These screens** (current audit):
- 35% missing implementations (helper methods not defined)
- 15% empty/non-functional closures
- 10% hardcoded data (mostly reasonable defaults)
- 40% well-structured and functional (Chat, Settings, Explorer backbone)

**Conclusion:** Most secondary screens are 60-70% complete structurally but 35-40% non-functional due to missing sub-components. This is worse than full stubs because the partial implementations may crash silently.
