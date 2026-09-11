# Port map and semantic boundaries

The port targets the shipped Phase 36 implementation at
`1b6ac2c60f18595858ac8ac193e642f5868757ba`. It includes every library area,
all three controllers, the model checker and the assurance layers requested.
The source project's remaining roadmap items remain open.

| Source area | Kanon implementation |
| --- | --- |
| Kubernetes types, codecs, resource views | `model.kan`, `codecs.kan`, `resources.kan`, `objects.kan`, `defaults.kan`, `validators.kan` |
| VReplicaSet | `vrs.kan`, `packs.kan`, `programs.kan` |
| VDeployment | `deployment.kan`, `packs.kan`, `programs.kan` |
| VStatefulSet | `stateful.kan`, `stateful_core.kan`, `packs.kan`, `programs.kan` |
| API, controller, network and cluster transitions | `api_server.kan`, `controller_driver.kan`, `network.kan`, `cluster.kan`, `successors.kan` |
| Structural, store, RPC and request correspondence | `assurance_base.kan`, `assurance_response.kan`, `assurance_families.kan` |
| VRS invariants and liveness predicates | `assurance_vrs.kan` |
| VSTS guarantees, helper invariants and rely conditions | `assurance_stateful.kan`, `assurance_families.kan` |
| Local binding and state predicates | `assurance_local.kan`, `assurance_families.kan` |
| Independent API reference | `oracle_api.kan`, `oracle_dispatch.kan` |
| Graph search and finite-lasso temporal evaluation | `model_check.kan`, `temporal.kan` |
| Cluster and fault checker reports | `cluster_check.kan`, `checker_scenarios.kan`, `fault_check.kan`, `fault_scenarios.kan` |
| Scenarios and ESR formulas | `scenario.kan`, `esr.kan` |
| Discharge, step views and conditional liveness proofs | `discharge.kan`, `proof_kernel.kan`, `liveness.kan` |
| Executable API, reconcile manager and multi-controller driver | `runtime.kan`, `exec_seed.kan` |
| Action/state-machine abstractions, direct concurrency, native stub | `state_machine.kan` |
| Operator and JSON text boundary | `bin/anvil.mjs`, `runtime/host.mjs` |

`port-inventory.json` records all 255 original implementation, interface and test
hashes, together with their replacement areas. It is a traceability map, not a
claim that every original test file was translated line for line. New tests call
the pinned OCaml implementation and compare outputs directly.

## Representation changes

- OCaml functors and module signatures become typed functions, products and
  concrete instances. Record fields and convenience setters use the generated
  Kanon API, rather than preserving OCaml spelling or calling conventions.
- Signed integers retain OCaml's 63-bit modular range. Large integers cross the
  Wasm boundary as decimal bytes because the current direct Nat ABI accepts only
  `0..1073741823`.
- Generic collections use `Sequence A`, an indexed finite sequence. Concrete
  inductive collections represent resource stores and message multisets. Graph
  lookup uses structural equality rather than source hash tables, preserving
  search behavior while potentially using more time and memory.
- OCaml unit data uses the nominal singleton `Ghost`. Native erased empty
  products caused runtime casts to fail in generic results in this compiler.
- Mutable executable clients become explicit state transitions. `ClientResult`
  preserves the client state even when a transport error terminates a pass.
- The source library's seven resource-view instances are concrete Kanon
  functions. A new resource can supply the same validators and erased
  `ControllerProgram` interface without an OCaml first-class module.
- Comp_cat proof facts use concrete cluster temporal syntax with named state and
  action leaves. Formula equality is structural and ignores leaf closures, as in
  the source. Finite discharge errors preserve function/reason text in the
  shared `Error.decodeError` variant instead of Comp_cat's separate `Ill_formed`.
- The UTF-8 host parser accepts JSON, preserves duplicate keys and numeric tags,
  and supplies its own syntax diagnostics. Yojson-specific permissive syntax is
  not an interface promise. Non-finite values and unpaired Unicode surrogates
  return errors. This replaces source rendering paths that could raise.
- A negative existing-pod seed count returns an explicit error; the source's
  `List.init` path raises an exception for that input.

## Assurance limits retained

An exhausted bounded graph supports the corresponding bounded verdict. A depth
cutoff, counter ceiling, budget cutoff or genuine cycle retains the source's
non-decisive reporting where applicable. Fault histories are part of the search
state; RPC multiplicity, counter maxima and non-vacuity gates are preserved.

The independent API reference shares types, collection primitives and installed
policy functions with the primary model. Its handler transitions are separate.
Agreement tests can catch differences between those implementations, but cannot
detect a defect common to an installed policy function.

Liveness derivations retain assumed fairness, enabling and specification facts.
Operational obligations reject violations, zero witnesses and truncated graphs.
These derivations are conditional certificates over finite exploration, not a
new unbounded correctness theorem. The full Comp_cat topos library is not a
dependency of the shipped Wasm artifact; its finite-lasso semantics and the
entailment rules used by Anvil are implemented here.

The native Kubernetes client remains an explicit deferred error, matching the
source stub. Direct concurrency is deterministic and does not model a real
scheduler. Cluster exploration provides the interleaving model.
