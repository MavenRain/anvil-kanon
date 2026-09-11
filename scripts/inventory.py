"""Record the exact source baseline without copying the source repository."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

source = Path(sys.argv[1]).resolve()
output = Path(__file__).resolve().parent.parent / "port-inventory.json"
files = sorted(p for parent in ("lib", "bin", "test")
               for p in (source / parent).rglob("*")
               if p.suffix in (".ml", ".mli"))
rows = [{"path": str(p.relative_to(source)),
         "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
         "lines": len(p.read_text().splitlines()),
         "status": "pending"} for p in files]
revision = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                          check=True, capture_output=True, text=True).stdout.strip()
output.write_text(json.dumps({"source": "https://github.com/MavenRain/anvil-ocaml",
                              "revision": revision, "files": rows}, indent=2) + "\n")
print(f"Inventoried {len(rows)} source and test files at {revision}")
