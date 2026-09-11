module T = Comp_cat.Temporal
module R = Comp_cat.Rule
let rec syntax p =
  let node tag xs = `List (`String tag :: xs) in
  match T.view p with
  | T.V_tt -> node "tt" []
  | T.V_ff -> node "ff" []
  | T.V_state (name, _) -> node "state" [`String name]
  | T.V_action (name, _) -> node "action" [`String name]
  | T.V_conj (a, b) -> node "conj" [syntax a; syntax b]
  | T.V_disj (a, b) -> node "disj" [syntax a; syntax b]
  | T.V_impl (a, b) -> node "impl" [syntax a; syntax b]
  | T.V_neg a -> node "neg" [syntax a]
  | T.V_later a -> node "later" [syntax a]
  | T.V_next a -> node "next" [syntax a]
  | T.V_always a -> node "always" [syntax a]
  | T.V_eventually a -> node "eventually" [syntax a]
let invoke () =
  let open T in
  let sp = tt in let p = lift_state ~name:"p" (fun _ -> true) in let q = lift_state ~name:"q" (fun _ -> true) in let r = lift_state ~name:"r" (fun _ -> true) in
  let f = R.assume ~spec:sp (leads_to p q) in let g = R.assume ~spec:sp (leads_to q r) in
  let pp = R.assume ~spec:sp (always (implies p p)) in let qq = R.assume ~spec:sp (always (implies q q)) in
  let an = R.assume ~spec:sp (always (lift_action ~name:"next" (fun _ _ -> true))) in
  let pe = R.assume ~spec:sp (always (implies p q)) in let fair = R.assume ~spec:sp (leads_to (always q) r) in
  `List (List.map (Proof_oracle.result (fun f -> syntax (R.goal_of f))) [
    (R.leads_to_trans f g);
    (R.leads_to_trans f (R.assume ~spec:ff (R.goal_of g)));
    (R.leads_to_trans f f);
    (R.leads_to_trans (R.assume ~spec:sp p) g);
    (R.or_leads_to f (R.assume ~spec:sp (leads_to r q)));
    (R.or_leads_to f g);
    (R.leads_to_apply ~init:(R.assume ~spec:sp p) f);
    (R.leads_to_apply ~init:(R.assume ~spec:sp q) f);
    (R.borrow_inv ~inv:(R.assume ~spec:sp (always q)) (R.assume ~spec:sp (leads_to (conj p q) r)));
    (R.borrow_inv ~inv:(R.assume ~spec:sp (always r)) (R.assume ~spec:sp (leads_to (conj p q) r)));
    (R.borrow_inv ~inv:(R.assume ~spec:sp (always r)) f);
    (R.leads_to_weaken ~pre:pp ~post:qq f);
    (R.leads_to_weaken ~pre:f ~post:qq f);
    (R.leads_to_weaken ~pre:pp ~post:f f);
    (R.leads_to_weaken ~pre:qq ~post:pp f);
    (R.init_invariant ~spec:sp ~inv:p ~init_implies_inv:(fun () -> Ok true) ~inv_preserved:(fun () -> Ok true) ~spec_init:(R.assume ~spec:sp p) ~spec_next:an);
    (R.init_invariant ~spec:sp ~inv:p ~init_implies_inv:(fun () -> Ok false) ~inv_preserved:(fun () -> Ok true) ~spec_init:(R.assume ~spec:sp p) ~spec_next:an);
    (R.init_invariant ~spec:sp ~inv:p ~init_implies_inv:(fun () -> Ok true) ~inv_preserved:(fun () -> Ok false) ~spec_init:(R.assume ~spec:sp p) ~spec_next:an);
    (R.wf1 ~spec:sp ~pre:p ~post:q ~closure:(fun () -> Ok true) ~drives:(fun () -> Ok true) ~always_next:an ~pre_enables:pe ~fair:fair);
    (R.wf1 ~spec:sp ~pre:p ~post:q ~closure:(fun () -> Ok false) ~drives:(fun () -> Ok true) ~always_next:an ~pre_enables:pe ~fair:fair);
    (R.wf1 ~spec:sp ~pre:p ~post:q ~closure:(fun () -> Ok true) ~drives:(fun () -> Ok false) ~always_next:an ~pre_enables:pe ~fair:fair);
    (R.wf1 ~spec:sp ~pre:sp ~post:q ~closure:(fun () -> Ok true) ~drives:(fun () -> Ok true) ~always_next:an ~pre_enables:pe ~fair:fair);
    (R.wf1 ~spec:sp ~pre:p ~post:sp ~closure:(fun () -> Ok true) ~drives:(fun () -> Ok true) ~always_next:an ~pre_enables:pe ~fair:fair);
    (R.wf1 ~spec:sp ~pre:p ~post:q ~closure:(fun () -> Ok true) ~drives:(fun () -> Ok true) ~always_next:f ~pre_enables:pe ~fair:fair);
    (R.wf1 ~spec:sp ~pre:p ~post:q ~closure:(fun () -> Ok true) ~drives:(fun () -> Ok true) ~always_next:an ~pre_enables:f ~fair:fair);
    (R.wf1 ~spec:sp ~pre:p ~post:q ~closure:(fun () -> Ok true) ~drives:(fun () -> Ok true) ~always_next:an ~pre_enables:pe ~fair:f);
  ])
