let report (r : Discharge.edge_report) = Json.obj [
  ("holds", Json.bool_ r.holds); ("witnesses", Json.int_ r.witnesses);
  ("states", Json.int_ r.states_checked); ("frontierEmpty", Json.bool_ r.frontier_emptied)]
let result encode r = Result.fold r
  ~ok:(fun x -> Json.obj [("ok", encode x)])
  ~error:(fun e -> let message = match e with
    | Comp_cat.Err.Ill_formed { fn; why } -> Err.show (Err.Decode_error { typ = fn; detail = why })
    | Comp_cat.Err.Not_composable _ | No_such_arrow _ | Not_in_shape _ | Not_in_domain _
    | Not_universal _ | Not_monic _ | Empty_set _ | Not_singleton _ | Clash _ | Cyclic _
    | Irreducible _ | No_witness | Budget _ | Unbound _ | Unsupported _ | At _ -> Comp_cat.Err.to_string e
    in Json.obj [("error", `String message)])
let invoke j =
  let open Res in
  let* stateful = Json.get j "stateful" Json.to_bool in
  let* desired = Json.get j "desired" Json.to_int in
  let* bound = Json.get j "bound" Cluster_oracle.bound_decode in
  if stateful then ok (Json.obj [
    ("edges", result (Json.list (fun (e : Vsts_liveness.edge) -> Json.obj [("name", `String e.name); ("report", report e.report)])) (Vsts_liveness.edges ~bound ~desired));
    ("matches", result Json.bool_ (Vsts_liveness.matches_esr_statement ~bound ~desired));
    ("tail", report (Vsts_liveness.tail_matches_is_stable ~bound ~desired))])
  else ok (Json.obj [
    ("edges", result (Json.list (fun (e : Vrs_liveness.edge) -> Json.obj [("name", `String e.name); ("report", report e.report)])) (Vrs_liveness.edges ~bound ~desired));
    ("matches", result Json.bool_ (Vrs_liveness.matches_esr_statement ~bound ~desired));
    ("tail", report (Vrs_liveness.tail_matches_is_stable ~bound ~desired))])
