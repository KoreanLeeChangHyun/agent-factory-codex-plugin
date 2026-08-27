from pathlib import Path


output = Path("../out")
output.mkdir(exist_ok=True)
(output / "fixture.txt").write_bytes(b"agent-factory reproducibility fixture\n")
