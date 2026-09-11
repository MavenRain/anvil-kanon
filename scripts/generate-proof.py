"""Generate the concrete cluster temporal syntax and checked proof rules."""
from pathlib import Path
import json
root = Path(__file__).resolve().parents[1]
nodes = [('Tt', []), ('Ff', []), ('State', [('name','Bytes'),('pred','ClusterState -> Bool')]), ('Action',[('name','Bytes'),('act','ClusterState -> ClusterState -> Bool')]), *[(n,[('a','ProofFormula'),('b','ProofFormula')]) for n in ['Conj','Disj','Impl']], *[(n,[('a','ProofFormula')]) for n in ['Neg','Later','Next','Always','Eventually']]]
out=['-- Concrete cluster formulas retain leaf functions and structural atom names.', 'mu ProofFormula : Type 0 :=']
for n,args in nodes: out.append('| proof'+n+' '+ ' '.join(f'({a} : {t})' for a,t in args)+' : ProofFormula')
def match_cases(result, body):
    return '\n'.join('  | proof'+n+' '+ ' '.join(a for a,t in args)+' => '+body(n,args) for n,args in nodes)
out+=['def proofFormulaEqual : ProofFormula -> ProofFormula -> Bool := fun (xs : ProofFormula) (ys : ProofFormula) =>', '  match xs as self in ProofFormula return Bool with']
for n,args in nodes:
    checks=['bytesEqual name name2'] if n in ['State','Action'] else [f'proofFormulaEqual {a} {a}2' for a,t in args]
    eq='true' if not checks else checks[0] if len(checks)==1 else f'boolAnd ({checks[0]}) ({checks[1]})'
    out.append('  | proof'+n+' '+ ' '.join(a for a,t in args)+' => (match ys as other in ProofFormula return Bool with')
    for m,bs in nodes: out.append('      | proof'+m+' '+ ' '.join(a+'2' for a,t in bs)+' => '+(eq if n==m else 'false'))
    out[-1]+=')'
mapping={'Tt':'True','Ff':'False','State':'State','Action':'Action','Impl':'Implies'}
out+=['def proofFormulaEval : ProofFormula -> Formula ClusterState := fun (p : ProofFormula) => match p as self in ProofFormula return Formula ClusterState with',match_cases('Formula ClusterState',lambda n,args:'formula'+mapping.get(n,n)+' ClusterState '+ ' '.join(f'(proofFormulaEval {a})' if t=='ProofFormula' else a for a,t in args))]
out += ['def proofLeadsTo : ProofFormula -> ProofFormula -> ProofFormula := fun (p : ProofFormula) (q : ProofFormula) => proofAlways (proofImpl p (proofEventually q))',
        'def ProofFact : Type 0 := prod (ProofFormula, ProofFormula)',
        'def proofAssume : ProofFormula -> ProofFormula -> ProofFact := fun (s : ProofFormula) (g : ProofFormula) => tuple (s, g)',
        'def proofSelf : ProofFormula -> ProofFormula -> ProofFact := fun (s : ProofFormula) (p : ProofFormula) => proofAssume s (proofLeadsTo p p)',
        'def proofRequire : Bytes -> Bytes -> Bool -> Result Bool := fun (fn : Bytes) (why : Bytes) (b : Bool) => case b with | 0 (u : Unit) => err Bool (decodeError fn why) | 1 (u : Unit) => ok Bool true']
for name,ctor,args,ty,expr,err in [('Always','Always',['a'],'ProofFormula','a','expected an always []j (an invariant)'),('Impl','Impl',['a','b'],'prod (ProofFormula, ProofFormula)','tuple (a, b)','expected an always-implication [](a => b)'),('Eventually','Eventually',['a'],'ProofFormula','a','expected a leads_to (p ~> q)'),('Conj','Conj',['a','b'],'prod (ProofFormula, ProofFormula)','tuple (a, b)','expected a conjunction (p /\\ j)')]:
    out += [f'def proofAs{name} : Bytes -> ProofFormula -> Result ({ty}) := fun (fn : Bytes) (p : ProofFormula) => match p as self in ProofFormula return Result ({ty}) with',match_cases(ty,lambda n,aa: f'ok ({ty}) ({expr})' if n==ctor else f'err ({ty}) (decodeError fn b{json.dumps(err)})')]
out+=['def proofAsAlwaysImpl : Bytes -> ProofFormula -> Result (prod (ProofFormula, ProofFormula)) := fun (fn : Bytes) (p : ProofFormula) => resultBind ProofFormula (prod (ProofFormula, ProofFormula)) (proofAsAlways fn p) (proofAsImpl fn)',
      'def proofAsLeads : Bytes -> ProofFormula -> Result (prod (ProofFormula, ProofFormula)) := fun (fn : Bytes) (p : ProofFormula) => resultBind (prod (ProofFormula, ProofFormula)) (prod (ProofFormula, ProofFormula)) (proofAsAlwaysImpl fn p) (fun (pq : prod (ProofFormula, ProofFormula)) => resultMap ProofFormula (prod (ProofFormula, ProofFormula)) (fun (q : ProofFormula) => tuple (pq.0, q)) (proofAsEventually fn pq.1))']
for name in ['State','Action']:
    out += [f'def proofIs{name} : ProofFormula -> Bool := fun (p : ProofFormula) => match p as self in ProofFormula return Bool with',match_cases('Bool',lambda n,args:'true' if n==name else 'false')]
# Bind chains preserve the source kernel's error ordering and lazy obligations.
def rule(name,params,steps,goal):
    out.append(f'def proof{name} : '+' -> '.join([f'({t})' for a,t in params]+['Result ProofFact'])+' := '+ ' '.join(f'fun ({a} : {t}) =>' for a,t in params))
    out.append(f'  let fn : Bytes := b"Rule.{dict(Trans="leads_to_trans",Or="or_leads_to",Weaken="leads_to_weaken",Apply="leads_to_apply",Borrow="borrow_inv",InitInvariant="init_invariant",Wf1="wf1")[name]}" in')
    for var,typ,expr in steps: out.append(f'  resultBind ({typ}) ProofFact ({expr}) (fun ({var} : {typ}) =>')
    out.append(f'  ok ProofFact ({goal})'+')'*len(steps))
def req(why,expr): return ('checked','Bool',f'proofRequire fn b{json.dumps(why)} ({expr})')
def same(a,b): return req('facts have different specs',f'proofFormulaEqual {a}.0 {b}.0')
def leads(v): return (v+'pq','prod (ProofFormula, ProofFormula)',f'proofAsLeads fn {v}.1')
rule('Trans',[('f','ProofFact'),('g','ProofFact')],[same('f','g'),leads('f'),leads('g'),req('middle formulas do not match (q ~> _ vs _ ~> q)','proofFormulaEqual fpq.1 gpq.0')],'proofAssume f.0 (proofLeadsTo fpq.0 gpq.1)')
rule('Or',[('f','ProofFact'),('g','ProofFact')],[same('f','g'),leads('f'),leads('g'),req('leads_to targets do not match','proofFormulaEqual fpq.1 gpq.1')],'proofAssume f.0 (proofLeadsTo (proofDisj fpq.0 gpq.0) fpq.1)')
rule('Weaken',[('pre','ProofFact'),('post','ProofFact'),('f','ProofFact')],[req('premise-weakening fact has a different spec','proofFormulaEqual pre.0 f.0'),req('postcondition-strengthening fact has a different spec','proofFormulaEqual post.0 f.0'),('p','prod (ProofFormula, ProofFormula)','proofAsAlwaysImpl fn pre.1'),('q','prod (ProofFormula, ProofFormula)','proofAsAlwaysImpl fn post.1'),leads('f'),req('[](p2 => p1) consequent must match leads_to premise p1','proofFormulaEqual p.1 fpq.0'),req('[](q1 => q2) antecedent must match leads_to conclusion q1','proofFormulaEqual q.0 fpq.1')],'proofAssume f.0 (proofLeadsTo p.0 q.1)')
rule('Apply',[('init','ProofFact'),('f','ProofFact')],[same('init','f'),leads('f'),req('init fact must match the leads_to premise p','proofFormulaEqual init.1 fpq.0')],'proofAssume f.0 (proofEventually fpq.1)')
rule('Borrow',[('inv','ProofFact'),('f','ProofFact')],[same('inv','f'),('j','ProofFormula','proofAsAlways fn inv.1'),leads('f'),('pj','prod (ProofFormula, ProofFormula)','proofAsConj fn fpq.0'),req('right conjunct of the premise must be the invariant body j','proofFormulaEqual j pj.1')],'proofAssume f.0 (proofLeadsTo pj.0 fpq.1)')
rule('InitInvariant',[('sp','ProofFormula'),('inv','ProofFormula'),('initial','Ghost -> Result Bool'),('preserved','Ghost -> Result Bool'),('specInit','ProofFact'),('specNext','ProofFact')],[req('spec_init has a different spec','proofFormulaEqual sp specInit.0'),req('spec_next has a different spec','proofFormulaEqual sp specNext.0'),req('inv must be a lift_state leaf','proofIsState inv'),req('spec_init goal must be a lift_state leaf (|= init)','proofIsState specInit.1'),('next','ProofFormula','proofAsAlways fn specNext.1'),req('spec_next goal must be [](lift_action next)','proofIsAction next'),('initOk','Bool','initial ghost'),req('obligation failed: not (forall s. init s => inv s)','initOk'),('stepOk','Bool','preserved ghost'),req("obligation failed: not (forall s s'. inv s /\\ next s s' => inv s')",'stepOk')],'proofAssume sp (proofAlways inv)')
rule('Wf1',[('sp','ProofFormula'),('pre','ProofFormula'),('post','ProofFormula'),('closure','Ghost -> Result Bool'),('drives','Ghost -> Result Bool'),('alwaysNext','ProofFact'),('preEnables','ProofFact'),('fair','ProofFact')],[req('always_next has a different spec','proofFormulaEqual sp alwaysNext.0'),req('pre_enables has a different spec','proofFormulaEqual sp preEnables.0'),req('fair has a different spec','proofFormulaEqual sp fair.0'),req('pre must be a lift_state leaf','proofIsState pre'),req('post must be a lift_state leaf','proofIsState post'),('next','ProofFormula','proofAsAlways fn alwaysNext.1'),req('always_next goal must be [](lift_action next)','proofIsAction next'),('pe','prod (ProofFormula, ProofFormula)','proofAsAlwaysImpl fn preEnables.1'),req('pre_enables antecedent must be pre ([](pre => enabled forward))','proofFormulaEqual pe.0 pre'),('fairpq','prod (ProofFormula, ProofFormula)','proofAsLeads fn fair.1'),req('fair premise must be [](enabled forward), matching the pre_enables consequent','proofFormulaEqual fairpq.0 (proofAlways pe.1)'),('closed','Bool','closure ghost'),req("obligation failed: not (p /\\ next => p' \\/ q')",'closed'),('driven','Bool','drives ghost'),req("obligation failed: not (p /\\ next /\\ forward => q')",'driven')],'proofAssume sp (proofLeadsTo pre post)')
code = '\n'.join(out)+'\n'
# The public destructors report the whole expected shape, not the first failed layer.
code = code.replace('def proofAsAlwaysImpl :', 'def proofAsAlwaysImplRaw :').replace('def proofAsLeads :', 'def proofAsLeadsRaw :')
pos = code.index('def proofIsState :')
wrappers = ''
for name,why in [('AlwaysImpl','expected an always-implication [](a => b)'),('Leads','expected a leads_to (p ~> q)')]:
    wrappers += f'def proofAs{name} : Bytes -> ProofFormula -> Result (prod (ProofFormula, ProofFormula)) := fun (fn : Bytes) (p : ProofFormula) => resultFold (prod (ProofFormula, ProofFormula)) (Result (prod (ProofFormula, ProofFormula))) (fun (e : Error) => err (prod (ProofFormula, ProofFormula)) (decodeError fn b{json.dumps(why)})) (ok (prod (ProofFormula, ProofFormula))) (proofAs{name}Raw fn p)\n'
code = code[:pos]+wrappers+code[pos:]
# The raw leads extractor precedes the wrapped always-implication extractor.
start,end=code.index('def proofAsLeadsRaw'),code.index('def proofAsAlwaysImpl :')
code=code[:start]+code[start:end].replace('proofAsAlwaysImpl fn','proofAsAlwaysImplRaw fn')+code[end:]
code=code.replace('def proofFormulaEqual :','def rec proofFormulaEqual :').replace('def proofFormulaEval :','def rec proofFormulaEval :')
(root/'src/proof_kernel.kan').write_text('\n'.join(line.rstrip() for line in code.splitlines())+'\n')
