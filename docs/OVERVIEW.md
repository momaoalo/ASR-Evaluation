# Overview — Dashboard 1.6.0

The authoritative current aggregation contract is [DASHBOARD_1_6.md](DASHBOARD_1_6.md).

Legacy validated compact-row logic remains in evaluation/overview.py. Live and exported dashboard summaries use evaluation/dashboard.py: build_dashboard. All historical evaluations remain visible; the two charts use an explicitly paired subset. Do not use the old all-configuration intersection as a paired count.
