let state_decode j =
  let open Res in
  let entry j =
    let* key = Json.get j "key" Io_json.key_decode in
    let* obj = Json.get j "obj" Dynamic_object.of_json in
    ok (key, obj)
  in
  let* entries = Json.get j "resources" (Json.to_list entry) in
  let resources = List.fold_left (fun s (key, obj) -> Object_ref_map.add key obj s) Object_ref_map.empty entries in
  let* uid_counter = Json.get j "uidCounter" Json.to_int in
  let* resource_version_counter = Json.get j "resourceVersionCounter" Json.to_int in
  ok ({ resources; uid_counter; resource_version_counter } : Api_server.state)

let state_json (s : Api_server.state) = Json.obj [
  ("resources", Json.list (fun (key, obj) -> Json.obj [("key", Io_json.key_json key); ("obj", Dynamic_object.to_json obj)]) (Object_ref_map.bindings s.resources));
  ("uidCounter", Json.int_ s.uid_counter); ("resourceVersionCounter", Json.int_ s.resource_version_counter)]

let policy_decode j =
  let open Res in
  let* spec = Json.get j "spec" Json.to_bool in
  let* status = Json.get j "status" Json.to_bool in
  let* valid = Json.get j "valid" Json.to_bool in
  let* transition = Json.get j "transition" Json.to_bool in
  let* default_status = Json.mem j "defaultStatus" in
  ok ({ unmarshallable_spec = (fun _ _ -> spec); unmarshallable_status = (fun _ _ -> status);
    valid_object = (fun _ -> valid); valid_transition = (fun _ _ -> transition);
    marshalled_default_status = (fun _ -> Value.of_json default_status) } : Api_server.installed_types)

let invoke_with reference j =
  let open Res in
  let* policy = Json.get j "policy" policy_decode in
  let* state = Json.get j "state" state_decode in
  let* request = Json.get j "request" Io_json.request_decode in
  let msg = Message.form_msg ~src:Message.Pod_monkey ~dst:Message.Api_server
    ~rpc_id:(Message.Rpc_id.of_int 9) ~content:(Message.Api_request request) in
  let state, message = if reference then
    let s, m = Oracle_api_server.handle policy msg (Oracle_api_server.of_api_server state) in
    ({ Api_server.resources = s.resources; uid_counter = s.uid; resource_version_counter = s.rv }, m)
    else Api_server.transition_by_etcd policy msg state in
  let response = match message.content with
    | Message.Api_response r -> Io_json.response_json r
    | Message.Api_request _ | Message.External_request _ | Message.External_response _ -> `Null in
  ok (Json.obj [("state", state_json state); ("response", response)])
let invoke = invoke_with false
let reference = invoke_with true
