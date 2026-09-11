let invoke j =
  let open Res in
  let* s = Json.get j "state" Json.to_int in
  let* input = Json.get j "input" Json.to_int in
  let* next = Json.get j "next" Json.to_int in
  let module A = Anvil_state_machine.Action in
  let module S = Anvil_state_machine.State_machine in
  let a : (int, int, int) A.t = { precondition = (fun i s -> i >= 0 && s < i); transition = (fun i s -> (s + i, s - i)) } in
  let sm : (int, int, int, int, int) S.t = { init = (fun s -> s = 0); step_to_action = (fun _ -> a); action_input = (fun step input -> step + input) } in
  ok (Json.obj [("pre", Json.bool_ (A.pre a input s)); ("forward", Json.bool_ (A.forward a input s next));
    ("next", Json.list (fun (s, o) -> Json.obj [("state", Json.int_ s); ("output", Json.int_ o)]) (S.next_results sm ~steps:[0;1;2] input s))])
