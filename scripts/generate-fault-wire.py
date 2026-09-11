from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
queries = ['always', 'correspondence', 'reconcile', 'responseRv', 'responseMatched', 'store', 'helper', 'unique', 'settles', 'provenance', 'rely', 'forge', 'internal', 'scaleDown', 'localBinding', 'statePredicates']
def obj(fields):
    result = 'jsonObjectNil'
    for key, value in reversed(fields): result = f'jsonObjectCons b"{key}" ({value}) ({result})'
    return f'jsonObject ({result})'
def decoder(typ, fields):
    result = f'ok {typ} (tuple (' + ', '.join(f'f{i}' for i in range(len(fields))) + '))'
    for i, (name, field_type, decode) in reversed(list(enumerate(fields))):
        result = f'resultBind ({field_type}) {typ} (jsonField ({field_type}) j b"{name}" ({decode})) (fun (f{i} : {field_type}) => {result})'
    return f'def {typ[0].lower() + typ[1:]}Decode : Value -> Result {typ} := fun (j : Value) => {result}'
query = 'err FaultQuery (decodeError b"fault query" name)'
for q in reversed(queries):
    query = f'(case (bytesEqual name b"{q}") with | 1 (u : Unit) => ok FaultQuery faultQuery{q[0].upper() + q[1:]} | 0 (u : Unit) => {query})'
out = ['-- Generated wire representation for bounded fault reports.',
 f'def faultQueryDecode : Value -> Result FaultQuery := fun (j : Value) => resultBind Bytes FaultQuery (jsonGetString j) (fun (name : Bytes) => {query})',
 decoder('FaultBudget', [(k, 'Int', 'jsonGetInt') for k in ['maxCrashes', 'maxDrops', 'maxMonkeyOps']]),
 decoder('FaultOptions', [('desired', 'Int', 'jsonGetInt'), ('desireds', 'Sequence Int', 'jsonSequenceDecode Int jsonGetInt'), ('ordinals', 'Sequence Int', 'jsonSequenceDecode Int jsonGetInt'), ('drop', 'Bool', 'jsonGetBool'), ('monkey', 'Bool', 'jsonGetBool'), ('vct', 'Bool', 'jsonGetBool'), ('requireFault', 'Bool', 'jsonGetBool')]),
 'def faultBudgetEncode : FaultBudget -> Value := fun (b : FaultBudget) => ' + obj([(k, f'jsonInt b.{i}') for i,k in enumerate(['maxCrashes', 'maxDrops', 'maxMonkeyOps'])]),
 'def faultedEncode : Faulted -> Value := fun (f : Faulted) => ' + obj([('state', 'clusterStateWireEncode f.0'), ('crashes', 'jsonInt f.1'), ('drops', 'jsonInt f.2'), ('monkeys', 'jsonInt f.3')]),
 'def faultOutcomeEncode : Outcome Faulted -> Value := fun (o : Outcome Faulted) => case o with',
 '  | 0 (r : prod (Lasso Faulted, Nat)) => ' + obj([('tag','jsonString b"refuted"'), ('stem','jsonSequenceEncode Faulted faultedEncode r.0.0'), ('loop','jsonSequenceEncode Faulted faultedEncode r.0.1'), ('steps','jsonEncodeNat r.1')]),
 '  | 1 (r : prod (Bool, Int, Nat)) => ' + obj([('tag','jsonString b"noCounterexample"'), ('decisive','jsonBool r.0'), ('depth','jsonInt r.1'), ('states','jsonEncodeNat r.2')])]
fields = [('outcome','faultOutcomeEncode r.0'), ('bound','boundWireEncode r.1'), ('budget','faultBudgetEncode r.2')]
for i, name in enumerate(['maxUidSeen','maxRvSeen','maxCrashesSeen','maxDropsSeen','maxMonkeysSeen']): fields.append((name,f'jsonInt r.3.{i}'))
fields += [('prunedByCeiling','jsonBool r.3.8'), ('prunedByBudget','jsonBool r.3.9'), ('violated','jsonEncodeOption Invariant invariantIdentityEncode r.4'), ('gateStates','jsonEncodeOption Nat jsonEncodeNat r.5')]
for i, name in enumerate(['crashWitnessStates','faultFreeStates','settledWithFaultsLive'],5): fields.append((name,f'jsonEncodeNat r.3.{i}'))
out += ['def faultReportEncode : FaultReport -> Value := fun (r : FaultReport) => ' + obj(fields),
 '''def faultCheckInvoke : Value -> Result Value := fun (j : Value) =>
  resultBind FaultQuery Value (jsonField FaultQuery j b"query" faultQueryDecode) (fun (q : FaultQuery) =>
  resultBind Int Value (jsonField Int j b"depth" jsonGetInt) (fun (depth : Int) =>
  resultBind Bound Value (jsonField Bound j b"bound" boundWireDecode) (fun (b : Bound) =>
  resultBind FaultBudget Value (jsonField FaultBudget j b"budget" faultBudgetDecode) (fun (budget : FaultBudget) =>
  resultMap FaultOptions Value (fun (o : FaultOptions) => faultReportEncode (checkFaultScenario q depth b budget o)) (jsonField FaultOptions j b"options" faultOptionsDecode)))))
def faultCheckRender : Value -> Bytes := fun (j : Value) => case (faultCheckInvoke j) with
  | 0 (e : Error) => bytesAppend b"error: " (errorText e) | 1 (j : Value) => valueRender j
def faultForgeRender : Int -> Bool -> Bytes := fun (desired : Int) (respecting : Bool) => valueRender (podTResourceEncode (select PodT respecting (faultRelyRespectingForge desired) (faultRelyViolatingForge desired)))''']
(ROOT/'src/fault_wire.kan').write_text('\n'.join(out)+'\n')
