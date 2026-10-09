# Overview: current and historical dashboard notes

The current local application loads its saved-run overview through
`app.py` → `evaluation.dashboard.build_dashboard()` (imported under the
alias `build_overview`). Shared-case data is assembled using
`evaluation/overview.py`. Open [current architecture](ARCHITECTURE.md)
for route definitions.

- [Dashboard 1.6.2](DASHBOARD_1_6_2.md): historical scorecard rules and UI choices
- [Overview case list](OVERVIEW_CASE_LIST.md): historical grouping contracts
- [Verification](portfolio/VERIFICATION.md): current CI scope vs previous archived tests

Historical versioned documentation is retained as implementation history, not
a promise that old ZIP installation instructions still apply to a Git checkout.
