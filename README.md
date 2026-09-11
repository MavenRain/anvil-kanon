# anvil-kanon

Kanon port of [MavenRain/anvil-ocaml](https://github.com/MavenRain/anvil-ocaml),
pinned at `1b6ac2c60f18595858ac8ac193e642f5868757ba` (Phase 36).

The Kanon library includes all three controllers (VReplicaSet, VDeployment and
VStatefulSet), the Kubernetes API and cluster model, bounded safety and temporal
model checking, fault-budget exploration, assurance predicates, independent API
reference transitions, conditional liveness derivations, and deterministic
executable reconcile drivers. It compiles to WebAssembly GC. JavaScript handles
loading, JSON text and command-line I/O; controller and checker logic runs in Kanon.

The assurance results retain the source's limits: bounded exploration is not an
unbounded proof, liveness facts depend on explicit assumptions, and native
Kubernetes list/watch/auth/TLS remains deferred. No Verus proof transfers through
this port. See [PORTING.md](PORTING.md) and [VALIDATION.md](VALIDATION.md).

## Build and run

Prerequisites: a built Kanon compiler and Node with WebAssembly GC support.
Validation used Node 23.10.0 and the compiler recorded in [toolchain.json](toolchain.json).
There are no npm dependencies to install. With `kanon` as a sibling directory:

```sh
npm run build
npm run operator -- vrs 3
npm run operator -- stateful 3
npm run operator -- deployment 3
```

The Deployment example runs Deployment and ReplicaSet together. The StatefulSet
example also creates PVCs. Each reports convergence, object counts and independent
API-oracle agreement. These operate on an in-memory store.

For a different compiler location, set `KANON_ROOT` or `KANON_BIN`.
The checked-in `.kan` sources build directly; Python 3 is needed only for
`npm run generate`.

## JSON and library interfaces

`node bin/anvil.mjs --help` lists the JSON commands. For example:

```sh
node bin/anvil.mjs cluster-check < examples/checker.json
node bin/anvil.mjs fault-check < examples/fault-checker.json
node bin/anvil.mjs proof < examples/proof.json
```

The host exposes both JavaScript-value and lossless JSON-text input:

```js
import { load } from './runtime/host.mjs';
const host = await load();
const parsed = host.parse('{"x":4611686018427387903,"x":1.0}');
if (parsed.ok) console.log(host.text(host.w.valueRender(parsed.value)));
```

Text input preserves duplicate members, their order, signed 63-bit integers,
out-of-range integer literals, and integer versus float tags. Use `BigInt` for
large integers passed through `host.json`. Parsing rejects non-finite numbers and
malformed JSON with an explicit error. The text interface uses UTF-8; the lower
level byte interface also supports arbitrary bytes.

The typed Kanon API is organized by [modules.json](modules.json). Records use
generated constructors, projections and setters; generic sequences and explicit
Result/Option values replace OCaml collections and functor plumbing. The host's
`w` field exposes the Wasm exports. JSON command fixtures in `test/` provide
examples for every driver and report format.

## Validate

The differential tests additionally require the pinned `anvil-ocaml` checkout
and its OCaml dependencies. Place it beside this repository, or set
`ANVIL_OCAML_ROOT`, then run:

```sh
npm run oracle:build
npm test
```

`ANVIL_OPAM_SWITCH` defaults to `anvil-ocaml`. `ANVIL_ORACLE` may point to an
existing adapter executable. The builder creates an isolated clone under
`build/`, verifies its revision and tracked-source cleanliness, and adds the
adapter there. Tests fail if the oracle is unavailable; they do not silently skip.
The original checkout is untouched. Regenerate declarations and adapters with
`npm run generate`.

MIT OR Apache-2.0, preserving the source licenses. The small temporal entailment
kernel follows the MIT-licensed Comp_cat implementation identified in
[NOTICE.md](NOTICE.md).
