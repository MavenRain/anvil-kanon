let outcome_json (outcome : int Model_check.outcome) =
  match outcome with
  | Model_check.Refuted { lasso; steps } -> Json.obj [
      ("tag", Json.str "refuted"); ("stem", Json.list Json.int_ (Array.to_list lasso.stem));
      ("loop", Json.list Json.int_ (Array.to_list lasso.loop)); ("steps", Json.int_ steps)]
  | Model_check.No_counterexample { decisive; depth; states } -> Json.obj [
      ("tag", Json.str "noCounterexample"); ("decisive", Json.bool_ decisive);
      ("depth", Json.int_ depth); ("states", Json.int_ states)]

let invoke j =
  let open Res in
  let* graph = Json.get j "graph" (Json.to_list (Json.to_list Json.to_int)) in
  let* init = Json.get j "init" (Json.to_list Json.to_int) in
  let* depth = Json.get j "depth" Json.to_int in
  let* mode = Json.get j "mode" Json.to_str in
  let* target = Json.get j "target" (Json.to_list Json.to_int) in
  let* second = Json.get j "second" (Json.to_list Json.to_int) in
  let* fair = Json.get j "fair" Json.to_bool in
  let successors n = Option.value ~default:[] (List.nth_opt graph n) in
  let target_pred n = List.mem n target in
  let module T = Comp_cat.Temporal in
  let p = T.lift_state ~name:"target" target_pred in
  let q = T.lift_state ~name:"second" (fun n -> List.mem n second) in
  let goal = match mode with
    | "always" -> T.always p
    | "eventually" -> T.eventually p
    | "next" -> T.tl_next p
    | "alwaysEventually" -> T.always (T.eventually p)
    | "eventuallyAlways" -> T.eventually (T.always p)
    | "alternating" -> T.neg (T.conj (T.always (T.eventually p)) (T.always (T.eventually q)))
    | "true" -> T.tt
    | _ -> T.ff
  in
  let fair_pred (l : int Model_check.lasso) = not fair || Array.exists target_pred l.loop in
  let reach = Model_check.explore ~depth ~successors ~equal:Int.equal ~hash:Fun.id ~init in
  let outcome = match mode with
    | "safety" -> Model_check.check_safety reach ~inv:target_pred ~equal:Int.equal
    | "reaches" -> Model_check.check_reaches reach ~target:target_pred
        ~quiescent:(fun n -> List.for_all (Int.equal n) (successors n)) ~equal:Int.equal
    | _ -> Model_check.check_temporal ~depth ~successors ~equal:Int.equal ~init ~fair:fair_pred ~goal ()
  in
  let order = List.rev (Model_check.fold_states reach ~init:[] ~f:(fun acc s -> s :: acc)) in
  ok (Json.obj [("outcome", outcome_json outcome); ("order", Json.list Json.int_ order);
    ("frontierEmptied", Json.bool_ (Model_check.frontier_emptied reach))])
