let outcome_json outcome =
  match outcome with
  | Model_check.Refuted { lasso; steps } -> Json.obj [
      ("tag", `String "refuted"); ("stem", Json.list Cluster_oracle.state_json (Array.to_list lasso.stem));
      ("loop", Json.list Cluster_oracle.state_json (Array.to_list lasso.loop)); ("steps", Json.int_ steps)]
  | Model_check.No_counterexample { decisive; depth; states } -> Json.obj [
      ("tag", `String "noCounterexample"); ("decisive", Json.bool_ decisive); ("depth", Json.int_ depth); ("states", Json.int_ states)]

let invoke j =
  let open Res in
  let* stateful = Json.get j "stateful" Json.to_bool in
  let* query = Json.get j "query" Json.to_str in
  let* desired = Json.get j "desired" Json.to_int in
  let* desireds = Json.get j "desireds" (Json.to_list Json.to_int) in
  let* depth = Json.get j "depth" Json.to_int in
  let* bound = Json.get j "bound" Cluster_oracle.bound_decode in
  let* bound_json = Json.mem j "bound" in
  let* force_false = Json.get j "forceFalse" Json.to_bool in
  let* report = match stateful, query with
    | false, "always" -> ok (Cluster_check.check_always ~depth bound ~desired)
    | false, "esr" -> ok (Cluster_check.check_esr ~depth bound ~desired)
    | false, "settled" -> ok (Cluster_check.check_esr_settled ~depth bound ~desired)
    | false, "temporal" -> ok (Cluster_check.check_esr_temporal ~depth bound ~desired)
    | false, "unique" -> ok (Cluster_check.check_unique_reconcile_id_vrs ~depth bound ~desireds)
    | true, "always" -> ok (Cluster_check.check_always_vsts ~depth bound ~desired)
    | true, "esr" -> ok (Cluster_check.check_esr_vsts ~depth bound ~desired)
    | true, "settled" -> ok (Cluster_check.check_esr_settled_vsts ~depth bound ~desired)
    | true, "temporal" -> ok (Cluster_check.check_esr_temporal_vsts ~depth
        ~current_state_matches:(if force_false then (fun _ _ -> false) else Vsts_invariants.current_state_matches) bound ~desired)
    | true, "unique" -> ok (Cluster_check.check_unique_reconcile_id_vsts ~depth bound ~desireds)
    | (false | true), _ -> error (Err.Decode_error { typ = "cluster query"; detail = query }) in
  ok (Json.obj [
    ("outcome", outcome_json report.outcome); ("bound", bound_json);
    ("maxUidSeen", Json.int_ report.max_uid_seen); ("maxRvSeen", Json.int_ report.max_rv_seen);
    ("pruned", Json.bool_ report.pruned);
    ("violated", Option.fold ~none:`Null ~some:(fun (i : Invariants.invariant) -> Json.obj [("name", `String i.name); ("source", `String i.source)]) report.violated);
    ("gateStates", Option.fold ~none:`Null ~some:Json.int_ report.gate_states)])
