# Validation record

Date: 2026-09-10. The differential oracle uses an isolated, unmodified tracked
checkout of `MavenRain/anvil-ocaml` at
`1b6ac2c60f18595858ac8ac193e642f5868757ba`. All 255 inventory hashes were checked
against that source. OCaml 5.3.0, Node 23.10.0 and the compiler fingerprint in
`toolchain.json` were used.

The full 28-test port suite passed. Subsequent changes to runtime result ordering,
the StatefulSet operator seed and the generic action interface were checked with
the focused runtime, CLI and action suites. There are 30 distinct tests in the
final suite. Generated source and adapters reproduced without differences.

| Coverage | Differential evidence |
| --- | --- |
| Foundation | Arbitrary bytes, signed 63-bit arithmetic boundaries, all kinds, map replacement/order and JSON value identity |
| Objects | 20 metadata/owner/selector fixtures comparing eight predicates, plus metadata updates |
| Codecs | 110 field fixtures and 57 complete controller-state fixtures, including exact decoder errors |
| Defaults | 56 typed source defaults, including present-false fields and empty placeholders |
| JSON text | 121 exact rendered values, including large integers, float tags, duplicate keys, Unicode and control escapes; malformed input checks |
| Controllers | 3,776 transition/error fixtures across every step, plus 120 ownership, scaling and storage fixtures |
| API server | 285 fixtures for all nine handlers, compared separately with the primary OCaml implementation and independent reference |
| Cluster | 65 complete labelled successor fixtures and end-to-end reconciliation of all three controllers |
| Generic model checker | 1,388 graph cases covering safety, reaching goals, temporal formulas, fairness, lassos and decisiveness |
| Assurance predicates | Shared 23-predicate, stateful 18-predicate and VRS 16-predicate fixture families; every predicate is falsified and non-vacuously exercised |
| Scenarios | 174 seed comparisons, invalid-count handling and ordinal-integrity checks |
| Cluster reports | 99 complete reports, including counter maxima, pruning, gates and a deliberately false temporal goal |
| Fault reports | 115 complete reports across all 16 drivers, including budget pruning, ceiling pruning and forged-resource refutation |
| Conditional proofs | 24 complete VRS/VSTS derivation/report comparisons and 26 entailment-kernel cases |
| Executable runtime | 197 complete trajectories, including multi-resource ordering, PVC creation, requeue, fuel exhaustion and Deployment/ReplicaSet joint convergence |
| Executable seeding | 12 successful/rejected source results with UID/RV stamping |
| Generic actions | 24 enabled/disabled/forward/state-machine cases |
| CLI | All three operator demos and three JSON example commands from outside the repository working directory; malformed input exit status |

The final Wasm artifact SHA-256 is recorded in `validation-results.json`.
The full and focused test evidence is recorded there separately, so an earlier
full-suite run is not presented as a rerun after unrelated packaging additions.

## Issues resolved during validation

- Native Nat arguments could not carry the source's larger integers. Decimal
  byte parsing now preserves the complete signed 63-bit interval.
- Empty-product data trapped inside generic results. Nominal singleton data
  preserves the source's unit semantics without those casts.
- Missing or null PodSpec containers must decode as an empty list.
- VDeployment scaling must honor the readiness-or-zero guard, and failed
  preparation must preserve the source local fields.
- Cluster report pruning and fault report pruning inspect different frontier
  sets. Both source behaviors are retained.
- Runtime per-resource results must use object-reference ordering even when
  work is queued in reverse order.
- JSON text must retain duplicate members, numeric tags and Yojson's float
  rendering; JavaScript object/number parsing alone loses that information.
- Node 23's Maglev background optimizer deadlocked during test-process
  shutdown. A sampled stack showed the main thread draining tasks while the
  compiler thread waited for a main-thread GC. The host disables Maglev on
  Node 23 before warming its adapters. The foundation suite and full port
  suite subsequently completed.

## Limits of this evidence

These comparisons are regression evidence, not a universal equivalence proof.
The large original Phase 26/36 graph pins were not re-established in Kanon. The
ported checker uses linear structural lookup, which can be substantially slower
on those larger graphs. Bounds and source verdict rules were not relaxed to
obtain the reported passes.

An optional run of the entire original OCaml test suite was stopped while
`t_p26_pins.exe` was still computing, to release the build lock for the final
adapter build. That interrupted run is not reported as passed. The original
source and its tests were not edited.

The independent API oracle shares installed policy functions with the primary
model. Liveness derivations retain their explicit assumptions. Native
Kubernetes transport remains deferred. See `PORTING.md` for the full boundaries.
