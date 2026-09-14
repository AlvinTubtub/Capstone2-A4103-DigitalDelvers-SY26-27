# ForecastPH Historical Source Correction Application

## Reason

Two confirmed PSE trading sessions were absent from the historical source dataset:

- December 29, 2022
- May 29, 2024

They were restored from official Philippine Stock Exchange Daily Quotation Reports before the formal experiment. The application used the previously verified transcription in `pse_dqr_missing_sessions_verified.csv`; it did not derive, interpolate, or alter any source value.

## Authoritative sources

### 2022-12-29

- URL: https://www.pse.com.ph/wp-content/uploads/sites/15/2022/12/December-29-2022.pdf
- PDF SHA-256: `1401a65c53c0bfcc21c82e224296c6fe1e799d4b05d5a6443894b4eee0bc7068`

### 2024-05-29

- URL: https://documents.pse.com.ph/wp-content/uploads/sites/15/2024/05/May-29-2024-EOD.pdf
- PDF SHA-256: `eca5563a524ace0a2d3ee775f726e3db0c93d36c10654390315b88a226226158`

## Correction scope

- Companies affected: 15
- Sessions restored: 2
- Rows added: 30
- Existing observations changed: 0
- Existing observations deleted: 0

## Dataset size

- Before: 1,633 rows per company; 24,495 rows total
- After: 1,635 rows per company; 24,525 rows total

## Per-company hashes

| Symbol | Pre-correction SHA-256 | Post-correction SHA-256 | Pre rows | Post rows |
|---|---|---|---:|---:|
| ALI | `0a3154f0cfbdb018296cd3057c9287fa3812497ba6c1e415336b8f128be08f76` | `7fa104278a44a0a7311f9d4f0cac12b07c33f34e2690fe7045538f4bbbea80de` | 1,633 | 1,635 |
| APX | `5605ed200ee0a685a710a099444f64cf2ce877b80e98b180fac231d40f8e8642` | `da3fe65acccaacc866213e058ae3c5856112423a98c9c918525e664c55fcbab2` | 1,633 | 1,635 |
| BPI | `f91ee5528cc875d24b0828182271236ba33f6b92af8d793987597b51a641b48c` | `0d265fdbc6a9e87fa7d5ba5a19683f44a9987ca8c8aec584819ed12123b57502` | 1,633 | 1,635 |
| GLO | `790eb2298019e32335b50dbfc254b800e6d51d9f58cd7ac7b40db50589a2cccf` | `37671b462b429edd9c2bef1ef170ab18b36e745727978e3572244ead13a1d235` | 1,633 | 1,635 |
| ICT | `47cb1c1e500f95f56d7dd26ed7d7c8c9df42ce1af9c3d4c6e6d31462ad26924d` | `0b8b9e9875939a069043eccbf694082d7291367387ce393193fc3e89a0f1c2b0` | 1,633 | 1,635 |
| JFC | `9770c6dfc83f8db575e8633ad42755b2d72d1c5b21251b2cb7718c1be7b74f89` | `d1fc3c5b736439c89340029b95ea6dff1d2d538adc0bb71760517175de0d313f` | 1,633 | 1,635 |
| MBT | `562dc33fa8e89288759f8cbd6c3410e53e14576bc5152e4f00b5b7ba20769d8b` | `de722b70a4f6994bea06f7fe7d8cf031f8ca9e9d2b065f2eee9b802de4073c2f` | 1,633 | 1,635 |
| MEG | `2a5309b73644753eb2541579d51913e125b4ed7a035f7c5165ee6c155eeb2a4a` | `c1be9632131c4f6deed4437ade656d528710ce34e8fae75a574934f117e15c21` | 1,633 | 1,635 |
| MER | `c2ce50073fbb9fd95ea12aa3807d6b958cba2454238f144d4b4197c0279fbdab` | `3df85b90461b60d3c35c419f8deef582a9865c1a08a9e5e40c954f228fbc7aed` | 1,633 | 1,635 |
| NIKL | `f651a6a5af116e1ae1bae81a4ca8f82be46462f947bd77afdfb2d5dafd73e132` | `3325d576ff0c1f1360c4a8ef679a02a4c54ba7738d7bf114ab053a633d0b79c7` | 1,633 | 1,635 |
| PGOLD | `1571f0fe034e62ea27f93cf3a5257d85de0df363ccfb9b42a8a67b1d4c321a0a` | `7e4ac38a7a8e565c1838597febda6a71e91b5b99dfe6f16167bc7e9a1e0f8d47` | 1,633 | 1,635 |
| SCC | `5ff9a025e9ad02bf7beeb1cc325c90a091c13f160b21cebd978b0f6e02cf7abf` | `bb145a27f68569c78086fc1344a5f94f58d676bc449796e6a744da2fc424bea1` | 1,633 | 1,635 |
| SECB | `7b3b0417a4f35d1824633371ce6846c6821c416e1024ac987ea1462533b07432` | `1b0a852fc92eea7f6e38fe163c3a05f63008a726e079970f7a46cdc2052fcf4e` | 1,633 | 1,635 |
| SHLPH | `61487c7712646be0ef4d366aea68928cc14ec519b941d2cc0f22f02112b3db20` | `dc2f4ba4a29ff0508172d490cf8dac6643c23236d3f5235ea0abbac299be3db4` | 1,633 | 1,635 |
| SMPH | `231e582c09505b1351eaba583d037597db0180d9670e667b6c4ad02c9fcd8e39` | `12f29985b18749ca9dd4275ec80b75b717e7ee5065fa7da0dfb1804353697eb5` | 1,633 | 1,635 |

## Validation

- New raw rows matched the verified correction source: 30/30
- Canonical raw validation: 15 companies, 1,635 rows each, 24,525 total rows, zero failures
- Chronological ordering: pass for all 15 companies
- Duplicate dates: 0
- OHLC consistency failures among inserted rows: 0
- Existing observations changed: 0
- Existing observations deleted: 0
- Session-completeness result: 103 unresolved weekday-derived dates before correction; 101 after correction
- `2022-12-29` no longer appears as missing: confirmed
- `2024-05-29` no longer appears as missing: confirmed

The remaining 101 dates await historical PSE/SCCP closure-calendar reconciliation. This record does not characterize those dates as missing market data.

## Provenance scope

This correction record preserves the official PSE source URLs and PDF hashes for the two restored sessions. It does not infer the source name, source reference, retrieval date, or other provenance of the original historical dataset. The formal provenance registry remains unchanged until independently supported information is available.
