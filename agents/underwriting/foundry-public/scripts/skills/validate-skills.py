#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MONOREPO_ROOT = PROJECT_ROOT.parents[2]
SKILLS_ROOT = PROJECT_ROOT / ".github" / "skills"
PROVENANCE_PATH = SKILLS_ROOT / "provenance.lock.json"
SCRIPTS_ROOT = PROJECT_ROOT / "scripts" / "skills"

FRONTMATTER_KEY_RE = re.compile(r"^([A-Za-z0-9_.-]+):")
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
STALE_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"\bbackend/app/maf\b",
        r"\bapp/maf\b",
        r"\bagent-framework(?:-foundry)?\b",
        r"\bFoundryChatClient\b",
        r"\bSequentialBuilder\b",
        r"\bmaf_workflow\b",
        r"\bfoundry-agent-evaluation\b",
        r"\btypescript-(?:setup|update)\b",
    )
]
STALE_ALLOW_HINTS = ("migration", "migrat", "history", "histor", "legacy", "deprecated")


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing opening frontmatter delimiter")
    try:
        _, rest = text.split("---\n", 1)
        frontmatter, _ = rest.split("\n---\n", 1)
    except ValueError as exc:
        raise ValueError("missing closing frontmatter delimiter") from exc
    keys: dict[str, str] = {}
    for line in frontmatter.splitlines():
        match = FRONTMATTER_KEY_RE.match(line)
        if match:
            keys[match.group(1)] = line
    missing = [key for key in ("name", "description") if key not in keys]
    if missing:
        raise ValueError(f"frontmatter missing required keys: {', '.join(missing)}")
    return keys


def local_link_errors() -> tuple[int, list[str]]:
    checked = 0
    errors: list[str] = []
    for path in sorted(SKILLS_ROOT.rglob("*.md")):
        text = CODE_FENCE_RE.sub("", path.read_text(encoding="utf-8"))
        for raw_target in MARKDOWN_LINK_RE.findall(text):
            target = raw_target.split()[0].strip().strip("<>")
            lowered = target.lower()
            if (
                not target
                or lowered.startswith(("http://", "https://", "mailto:", "#", "data:"))
                or target.startswith("{{")
                or "<" in target
            ):
                continue
            cleaned = target.split("#", 1)[0].split("?", 1)[0]
            if not cleaned:
                continue
            resolved = (
                PROJECT_ROOT / cleaned.lstrip("/")
                if cleaned.startswith("/")
                else (path.parent / cleaned).resolve()
            )
            checked += 1
            if not resolved.exists():
                errors.append(
                    f"Broken local link in {path.relative_to(PROJECT_ROOT)}: {raw_target}"
                )
    return checked, errors


def stale_identifier_errors(local_skill_dirs: list[Path]) -> list[str]:
    errors: list[str] = []
    paths = [skill_dir / "SKILL.md" for skill_dir in local_skill_dirs]
    paths.extend(sorted(SCRIPTS_ROOT.glob("*.sh")))
    for path in paths:
        if not path.exists():
            continue
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            lowered = line.lower()
            if any(hint in lowered for hint in STALE_ALLOW_HINTS):
                continue
            if any(pattern.search(line) for pattern in STALE_PATTERNS):
                errors.append(
                    f"Stale identifier in {path.relative_to(PROJECT_ROOT)}:"
                    f"{line_number}: {line.strip()}"
                )
    return errors


def main() -> int:
    errors: list[str] = []
    try:
        provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"Missing provenance file: {PROVENANCE_PATH}")
        provenance = {}
    skills = provenance.get("skills", {})
    if not isinstance(skills, dict):
        errors.append("provenance.lock.json: 'skills' must be an object")
        skills = {}

    top_dirs = sorted(
        path
        for path in SKILLS_ROOT.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )
    top_names = [path.name for path in top_dirs]
    if sorted(skills) != top_names:
        errors.append(
            "provenance skill set does not match top-level skill directories: "
            f"manifest={sorted(skills)}, dirs={top_names}"
        )

    nested_skill_count = 0
    for skill_file in sorted(SKILLS_ROOT.rglob("SKILL.md")):
        try:
            frontmatter = parse_frontmatter(skill_file)
            nested_skill_count += 1
            if skill_file.parent.parent == SKILLS_ROOT:
                expected = skill_file.parent.name
                if f"name: {expected}" not in frontmatter["name"]:
                    errors.append(
                        f"Top-level skill name mismatch in "
                        f"{skill_file.relative_to(PROJECT_ROOT)}: expected '{expected}'"
                    )
        except ValueError as exc:
            errors.append(f"{skill_file.relative_to(PROJECT_ROOT)}: {exc}")

    required = {
        "kind",
        "source_repo",
        "source_path",
        "source_commit_or_sha",
        "license",
        "reviewed_on",
        "purpose",
    }
    for skill_name, entry in skills.items():
        if not isinstance(entry, dict):
            errors.append(f"provenance entry for {skill_name} must be an object")
            continue
        missing = sorted(field for field in required if not entry.get(field))
        if missing:
            errors.append(
                f"provenance entry for {skill_name} missing fields: {', '.join(missing)}"
            )
        if entry.get("kind") == "upstream" and "/" not in str(
            entry.get("source_repo", "")
        ):
            errors.append(
                f"upstream provenance for {skill_name} must use owner/repo format"
            )
        if entry.get("kind") == "local":
            source_path = MONOREPO_ROOT / str(entry.get("source_path", ""))
            if not source_path.exists():
                errors.append(
                    f"local provenance path missing for {skill_name}: "
                    f"{entry.get('source_path')}"
                )

    link_count, link_errors = local_link_errors()
    errors.extend(link_errors)
    local_dirs = [
        SKILLS_ROOT / name
        for name, entry in skills.items()
        if isinstance(entry, dict) and entry.get("kind") == "local"
    ]
    errors.extend(stale_identifier_errors(local_dirs))

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    upstream_count = sum(
        1 for entry in skills.values() if entry.get("kind") == "upstream"
    )
    local_count = len(skills) - upstream_count
    print(
        f"Validated {len(top_dirs)} top-level skills, {nested_skill_count} "
        f"SKILL.md files, {upstream_count} upstream provenance entries, "
        f"{local_count} local provenance entries, and {link_count} local links."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
