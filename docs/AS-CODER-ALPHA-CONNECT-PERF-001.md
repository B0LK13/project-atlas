# AS-CODER-ALPHA-CONNECT-PERF-001

Current-main reconstruction of historical #376 connect performance harness.

Measures:

- COLD_CONNECT
- WARM_CONNECT (unchanged reconnect)
- one-file delta
- derived lens micro-timings

Honesty:

- PERFORMANCE_RESULT = OBSERVATIONAL
- BASELINE != SLA
- PERF != PRODUCT GATE
- no wall-clock product threshold inside the normal coverage suite
- does not weaken existing product-perf gates
- incremental skip is operational, not authority

Stacked on landed incremental connect (#374). Historical #376 is a
semantic reference only.
