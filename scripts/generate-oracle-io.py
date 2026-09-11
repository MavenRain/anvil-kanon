"""Test-only JSON transport for the pinned OCaml API request/response types."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
layout = json.loads((root / "layout-info.json").read_text())
def camel(s):
    return "".join(p[:1].upper() + p[1:] for p in s.split("_"))
def lower(s):
    return s[:1].lower() + s[1:]
out = ['''(* Test transport only. All transitions execute the pinned source library. *)
let key_json (k : Common.object_ref) = Json.obj [
  ("kind", Json.kind_to_json k.kind); ("name", Json.str k.name); ("namespace", Json.str k.namespace)]
let preconditions_json (p : Api_method.preconditions) = Json.obj_opt [
  ("uid", Json.opt (fun x -> Json.int_ (Common.Uid.to_int x)) p.uid);
  ("resourceVersion", Json.opt (fun x -> Json.int_ (Common.Resource_version.to_int x)) p.resource_version)]
let request_json (r : Api_method.api_request) =
  match r with''']
enc = {"CommonKind": "Json.kind_to_json", "CommonObjectRef": "key_json", "Bytes": "Json.str",
       "DynamicObjectT": "Dynamic_object.to_json", "OwnerReferenceT": "Owner_reference.to_json"}
for name, payload in layout["ApiMethodApiRequest"]["variants"]:
    fields = []
    for field, typ in layout[payload]["fields"]:
        value = f"Json.opt preconditions_json x.{field}" if typ.startswith("Option") else f"Some ({enc[typ]} x.{field})"
        fields.append(f'("{lower(camel(field))}", {value})')
    out.append(f'  | Api_method.{name} x -> Json.obj [("tag", Json.str "{lower(camel(name))}"); ("value", Json.obj_opt [' + '; '.join(fields) + '])]')
out.append('let error_decode j =\n  let open Res in\n  let* tag = Json.to_str j in\n  match tag with')
for name, _ in layout["ApiMethodApiError"]["variants"]:
    out.append(f'  | "{lower(camel(name))}" -> ok Api_method.{name}')
out.append('  | _ -> error (Err.Decode_error { typ = "api error"; detail = tag })')
out.append('''let result_decode decode j =
  let open Res in
  let* e = Json.opt_mem j "error" error_decode in
  Option.fold e ~some:(fun e -> ok (Error e)) ~none:(
    let* value = Json.get j "ok" decode in ok (Ok value))
let response_decode j =
  let open Res in
  let* tag = Json.get j "tag" Json.to_str in
  let* value = Json.mem j "value" in
  match tag with''')
for name, payload in layout["ApiMethodApiResponse"]["variants"]:
    inner = layout[payload]["fields"][0][1].split("(")[-1][:-1]
    decode = {"DynamicObjectT": "Dynamic_object.of_json", "ListDynamicObjectT": "Json.to_list Dynamic_object.of_json", "Ghost": '(fun j -> Res.map (fun _ -> ()) (Json.to_assoc j))'}[inner]
    # The source Json module does not expose to_assoc; unit payload uses its
    # singleton transport encoding, whose value is not consumed by controllers.
    if inner == "Ghost":
        decode = '(fun _ -> Res.ok ())'
    ty = lower(name)
    out.append(f'  | "{lower(camel(name))}" ->\n      let* res = Json.get value "res" (result_decode ({decode})) in\n      ok (Api_method.{name} ({{ res }} : Api_method.{ty}))')
out.append('  | _ -> error (Err.Decode_error { typ = "api response"; detail = tag })')
out.append('''let key_decode j =
  let open Res in
  let* kind = Json.get j "kind" Json.kind_of_json in
  let* name = Json.get j "name" Json.to_str in
  let* namespace = Json.get j "namespace" Json.to_str in
  ok ({ kind; name; namespace } : Common.object_ref)
let preconditions_decode j =
  let open Res in
  let* uid = Json.opt_mem j "uid" (fun v -> Res.map Common.Uid.of_int (Json.to_int v)) in
  let* resource_version = Json.opt_mem j "resourceVersion" (fun v -> Res.map Common.Resource_version.of_int (Json.to_int v)) in
  ok ({ uid; resource_version } : Api_method.preconditions)
let request_decode j =
  let open Res in
  let* tag = Json.get j "tag" Json.to_str in
  let* value = Json.mem j "value" in
  match tag with''')
dec = {"CommonKind": "Json.kind_of_json", "CommonObjectRef": "key_decode", "Bytes": "Json.to_str",
       "DynamicObjectT": "Dynamic_object.of_json", "OwnerReferenceT": "Owner_reference.of_json"}
for name, payload in layout["ApiMethodApiRequest"]["variants"]:
    out.append(f'  | "{lower(camel(name))}" ->')
    fields = []
    for field, typ in layout[payload]["fields"]:
        wire = lower(camel(field))
        read = f'Json.opt_mem value "{wire}" preconditions_decode' if typ.startswith("Option") else f'Json.get value "{wire}" {dec[typ]}'
        out.append(f'      let* {field} = {read} in')
        fields.append(field)
    out.append(f'      ok (Api_method.{name} ({{ ' + '; '.join(fields) + f' }} : Api_method.{lower(name)}))')
out.append('  | _ -> error (Err.Decode_error { typ = "api request"; detail = tag })')
out.append('let error_json (e : Api_method.api_error) = match e with')
for name, _ in layout["ApiMethodApiError"]["variants"]:
    out.append(f'  | Api_method.{name} -> Json.str "{lower(camel(name))}"')
out.append('''let result_json encode r = Result.fold r
  ~error:(fun e -> Json.obj [("error", error_json e)])
  ~ok:(fun x -> Json.obj [("ok", encode x)])
let response_json r = match r with''')
for name, payload in layout["ApiMethodApiResponse"]["variants"]:
    inner = layout[payload]["fields"][0][1].split("(")[-1][:-1]
    encode = {"DynamicObjectT": "Dynamic_object.to_json", "ListDynamicObjectT": "Json.list Dynamic_object.to_json", "Ghost": '(fun () -> Json.obj [])'}[inner]
    out.append(f'  | Api_method.{name} x -> Json.obj [("tag", Json.str "{lower(camel(name))}"); ("value", Json.obj [("res", result_json ({encode}) x.res)])]')
(root / "oracle/io_json.ml").write_text("\n".join(out) + "\n")
print("Generated the OCaml test transport")
