let invoke j =
  let open Res in
  let* installed_types = Json.get j "policy" Api_oracle.policy_decode in
  let* state = Json.get j "state" Cluster_oracle.state_decode in
  let* bound = Json.get j "bound" Cluster_oracle.bound_decode in
  let* controller_id = Json.get j "controllerId" Json.to_int in
  let* pending = Json.mem j "pendingState" in
  let* quiet = Json.mem j "quietState" in
  let config : Cluster.t = { installed_types; controller_models = Cluster_oracle.models } in
  let invariants = Invariants.cluster_structural ~controller_id
    @ Correspondence.family config ~controller_id
    @ Reconcile_correspondence.family ~controller_id
        ~pending_states:(Value.equal (Value.of_json pending))
        ~none_states:(Value.equal (Value.of_json quiet))
    @ Msg_provenance.provenance_family ~controller_id
    @ Req_resp_correspondence.rv_family bound
    @ Req_resp_correspondence.matched_family ~controller_id in
  ok (Json.list (fun (i : Invariants.invariant) -> Json.obj [
    ("name", `String i.name); ("source", `String i.source);
    ("holds", Json.bool_ (i.holds state)); ("interesting", Json.bool_ (i.interesting state))]) invariants)

let invoke_stateful j =
  let open Res in
  let* state = Json.get j "state" Cluster_oracle.state_decode in
  let* controller_id = Json.get j "controllerId" Json.to_int in
  let* obj = Json.get j "cr" Dynamic_object.of_json in
  let* cr = V_stateful_set.unmarshal obj in
  let invariants = List.filteri (fun index _ -> index >= 6) (Vsts_invariants.always ~cr ~controller_id)
    @ Internal_guarantee.guarantee_family ~cr ~controller_id
    @ Helper_invariants.helper_family ~cr ~controller_id
    @ Rely_conditions.rely_family
    @ Local_binding.binding_family ~cr ~controller_id
    @ State_predicates.predicate_family ~cr ~controller_id
    @ [Internal_guarantee.local_pods_and_pvcs_are_bound_to_vsts ~controller_id;
       Vsts_invariants.liveness_goal ~cr] in
  ok (Json.list (fun (i : Invariants.invariant) -> Json.obj [
    ("name", `String i.name); ("source", `String i.source);
    ("holds", Json.bool_ (i.holds state)); ("interesting", Json.bool_ (i.interesting state))]) invariants)

let invoke_vrs j =
  let open Res in
  let* state = Json.get j "state" Cluster_oracle.state_decode in
  let* controller_id = Json.get j "controllerId" Json.to_int in
  let* obj = Json.get j "cr" Dynamic_object.of_json in
  let* cr = Vreplica_set.unmarshal obj in
  let invariants = Invariants.all ~cr ~controller_id @ [Invariants.liveness_goal ~cr] in
  ok (Json.list (fun (i : Invariants.invariant) -> Json.obj [
    ("name", `String i.name); ("source", `String i.source);
    ("holds", Json.bool_ (i.holds state)); ("interesting", Json.bool_ (i.interesting state))]) invariants)
