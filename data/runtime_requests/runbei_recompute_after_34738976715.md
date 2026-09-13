# Runbei production recompute request

Purpose: trigger the repository's existing explicit production authority closure after the Runbei multidimensional comparison feature was merged.

Context:
- Previous automatic Postscan lineage originated from a push-triggered Opportunity Discovery and was intentionally skipped by production guards.
- This marker requests a fresh workflow_dispatch-based production chain through the existing `[run-production]` mechanism.
- No investment thresholds, authority semantics, UNKNOWN handling, or auto-trade rules are changed.
