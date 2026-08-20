#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Iterable

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
        r"\bMAF\b",
        r"\bbackend/app/maf\b",
        r"\bapp/maf\b",
        r"\bagent-framework(?:-foundry)?\b",
        r"\bFoundryChatClient\b",
        r"\bSequentialBuilder\b",
        r"\bmaf_workflow\b",
        r"\bfoundry-agent-evaluation\b",
        r"\btypescript-(?:setup|update)\b",
        r"\bagent-framework-foundry-py\b",
    )
]
STALE_ALLOW_HINTS = ("migration", "migrat", "history", "histor", "legacy", "deprecated")


def load_provenance() -> dict:
    try:
        return json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"Missing provenance file: {PROVENANCE_PATH}")


def top_level_skill_dirs() -> list[Path]:
    return sorted(path for path in SKILLS_ROOT.iterdir() if path.is_dir() and not path.name.startswith("."))


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing opening frontmatter delimiter")
    try:
        _, rest = text.split("---\n", 1)
        frontmatter, _body = rest.split("\n---\n", 1)
    except ValueError as exc:
        raise ValueError("missing closing frontmatter delimiter") from exc
    keys: dict[str, str] = {}
    for line in frontmatter.splitlines():
        match = FRONTMATTER_KEY_RE.match(line)
        if match:
            keys[match.group(1)] = line
    if "name" not in keys or "description" not in keys:
        missing = ", ".join(key for key in ("name", "description") if key not in keys)
        raise ValueError(f"frontmatter missing required keys: {missing}")
    return keys


def iter_markdown_files() -> Iterable[Path]:
    for path in sorted(SKILLS_ROOT.rglob("*.md")):
        if path.is_file():
            yield path


def strip_code_fences(text: str) -> str:
    return CODE_FENCE_RE.sub("", text)


def is_local_link(target: str) -> bool:
    lowered = target.lower()
    return not (
        lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("mailto:")
        or lowered.startswith("#")
        or lowered.startswith("data:")
        or lowered.startswith("javascript:")
    )


def resolve_link(source: Path, target: str) -> Path | None:
    cleaned = target.strip().strip("<>").strip()
    if not cleaned or cleaned.startswith("{{") or "<" in cleaned:
        return None
    cleaned = cleaned.split("#", 1)[0].split("?", 1)[0]
    if not cleaned:
        return None
    if cleaned.startswith("/"):
        return PROJECT_ROOT / cleaned.lstrip("/")
    return (source.parent / cleaned).resolve()


def validate_links(markdown_paths: Iterable[Path]) -> tuple[int, list[str]]:
    checked = 0
    errors: list[str] = []
    for path in markdown_paths:
        text = strip_code_fences(path.read_text(encoding="utf-8"))
        for raw_target in MARKDOWN_LINK_RE.findall(text):
            target = raw_target.split()[0]
            if not is_local_link(target):
                continue
            resolved = resolve_link(path, target)
            if resolved is None:
                continue
            checked += 1
            if not resolved.exists():
                rel = path.relative_to(PROJECT_ROOT)
                errors.append(f"Broken local link in {rel}: {raw_target}")
    return checked, errors


def validate_stale_identifiers(local_skill_dirs: list[Path]) -> list[str]:
    errors: list[str] = []
    files_to_scan = [skill_dir / "SKILL.md" for skill_dir in local_skill_dirs]
    files_to_scan.extend(sorted(SCRIPTS_ROOT.glob("*.sh")))
    for path in files_to_scan:
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            lower = line.lower()
            if any(hint in lower for hint in STALE_ALLOW_HINTS):
                continue
            for pattern in STALE_PATTERNS:
                if pattern.search(line):
                    errors.append(
                        f"Stale identifier in {path.relative_to(PROJECT_ROOT)}:{lineno}: {line.strip()}"
                    )
                    break
    return errors


def main() -> int:
    errors: list[str] = []
    provenance = load_provenance()
    skills = provenance.get("skills", {})
    if not isinstance(skills, dict):
        errors.append("provenance.lock.json: 'skills' must be an object")
        skills = {}

    top_dirs = top_level_skill_dirs()
    top_names = [path.name for path in top_dirs]

    if sorted(skills.keys()) != top_names:
        errors.append(
            "provenance skill set does not match top-level skill directories: "
            f"manifest={sorted(skills.keys())}, dirs={top_names}"
        )

    frontmatter_count = 0
    for skill_dir in top_dirs:
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            errors.append(f"Missing top-level SKILL.md: {skill_file.relative_to(PROJECT_ROOT)}")
        else:
            try:
                frontmatter = parse_frontmatter(skill_file)
                frontmatter_count += 1
                name_line = frontmatter.get("name", "")
                if f"name: {skill_dir.name}" not in name_line:
                    errors.append(
                        f"Top-level skill name mismatch in {skill_file.relative_to(PROJECT_ROOT)}: expected '{skill_dir.name}'"
                    )
            except ValueError as exc:
                errors.append(f"{skill_file.relative_to(PROJECT_ROOT)}: {exc}")

    nested_skill_count = 0
    for skill_file in sorted(SKILLS_ROOT.rglob("SKILL.md")):
        try:
            parse_frontmatter(skill_file)
            nested_skill_count += 1
        except ValueError as exc:
            errors.append(f"{skill_file.relative_to(PROJECT_ROOT)}: {exc}")

    for skill_name, entry in skills.items():
        if not isinstance(entry, dict):
            errors.append(f"provenance entry for {skill_name} must be an object")
            continue
        required = ["kind", "source_repo", "source_path", "source_commit_or_sha", "license", "reviewed_on", "purpose"]
        missing = [field for field in required if not entry.get(field)]
        if missing:
            errors.append(f"provenance entry for {skill_name} missing fields: {', '.join(missing)}")
        if entry.get("kind") == "upstream":
            if "/" not in str(entry.get("source_repo", "")):
                errors.append(f"upstream provenance for {skill_name} must use owner/repo format")
        skill_path = MONOREPO_ROOT / str(entry.get("source_path", ""))
        if entry.get("kind") == "local" and not skill_path.exists():
            errors.append(f"local provenance path missing for {skill_name}: {entry.get('source_path')}")

    link_count, link_errors = validate_links(iter_markdown_files())
    errors.extend(link_errors)

    local_skill_dirs = [SKILLS_ROOT / name for name, entry in skills.items() if isinstance(entry, dict) and entry.get("kind") == "local"]
    errors.extend(validate_stale_identifiers(local_skill_dirs))

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    upstream_count = sum(1 for entry in skills.values() if isinstance(entry, dict) and entry.get("kind") == "upstream")
    local_count = sum(1 for entry in skills.values() if isinstance(entry, dict) and entry.get("kind") == "local")
    print(
        f"Validated {len(top_dirs)} top-level skills, {nested_skill_count} SKILL.md files, "
        f"{upstream_count} upstream provenance entries, {local_count} local provenance entries, and {link_count} local links."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
