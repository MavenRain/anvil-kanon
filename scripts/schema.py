"""Extract record layouts for review. Behaviour is ported separately."""
import json
from pathlib import Path
import re
import sys

source = Path(sys.argv[1]).resolve()
records = []
declarations = []
for directory in (source / "lib/k8s_objects", source / "lib/controllers"):
    for path in sorted(directory.rglob("*.ml")):
        text = re.sub(r"\(\*.*?\*\)", "", path.read_text(), flags=re.S)
        for declaration in re.finditer(r"^type (\w+) =\s*(.*?)(?=^type |^let |^module |^include |\Z)", text, re.M | re.S):
            declarations.append({"source": str(path.relative_to(source)),
                                 "module": path.stem, "type": declaration[1],
                                 "body": " ".join(declaration[2].split())})
        for match in re.finditer(r"^type (\w+) = \{([^{}]*)\}", text, re.M):
            fields = []
            for field in match[2].split(";"):
                if field.strip():
                    name, typ = field.split(":", 1)
                    fields.append({"name": name.strip(), "ocaml_type": " ".join(typ.split())})
            records.append({"source": str(path.relative_to(source)),
                            "module": path.stem, "type": match[1], "fields": fields})
output = Path(__file__).resolve().parent.parent / "record-layouts.json"
output.write_text(json.dumps(records, indent=2) + "\n")
(output.parent / "model-schema.json").write_text(json.dumps(declarations, indent=2) + "\n")
print(f"Extracted {len(records)} layouts; {sum(len(r['fields']) for r in records)} fields")
