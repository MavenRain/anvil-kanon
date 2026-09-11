let invoke j =
  let open Res in
  let* mode = Json.get j "mode" Json.to_str in
  let* desired = Json.get j "desired" Json.to_int in
  let* fair = Json.get j "fair" Json.to_bool in
  let* crash = Json.get j "crash" Json.to_bool in
  let* req_drop = Json.get j "drop" Json.to_bool in
  let* pod_monkey = Json.get j "monkey" Json.to_bool in
  let* vct = Json.get j "vct" Json.to_bool in
  let* existing = Json.get j "existing" Json.to_int in
  let* desireds = Json.get j "desireds" (Json.to_list Json.to_int) in
  let* ordinals = Json.get j "ordinals" (Json.to_list Json.to_int) in
  let* state = match mode with
    | "vrs" -> ok (Scenario.seed ~desired ~fair)
    | "vrsMulti" -> ok (Scenario.seed_multi ~desireds ~fair)
    | "vrsPods" -> if existing < 0 then error (Err.Decode_error { typ = "Scenario.seed_with_pods"; detail = "negative existing count" }) else ok (Scenario.seed_with_pods ~desired ~existing ~fair)
    | "vrsOrphan" -> ok (Scenario.seed_with_orphan ~desired ~fair)
    | "stateful" -> ok (Scenario.vsts_seed ~desired ~fair)
    | "statefulFaults" -> ok (Scenario.vsts_seed_faults ~desired ~crash ~req_drop ~pod_monkey ~vct ())
    | "statefulPods" -> ok (Scenario.vsts_seed_with_pods ~desired ~ordinals ~crash ~req_drop ~pod_monkey ~vct ())
    | "statefulMulti" -> ok (Scenario.vsts_seed_multi ~desireds ~fair)
    | "statefulMultiFaults" -> ok (Scenario.vsts_seed_multi_faults_vct ~desireds ~crash ~req_drop ~pod_monkey ~vct)
    | "deployment" -> ok (Scenario.vd_vrs_seed ~desired ~fair)
    | _ -> error (Err.Decode_error { typ = "scenario"; detail = mode }) in
  ok (Cluster_oracle.state_json state)

let intact j =
  let open Res in
  let* state = Json.get j "state" Cluster_oracle.state_decode in
  let* ordinals = Json.get j "ordinals" (Json.to_list Json.to_int) in
  ok (Json.bool_ (Scenario.vsts_seed_pods_intact state ~ordinals))
