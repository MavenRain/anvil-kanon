let host_decode j =
  let open Res in
  let* tag = Json.get j "tag" Json.to_str in
  match tag with
  | "api" -> ok Message.Api_server
  | "builtin" -> ok Message.Builtin_controller
  | "monkey" -> ok Message.Pod_monkey
  | "controller" -> let* id = Json.get j "id" Json.to_int in let* key = Json.get j "key" Io_json.key_decode in ok (Message.Controller (id, key))
  | "external" -> let* id = Json.get j "id" Json.to_int in ok (Message.External id)
  | _ -> error (Err.Decode_error { typ = "host"; detail = tag })

let host_json h =
  let obj tag fields = Json.obj (("tag", Json.str tag) :: fields) in
  match h with
  | Message.Api_server -> obj "api" []
  | Message.Builtin_controller -> obj "builtin" []
  | Message.Pod_monkey -> obj "monkey" []
  | Message.Controller (id, key) -> obj "controller" [("id", Json.int_ id); ("key", Io_json.key_json key)]
  | Message.External id -> obj "external" [("id", Json.int_ id)]

let content_decode j =
  let open Res in
  let* tag = Json.get j "tag" Json.to_str in
  let* body = Json.mem j "body" in
  match tag with
  | "request" -> Res.map (fun r -> Message.Api_request r) (Io_json.request_decode body)
  | "response" -> Res.map (fun r -> Message.Api_response r) (Io_json.response_decode body)
  | "externalRequest" -> ok (Message.External_request (Value.of_json body))
  | "externalResponse" -> ok (Message.External_response (Value.of_json body))
  | _ -> error (Err.Decode_error { typ = "content"; detail = tag })

let content_json c =
  let tag, body = match c with
    | Message.Api_request r -> "request", Io_json.request_json r
    | Message.Api_response r -> "response", Io_json.response_json r
    | Message.External_request v -> "externalRequest", Value.json v
    | Message.External_response v -> "externalResponse", Value.json v in
  Json.obj [("tag", Json.str tag); ("body", body)]

let message_decode j =
  let open Res in
  let* src = Json.get j "src" host_decode in
  let* dst = Json.get j "dst" host_decode in
  let* rpc = Json.get j "rpcId" Json.to_int in
  let* content = Json.get j "content" content_decode in
  ok (Message.form_msg ~src ~dst ~rpc_id:(Message.Rpc_id.of_int rpc) ~content)

let message_json (m : Message.t) = Json.obj [
  ("src", host_json m.src); ("dst", host_json m.dst); ("rpcId", Json.int_ (Message.Rpc_id.to_int m.rpc_id)); ("content", content_json m.content)]

let value_decode j = Res.ok (Value.of_json j)
let ongoing_decode j =
  let open Res in
  let* triggering_cr = Json.get j "triggeringCr" Dynamic_object.of_json in
  let* pending_req_msg = Json.opt_mem j "pendingReqMsg" message_decode in
  let* local_state = Json.get j "localState" value_decode in
  let* reconcile_id = Json.get j "reconcileId" Json.to_int in
  ok ({ triggering_cr; pending_req_msg; local_state; reconcile_id } : Controller.ongoing_reconcile)

let ongoing_json (r : Controller.ongoing_reconcile) = Json.obj [
  ("triggeringCr", Dynamic_object.to_json r.triggering_cr);
  ("pendingReqMsg", Option.fold ~none:`Null ~some:message_json r.pending_req_msg);
  ("localState", Value.json r.local_state); ("reconcileId", Json.int_ r.reconcile_id)]

let map_decode key_decode value_decode j =
  let entry j =
    let open Res in
    let* key = Json.get j "key" key_decode in
    let* value = Json.get j "value" value_decode in ok (key, value) in
  Json.to_list entry j

let map_json key_json value_json entries = Json.list (fun (key, value) ->
  Json.obj [("key", key_json key); ("value", value_json value)]) entries

(* Allocator APIs are intentionally abstract; replay allocation from zero. *)
let rec reconcile_allocator n alloc =
  if n <= 0 then alloc else
    let next, _ = Controller.Reconcile_id_allocator.allocate alloc in reconcile_allocator (n - 1) next
let rec rpc_allocator n alloc =
  if n <= 0 then alloc else
    let next, _ = Message.Rpc_id_allocator.allocate alloc in rpc_allocator (n - 1) next

let controller_decode j =
  let open Res in
  let* entries = Json.get j "ongoing" (map_decode Io_json.key_decode ongoing_decode) in
  let ongoing_reconciles = List.fold_left (fun s (k, v) -> Object_ref_map.add k v s) Object_ref_map.empty entries in
  let* scheduled = Json.mem j "scheduled" in
  let* api = Api_oracle.state_decode (Json.obj [("resources", scheduled); ("uidCounter", Json.int_ 0); ("resourceVersionCounter", Json.int_ 0)]) in
  let* count = Json.get j "reconcileIdAllocator" Json.to_int in
  let reconcile_id_allocator = reconcile_allocator count (Controller.Reconcile_id_allocator.init ()) in
  ok ({ ongoing_reconciles; scheduled_reconciles = api.resources; reconcile_id_allocator } : Controller.state)

let controller_json (c : Controller.state) = Json.obj [
  ("ongoing", map_json Io_json.key_json ongoing_json (Object_ref_map.bindings c.ongoing_reconciles));
  ("scheduled", Json.list (fun (key, obj) -> Json.obj [("key", Io_json.key_json key); ("obj", Dynamic_object.to_json obj)]) (Object_ref_map.bindings c.scheduled_reconciles));
  ("reconcileIdAllocator", Json.int_ (Controller.Reconcile_id_allocator.reconcile_count c.reconcile_id_allocator))]

let actor_decode j =
  let open Res in
  let* controller = Json.get j "controller" controller_decode in
  let* external_ = Json.opt_mem j "external" (fun j -> Res.map (fun state -> ({ state } : External.state)) (Json.get j "state" value_decode)) in
  let* crash_enabled = Json.get j "crashEnabled" Json.to_bool in
  ok ({ controller; external_; crash_enabled } : Cluster.controller_and_external)

let actor_json (a : Cluster.controller_and_external) = Json.obj [
  ("controller", controller_json a.controller);
  ("external", Option.fold ~none:`Null ~some:(fun (s : External.state) -> Json.obj [("state", Value.json s.state)]) a.external_);
  ("crashEnabled", Json.bool_ a.crash_enabled)]

let state_decode j =
  let open Res in
  let* api_server = Json.get j "apiServer" Api_oracle.state_decode in
  let* actors = Json.get j "controllers" (map_decode Json.to_int actor_decode) in
  let controller_and_externals = List.fold_left (fun s (k, v) -> Imap.add k v s) Imap.empty actors in
  let* messages = Json.get j "network" (Json.to_list message_decode) in
  let network : Network.state = { in_flight = Message.Pool.of_list messages } in
  let* rpc = Json.get j "rpcIdAllocator" Json.to_int in
  let rpc_id_allocator = rpc_allocator rpc (Message.Rpc_id_allocator.init ()) in
  let* req_drop_enabled = Json.get j "reqDropEnabled" Json.to_bool in
  let* pod_monkey_enabled = Json.get j "podMonkeyEnabled" Json.to_bool in
  ok ({ api_server; controller_and_externals; network; rpc_id_allocator; req_drop_enabled; pod_monkey_enabled } : Cluster.cluster_state)

let state_json (s : Cluster.cluster_state) =
  let _, next_rpc = Message.Rpc_id_allocator.allocate s.rpc_id_allocator in
  Json.obj [("apiServer", Api_oracle.state_json s.api_server);
    ("controllers", map_json Json.int_ actor_json (Imap.bindings s.controller_and_externals));
    ("network", Json.list message_json (Message.Pool.to_list s.network.in_flight));
    ("rpcIdAllocator", Json.int_ (Message.Rpc_id.to_int next_rpc));
    ("reqDropEnabled", Json.bool_ s.req_drop_enabled); ("podMonkeyEnabled", Json.bool_ s.pod_monkey_enabled)]

let bound_decode j =
  let open Res in
  let* max_in_flight = Json.get j "maxInFlight" Json.to_int in
  let* max_objects_per_kind = Json.get j "maxObjectsPerKind" Json.to_int in
  let* max_controllers = Json.get j "maxControllers" Json.to_int in
  let* uid_ceiling = Json.get j "uidCeiling" Json.to_int in
  let* rv_ceiling = Json.get j "rvCeiling" Json.to_int in
  let* reconcile_ceiling = Json.get j "reconcileCeiling" Json.to_int in
  let* max_reconcile_depth = Json.get j "maxReconcileDepth" Json.to_int in
  let* monkey_forge = Json.get j "monkeyForge" (Json.to_list (fun j -> Res.bind (Dynamic_object.of_json j) Pod.unmarshal)) in
  ok ({ max_in_flight; max_objects_per_kind; max_controllers; uid_ceiling; rv_ceiling; reconcile_ceiling; max_reconcile_depth; monkey_forge } : Bound.t)

let step_json step =
  let obj tag fields = Json.obj (("tag", Json.str tag) :: fields) in
  let recv r = Option.fold ~none:`Null ~some:message_json r in
  match step with
  | Step.Api_server_step r -> obj "api" [("recv", recv r)]
  | Step.Builtin_controllers_step (_, key) -> obj "builtin" [("key", Io_json.key_json key)]
  | Step.Controller_step (id, r, key) -> obj "controller" [("id", Json.int_ id); ("recv", recv r); ("key", Option.fold ~none:`Null ~some:Io_json.key_json key)]
  | Step.Schedule_controller_reconcile_step (id, key) -> obj "schedule" [("id", Json.int_ id); ("key", Io_json.key_json key)]
  | Step.Restart_controller_step id -> obj "restart" [("id", Json.int_ id)]
  | Step.Disable_crash_step id -> obj "disableCrash" [("id", Json.int_ id)]
  | Step.Drop_req_step (msg, error) -> obj "drop" [("msg", message_json msg); ("error", Io_json.error_json error)]
  | Step.Disable_req_drop_step -> obj "disableDrop" []
  | Step.Pod_monkey_step pod -> obj "monkey" [("pod", Dynamic_object.to_json (Pod.marshal pod))]
  | Step.Disable_pod_monkey_step -> obj "disableMonkey" []
  | Step.External_step (id, r) -> obj "external" [("id", Json.int_ id); ("recv", recv r)]
  | Step.Stutter_step -> obj "stutter" []

let models = Imap.empty
  |> Imap.add 0 ({ Cluster.reconciler = (module Vreplica_set_pack.Controller); kind = Vreplica_set.kind; external_model = None } : Cluster.controller_model)
  |> Imap.add 1 ({ Cluster.reconciler = (module V_deployment_pack.Controller); kind = V_deployment.kind; external_model = None } : Cluster.controller_model)
  |> Imap.add 2 ({ Cluster.reconciler = (module V_stateful_set_pack.Controller); kind = V_stateful_set.kind; external_model = None } : Cluster.controller_model)

let invoke j =
  let open Res in
  let* installed_types = Json.get j "policy" Api_oracle.policy_decode in
  let* state = Json.get j "state" state_decode in
  let* bound = Json.get j "bound" bound_decode in
  let* echo = Json.get j "echoExternal" Json.to_bool in
  let controller_models = if echo then
    let external_model : External.model = { init = (fun () -> Value.of_json `Null); transition = (fun request state _ -> request, state) } in
    Imap.update 2 (Option.map (fun (m : Cluster.controller_model) -> { m with external_model = Some external_model })) models
    else models in
  let config : Cluster.t = { installed_types; controller_models } in
  let successors = Cluster.enabled_successors bound config state in
  ok (Json.list (fun (step, state) -> Json.obj [("step", step_json step); ("state", state_json state)]) successors)
