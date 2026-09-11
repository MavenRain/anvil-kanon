"""Paired fixtures call the two kernels; they do not duplicate rule logic."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
pairs=[]
def add(k,o): pairs.append((k,o))
add('proofTrans f g','R.leads_to_trans f g')
add('proofTrans f (proofAssume proofFf g.1)','R.leads_to_trans f (R.assume ~spec:ff (R.goal_of g))')
add('proofTrans f f','R.leads_to_trans f f')
add('proofTrans (proofAssume sp p) g','R.leads_to_trans (R.assume ~spec:sp p) g')
add('proofOr f (proofAssume sp (proofLeadsTo r q))','R.or_leads_to f (R.assume ~spec:sp (leads_to r q))')
add('proofOr f g','R.or_leads_to f g')
add('proofApply (proofAssume sp p) f','R.leads_to_apply (R.assume ~spec:sp p) f')
add('proofApply (proofAssume sp q) f','R.leads_to_apply (R.assume ~spec:sp q) f')
add('proofBorrow (proofAssume sp (proofAlways q)) (proofAssume sp (proofLeadsTo (proofConj p q) r))','R.borrow_inv (R.assume ~spec:sp (always q)) (R.assume ~spec:sp (leads_to (conj p q) r))')
add('proofBorrow (proofAssume sp (proofAlways r)) (proofAssume sp (proofLeadsTo (proofConj p q) r))','R.borrow_inv (R.assume ~spec:sp (always r)) (R.assume ~spec:sp (leads_to (conj p q) r))')
add('proofBorrow (proofAssume sp (proofAlways r)) f','R.borrow_inv (R.assume ~spec:sp (always r)) f')
for pre,post in [('pp','qq'),('f','qq'),('pp','f'),('qq','pp')]:add(f'proofWeaken {pre} {post} f',f'R.leads_to_weaken ~pre:{pre} ~post:{post} f')
for initial,preserved in [('true','true'),('false','true'),('true','false')]:
    add(f'proofInitInvariant sp p (fun (u : Ghost) => ok Bool {initial}) (fun (u : Ghost) => ok Bool {preserved}) (proofAssume sp p) an',f'R.init_invariant ~spec:sp ~inv:p ~init_implies:(fun () -> Ok {initial}) ~inv_preserved:(fun () -> Ok {preserved}) ~spec_init:(R.assume ~spec:sp p) ~spec_next:an')
for pre,post,an,pe,fair,closure,drives in [('p','q','an','pe','fair','true','true'),('p','q','an','pe','fair','false','true'),('p','q','an','pe','fair','true','false'),('sp','q','an','pe','fair','true','true'),('p','sp','an','pe','fair','true','true'),('p','q','f','pe','fair','true','true'),('p','q','an','f','fair','true','true'),('p','q','an','pe','f','true','true')]:
    add(f'proofWf1 sp {pre} {post} (fun (u : Ghost) => ok Bool {closure}) (fun (u : Ghost) => ok Bool {drives}) {an} {pe} {fair}',f'R.wf1 ~spec:sp ~pre:{pre} ~post:{post} ~closure:(fun () -> Ok {closure}) ~drives:(fun () -> Ok {drives}) ~always_next:{an} ~pre_enables:{pe} ~fair:{fair}')
nodes=[('Tt',[]),('Ff',[]),('State',['name','pred']),('Action',['name','act']),('Conj',['a','b']),('Disj',['a','b']),('Impl',['a','b']),*[(n,['a']) for n in ['Neg','Later','Next','Always','Eventually']]]
out=['def rec proofSyntax : ProofFormula -> Value := fun (p : ProofFormula) => match p as self in ProofFormula return Value with']
for n,args in nodes:
    vals=[f'jsonString b"{n.lower()}"']+(['jsonString name'] if n in ['State','Action'] else [f'proofSyntax {a}' for a in args])
    arr='jsonArrayNil'
    for v in reversed(vals): arr=f'jsonArrayCons ({v}) ({arr})'
    out.append(f'  | proof{n} '+ ' '.join(args)+f' => jsonArray ({arr})')
out+=['def kernelFixtures : Nat -> Bytes := fun (u : Nat) =>',
'  let sp : ProofFormula := proofTt in let p : ProofFormula := proofState b"p" (fun (s : ClusterState) => true) in let q : ProofFormula := proofState b"q" (fun (s : ClusterState) => true) in let r : ProofFormula := proofState b"r" (fun (s : ClusterState) => true) in',
'  let f : ProofFact := proofAssume sp (proofLeadsTo p q) in let g : ProofFact := proofAssume sp (proofLeadsTo q r) in',
'  let pp : ProofFact := proofAssume sp (proofAlways (proofImpl p p)) in let qq : ProofFact := proofAssume sp (proofAlways (proofImpl q q)) in',
'  let an : ProofFact := proofAssume sp (proofAlways (proofAction b"next" (fun (s : ClusterState) (t : ClusterState) => true))) in',
'  let pe : ProofFact := proofAssume sp (proofAlways (proofImpl p q)) in let fair : ProofFact := proofAssume sp (proofLeadsTo (proofAlways q) r) in']
vals=[f'proofResultEncode ProofFact (fun (f : ProofFact) => proofSyntax f.1) ({k})' for k,o in pairs]
arr='jsonArrayNil'
for v in reversed(vals):arr=f'jsonArrayCons ({v}) ({arr})'
out.append(f'  valueRender (jsonArray ({arr}))')
(root/'src/kernel_fixtures.kan').write_text('\n'.join(out)+'\n')
ml=['module T = Comp_cat.Temporal','module R = Comp_cat.Rule','let rec syntax p =','  let node tag xs = `List (`String tag :: xs) in','  match T.view p with']
for n,args in nodes:
    tag={'Tt':'tt','Ff':'ff'}.get(n,n.lower())
    pattern={'State':'V_state (name, _)','Action':'V_action (name, _)','Tt':'V_tt','Ff':'V_ff'}.get(n,'V_'+tag+' '+ ('('+', '.join(args)+')' if len(args)==2 else args[0] if args else ''))
    children='[`String name]' if n in ['State','Action'] else '['+'; '.join('syntax '+a for a in args)+']'
    ml.append(f'  | T.{pattern} -> node "{n.lower()}" {children}')
ml+=['let invoke () =','  let open T in','  let sp = tt in let p = lift_state ~name:"p" (fun _ -> true) in let q = lift_state ~name:"q" (fun _ -> true) in let r = lift_state ~name:"r" (fun _ -> true) in',
'  let f = R.assume ~spec:sp (leads_to p q) in let g = R.assume ~spec:sp (leads_to q r) in',
'  let pp = R.assume ~spec:sp (always (implies p p)) in let qq = R.assume ~spec:sp (always (implies q q)) in',
'  let an = R.assume ~spec:sp (always (lift_action ~name:"next" (fun _ _ -> true))) in',
'  let pe = R.assume ~spec:sp (always (implies p q)) in let fair = R.assume ~spec:sp (leads_to (always q) r) in',
'  `List (List.map (Proof_oracle.result (fun f -> syntax (R.goal_of f))) [']
ml+=['    ('+o.replace('R.leads_to_apply (','R.leads_to_apply ~init:(').replace('R.borrow_inv (','R.borrow_inv ~inv:(').replace('~init_implies:', '~init_implies_inv:')+');' for k,o in pairs]
ml+=['  ])']
(root/'oracle/kernel_oracle.ml').write_text('\n'.join(ml)+'\n')
