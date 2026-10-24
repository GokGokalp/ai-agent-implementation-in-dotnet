#!/usr/bin/env python3
"""Domain guardrail check for pull requests.

Compares the code change of a PR with the OpenSpec specs and flags drift.
The model only judges. Everything else (diff, routing, evidence rule, comment, status) is plain code.

Environment (set by the workflow):
  BASE_SHA, HEAD_SHA, PR_NUMBER, REPO   the pull request
  GH_TOKEN                              to comment and set the commit status
  APIM_ENDPOINT, APIM_TOKEN, MODEL      the AI gateway, e.g. https://<apim>.azure-api.net/openai/v1
Optional:
  SRC_PATHS         space separated pathspecs the check looks at (default "src/")
  MAX_DIFF_CHARS    default 60000
  SKIP_LABEL        default "no-spec-impact"
  REASONING_EFFORT  passed to the model when set (low, medium, high)
  LABELS            only with --dry-run, comma separated, stands in for the PR labels

Run with --dry-run to print the result without calling GitHub.
Standard library only, so the workflow needs no pip install.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKER = "<!-- spec-guardrail -->"
CONTEXT = "spec-guardrail"
BLOCKING = {"spec_gap", "contradiction"}
DELTA_RE = re.compile(r"^openspec/changes/(?!archive/)[^/]+/specs/(.+)/spec\.md$")
# Names and paths that end up inside our own tags must not be able to break out of an attribute.
SAFE_NAME = re.compile(r"^[A-Za-z0-9._/-]+$")
# Our own tags. Content that contains them could close a section early, so they are neutralized.
TAG_RE = re.compile(r"<(/?)(diff|capabilities|main_spec|spec_delta|note)\b", re.I)
TITLES = {
    "no_behavior_change": "No behavior change",
    "spec_gap": "Spec gap",
    "contradiction": "Contradiction",
    "unsure": "Unsure",
}

SELECT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["changes_behavior", "relevant_capabilities", "reason"],
    "properties": {
        "changes_behavior": {"type": "boolean"},
        "relevant_capabilities": {"type": "array", "items": {"type": "string"}},
        "reason": {"type": "string"},
    },
}

CLASSIFY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict", "summary", "findings", "suggested_delta"],
    "properties": {
        "verdict": {"type": "string", "enum": list(TITLES)},
        "summary": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["file", "lines", "requirement", "evidence", "explanation"],
                "properties": {
                    "file": {"type": "string"},
                    "lines": {"type": "string"},
                    "requirement": {"type": "string"},
                    "evidence": {"type": "string"},
                    "explanation": {"type": "string"},
                },
            },
        },
        "suggested_delta": {"type": ["string", "null"]},
    },
}


def cfg(name, default=""):
    return os.environ.get(name, default)


# ---------------------------------------------------------------------------
# Step 1 (deterministic): the diff, the specs and the spec deltas of the PR
# ---------------------------------------------------------------------------

def git(*args):
    p = subprocess.run(["git", *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:2])} failed: {p.stderr.strip()[:300]}")
    return p.stdout


def read_specs(root=Path("openspec/specs")):
    specs = {}
    for p in sorted(root.rglob("spec.md")):
        name = p.parent.relative_to(root).as_posix()
        if SAFE_NAME.match(name):
            specs[name] = p.read_text(encoding="utf-8")
    return specs


def purpose(text):
    m = re.search(r"^## Purpose\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return " ".join(m.group(1).split())[:300] if m else "(no purpose written)"


def defang(text):
    """Neutralizes our own tags inside content that comes from the pull request."""
    return TAG_RE.sub(r"&lt;\1\2", text)


def norm(line):
    """A line as it is compared: without the diff marker, the indentation and repeated spaces."""
    line = line.strip()
    if line[:1] in ("+", "-"):
        line = line[1:]
    return " ".join(line.split())


def verify(findings, diff, spec_texts):
    """Evidence rule: keeps only findings whose file, quote and requirement can be found.

    The file must be part of the diff, every quoted line must appear in the diff and the
    requirement must exist in a spec the model was given (or be "none").
    Returns (kept findings, number dropped).
    """
    files = set(re.findall(r"^diff --git a/(\S+) b/", diff, re.M))
    diff_lines = [norm(l) for l in diff.splitlines()]
    known = {" ".join(m.lower().split()) for t in spec_texts for m in re.findall(r"^### Requirement:\s*(.+?)\s*$", t, re.M)}
    kept = []
    for f in findings:
        path = f.get("file", "").strip()
        if path[:2] in ("a/", "b/") and path not in files:
            path = path[2:]
        quote = [q for q in (norm(l) for l in f.get("evidence", "").splitlines()) if len(q) >= 4]
        requirement = " ".join(f.get("requirement", "").lower().split()).removeprefix("requirement:").strip()
        quoted_in_diff = bool(quote) and all(any(q in d for d in diff_lines) for q in quote)
        if path in files and quoted_in_diff and f.get("lines", "").strip() and requirement in ({"", "none"} | known):
            kept.append(dict(f, file=path))
    return kept, len(findings) - len(kept)


def result(verdict, summary, findings, **extra):
    base = {
        "verdict": verdict,
        "summary": summary,
        "findings": findings,
        "suggested_delta": None,
        "capabilities": [],
        "mode": "",
        "truncated": False,
        "dropped": 0,
    }
    base.update(extra)
    return base


# ---------------------------------------------------------------------------
# Step 2 (the model judges): pick the specs, then classify the change
# ---------------------------------------------------------------------------

class Gateway:
    """Calls the OpenAI compatible chat completions endpoint of the AI gateway."""

    def __init__(self):
        self.url = cfg("APIM_ENDPOINT").rstrip("/") + "/chat/completions"
        self.token = cfg("APIM_TOKEN")
        self.model = cfg("MODEL", "gpt-6-luna")
        self.effort = cfg("REASONING_EFFORT")

    def ask(self, system, user, name, schema):
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": name, "strict": True, "schema": schema},
            },
        }
        if self.effort:
            body["reasoning_effort"] = self.effort
        data = json.dumps(body).encode()
        for attempt in range(3):
            req = urllib.request.Request(
                self.url,
                data=data,
                headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    reply = json.load(r)
                break
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 2:  # the gateway's token limit: wait and try again
                    time.sleep(min(int(e.headers.get("Retry-After", "20")), 60))
                    continue
                raise RuntimeError(f"gateway returned {e.code}: {e.read().decode(errors='replace')[:400]}")
        message = reply["choices"][0]["message"]
        if message.get("refusal"):
            raise RuntimeError(f"the model refused: {message['refusal'][:200]}")
        return json.loads(message["content"])


def analyze(base, head, model, src_paths, max_chars=60000):
    diff = git("diff", "--unified=5", f"{base}...{head}", "--", *src_paths)
    if not diff.strip():
        return result("no_behavior_change", "No changes under the checked paths.", [], mode="no-changes")
    truncated = len(diff) > max_chars
    diff = defang(diff[:max_chars])

    deltas = {}
    for f in git("diff", "--name-only", f"{base}...{head}").splitlines():
        m = DELTA_RE.match(f)
        if m and SAFE_NAME.match(f) and Path(f).exists():
            deltas[m.group(1)] = (f, Path(f).read_text(encoding="utf-8"))
    specs = read_specs()

    if deltas:
        # The PR brings its own spec delta: compare the code with the delta and its main spec.
        caps, mode = list(deltas), "delta"
    else:
        # Show the model only the diff and the list of capabilities, and let it pick the relevant ones.
        catalog = "\n".join(f"- {n}: {defang(purpose(t))}" for n, t in specs.items()) or "(no specs exist yet)"
        sel = model.ask(
            (HERE / "prompts" / "select.md").read_text(encoding="utf-8"),
            f"<diff>\n{diff}\n</diff>\n<capabilities>\n{catalog}\n</capabilities>",
            "spec_selection",
            SELECT_SCHEMA,
        )
        if not sel["changes_behavior"]:
            return result("no_behavior_change", sel["reason"], [], mode="selected", truncated=truncated)
        caps, mode = [c for c in sel["relevant_capabilities"] if c in specs], "selected"

    parts = [f"<diff>\n{diff}\n</diff>"]
    if truncated:
        parts.append("<note>The diff was cut off at the size limit. Judge only what you can see.</note>")
    spec_texts = []
    for cap in caps:
        if cap in specs:
            spec_texts.append(specs[cap])
            parts.append(f'<main_spec capability="{cap}">\n{defang(specs[cap])}\n</main_spec>')
    for cap, (path, text) in deltas.items():
        spec_texts.append(text)
        parts.append(f'<spec_delta capability="{cap}" path="{path}">\n{defang(text)}\n</spec_delta>')
    if not caps:
        parts.append("<note>No existing spec covers this change.</note>")

    out = model.ask(
        (HERE / "prompts" / "classify.md").read_text(encoding="utf-8"),
        "\n".join(parts),
        "spec_classification",
        CLASSIFY_SCHEMA,
    )

    # Evidence rule: a finding whose file, quote or requirement can't be found is dropped.
    findings, dropped = verify(out["findings"], diff, spec_texts)
    verdict = out["verdict"]
    if verdict in BLOCKING and not findings:
        verdict = "unsure"
    return result(
        verdict,
        out["summary"],
        findings,
        suggested_delta=out["suggested_delta"] if verdict == "spec_gap" else None,
        capabilities=caps,
        mode=mode,
        truncated=truncated,
        dropped=dropped,
    )


# ---------------------------------------------------------------------------
# Step 3 (deterministic): the rule, the comment and the commit status
# ---------------------------------------------------------------------------

def decide(r, skip_label, labels):
    """Returns (status state, description, overridden)."""
    if r["verdict"] in BLOCKING:
        if skip_label in labels:
            return "success", f"Overridden by the {skip_label} label", True
        return "failure", f"{TITLES[r['verdict']]}: add a spec delta or the {skip_label} label", False
    if r["verdict"] == "unsure":
        return "success", "Unsure, please review by hand", False
    if r.get("mode") == "delta":
        return "success", "Code matches the spec delta", False
    return "success", "No spec impact", False


def clean(text):
    """The model writes into a PR comment: no @mentions, and nothing that closes a code fence."""
    return text.replace("@", "@​").replace("```", "'''")


def render(r, skip_label, overridden):
    passed = r["verdict"] == "no_behavior_change"
    headline = "Spec guardrail check passed." if passed else f"Result: {TITLES[r['verdict']]}"
    out = [MARKER, "## Domain guardrail check", "", f"**{headline}**"]
    if overridden:
        out.append(f"Overridden by the `{skip_label}` label.")
    out += ["", clean(r["summary"])]
    if r["capabilities"]:
        out += ["", "Specs considered: " + ", ".join(f"`{c}`" for c in r["capabilities"])]
    for i, f in enumerate(r["findings"], 1):
        out += [
            "",
            f"**{i}. `{clean(f['file'])}`, lines {clean(f['lines'])}** (requirement: {clean(f['requirement'])})",
            "",
            "```text",
            clean(f["evidence"]),
            "```",
            clean(f["explanation"]),
        ]
    if r.get("dropped"):
        out += ["", f"_{r['dropped']} finding(s) left out: their file, quote or requirement could not be found in the change or the specs._"]
    if r["suggested_delta"]:
        out += [
            "",
            "<details><summary>Suggested spec delta</summary>",
            "",
            "````markdown",
            r["suggested_delta"].replace("````", "'''"),
            "````",
            "</details>",
        ]
    if r["verdict"] in BLOCKING and not overridden:
        out += [
            "",
            f"To continue, add a spec delta under `openspec/changes/<id>/specs/` in this PR, "
            f"or add the `{skip_label}` label with a short reason. The check flags, a person decides.",
        ]
    if r["truncated"]:
        out += ["", "_The diff was cut off at the size limit, so this result may be incomplete._"]
    return "\n".join(out) + "\n"


def github(method, path, body=None):
    req = urllib.request.Request(
        cfg("GITHUB_API_URL", "https://api.github.com") + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {cfg('GH_TOKEN')}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"GitHub {method} {path.split('?')[0]} returned {e.code}: {e.read().decode(errors='replace')[:200]}")


def find_comment(repo, pr):
    page = 1
    while True:
        batch = github("GET", f"/repos/{repo}/issues/{pr}/comments?per_page=100&page={page}")
        for c in batch:
            if c["body"].startswith(MARKER) and c["user"]["login"] == "github-actions[bot]":
                return c["id"]
        if len(batch) < 100:
            return None
        page += 1


def set_status(repo, sha, state, description):
    run = cfg("GITHUB_RUN_ID")
    body = {"state": state, "context": CONTEXT, "description": description[:140]}
    if run:
        body["target_url"] = f"{cfg('GITHUB_SERVER_URL', 'https://github.com')}/{repo}/actions/runs/{run}"
    github("POST", f"/repos/{repo}/statuses/{sha}", body)


def main():
    dry = "--dry-run" in sys.argv
    base, head, repo, pr = cfg("BASE_SHA"), cfg("HEAD_SHA"), cfg("REPO"), cfg("PR_NUMBER")
    skip_label = cfg("SKIP_LABEL", "no-spec-impact")
    try:
        if not dry:
            set_status(repo, head, "pending", "Checking the change against the specs")
        r = analyze(base, head, Gateway(), cfg("SRC_PATHS", "src/").split(), int(cfg("MAX_DIFF_CHARS", "60000")))
        labels = [x for x in cfg("LABELS").split(",") if x] if dry else [
            l["name"] for l in github("GET", f"/repos/{repo}/issues/{pr}/labels?per_page=100")
        ]
        state, description, overridden = decide(r, skip_label, labels)
        body = render(r, skip_label, overridden)
        if dry:
            print(body)
            print(f"status: {state} - {description}")
            return 0
        existing = find_comment(repo, pr)  # one comment per PR, refreshed on every run
        if existing:
            github("PATCH", f"/repos/{repo}/issues/comments/{existing}", {"body": body})
        else:
            github("POST", f"/repos/{repo}/issues/{pr}/comments", {"body": body})
        set_status(repo, head, state, description)
        print(f"{r['verdict']} ({r['mode']}): {state} - {description}")
        return 0
    except Exception as e:  # fail closed: the merge stays blocked until the check runs again
        print(f"spec-guardrail failed: {e}", file=sys.stderr)
        if not dry and repo and head:
            try:
                set_status(repo, head, "error", "The check could not run, see the workflow log")
            except Exception:
                pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
