"""Replay the HEB-160 direct-action population against retained upstream manifests.

Usage: python docs/evidence/heb-160/verify_population.py BASE TREE
Run from a Git checkout. Uses Git blobs only, never untracked working-tree data.
Upstream freshness is a separate network read; this replays retained evidence.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[3]
SURFACES = (".github/workflows", "plugins/bedrock/skills", "tests/fixtures/safety")
LOCI = {
    "plugins/bedrock/skills/infrastructure-code/reference/05-delivery-pipeline.md": (
        "hashicorp/setup-terraform", "b9cd54a3c349d3f38e8881555d616ced269862dd",
        "dfe3c3f87815947d99a8997f908cb6525fc44e9e",
    ),
    "tests/fixtures/safety/pr-image-build.yml": (
        "actions/checkout", "11d5960a326750d5838078e36cf38b85af677262",
        "fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09",
    ),
}


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True)


def population(revision, extractor):
    files = git("ls-tree", "-r", "--name-only", revision, "--", *SURFACES).splitlines()
    rows = []
    selected = []
    for name in files:
        if Path(name).suffix not in {".md", ".yaml", ".yml"}:
            continue
        selected.append(name)
        text = git("show", f"{revision}:{name}")
        errors = []
        references = extractor(text, name, errors)
        assert not errors, errors
        for action, commit in references:
            if action.startswith(("./", "docker://")):
                continue
            assert re.fullmatch(r"[0-9a-fA-F]{40}", commit), (name, action, commit)
            rows.append({"path": name, "repository": action.lower(), "commit": commit.lower()})
    assert rows, "empty action population"
    return selected, rows


def main():
    baseline, candidate = sys.argv[1:]
    upstream = json.loads((Path(__file__).parent / "upstream.json").read_text())
    manifests = {}
    for row in upstream["manifests"]:
        manifest = row["manifest"]
        assert hashlib.sha256(manifest.encode()).hexdigest() == row["sha256"]
        parsed = yaml.safe_load(manifest)["runs"]["using"]
        literal = re.search(r"^runs:\s*\n\s+using:\s*['\"]?(node\d+)", manifest, re.M).group(1)
        assert parsed == literal == row["runtime"]
        manifests[(row["repository"], row["commit"])] = parsed
    # Use the candidate validator's parser for both trees, so the same supported
    # YAML grammar defines the before/after comparison (without importing files
    # or copying working-tree content).
    namespace = {"__name__": "heb160_population_parser"}
    exec(compile(git("show", f"{candidate}:scripts/validate_safety.py"),
                 f"{candidate}:scripts/validate_safety.py", "exec"), namespace)
    extractor = namespace["action_references"]
    before_files, before = population(baseline, extractor)
    after_files, after = population(candidate, extractor)
    expected_old = sorted((path, repo, old) for path, (repo, old, new) in LOCI.items())
    observed_old = sorted((r["path"], r["repository"], r["commit"]) for r in before
                          if manifests[(r["repository"], r["commit"])] == "node20")
    assert expected_old == observed_old, ("changed Node 20 population", observed_old)
    expected_after = []
    for row in before:
        updated = dict(row)
        if row["path"] in LOCI:
            repo, old, new = LOCI[row["path"]]
            assert (row["repository"], row["commit"]) == (repo, old)
            updated["commit"] = new
        expected_after.append(updated)
    assert before_files == after_files
    assert expected_after == after, "candidate population differs from settled substitutions"
    for row in after:
        assert manifests[(row["repository"], row["commit"])] == "node24", row
    for path, (repo, old, new) in LOCI.items():
        assert manifests[(repo, new)] == "node24"
        assert manifests[(repo, old)] != "node24", "known-old control failed to refuse"
    print(json.dumps({
        "baseline": baseline, "candidate_tree": candidate,
        "surface_roots": SURFACES, "selected_files": before_files,
        "before": before, "after": after,
        "before_members": sorted({r["repository"]+"@"+r["commit"] for r in before}),
        "after_members": sorted({r["repository"]+"@"+r["commit"] for r in after}),
        "runtime_control": "YAML runs.using equals anchored textual declaration; known-old specimens refused",
        "result": "confirmed",
        "limits": "Direct references in validator-selected Markdown/YAML surfaces only; no transitive actions, historical evidence, SOFIA, hosted execution, or production reachability claim."
    }, indent=2))


if __name__ == "__main__":
    main()
