"""Generate field codecs for record views, retaining explicit decoder errors.

Resource marshalling, API responses, and reconcile-state pack codecs are separate
contracts. They are intentionally not inferred from record layout.
"""
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parent.parent
layout = json.loads((root / "layout-info.json").read_text())
out = ["-- Generated field-view codecs. Resource marshalling is separate."]
emitted = set()
exports = []
variants = ["jsonNull", "jsonBool x", "jsonInt x", "jsonIntLiteral x", "jsonFloat x",
            "jsonString x", "jsonArray x", "jsonObject x", "jsonArrayNil",
            "jsonArrayCons h t", "jsonObjectNil", "jsonObjectCons k v t"]

def lower(s):
    return s[:1].lower() + s[1:]

def camel(s):
    return "".join(p[:1].upper() + p[1:] for p in s.split("_") if p)

def wire_key(key):
    return "downwardAPI" if key == "downward_api" else lower(camel(key))

def emit(s):
    out.append(s)

def codec(typ):
    if typ.startswith("Either ("):
        a, b = re.fullmatch(r"Either \((\w+)\) \((\w+)\)", typ).groups()
        ae, ad = codec(a)
        be, bd = codec(b)
        return f"jsonEncodeEither {a} {b} ({ae}) ({be})", f"jsonDecodeEither {a} {b} ({ad}) ({bd})"
    if typ.startswith("Option ("):
        inner = typ[8:-1]
        encode, decode = codec(inner)
        return f"jsonEncodeOption ({inner}) ({encode})", f"jsonOptional ({inner}) ({decode})"
    prims = {"Bytes": ("jsonEncodeBytes", "jsonGetString"), "Int": ("jsonEncodeInt", "jsonGetInt"),
             "Bool": ("jsonEncodeBool", "jsonGetBool"), "Ghost": ("jsonEncodeGhost", "jsonDecodeGhost"),
             "Value": ("jsonEncodeValue", "jsonDecodeValue"), "StringMap": ("jsonEncodeMap", "jsonDecodeMap")}
    if typ in prims:
        return prims[typ]
    f = lower(typ)
    encode, decode = f + "Encode", f + "Decode"
    if typ in emitted:
        return encode, decode
    emitted.add(typ)
    info = layout[typ]
    if info["kind"] == "alias":
        enc, dec = codec(info["type"])
        emit(f"def {encode} : {typ} -> Value := fun (x : {typ}) => {enc} x")
        ghosts = {"AffinityT": "Affinity", "PodSecurityContextT": "PodSecurityContext",
                  "LocalObjectReferenceT": "LocalObjectReference", "TolerationT": "Toleration",
                  "ContainerSecurityContext": "SecurityContext", "PersistentVolumeClaimStatus": "PersistentVolumeClaimStatus"}
        if typ in ghosts:
            emit(f"def {decode} : Value -> Result {typ} := fun (j : Value) =>\n"
                 f'  case (jsonGetObject j) with | 1 (m : Members) => ok {typ} ghost\n'
                 f'  | 0 (e : Error) => err {typ} (decodeError b"{ghosts[typ]}" b"expected an object")')
        else:
            emit(f"def {decode} : Value -> Result {typ} := fun (j : Value) => {dec} j")
    elif info["kind"] == "list":
        item = info["element"]
        enc, dec = codec(item)
        emit(f"def rec {f}EncodeItems : {typ} -> Values := fun (xs : {typ}) =>\n"
             f"  match xs as self in {typ} return Values with\n"
             f"  | {f}Nil => jsonArrayNil\n"
             f"  | {f}Cons h t => jsonArrayCons ({enc} h) ({f}EncodeItems t)")
        emit(f"def {encode} : {typ} -> Value := fun (xs : {typ}) => jsonArray ({f}EncodeItems xs)")
        emit(f"def rec {f}DecodeItems : Values -> Result {typ} := fun (xs : Values) =>\n"
             f"  match xs as self in JsonTree sort return Result {typ} with\n" + "\n".join(
                 "  | " + v + " => " + (f"ok {typ} {f}Nil" if v == "jsonArrayNil" else
                 f"resultBind ({item}) {typ} ({dec} h) (fun (value : {item}) => resultMap {typ} {typ} (fun (tail : {typ}) => {f}Cons value tail) ({f}DecodeItems t))"
                 if v.startswith("jsonArrayCons") else f'err {typ} (decodeError b"list" b"expected a JSON array")')
                 for v in variants))
        emit(f"def {decode} : Value -> Result {typ} := fun (j : Value) => resultBind Values {typ} (jsonGetArray j) {f}DecodeItems")
    elif info["kind"] == "record":
        fields = info["fields"]
        # Decode order follows source field order, preserving the first error.
        for _, t in fields:
            codec(t)
        members = "jsonObjectNil"
        for key, t in reversed(fields):
            getter = f + camel(key)
            wire = wire_key(key)
            if t.startswith("Option ("):
                inner = t[8:-1]
                enc, _ = codec(inner)
                members = f'jsonOptionalMember ({inner}) b"{wire}" ({enc}) ({getter} x) ({members})'
            else:
                enc, _ = codec(t)
                members = f'jsonObjectCons b"{wire}" ({enc} ({getter} x)) ({members})'
        emit(f"def {encode} : {typ} -> Value := fun (x : {typ}) => jsonObject ({members})")
        body = f"ok {typ} ({f}Make " + " ".join("field" + str(i) for i in range(len(fields))) + ")"
        for i, (key, t) in reversed(list(enumerate(fields))):
            wire = wire_key(key)
            if t.startswith("Option ("):
                inner = t[8:-1]
                _, dec = codec(inner)
                read = f'jsonOptionalField ({inner}) j b"{wire}" ({dec})'
            else:
                _, dec = codec(t)
                read = f'jsonField ({t}) j b"{wire}" ({dec})'
                # pod_spec.ml:100-104 deliberately defaults absent/null
                # containers to [], despite its non-optional record field.
                if typ == "PodSpecT" and key == "containers":
                    read = f'resultMap (Option {t}) {t} (fun (o : Option {t}) => optionFold {t} {t} {lower(t)}Nil (fun (x : {t}) => x) o) (jsonOptionalField {t} j b"containers" ({dec}))'
            body = f"resultBind ({t}) {typ} ({read}) (fun (field{i} : {t}) => {body})"
        emit(f"def {decode} : Value -> Result {typ} := fun (j : Value) => {body}")
    elif typ == "CommonKind":
        branches = []
        tests = 'err CommonKind (decodeError b"kind" (bytesAppend b"unknown kind tag: " tag))'
        for name, payload in reversed(info["variants"]):
            ctor = f + camel(name)
            if payload is None:
                text = camel(name)
                tests = f'(case (bytesEqual tag b"{text}") with | 1 (u : Unit) => ok CommonKind {ctor} | 0 (u : Unit) => {tests})'
            branches.append(f"  | {ctor}" + ("" if payload is None else " s") + " => " +
                            (f'jsonString b"{camel(name)}"' if payload is None else
                             'jsonObject (jsonObjectCons b"customResource" (jsonString s) jsonObjectNil)'))
        emit(f"def {encode} : CommonKind -> Value := fun (k : CommonKind) =>\n"
             "  match k as self in CommonKind return Value with\n" + "\n".join(reversed(branches)))
        emit(f"def kindDecodeTag : Bytes -> Result CommonKind := fun (tag : Bytes) => {tests}")
        # Exact one-member custom-resource object, as the OCaml decoder.
        emit("def kindDecodeMember : Members -> Result CommonKind := fun (m : Members) =>\n"
             "  match m as self in JsonTree sort return Result CommonKind with\n" + "\n".join(
             "  | " + v + " => " + ('(case (boolAnd (bytesEqual k b"customResource") (jsonTreeEmpty objectSort t)) with '
             '| 0 (u : Unit) => err CommonKind (decodeError b"kind" b"unrecognized kind encoding") '
             '| 1 (u : Unit) => (case (jsonGetString v) with | 1 (s : Bytes) => ok CommonKind (commonKindCustomResource s) '
             '| 0 (e : Error) => err CommonKind (decodeError b"kind" b"unrecognized kind encoding")))'
             if v.startswith("jsonObjectCons") else 'err CommonKind (decodeError b"kind" b"unrecognized kind encoding")') for v in variants))
        emit(f"def {decode} : Value -> Result CommonKind := fun (j : Value) =>\n"
             "  match j as self in JsonTree sort return Result CommonKind with\n" + "\n".join(
             "  | " + v + " => " + ("kindDecodeTag x" if v == "jsonString x" else "kindDecodeMember x"
             if v == "jsonObject x" else 'err CommonKind (decodeError b"kind" b"unrecognized kind encoding")') for v in variants))
    elif typ == "DeploymentStrategyStrategyType":
        emit(f"def {encode} : {typ} -> Value := fun (x : {typ}) =>\n"
             f"  match x as self in {typ} return Value with\n"
             f'  | {f}Recreate => jsonString b"Recreate"\n'
             f'  | {f}RollingUpdate => jsonString b"RollingUpdate"')
        emit(f"def {decode} : Value -> Result {typ} := fun (j : Value) =>\n"
             f"  resultBind Bytes {typ} (jsonGetString j) (fun (tag : Bytes) =>\n"
             f'    case (bytesEqual tag b"Recreate") with | 1 (u : Unit) => ok {typ} {f}Recreate\n'
             f'    | 0 (u : Unit) => (case (bytesEqual tag b"RollingUpdate") with | 1 (u : Unit) => ok {typ} {f}RollingUpdate\n'
             f'      | 0 (u : Unit) => err {typ} (decodeError b"deployment_strategy.type" tag)))')
    elif info["kind"] == "enum" and typ.startswith("ApiMethod"):
        branches = []
        tests = f'err {typ} (decodeError b"{typ}" tag)'
        for name, payload in reversed(info["variants"]):
            ctor = f + camel(name)
            tag = lower(camel(name))
            if payload:
                enc, dec = codec(payload)
                val = f'resultMap {payload} {typ} (fun (x : {payload}) => {ctor} x) (jsonField {payload} j b"value" ({dec}))'
                encoded = f'jsonObject (jsonObjectCons b"tag" (jsonString b"{tag}") (jsonObjectCons b"value" ({enc} x) jsonObjectNil))'
            else:
                val = f'ok {typ} {ctor}'
                encoded = f'jsonString b"{tag}"'
            tests = f'(case (bytesEqual tag b"{tag}") with | 1 (u : Unit) => {val} | 0 (u : Unit) => {tests})'
            branches.append(f'  | {ctor}' + (' x' if payload else '') + f' => {encoded}')
        emit(f'def {encode} : {typ} -> Value := fun (x : {typ}) =>\n  match x as self in {typ} return Value with\n' + '\n'.join(reversed(branches)))
        read = 'jsonField Bytes j b"tag" jsonGetString' if any(p for _, p in info['variants']) else 'jsonGetString j'
        emit(f'def {decode} : Value -> Result {typ} := fun (j : Value) => resultBind Bytes {typ} ({read}) (fun (tag : Bytes) => {tests})')
    else:
        raise ValueError(f"No inferred codec contract for {typ}")
    # Stable observable boundary for differential field-codec testing.
    emit(f"def {f}DecodeRender : Value -> Bytes := fun (j : Value) =>\n"
         f"  case ({decode} j) with | 0 (e : Error) => bytesAppend b\"error: \" (errorText e)\n"
         f"  | 1 (x : {typ}) => valueRender ({encode} x)")
    exports.append(f + "DecodeRender")
    return encode, decode

# Nested field views and custom-resource spec records. Resource marshal methods
# have their own kind, status, and null contracts and are not generated here.
for typ, info in layout.items():
    source = info.get("source", "")
    if info["kind"] == "record" and ("k8s_objects/" in source and
       "api_method.ml" not in source and "views/" not in source or typ in
       {"StatefulSetOrdinals", "StatefulSetRollingUpdate", "StatefulSetUpdateStrategy",
        "StatefulSetRetentionPolicy", "StatefulSetSsSpec", "StatefulSetSsStatus",
        "VreplicaSetVrsSpec", "VreplicaSetVrsStatus", "VDeploymentVdSpec"}):
        codec(typ)
codec("ApiMethodApiRequest")
codec("ApiMethodApiResponse")
(root / "src/codecs.kan").write_text("\n\n".join(out) + "\n")
(root / "codec-exports.json").write_text(json.dumps(exports, indent=2) + "\n")
print(f"Generated {len(emitted)} field codec pairs")
