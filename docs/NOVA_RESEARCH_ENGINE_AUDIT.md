# NOVA research engine audit

## Revisions

On 24 November 2026 GitHub main was at 1e7fb37. The structured-output work at 82ede5d was on open PR #4. It contains the source observation and repeated-action paths that match the reported failure. Production health returned HTTP 200 without a revision identifier, so the exact revision of the reported run remains unverified. These changes build on PR #4 in a separate checkout. [GitHub main](https://github.com/tahanassiri/pizza-slice/tree/1e7fb37538d99c26dca7485ea70f8804c23e2212) · [PR #4](https://github.com/tahanassiri/pizza-slice/pull/4)

## Where evidence stopped becoming results

| Boundary | Failure mechanism in PR #4 | Change |
| --- | --- | --- |
| Extraction to persistence | Generic trade prose could inherit the requested product. Table extraction could admit unrelated HS codes or confuse a trade partner with the importer. The persisted-claim count increased even when the stable claim already existed. Model-supplied text could enter extraction as source data. | Extract from fetched text and tables, check product and HS scope, map trade direction and ISO countries, and count each normalized statement once per source. |
| Persistence to decision | A source ID could point to several claims. The same first 12 claims were sent repeatedly. The checkpoint kept a subset of claims and observations despite more rows in the database. | Use stable claim IDs for citations. Load source state from the evidence table. Use bounded previews, country coverage, and selective retrieval from the complete ordered claim ledger. |
| Action to strategy | Repetition was counted before execution. Unproductive searches could end research as evidence accumulated. Fetch and extraction failures had incomplete lifecycle transitions. | Measure progress after execution. Return actual failure reasons, suppress exhausted actions, and allow productive alternatives. Track inaccessible sources and failed extractions separately. |
| Decision to market | Only the terminal action supplied candidates. Proposal rejections were silent. Cited statements were assigned to demand regardless of criterion. | Validate proposals on every decision, record rejections, track evidence by criterion, and preserve model ordering. Missing criteria and numerical scores remain unknown. |
| Termination to recovery | A blocked finish discarded proposals and the controller replaced the checkpoint with counts. | Publish supported provisional markets on operational termination and retain the evidence, reason, and checkpoint. |
| Provider to telemetry | Aggregate tokens did not explain which request, retry or fallback spent them. Old text and corrections repeated. Synchronous requests occupied the async server loop. | Record each provider attempt with purpose, method, latency, token usage and reported cost where available. Keep old text out of repeat contexts and run blocking requests off the event loop. |

The selected model makes research decisions. The backend checks provenance, market scope and progress and enforces existing operational limits. Research continues to use the existing database, structured provider outputs, SSE, and run authorization.

## Reconciling the 28 reported claims

The production snapshot confirms 28 reported claims across three extraction events. WITS contributed 12 and two Tendata pages contributed eight each. The WITS page used partner WLD, which describes worldwide imports. It cannot on its own establish access from Iran. The terminal tool trace recorded two HTTP 525 failures and then three HTTP 403 failures on fetch actions. The next model decision was another fetch, and the engine stopped before execution. The report exposes neither the individual statements nor the claim IDs and exact decision contexts. A database export for the run is still needed for that reconciliation. If the 28 rows were all distinct, the old decision context could still show at most 12.

The updated terminal SSE event carries the source ledger, validated claims, country and criterion coverage, questions, candidates, and model request profiles. The ordered decision and outcome events identify claim previews, source and claim additions, candidate updates, and market rejection reasons. The relationships use run ID, iteration, source ID and claim ID.

## Verification and deployment

The full local API suite finished with 147 passing tests and one skipped test. This includes recovery after interruption and replay of durable SSE events.

The local extractor fetched the public World Bank WITS table for HS 091020 imports from Iran in 2023. It examined 39 rows and returned 12 claims under the existing per-page selection rule, with country codes and the published trade value unit. This was a live source check outside the deployed engine. [World Bank WITS](https://wits.worldbank.org/trade/comtrade/en/country/All/year/2023/tradeflow/Imports/partner/IRN/product/091020)

| Measurement | Reported baseline | Updated production acceptance |
| --- | ---: | --- |
| Runtime | 131.976 seconds wall clock, 125 seconds reported as active research | Pending |
| Model tokens | 89,960 | Pending |
| Estimated cost | USD 0.015326 | Pending |
| Claims | 28 reported, distinct count unverified | Pending |
| Ranked markets | 0 | Pending |
| Termination | Repeated action without progress, limit 3 | Pending |

GitHub reported zero active workflows, zero repository Actions secrets and zero deployment environments. The manual deployment workflow exists on open PR #5. Strict SSH verification could not match a trusted key for the production host or current IP. An authenticated deployment route is required before verifying the updated workflow with the selected model. [PR #5](https://github.com/tahanassiri/pizza-slice/pull/5)
