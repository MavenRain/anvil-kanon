"""Generate the three source-defined state wire contracts and controller ABI."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
layout = json.loads((root / "layout-info.json").read_text())
out = ["-- Complete controller-state codecs. Child resources use their marshal contract."]
exports = []
models = ['''-- Programs expose the source erasure behavior at every cluster boundary.
def ProgramOutput : Type 0 := prod (Value, Option RequestView)
def ControllerProgram : Type 0 := prod (CommonKind, Value, (DynamicObjectT -> Option ResponseView -> Value -> ProgramOutput), (Value -> Bool), (Value -> Bool))''']

def lower(s):
    return s[:1].lower() + s[1:]

def camel(s):
    return "".join(p[:1].upper() + p[1:] for p in s.split("_") if p)

def emit(s):
    out.append(s)

def obj(fields):
    tail = "jsonObjectNil"
    for key, value in reversed(fields):
        tail = f'jsonObjectCons b"{key}" ({value}) ({tail})'
    return f"jsonObject ({tail})"

branches = ["jsonNull", "jsonBool x", "jsonInt x", "jsonIntLiteral x", "jsonFloat x", "jsonString x", "jsonArray x", "jsonObject x", "jsonArrayNil", "jsonArrayCons h t", "jsonObjectNil", "jsonObjectCons k v t"]
for typ in ["PodT", "VreplicaSetT", "PersistentVolumeClaimT"]:
    f = lower(typ)
    emit(f"def {f}ResourceEncode : {typ} -> Value := fun (x : {typ}) => dynamicObjectTEncode ({f}Marshal x)")
    emit(f"def {f}ResourceDecode : Value -> Result {typ} := fun (j : Value) => resultBind DynamicObjectT {typ} (dynamicObjectTDecode j) {f}Unmarshal")

emit('def neededPodDecode : Value -> Result (Option PodT) := fun (j : Value) =>\n'
     '  case (jsonIsNull j) with | 1 (u : Unit) => ok (Option PodT) (none PodT)\n'
     '  | 0 (u : Unit) => resultMap PodT (Option PodT) (some PodT) (decodeResourceObject PodT b"v_stateful_set_pack.needed" b"expected object or null" podTResourceDecode j)')
for typ, item, enc, dec in [
    ("ListPodT", "PodT", "podTResourceEncode", "podTResourceDecode"),
    ("ListVreplicaSetT", "VreplicaSetT", "vreplicaSetTResourceEncode", "vreplicaSetTResourceDecode"),
    ("ListPersistentVolumeClaimT", "PersistentVolumeClaimT", "persistentVolumeClaimTResourceEncode", "persistentVolumeClaimTResourceDecode"),
    ("ListOptionPodT", "Option PodT", "jsonEncodeOption PodT podTResourceEncode", "neededPodDecode")]:
    f = lower(typ)
    emit(f"def rec {f}ResourceItems : {typ} -> Values := fun (xs : {typ}) =>\n"
         f"  match xs as self in {typ} return Values with | {f}Nil => jsonArrayNil\n"
         f"  | {f}Cons h t => jsonArrayCons ({enc} h) ({f}ResourceItems t)")
    emit(f"def {f}ResourceEncode : {typ} -> Value := fun (xs : {typ}) => jsonArray ({f}ResourceItems xs)")
    bs = []
    for b in branches:
        body = f'err {typ} (decodeError b"list" b"expected a JSON array")'
        if b == "jsonArrayNil":
            body = f"ok {typ} {f}Nil"
        elif b == "jsonArrayCons h t":
            body = f"resultBind ({item}) {typ} ({dec} h) (fun (v : {item}) => resultMap {typ} {typ} (fun (tail : {typ}) => {f}Cons v tail) ({f}ResourceDecodeItems t))"
        bs.append(f"  | {b} => {body}")
    emit(f"def rec {f}ResourceDecodeItems : Values -> Result {typ} := fun (xs : Values) =>\n  match xs as self in JsonTree sort return Result {typ} with\n" + "\n".join(bs))
    emit(f"def {f}ResourceDecode : Value -> Result {typ} := fun (j : Value) => resultBind Values {typ} (jsonGetArray j) {f}ResourceDecodeItems")

configs = [
    ("vrs", "VreplicaSetReconciler", "vreplica_set", "VreplicaSetT", [
        ("filtered_pods", "Option ListPodT", "listPodTResourceEncode", "listPodTResourceDecode", None)]),
    ("deployment", "VDeploymentReconciler", "v_deployment", "VDeploymentT", [
        ("new_vrs", "Option VreplicaSetT", "vreplicaSetTResourceEncode", "vreplicaSetTResourceDecode", None),
        ("old_vrs_list", "ListVreplicaSetT", "listVreplicaSetTResourceEncode", "listVreplicaSetTResourceDecode", "listVreplicaSetTNil"),
        ("old_vrs_index", "Int", "jsonEncodeInt", "jsonGetInt", "nonnegative 0")]),
    ("stateful", "VStatefulSetReconciler", "v_stateful_set", "VStatefulSetT", [
        ("needed", "ListOptionPodT", "listOptionPodTResourceEncode", "listOptionPodTResourceDecode", "listOptionPodTNil"),
        ("needed_index", "Int", "jsonEncodeInt", "jsonGetInt", "nonnegative 0"),
        ("condemned", "ListPodT", "listPodTResourceEncode", "listPodTResourceDecode", "listPodTNil"),
        ("condemned_index", "Int", "jsonEncodeInt", "jsonGetInt", "nonnegative 0"),
        ("pvcs", "ListPersistentVolumeClaimT", "listPersistentVolumeClaimTResourceEncode", "listPersistentVolumeClaimTResourceDecode", "listPersistentVolumeClaimTNil"),
        ("pvc_index", "Int", "jsonEncodeInt", "jsonGetInt", "nonnegative 0")])]

for prefix, model, source, cr, fields in configs:
    step = model + "Step"
    state = model + "S"
    sf = lower(state)
    stepf = lower(step)
    encoded = []
    tests = f'err {step} (decodeError b"{source}_reconciler.step" tag)'
    for name, payload in reversed(layout[step]["variants"]):
        ctor = stepf + camel(name)
        tag = lower(camel(name))
        members = [("step", f'jsonString b"{tag}"')]
        body = f"ok {step} {ctor}"
        if payload:
            assert payload == "Int"
            members.append(("diff", "jsonInt d"))
            body = f'resultMap Int {step} (fun (d : Int) => {ctor} d) (jsonField Int j b"diff" jsonGetInt)'
        encoded.append(f"  | {ctor}" + (" d" if payload else "") + " => " + obj(members))
        tests = f'(case (bytesEqual tag b"{tag}") with | 1 (u : Unit) => {body} | 0 (u : Unit) => {tests})'
    emit(f"def {prefix}StepEncode : {step} -> Value := fun (step : {step}) =>\n  match step as self in {step} return Value with\n" + "\n".join(reversed(encoded)))
    emit(f'def {prefix}StepDecode : Value -> Result {step} := fun (j : Value) => resultBind Bytes {step} (jsonField Bytes j b"step" jsonGetString) (fun (tag : Bytes) => {tests})')
    members = "jsonObjectNil"
    for key, typ, enc, dec, default in reversed(fields):
        wire, get = lower(camel(key)), sf + camel(key)
        if typ.startswith("Option "):
            members = f'jsonOptionalMember {typ[7:]} b"{wire}" ({enc}) ({get} s) ({members})'
        else:
            members = f'jsonObjectCons b"{wire}" ({enc} ({get} s)) ({members})'
    emit(f'def {prefix}StateEncode : {state} -> Value := fun (s : {state}) => jsonObject (jsonObjectCons b"step" ({prefix}StepEncode ({sf}ReconcileStep s)) ({members}))')
    body = f"ok {state} ({sf}Make step " + " ".join(f"f{i}" for i in range(len(fields))) + ")"
    for i, (key, typ, enc, dec, default) in reversed(list(enumerate(fields))):
        wire = lower(camel(key))
        if typ.startswith("Option "):
            read = f'jsonOptionalField {typ[7:]} j b"{wire}" ({dec})'
        else:
            read = f'resultMap (Option {typ}) {typ} (optionValue {typ} ({default})) (jsonOptionalField {typ} j b"{wire}" ({dec}))'
        body = f"resultBind ({typ}) {state} ({read}) (fun (f{i} : {typ}) => {body})"
    body = f'resultBind {step} {state} (jsonField {step} j b"step" {prefix}StepDecode) (fun (step : {step}) => {body})'
    emit(f'def {prefix}StateDecode : Value -> Result {state} := fun (j : Value) => decodeResourceObject {state} b"{source}_pack.state" b"expected object" (fun (j : Value) => {body}) j')
    emit(f'def {prefix}StateDecodeRender : Value -> Bytes := fun (j : Value) => case ({prefix}StateDecode j) with\n'
         f'  | 0 (e : Error) => bytesAppend b"error: " (errorText e) | 1 (s : {state}) => valueRender ({prefix}StateEncode s)')
    emit(f'def {prefix}Invoke : Value -> Value -> Value -> Result Value := fun (cr : Value) (response : Value) (s : Value) =>\n'
         f'  resultBind DynamicObjectT Value (dynamicObjectTDecode cr) (fun (obj : DynamicObjectT) =>\n'
         f'  resultBind {cr} Value ({lower(cr)}Unmarshal obj) (fun (resource : {cr}) =>\n'
         f'  resultBind (Option Response) Value (jsonOptional Response apiMethodApiResponseDecode response) (fun (resp : Option Response) =>\n'
         f'  resultMap {state} Value (fun (state : {state}) =>\n'
         f'    let next : {prefix[:1].upper()+prefix[1:]}Output := {prefix}Core resource resp state in\n'
         f'    {obj([("state", f"{prefix}StateEncode next.0"), ("request", "jsonEncodeOption Request apiMethodApiRequestEncode next.1")])}) ({prefix}StateDecode s))))')
    emit(f'def {prefix}InvokeRender : Value -> Value -> Value -> Bytes := fun (cr : Value) (response : Value) (s : Value) =>\n'
         f'  case ({prefix}Invoke cr response s) with | 0 (e : Error) => bytesAppend b"error: " (errorText e) | 1 (v : Value) => valueRender v')
    emit(f'def {prefix}InitJson : Value := {prefix}StateEncode {prefix}Init')
    exports += [prefix + n for n in ["StateDecodeRender", "InvokeRender", "InitJson"]]
    models.append(f'''def {prefix}ProgramTransition : DynamicObjectT -> Option ResponseView -> Value -> ProgramOutput := fun (obj : DynamicObjectT) (resp : Option ResponseView) (s : Value) =>
  optionFold {cr} ProgramOutput (tuple (s, none RequestView)) (fun (cr : {cr}) =>
  optionFold {state} ProgramOutput (tuple (s, none RequestView)) (fun (state : {state}) =>
    let result : {prefix[:1].upper()+prefix[1:]}Output := {prefix}Core cr (optionBind ResponseView Response resp responseViewKube) state in
    tuple ({prefix}StateEncode result.0, optionMap Request RequestView (fun (req : Request) => kubeRequest req) result.1))
    (resultToOption {state} ({prefix}StateDecode s))) (resultToOption {cr} ({lower(cr)}Unmarshal obj))
def {prefix}ProgramDone : Value -> Bool := fun (s : Value) => optionFold {state} Bool false {prefix}Done (resultToOption {state} ({prefix}StateDecode s))
def {prefix}ProgramFailed : Value -> Bool := fun (s : Value) => optionFold {state} Bool false {prefix}Failed (resultToOption {state} ({prefix}StateDecode s))
def {prefix}Program : ControllerProgram := tuple ({lower(cr)}Kind, {prefix}InitJson, {prefix}ProgramTransition, {prefix}ProgramDone, {prefix}ProgramFailed)''')

(root / "src/packs.kan").write_text("\n\n".join(out) + "\n")
(root / "pack-exports.json").write_text(json.dumps(exports, indent=2) + "\n")
(root / "src/programs.kan").write_text("\n\n".join(models) + "\n")
print("Generated all three complete controller-state wire contracts")
