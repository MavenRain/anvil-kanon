let faulted_json (f : Fault_check.faulted) = Json.obj [
  ("state", Cluster_oracle.state_json f.cs); ("crashes", Json.int_ f.crashes); ("drops", Json.int_ f.drops); ("monkeys", Json.int_ f.monkeys)]
let outcome_json = function
  | Model_check.Refuted { lasso; steps } -> Json.obj [
      ("tag", `String "refuted"); ("stem", Json.list faulted_json (Array.to_list lasso.stem));
      ("loop", Json.list faulted_json (Array.to_list lasso.loop)); ("steps", Json.int_ steps)]
  | Model_check.No_counterexample { decisive; depth; states } -> Json.obj [
      ("tag", `String "noCounterexample"); ("decisive", Json.bool_ decisive); ("depth", Json.int_ depth); ("states", Json.int_ states)]
let invoke j =
  let open Res in
  let* query = Json.get j "query" Json.to_str in
  let* depth = Json.get j "depth" Json.to_int in
  let* bound = Json.get j "bound" Cluster_oracle.bound_decode in
  let* bound_json = Json.mem j "bound" in
  let* bj = Json.mem j "budget" in
  let* max_crashes = Json.get bj "maxCrashes" Json.to_int in
  let* max_drops = Json.get bj "maxDrops" Json.to_int in
  let* max_monkey_ops = Json.get bj "maxMonkeyOps" Json.to_int in
  let budget : Fault_check.budget = { max_crashes; max_drops; max_monkey_ops } in
  let* options = Json.mem j "options" in
  let* desired = Json.get options "desired" Json.to_int in
  let* desireds = Json.get options "desireds" (Json.to_list Json.to_int) in
  let* ordinals = Json.get options "ordinals" (Json.to_list Json.to_int) in
  let* req_drop = Json.get options "drop" Json.to_bool in
  let* pod_monkey = Json.get options "monkey" Json.to_bool in
  let* vct = Json.get options "vct" Json.to_bool in
  let* require_fault = Json.get options "requireFault" Json.to_bool in
  let open Fault_check in
  let* r = match query with
    | "always" -> ok (check_invariants_under_faults ~depth bound budget ~desired)
    | "correspondence" -> ok (check_correspondence_under_faults ~depth bound budget ~desired ~require_crash:require_fault)
    | "reconcile" -> ok (check_reconcile_correspondence_under_faults ~depth ~req_drop ~pod_monkey bound budget ~desired ~require_fault)
    | "responseRv" -> ok (check_req_resp_under_faults ~depth ~req_drop ~pod_monkey ~vct bound budget ~desired ~list_select:Rv_list ~require_fault)
    | "responseMatched" -> ok (check_req_resp_under_faults ~depth ~req_drop ~pod_monkey ~vct bound budget ~desired ~list_select:Matched_list ~require_fault)
    | "store" -> ok (check_objects_in_store_under_faults ~depth ~req_drop ~pod_monkey bound budget ~desired ~require_fault)
    | "helper" -> ok (check_helper_invariants_under_faults ~depth ~req_drop ~pod_monkey ~vct bound budget ~desired ~require_fault)
    | "unique" -> ok (check_unique_reconcile_id_under_faults ~depth bound budget ~desireds)
    | "settles" -> ok (check_settles_after_disable ~depth bound budget ~desired)
    | "provenance" -> ok (check_msg_provenance_under_faults ~depth ~req_drop ~pod_monkey bound budget ~desired ~require_fault)
    | "rely" -> ok (check_rely_conditions_under_faults ~depth ~req_drop ~pod_monkey bound budget ~desired ~require_fault)
    | "forge" -> ok (check_rely_forge_under_faults ~depth ~req_drop ~pod_monkey bound budget ~desired)
    | "internal" -> ok (check_internal_guarantee_under_faults ~depth ~req_drop ~pod_monkey bound budget ~desired ~require_fault)
    | "scaleDown" -> ok (check_scale_down_under_faults ~depth ~req_drop ~pod_monkey bound budget ~desired ~ordinals ~require_fault)
    | "localBinding" -> ok (check_local_binding_under_faults ~depth ~req_drop ~pod_monkey bound budget ~desired ~ordinals ~require_fault)
    | "statePredicates" -> ok (check_state_predicates_under_faults ~depth ~req_drop ~pod_monkey bound budget ~desired ~ordinals ~require_fault)
    | _ -> error (Err.Decode_error { typ = "fault query"; detail = query }) in
  ok (Json.obj [
    ("outcome", outcome_json r.outcome); ("bound", bound_json); ("budget", bj);
    ("maxUidSeen", Json.int_ r.max_uid_seen); ("maxRvSeen", Json.int_ r.max_rv_seen);
    ("maxCrashesSeen", Json.int_ r.max_crashes_seen); ("maxDropsSeen", Json.int_ r.max_drops_seen); ("maxMonkeysSeen", Json.int_ r.max_monkeys_seen);
    ("prunedByCeiling", Json.bool_ r.pruned_by_ceiling); ("prunedByBudget", Json.bool_ r.pruned_by_budget);
    ("violated", Option.fold ~none:`Null ~some:(fun (i : Invariants.invariant) -> Json.obj [("name", `String i.name); ("source", `String i.source)]) r.violated);
    ("gateStates", Option.fold ~none:`Null ~some:Json.int_ r.gate_states);
    ("crashWitnessStates", Json.int_ r.crash_witness_states); ("faultFreeStates", Json.int_ r.fault_free_states); ("settledWithFaultsLive", Json.int_ r.settled_with_faults_live)])
let forge j =
  let open Res in
  let* desired = Json.get j "desired" Json.to_int in
  let* respecting = Json.get j "respecting" Json.to_bool in
  ok (Dynamic_object.to_json (Pod.marshal (if respecting then Fault_check.rely_respecting_forge ~desired else Fault_check.rely_violating_forge ~desired)))
