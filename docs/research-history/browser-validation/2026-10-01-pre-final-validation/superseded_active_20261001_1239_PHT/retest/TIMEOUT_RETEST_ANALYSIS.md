# Original timeout observations and controlled retries

The original run contained 10 timeout observations: three responsive cases and seven performance trials. Their source rows, original 30-second navigation limit, viewports, routes, and outcomes are enumerated in `original_timeout_inventory.csv`. Original failures remain intact under `initial_run/`.

Each observation was retried five times in a fresh Chromium browser context at the same route, viewport, 30-second navigation limit, and route-specific checks. Performance retries retained the 5,000 ms usable-page criterion. The first 50-attempt preflight was invalid because the retest harness passed arguments incorrectly to `page.evaluate`; its results are preserved in `logs/timeout_retest_harness_preflight_results.csv` and are excluded from controlled-retry counts. The corrected run produced 50 valid attempts in `timeout_retest_results.csv`: **50 PASS, 0 FAIL**.

Classification: all 10 original observations are **transient / not reproduced** under the controlled-retry rule; zero are intermittent or reproducible in this batch. This does not erase the original timeouts or prove future network stability. The final clean matrices independently measure the live deployment and determine final category status.
