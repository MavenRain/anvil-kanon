(* Test transport only. All transitions execute the pinned source library. *)
let key_json (k : Common.object_ref) = Json.obj [
  ("kind", Json.kind_to_json k.kind); ("name", Json.str k.name); ("namespace", Json.str k.namespace)]
let preconditions_json (p : Api_method.preconditions) = Json.obj_opt [
  ("uid", Json.opt (fun x -> Json.int_ (Common.Uid.to_int x)) p.uid);
  ("resourceVersion", Json.opt (fun x -> Json.int_ (Common.Resource_version.to_int x)) p.resource_version)]
let request_json (r : Api_method.api_request) =
  match r with
  | Api_method.Get_request x -> Json.obj [("tag", Json.str "getRequest"); ("value", Json.obj_opt [("key", Some (key_json x.key))])]
  | Api_method.List_request x -> Json.obj [("tag", Json.str "listRequest"); ("value", Json.obj_opt [("kind", Some (Json.kind_to_json x.kind)); ("namespace", Some (Json.str x.namespace))])]
  | Api_method.Create_request x -> Json.obj [("tag", Json.str "createRequest"); ("value", Json.obj_opt [("namespace", Some (Json.str x.namespace)); ("obj", Some (Dynamic_object.to_json x.obj))])]
  | Api_method.Delete_request x -> Json.obj [("tag", Json.str "deleteRequest"); ("value", Json.obj_opt [("key", Some (key_json x.key)); ("preconditions", Json.opt preconditions_json x.preconditions)])]
  | Api_method.Update_request x -> Json.obj [("tag", Json.str "updateRequest"); ("value", Json.obj_opt [("namespace", Some (Json.str x.namespace)); ("name", Some (Json.str x.name)); ("obj", Some (Dynamic_object.to_json x.obj))])]
  | Api_method.Update_status_request x -> Json.obj [("tag", Json.str "updateStatusRequest"); ("value", Json.obj_opt [("namespace", Some (Json.str x.namespace)); ("name", Some (Json.str x.name)); ("obj", Some (Dynamic_object.to_json x.obj))])]
  | Api_method.Get_then_delete_request x -> Json.obj [("tag", Json.str "getThenDeleteRequest"); ("value", Json.obj_opt [("key", Some (key_json x.key)); ("ownerRef", Some (Owner_reference.to_json x.owner_ref))])]
  | Api_method.Get_then_update_request x -> Json.obj [("tag", Json.str "getThenUpdateRequest"); ("value", Json.obj_opt [("namespace", Some (Json.str x.namespace)); ("name", Some (Json.str x.name)); ("ownerRef", Some (Owner_reference.to_json x.owner_ref)); ("obj", Some (Dynamic_object.to_json x.obj))])]
  | Api_method.Get_then_update_status_request x -> Json.obj [("tag", Json.str "getThenUpdateStatusRequest"); ("value", Json.obj_opt [("namespace", Some (Json.str x.namespace)); ("name", Some (Json.str x.name)); ("ownerRef", Some (Owner_reference.to_json x.owner_ref)); ("obj", Some (Dynamic_object.to_json x.obj))])]
let error_decode j =
  let open Res in
  let* tag = Json.to_str j in
  match tag with
  | "badRequest" -> ok Api_method.Bad_request
  | "conflict" -> ok Api_method.Conflict
  | "forbidden" -> ok Api_method.Forbidden
  | "invalid" -> ok Api_method.Invalid
  | "objectNotFound" -> ok Api_method.Object_not_found
  | "objectAlreadyExists" -> ok Api_method.Object_already_exists
  | "notSupported" -> ok Api_method.Not_supported
  | "internalError" -> ok Api_method.Internal_error
  | "timeout" -> ok Api_method.Timeout
  | "serverTimeout" -> ok Api_method.Server_timeout
  | "transactionAbort" -> ok Api_method.Transaction_abort
  | "other" -> ok Api_method.Other
  | _ -> error (Err.Decode_error { typ = "api error"; detail = tag })
let result_decode decode j =
  let open Res in
  let* e = Json.opt_mem j "error" error_decode in
  Option.fold e ~some:(fun e -> ok (Error e)) ~none:(
    let* value = Json.get j "ok" decode in ok (Ok value))
let response_decode j =
  let open Res in
  let* tag = Json.get j "tag" Json.to_str in
  let* value = Json.mem j "value" in
  match tag with
  | "getResponse" ->
      let* res = Json.get value "res" (result_decode (Dynamic_object.of_json)) in
      ok (Api_method.Get_response ({ res } : Api_method.get_response))
  | "listResponse" ->
      let* res = Json.get value "res" (result_decode (Json.to_list Dynamic_object.of_json)) in
      ok (Api_method.List_response ({ res } : Api_method.list_response))
  | "createResponse" ->
      let* res = Json.get value "res" (result_decode (Dynamic_object.of_json)) in
      ok (Api_method.Create_response ({ res } : Api_method.create_response))
  | "deleteResponse" ->
      let* res = Json.get value "res" (result_decode ((fun _ -> Res.ok ()))) in
      ok (Api_method.Delete_response ({ res } : Api_method.delete_response))
  | "updateResponse" ->
      let* res = Json.get value "res" (result_decode (Dynamic_object.of_json)) in
      ok (Api_method.Update_response ({ res } : Api_method.update_response))
  | "updateStatusResponse" ->
      let* res = Json.get value "res" (result_decode (Dynamic_object.of_json)) in
      ok (Api_method.Update_status_response ({ res } : Api_method.update_status_response))
  | "getThenDeleteResponse" ->
      let* res = Json.get value "res" (result_decode ((fun _ -> Res.ok ()))) in
      ok (Api_method.Get_then_delete_response ({ res } : Api_method.get_then_delete_response))
  | "getThenUpdateResponse" ->
      let* res = Json.get value "res" (result_decode (Dynamic_object.of_json)) in
      ok (Api_method.Get_then_update_response ({ res } : Api_method.get_then_update_response))
  | "getThenUpdateStatusResponse" ->
      let* res = Json.get value "res" (result_decode (Dynamic_object.of_json)) in
      ok (Api_method.Get_then_update_status_response ({ res } : Api_method.get_then_update_status_response))
  | _ -> error (Err.Decode_error { typ = "api response"; detail = tag })
let key_decode j =
  let open Res in
  let* kind = Json.get j "kind" Json.kind_of_json in
  let* name = Json.get j "name" Json.to_str in
  let* namespace = Json.get j "namespace" Json.to_str in
  ok ({ kind; name; namespace } : Common.object_ref)
let preconditions_decode j =
  let open Res in
  let* uid = Json.opt_mem j "uid" (fun v -> Res.map Common.Uid.of_int (Json.to_int v)) in
  let* resource_version = Json.opt_mem j "resourceVersion" (fun v -> Res.map Common.Resource_version.of_int (Json.to_int v)) in
  ok ({ uid; resource_version } : Api_method.preconditions)
let request_decode j =
  let open Res in
  let* tag = Json.get j "tag" Json.to_str in
  let* value = Json.mem j "value" in
  match tag with
  | "getRequest" ->
      let* key = Json.get value "key" key_decode in
      ok (Api_method.Get_request ({ key } : Api_method.get_request))
  | "listRequest" ->
      let* kind = Json.get value "kind" Json.kind_of_json in
      let* namespace = Json.get value "namespace" Json.to_str in
      ok (Api_method.List_request ({ kind; namespace } : Api_method.list_request))
  | "createRequest" ->
      let* namespace = Json.get value "namespace" Json.to_str in
      let* obj = Json.get value "obj" Dynamic_object.of_json in
      ok (Api_method.Create_request ({ namespace; obj } : Api_method.create_request))
  | "deleteRequest" ->
      let* key = Json.get value "key" key_decode in
      let* preconditions = Json.opt_mem value "preconditions" preconditions_decode in
      ok (Api_method.Delete_request ({ key; preconditions } : Api_method.delete_request))
  | "updateRequest" ->
      let* namespace = Json.get value "namespace" Json.to_str in
      let* name = Json.get value "name" Json.to_str in
      let* obj = Json.get value "obj" Dynamic_object.of_json in
      ok (Api_method.Update_request ({ namespace; name; obj } : Api_method.update_request))
  | "updateStatusRequest" ->
      let* namespace = Json.get value "namespace" Json.to_str in
      let* name = Json.get value "name" Json.to_str in
      let* obj = Json.get value "obj" Dynamic_object.of_json in
      ok (Api_method.Update_status_request ({ namespace; name; obj } : Api_method.update_status_request))
  | "getThenDeleteRequest" ->
      let* key = Json.get value "key" key_decode in
      let* owner_ref = Json.get value "ownerRef" Owner_reference.of_json in
      ok (Api_method.Get_then_delete_request ({ key; owner_ref } : Api_method.get_then_delete_request))
  | "getThenUpdateRequest" ->
      let* namespace = Json.get value "namespace" Json.to_str in
      let* name = Json.get value "name" Json.to_str in
      let* owner_ref = Json.get value "ownerRef" Owner_reference.of_json in
      let* obj = Json.get value "obj" Dynamic_object.of_json in
      ok (Api_method.Get_then_update_request ({ namespace; name; owner_ref; obj } : Api_method.get_then_update_request))
  | "getThenUpdateStatusRequest" ->
      let* namespace = Json.get value "namespace" Json.to_str in
      let* name = Json.get value "name" Json.to_str in
      let* owner_ref = Json.get value "ownerRef" Owner_reference.of_json in
      let* obj = Json.get value "obj" Dynamic_object.of_json in
      ok (Api_method.Get_then_update_status_request ({ namespace; name; owner_ref; obj } : Api_method.get_then_update_status_request))
  | _ -> error (Err.Decode_error { typ = "api request"; detail = tag })
let error_json (e : Api_method.api_error) = match e with
  | Api_method.Bad_request -> Json.str "badRequest"
  | Api_method.Conflict -> Json.str "conflict"
  | Api_method.Forbidden -> Json.str "forbidden"
  | Api_method.Invalid -> Json.str "invalid"
  | Api_method.Object_not_found -> Json.str "objectNotFound"
  | Api_method.Object_already_exists -> Json.str "objectAlreadyExists"
  | Api_method.Not_supported -> Json.str "notSupported"
  | Api_method.Internal_error -> Json.str "internalError"
  | Api_method.Timeout -> Json.str "timeout"
  | Api_method.Server_timeout -> Json.str "serverTimeout"
  | Api_method.Transaction_abort -> Json.str "transactionAbort"
  | Api_method.Other -> Json.str "other"
let result_json encode r = Result.fold r
  ~error:(fun e -> Json.obj [("error", error_json e)])
  ~ok:(fun x -> Json.obj [("ok", encode x)])
let response_json r = match r with
  | Api_method.Get_response x -> Json.obj [("tag", Json.str "getResponse"); ("value", Json.obj [("res", result_json (Dynamic_object.to_json) x.res)])]
  | Api_method.List_response x -> Json.obj [("tag", Json.str "listResponse"); ("value", Json.obj [("res", result_json (Json.list Dynamic_object.to_json) x.res)])]
  | Api_method.Create_response x -> Json.obj [("tag", Json.str "createResponse"); ("value", Json.obj [("res", result_json (Dynamic_object.to_json) x.res)])]
  | Api_method.Delete_response x -> Json.obj [("tag", Json.str "deleteResponse"); ("value", Json.obj [("res", result_json ((fun () -> Json.obj [])) x.res)])]
  | Api_method.Update_response x -> Json.obj [("tag", Json.str "updateResponse"); ("value", Json.obj [("res", result_json (Dynamic_object.to_json) x.res)])]
  | Api_method.Update_status_response x -> Json.obj [("tag", Json.str "updateStatusResponse"); ("value", Json.obj [("res", result_json (Dynamic_object.to_json) x.res)])]
  | Api_method.Get_then_delete_response x -> Json.obj [("tag", Json.str "getThenDeleteResponse"); ("value", Json.obj [("res", result_json ((fun () -> Json.obj [])) x.res)])]
  | Api_method.Get_then_update_response x -> Json.obj [("tag", Json.str "getThenUpdateResponse"); ("value", Json.obj [("res", result_json (Dynamic_object.to_json) x.res)])]
  | Api_method.Get_then_update_status_response x -> Json.obj [("tag", Json.str "getThenUpdateStatusResponse"); ("value", Json.obj [("res", result_json (Dynamic_object.to_json) x.res)])]
