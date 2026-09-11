module Client = struct
  type 'a io = 'a
  type t = { mutable state : Api_server.state; policy : Api_server.installed_types; mutable rpc : int; mutable checks : bool list }
  let request c req =
    let key = Scenario.vrs_ref in
    let msg = Message.form_msg ~src:(Message.Controller (0, key)) ~dst:Message.Api_server ~rpc_id:(Message.Rpc_id.of_int c.rpc) ~content:(Message.Api_request req) in
    c.rpc <- c.rpc + 1;
    c.checks <- Oracle_api_server.agrees c.policy msg c.state :: c.checks;
    let state, response = Api_server.transition_by_etcd c.policy msg c.state in
    c.state <- state;
    match response.content with
    | Message.Api_response r -> Res.ok r
    | Message.Api_request _ | Message.External_request _ | Message.External_response _ -> Res.error (Err.Malformed_value { kind = "api_response"; detail = "api-server returned non-response content" })
end
module Runtime = Controller_runtime.Make (Concurrency.Direct) (Client)
module Multi = Multi_controller.Make (Concurrency.Direct) (Client)
let create j =
  let open Res in
  let* installed = Json.get j "policy" Api_oracle.policy_decode in
  let* seed = Json.get j "seed" (Json.to_list Dynamic_object.of_json) in
  ok (Result.fold (Exec_api_server.create ~installed ~seed ())
    ~ok:(fun client -> Json.obj [("ok", Api_oracle.state_json (Exec_api_server.state client))])
    ~error:(fun e -> Json.obj [("error", `String (Err.show e))]))
let outcome = function
  | Controller_runtime.Reconciled -> `String "reconciled"
  | Controller_runtime.Errored -> `String "errored"
  | Controller_runtime.Incomplete n -> Json.obj [("incomplete", Json.int_ n)]
let model = function
  | "vrs" -> Res.ok (Controller.model_of_controller ~kind:Vreplica_set_pack.kind (module Vreplica_set_pack.Controller))
  | "deployment" -> Res.ok (Controller.model_of_controller ~kind:V_deployment_pack.kind (module V_deployment_pack.Controller))
  | "stateful" -> Res.ok (Controller.model_of_controller ~kind:V_stateful_set_pack.kind (module V_stateful_set_pack.Controller))
  | name -> Res.error (Err.Decode_error { typ = "program"; detail = name })
let invoke j =
  let open Res in
  let* policy = Json.get j "policy" Api_oracle.policy_decode in
  let* state = Json.get j "state" Api_oracle.state_decode in
  let* mode = Json.get j "mode" Json.to_str in
  let* names = Json.get j "models" (Json.to_list Json.to_str) in
  let* models = Res.all (List.map model names) in
  let* fuel = Json.get j "fuel" Json.to_int in
  let* rounds = Json.get j "rounds" Json.to_int in
  let* namespace = Json.get j "namespace" Json.to_str in
  let client : Client.t = { state; policy; rpc = 0; checks = [] } in
  let first = Option.value ~default:(Controller.model_of_controller ~kind:Vreplica_set_pack.kind (module Vreplica_set_pack.Controller)) (List.nth_opt models 0) in
  let result = match mode with
    | "fixpoint" -> Res.map (fun (r : Multi.report) -> Json.obj [("rounds", Json.int_ r.rounds); ("converged", Json.bool_ r.converged)])
        (Multi.run_to_fixpoint ~client ~models ~namespace ~rv:(fun () -> client.state.resource_version_counter) ~fuel ~max_rounds:rounds)
    | "controller" -> let* queue = Json.get j "queue" (Json.to_list Io_json.key_decode) in
        Res.map (fun rs -> Json.list (fun (key, o) -> Json.obj [("key", Io_json.key_json key); ("outcome", outcome o)]) (Object_ref_map.bindings rs))
          (Runtime.run_controller ~client ~model:first ~queue ~fuel ~max_rounds:rounds)
    | "reconcile" -> let* cr = Json.get j "cr" Dynamic_object.of_json in
        Res.map outcome (Runtime.reconcile_with ~client ~model:first ~cr ~fuel)
    | name -> error (Err.Decode_error { typ = "runtime mode"; detail = name }) in
  ok (Json.obj [("state", Api_oracle.state_json client.state); ("rpc", Json.int_ client.rpc); ("checks", Json.list Json.bool_ (List.rev client.checks));
    ("result", Result.fold result ~ok:(fun value -> Json.obj [("ok", value)]) ~error:(fun e -> Json.obj [("error", `String (Err.show e))]))])
