(* Read-only differential oracle against the pinned OCaml library. *)
let summarize (j : Yojson.Safe.t) : Yojson.Safe.t Res.t =
  let open Res in
  let* left = Json.get j "left" Object_meta.of_json in
  let* right = Json.get j "right" Object_meta.of_json in
  let* owner = Json.get j "owner" Owner_reference.of_json in
  let* other = Json.get j "other" Owner_reference.of_json in
  let* selector = Json.get j "selector" Label_selector.of_json in
  let* labels = Json.get j "labels" Json.to_smap in
  ok (Json.obj [
    ("wellFormed", Json.bool_ (Object_meta.well_formed_for_namespaced left));
    ("metadataEqual", Json.bool_ (Object_meta.equal left right));
    ("ownerEqual", Json.bool_ (Owner_reference.equal owner other));
    ("ownerEqualWithoutUid", Json.bool_ (Owner_reference.eq_without_uid owner other));
    ("controller", Json.bool_ (Owner_reference.is_controller owner));
    ("contains", Json.bool_ (Object_meta.owner_references_contains left owner));
    ("onlyContains", Json.bool_ (Object_meta.owner_references_only_contains left owner));
    ("selectorMatches", Json.bool_ (Label_selector.matches selector labels))
  ])

let codec typ j =
  let pair decode encode = Res.map encode (decode j) in
  match typ with
  | "metadata" -> pair Object_meta.of_json Object_meta.to_json
  | "owner" -> pair Owner_reference.of_json Owner_reference.to_json
  | "kind" -> pair Json.kind_of_json Json.kind_to_json
  | "podSpec" -> pair Pod_spec.of_json Pod_spec.to_json
  | "template" -> pair Pod_template_spec.of_json Pod_template_spec.to_json
  | "container" -> pair Container.of_json Container.to_json
  | "volume" -> pair Volume.of_json Volume.to_json
  | "pvc" -> pair Persistent_volume_claim.of_json Persistent_volume_claim.to_json
  | "selector" -> pair Label_selector.of_json Label_selector.to_json
  | "statefulSpec" -> pair Stateful_set.ss_spec_of_json Stateful_set.ss_spec_to_json
  | "strategy" -> pair Deployment_strategy.of_json Deployment_strategy.to_json
  | _ -> Res.error (Err.Decode_error { typ = "oracle codec"; detail = typ })

let invoke typ j =
  let open Res in
  let* cr = Json.get j "cr" Dynamic_object.of_json in
  let* state = Json.mem j "state" in
  let* response = Json.opt_mem j "response" Io_json.response_decode in
  let resp = Option.map (fun r -> Io.K_response r) response in
  let finish encode (state, request) =
    let req = Option.map (fun (r : Io.void Io.request_view) -> match r with
      | Io.K_request r -> Io_json.request_json r
      | Io.External_request _ -> .) request in
    ok (Json.obj [("state", Value.json (encode state));
      ("request", Option.value ~default:`Null req)])
  in
  match typ with
  | "vrs" ->
      let* cr = Vreplica_set.unmarshal cr in
      let* state = Vreplica_set_pack.unmarshal_state (Value.of_json state) in
      finish Vreplica_set_pack.marshal_state (Vreplica_set_reconciler.reconcile_core ~cr ~resp ~state)
  | "deployment" ->
      let* cr = V_deployment.unmarshal cr in
      let* state = V_deployment_pack.unmarshal_state (Value.of_json state) in
      finish V_deployment_pack.marshal_state (V_deployment_reconciler.reconcile_core ~cr ~resp ~state)
  | "stateful" ->
      let* cr = V_stateful_set.unmarshal cr in
      let* state = V_stateful_set_pack.unmarshal_state (Value.of_json state) in
      finish V_stateful_set_pack.marshal_state (V_stateful_set_reconciler.reconcile_core ~cr ~resp ~state)
  | _ -> error (Err.Decode_error { typ = "controller"; detail = typ })

let pack typ j =
  match typ with
  | "vrs" -> Res.map (fun s -> Value.json (Vreplica_set_pack.marshal_state s)) (Vreplica_set_pack.unmarshal_state (Value.of_json j))
  | "deployment" -> Res.map (fun s -> Value.json (V_deployment_pack.marshal_state s)) (V_deployment_pack.unmarshal_state (Value.of_json j))
  | "stateful" -> Res.map (fun s -> Value.json (V_stateful_set_pack.marshal_state s)) (V_stateful_set_pack.unmarshal_state (Value.of_json j))
  | _ -> Res.error (Err.Decode_error { typ = "pack"; detail = typ })

let () =
  match Sys.argv with
  | [| _program; "action"; input |] ->
      let result = Res.bind (Value.of_string input) (fun v -> Action_oracle.invoke (Value.json v)) in
      Result.fold result ~ok:(fun value -> print_endline (Yojson.Safe.to_string value))
        ~error:(fun error -> print_endline ("error: " ^ Err.show error))
  | [| _program; "exec-create"; input |] ->
      let result = Res.bind (Value.of_string input) (fun v -> Runtime_oracle.create (Value.json v)) in
      Result.fold result ~ok:(fun value -> print_endline (Yojson.Safe.to_string value))
        ~error:(fun error -> print_endline ("error: " ^ Err.show error))
  | [| _program; "defaults" |] -> print_endline (Yojson.Safe.to_string (Defaults_oracle.invoke ()))
  | [| _program; "value"; input |] ->
      Result.fold (Value.of_string input) ~ok:(fun v -> print_endline (Value.to_string v)) ~error:(fun e -> print_endline ("error: " ^ Err.show e))
  | [| _program; "kernel" |] -> print_endline (Yojson.Safe.to_string (Kernel_oracle.invoke ()))
  | [| _program; "runtime"; input |] ->
      let result = Res.bind (Value.of_string input) (fun v -> Runtime_oracle.invoke (Value.json v)) in
      Result.fold result ~ok:(fun value -> print_endline (Yojson.Safe.to_string value))
        ~error:(fun error -> print_endline ("error: " ^ Err.show error))
  | [| _program; "api-reference"; input |] ->
      let result = Res.bind (Value.of_string input) (fun v -> Api_oracle.reference (Value.json v)) in
      Result.fold result ~ok:(fun value -> print_endline (Yojson.Safe.to_string value))
        ~error:(fun error -> print_endline ("error: " ^ Err.show error))
  | [| _program; "proof"; input |] ->
      let result = Res.bind (Value.of_string input) (fun v -> Proof_oracle.invoke (Value.json v)) in
      Result.fold result ~ok:(fun value -> print_endline (Yojson.Safe.to_string value))
        ~error:(fun error -> print_endline ("error: " ^ Err.show error))
  | [| _program; ("fault-check" | "forge" as mode); input |] ->
      let run = if String.equal mode "forge" then Fault_oracle.forge else Fault_oracle.invoke in
      let result = Res.bind (Value.of_string input) (fun v -> run (Value.json v)) in
      Result.fold result ~ok:(fun value -> print_endline (Yojson.Safe.to_string value))
        ~error:(fun error -> print_endline ("error: " ^ Err.show error))
  | [| _program; "cluster-check"; input |] ->
      let result = Res.bind (Value.of_string input) (fun v -> Checker_oracle.invoke (Value.json v)) in
      Result.fold result ~ok:(fun value -> print_endline (Yojson.Safe.to_string value))
        ~error:(fun error -> print_endline ("error: " ^ Err.show error))
  | [| _program; ("scenario" | "intact" as mode); input |] ->
      let run = if String.equal mode "intact" then Scenario_oracle.intact else Scenario_oracle.invoke in
      let result = Res.bind (Value.of_string input) (fun v -> run (Value.json v)) in
      Result.fold result ~ok:(fun value -> print_endline (Yojson.Safe.to_string value))
        ~error:(fun error -> print_endline ("error: " ^ Err.show error))
  | [| _program; "assurance-vrs"; input |] ->
      let result = Res.bind (Value.of_string input) (fun v -> Assurance_oracle.invoke_vrs (Value.json v)) in
      Result.fold result ~ok:(fun value -> print_endline (Yojson.Safe.to_string value))
        ~error:(fun error -> print_endline ("error: " ^ Err.show error))
  | [| _program; "assurance-stateful"; input |] ->
      let result = Res.bind (Value.of_string input) (fun v -> Assurance_oracle.invoke_stateful (Value.json v)) in
      Result.fold result ~ok:(fun value -> print_endline (Yojson.Safe.to_string value))
        ~error:(fun error -> print_endline ("error: " ^ Err.show error))
  | [| _program; "assurance"; input |] ->
      let result = Res.bind (Value.of_string input) (fun v -> Assurance_oracle.invoke (Value.json v)) in
      Result.fold result ~ok:(fun value -> print_endline (Yojson.Safe.to_string value))
        ~error:(fun error -> print_endline ("error: " ^ Err.show error))
  | [| _program; "cluster"; input |] ->
      let result = Res.bind (Value.of_string input) (fun v -> Cluster_oracle.invoke (Value.json v)) in
      Result.fold result ~ok:(fun value -> print_endline (Yojson.Safe.to_string value))
        ~error:(fun error -> print_endline ("error: " ^ Err.show error))
  | [| _program; "graph"; input |] ->
      let result = Res.bind (Value.of_string input) (fun v -> Graph_oracle.invoke (Value.json v)) in
      Result.fold result ~ok:(fun value -> print_endline (Yojson.Safe.to_string value))
        ~error:(fun error -> print_endline ("error: " ^ Err.show error))
  | [| _program; "api"; input |] ->
      let result = Res.bind (Value.of_string input) (fun v -> Api_oracle.invoke (Value.json v)) in
      Result.fold result ~ok:(fun value -> print_endline (Yojson.Safe.to_string value))
        ~error:(fun error -> print_endline ("error: " ^ Err.show error))
  | [| _program; ("invoke" | "pack" as operation); typ; input |] ->
      let run = if String.equal operation "invoke" then invoke else pack in
      let result = Res.bind (Value.of_string input) (fun v -> run typ (Value.json v)) in
      Result.fold result
        ~ok:(fun value -> print_endline (Yojson.Safe.to_string value))
        ~error:(fun error -> print_endline ("error: " ^ Err.show error))
  | [| _program; "codec"; typ; input |] ->
      let result = Res.bind (Value.of_string input) (fun v -> codec typ (Value.json v)) in
      Result.fold result
        ~ok:(fun value -> print_endline (Yojson.Safe.to_string value))
        ~error:(fun error -> print_endline ("error: " ^ Err.show error))
  | [| _program; input |] ->
      let result = Res.bind (Value.of_string input) (fun value -> summarize (Value.json value)) in
      Result.fold result
        ~ok:(fun value -> print_endline (Yojson.Safe.to_string value))
        ~error:(fun error -> prerr_endline (Err.show error); exit 1)
  | _args -> prerr_endline "usage: port_oracle JSON"; exit 2
