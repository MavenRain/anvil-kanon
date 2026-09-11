"""Generate exhaustive JSON eliminators for the indexed tree representation."""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
variants = ["jsonNull", "jsonBool x", "jsonInt x", "jsonIntLiteral x", "jsonFloat x",
            "jsonString x", "jsonArray x", "jsonObject x", "jsonArrayNil",
            "jsonArrayCons h t", "jsonObjectNil", "jsonObjectCons k v t"]
out = ["-- Generated exhaustive JSON eliminators. Source: k8s_objects/json.ml."]
for fn, typ, tag, label, detail in [
    ("jsonGetInt", "Int", "jsonInt", "int", "expected a JSON integer"),
    ("jsonGetBool", "Bool", "jsonBool", "bool", "expected a JSON boolean"),
    ("jsonGetArray", "Values", "jsonArray", "list", "expected a JSON array"),
    ("jsonGetObject", "Members", "jsonObject", "object", "expected a JSON object"),
]:
    out.append(f"def {fn} : Value -> Result {typ} := fun (j : Value) =>\n"
               f"  match j as self in JsonTree sort return Result {typ} with\n" + "\n".join(
                   "  | " + v + " => " + (f"ok {typ} x" if v.split()[0] == tag else
                   f'err {typ} (decodeError b"{label}" b"{detail}")') for v in variants))
out.append("def jsonIsNull : Value -> Bool := fun (j : Value) =>\n"
           "  match j as self in JsonTree sort return Bool with\n" + "\n".join(
               "  | " + v + " => " + ("true" if v == "jsonNull" else "false") for v in variants))
out.append("def rec jsonMemberOption : Members -> Bytes -> Option Value := fun (members : Members) (key : Bytes) =>\n"
           "  match members as self in JsonTree sort return Option Value with\n" + "\n".join(
               "  | " + v + " => " + ("(case (bytesEqual key k) with | 1 (u : Unit) => some Value v | 0 (u : Unit) => jsonMemberOption t key)"
               if v.startswith("jsonObjectCons") else "none Value") for v in variants))
(root / "src/json.kan").write_text("\n\n".join(out) + "\n")
