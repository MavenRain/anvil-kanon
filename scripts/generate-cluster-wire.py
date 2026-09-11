"""Explicit JSON fixtures for cluster states and transition labels."""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
out = ["-- Cluster transport. Functions and installed models remain configuration data."]
codecs = {
    "Bytes": ("jsonEncodeBytes", "jsonGetString"), "Int": ("jsonEncodeInt", "jsonGetInt"),
    "Bool": ("jsonEncodeBool", "jsonGetBool"), "Value": ("jsonEncodeValue", "jsonDecodeValue"),
    "CommonObjectRef": ("commonObjectRefEncode", "commonObjectRefDecode"),
    "Request": ("apiMethodApiRequestEncode", "apiMethodApiRequestDecode"),
    "Response": ("apiMethodApiResponseEncode", "apiMethodApiResponseDecode"),
    "ApiError": ("apiMethodApiErrorEncode", "apiMethodApiErrorDecode"),
    "DynamicObjectT": ("dynamicObjectTEncode", "dynamicObjectTDecode"),
    "PodT": ("podTResourceEncode", "podTResourceDecode"),
    "ListPodT": ("listPodTResourceEncode", "listPodTResourceDecode"),
    "ResourceStore": ("resourceStoreWireEncode", "resourceStoreDecode"),
    "ApiState": ("apiStateEncode", "apiStateDecode")}
out.append("def resourceStoreWireEncode : ResourceStore -> Value := fun (s : ResourceStore) => jsonArray (resourceStoreEncodeItems s)")

def low(s):
    return s[0].lower() + s[1:]

def obj(fields):
    tail = "jsonObjectNil"
    for key, value in reversed(fields):
        tail = f'jsonObjectCons b"{key}" ({value}) ({tail})'
    return f"jsonObject ({tail})"

def codec(typ):
    if typ.startswith("Option "):
        inner = typ[7:]
        enc, dec = codec(inner)
        return f"jsonEncodeOption {inner} ({enc})", f"jsonOptional {inner} ({dec})"
    return codecs[typ]

def record(typ, fields, make="tuple"):
    f = low(typ) + "Wire"
    codecs[typ] = f + "Encode", f + "Decode"
    encoded = [(name, f"{codec(t)[0]} x.{i}") for i, (name, t) in enumerate(fields)]
    out.append(f"def {f}Encode : {typ} -> Value := fun (x : {typ}) => " + obj(encoded))
    body = "tuple (" + ", ".join(f"f{i}" for i in range(len(fields))) + ")"
    body = f"ok {typ} ({body})"
    for i, (name, t) in reversed(list(enumerate(fields))):
        body = f'resultBind ({t}) {typ} (jsonField ({t}) j b"{name}" ({codec(t)[1]})) (fun (f{i} : {t}) => {body})'
    out.append(f"def {f}Decode : Value -> Result {typ} := fun (j : Value) => {body}")

def enum(typ, variants):
    f = low(typ) + "Wire"
    codecs[typ] = f + "Encode", f + "Decode"
    branches = []
    tests = f'err {typ} (decodeError b"{typ}" tag)'
    for ctor, tag, fields in reversed(variants):
        members = [("tag", f'jsonString b"{tag}"')]
        members += [(name, f"{codec(t)[0]} f{i}") for i, (name, t) in enumerate(fields)]
        args = " ".join(f"f{i}" for i in range(len(fields)))
        branches.append(f"  | {ctor} {args} => {obj(members)}")
        body = f"ok {typ} ({ctor} {args})"
        for i, (name, t) in reversed(list(enumerate(fields))):
            body = f'resultBind ({t}) {typ} (jsonField ({t}) j b"{name}" ({codec(t)[1]})) (fun (f{i} : {t}) => {body})'
        tests = f'(case (bytesEqual tag b"{tag}") with | 1 (u : Unit) => {body} | 0 (u : Unit) => {tests})'
    out.append(f"def {f}Encode : {typ} -> Value := fun (x : {typ}) =>\n  match x as self in {typ} return Value with\n" + "\n".join(reversed(branches)))
    out.append(f'def {f}Decode : Value -> Result {typ} := fun (j : Value) => resultBind Bytes {typ} (jsonField Bytes j b"tag" jsonGetString) (fun (tag : Bytes) => {tests})')

def map_wire(typ, key, value):
    f = low(typ)
    codecs[typ] = f + "WireEncode", f + "WireDecode"
    ke, kd = codec(key)
    ve, vd = codec(value)
    entry = obj([("key", f"{ke} k"), ("value", f"{ve} v")])
    out.append(f'def {f}WireEncode : {typ} -> Value := fun (s : {typ}) =>\n  jsonSequenceEncode Value jsonEncodeValue ({f}Fold (Sequence Value) s (sequenceEmpty Value) (fun (k : {key}) (v : {value}) (acc : Sequence Value) => sequencePush Value acc ({entry})))')
    pair = f"prod ({key}, {value})"
    out.append(f'def {f}WireEntryDecode : Value -> Result ({pair}) := fun (j : Value) =>\n  resultBind {key} ({pair}) (jsonField {key} j b"key" ({kd})) (fun (k : {key}) =>\n    resultMap {value} ({pair}) (fun (v : {value}) => tuple (k, v)) (jsonField {value} j b"value" ({vd})))')
    out.append(f'def {f}WireDecode : Value -> Result {typ} := fun (j : Value) =>\n  resultMap (Sequence ({pair})) {typ} (fun (xs : Sequence ({pair})) => sequenceFold ({pair}) {typ} xs {f}Nil (fun (s : {typ}) (p : {pair}) => {f}Set p.0 p.1 s)) (jsonSequenceDecode ({pair}) {f}WireEntryDecode j)')

enum("Host", [("hostApi", "api", []), ("hostBuiltin", "builtin", []),
    ("hostController", "controller", [("id", "Int"), ("key", "CommonObjectRef")]),
    ("hostExternal", "external", [("id", "Int")]), ("hostMonkey", "monkey", [])])
enum("Content", [("contentRequest", "request", [("body", "Request")]),
    ("contentResponse", "response", [("body", "Response")]),
    ("contentExternalRequest", "externalRequest", [("body", "Value")]),
    ("contentExternalResponse", "externalResponse", [("body", "Value")])])
record("Message", [("src", "Host"), ("dst", "Host"), ("rpcId", "Int"), ("content", "Content")])
out += ['''def messagePoolWireEncode : MessagePool -> Value := fun (pool : MessagePool) =>
  jsonSequenceEncode Message messageWireEncode (messagePoolFold (Sequence Message) pool (sequenceEmpty Message) (sequencePush Message))
def messagePoolWireDecode : Value -> Result MessagePool := fun (j : Value) => resultMap (Sequence Message) MessagePool
  (fun (xs : Sequence Message) => sequenceFold Message MessagePool (sequenceReverse Message xs) messagePoolNil (fun (acc : MessagePool) (m : Message) => messagePoolCons m acc))
  (jsonSequenceDecode Message messageWireDecode j)''']
codecs["MessagePool"] = "messagePoolWireEncode", "messagePoolWireDecode"
record("Ongoing", [("triggeringCr", "DynamicObjectT"), ("pendingReqMsg", "Option Message"), ("localState", "Value"), ("reconcileId", "Int")])
map_wire("OngoingMap", "CommonObjectRef", "Ongoing")
record("ControllerState", [("ongoing", "OngoingMap"), ("scheduled", "ResourceStore"), ("reconcileIdAllocator", "Int")])
out.append('''def ExternalState : Type 0 := Value
def externalStateWireEncode : ExternalState -> Value := fun (s : ExternalState) => jsonObject (jsonObjectCons b"state" s jsonObjectNil)
def externalStateWireDecode : Value -> Result ExternalState := fun (j : Value) => jsonMember j b"state"''')
codecs["ExternalState"] = "externalStateWireEncode", "externalStateWireDecode"
record("Actor", [("controller", "ControllerState"), ("external", "Option ExternalState"), ("crashEnabled", "Bool")])
map_wire("ActorMap", "Int", "Actor")
record("ClusterState", [("apiServer", "ApiState"), ("controllers", "ActorMap"), ("network", "MessagePool"), ("rpcIdAllocator", "Int"), ("reqDropEnabled", "Bool"), ("podMonkeyEnabled", "Bool")])
record("Bound", [("maxInFlight", "Int"), ("maxObjectsPerKind", "Int"), ("maxControllers", "Int"), ("uidCeiling", "Int"), ("rvCeiling", "Int"), ("reconcileCeiling", "Int"), ("maxReconcileDepth", "Int"), ("monkeyForge", "ListPodT")])
enum("ClusterStep", [("stepApi", "api", [("recv", "Option Message")]), ("stepBuiltin", "builtin", [("key", "CommonObjectRef")]),
    ("stepController", "controller", [("id", "Int"), ("recv", "Option Message"), ("key", "Option CommonObjectRef")]),
    ("stepSchedule", "schedule", [("id", "Int"), ("key", "CommonObjectRef")]), ("stepRestart", "restart", [("id", "Int")]),
    ("stepDisableCrash", "disableCrash", [("id", "Int")]), ("stepDrop", "drop", [("msg", "Message"), ("error", "ApiError")]),
    ("stepDisableDrop", "disableDrop", []), ("stepMonkey", "monkey", [("pod", "PodT")]), ("stepDisableMonkey", "disableMonkey", []),
    ("stepExternal", "external", [("id", "Int"), ("recv", "Option Message")]), ("stepStutter", "stutter", [])])
out.append('''def rec successorsWireItems : Successors -> Values := fun (xs : Successors) => match xs as self in Successors return Values with
  | successorsNil => jsonArrayNil
  | successorsCons step state tail => jsonArrayCons (jsonObject (jsonObjectCons b"step" (clusterStepWireEncode step)
      (jsonObjectCons b"state" (clusterStateWireEncode state) jsonObjectNil))) (successorsWireItems tail)
def successorsWireEncode : Successors -> Value := fun (xs : Successors) => jsonArray (successorsWireItems xs)
def fixtureModels : ModelMap := modelMapCons (nonnegative 0) (tuple (vrsProgram, none ExternalProgram))
  (modelMapCons (nonnegative 1) (tuple (deploymentProgram, none ExternalProgram)) (modelMapCons (nonnegative 2) (tuple (statefulProgram, none ExternalProgram)) modelMapNil))
def fixtureModelsFor : Bool -> ModelMap := fun (echo : Bool) =>
  let external : ExternalProgram := tuple (jsonNull, (fun (request : Value) (state : Value) (resources : ResourceStore) => tuple (request, state))) in
  select ModelMap echo (modelMapSet (nonnegative 2) (tuple (statefulProgram, some ExternalProgram external)) fixtureModels) fixtureModels
def clusterFixtureInvoke : Value -> Result Value := fun (input : Value) =>
  resultBind InstalledTypes Value (jsonField InstalledTypes input b"policy" apiFixturePolicy) (fun (policy : InstalledTypes) =>
  resultBind ClusterState Value (jsonField ClusterState input b"state" clusterStateWireDecode) (fun (s : ClusterState) =>
  resultBind Bool Value (jsonField Bool input b"echoExternal" jsonGetBool) (fun (echo : Bool) =>
  resultMap Bound Value (fun (bound : Bound) => successorsWireEncode (clusterEnabledSuccessors bound (tuple (policy, fixtureModelsFor echo)) s))
    (jsonField Bound input b"bound" boundWireDecode))))
def clusterFixtureRender : Value -> Bytes := fun (input : Value) => case (clusterFixtureInvoke input) with
  | 0 (e : Error) => bytesAppend b"error: " (errorText e) | 1 (v : Value) => valueRender v''')
(root / "src/cluster_wire.kan").write_text("\n\n".join(out) + "\n")
print("Generated cluster-state and transition-label JSON fixtures")
