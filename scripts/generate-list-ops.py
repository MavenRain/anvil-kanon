"""Concrete collection operations used by controller and cluster code."""
import json
from pathlib import Path
root = Path(__file__).resolve().parent.parent
layout = json.loads((root / "layout-info.json").read_text())
out = ["-- Generated structural list operations."]
for typ, info in layout.items():
    if info["kind"] != "list":
        continue
    a = info["element"]
    f = typ[:1].lower() + typ[1:]
    out.extend([
        f"def rec {f}ReverseOnto : {typ} -> {typ} -> {typ} := fun (xs : {typ}) (acc : {typ}) =>\n"
        f"  match xs as self in {typ} return {typ} with | {f}Nil => acc | {f}Cons h t => {f}ReverseOnto t ({f}Cons h acc)",
        f"def {f}Reverse : {typ} -> {typ} := fun (xs : {typ}) => {f}ReverseOnto xs {f}Nil",
        f"def {f}Append : {typ} -> {typ} -> {typ} := fun (xs : {typ}) (ys : {typ}) => {f}ReverseOnto ({f}Reverse xs) ys",
        f"def rec {f}Fold : (0 B : Type 0) -> {typ} -> B -> (B -> {a} -> B) -> B :=\n"
        f"  fun (0 B : Type 0) (xs : {typ}) (acc : B) (step : B -> {a} -> B) =>\n"
        f"  match xs as self in {typ} return B with | {f}Nil => acc | {f}Cons h t => {f}Fold B t (step acc h) step",
        f"def rec {f}Find : {typ} -> ({a} -> Bool) -> Option ({a}) := fun (xs : {typ}) (p : {a} -> Bool) =>\n"
        f"  match xs as self in {typ} return Option ({a}) with | {f}Nil => none ({a})\n"
        f"  | {f}Cons h t => (case (p h) with | 1 (u : Unit) => some ({a}) h | 0 (u : Unit) => {f}Find t p)",
        f"def {f}Every : {typ} -> ({a} -> Bool) -> Bool := fun (xs : {typ}) (p : {a} -> Bool) =>\n"
        f"  boolNot (optionIsSome ({a}) ({f}Find xs (fun (x : {a}) => boolNot (p x))))",
        f"def {f}Filter : {typ} -> ({a} -> Bool) -> {typ} := fun (xs : {typ}) (p : {a} -> Bool) =>\n"
        f"  {f}Reverse ({f}Fold {typ} xs {f}Nil (fun (acc : {typ}) (h : {a}) => select {typ} (p h) ({f}Cons h acc) acc))",
        f"def {f}Map : {typ} -> ({a} -> {a}) -> {typ} := fun (xs : {typ}) (g : {a} -> {a}) =>\n"
        f"  {f}Reverse ({f}Fold {typ} xs {f}Nil (fun (acc : {typ}) (h : {a}) => {f}Cons (g h) acc))",
    ])
(root / "src/list_ops.kan").write_text("\n\n".join(out) + "\n")
