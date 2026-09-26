#!/usr/bin/env python3
"""Derive published and unpublished registry module versions.

"Published" means present at the last published ref (typically the latest
release tag). An empty published ref means nothing has been published yet.

The current working tree is read from `modules/<module>/metadata.json`.
Versions are never sorted; `metadata.json` order is the source of truth.

The CLI prints compact JSON:

  default      published `{module, version}` pairs at `--published-ref`
  --prune-plan versions to remove from the current working tree, ie every
               unpublished version except the last unpublished version of a
               module
"""

import argparse
import json
import pathlib
import subprocess
import sys


def repo_path(path):
    path = pathlib.Path(path)
    if path.is_absolute():
        try:
            path = path.relative_to(pathlib.Path.cwd())
        except ValueError:
            path = pathlib.Path(path.name)
    return path.as_posix()


def git_lines(*args):
    proc = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ERROR: git {' '.join(args)} failed: {proc.stderr.strip()}")
    return [line for line in proc.stdout.splitlines() if line]


def git_show_json(ref, path):
    proc = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        capture_output=True,
        text=True)
    if proc.returncode != 0:
        return None
    return json.loads(proc.stdout)


def metadata_versions_at_ref(published_ref, module, modules_root):
    data = git_show_json(
        published_ref,
        f"{modules_root}/{module}/metadata.json")
    if data is None:
        return []
    return list(data.get("versions", []))


def version_directories_at_ref(published_ref, module, modules_root):
    try:
        return git_lines(
            "ls-tree",
            "-d",
            "--name-only",
            f"{published_ref}:{modules_root}/{module}")
    except RuntimeError:
        return []


def published_pairs(published_ref, modules_root="modules"):
    published_ref = (published_ref or "").strip()
    if not published_ref:
        return set()
    modules_root = repo_path(modules_root)
    try:
        modules = git_lines(
            "ls-tree",
            "-d",
            "--name-only",
            f"{published_ref}:{modules_root}")
    except RuntimeError:
        return set()
    pairs = set()
    for module in modules:
        versions = set(metadata_versions_at_ref(published_ref, module, modules_root))
        versions.update(version_directories_at_ref(published_ref, module, modules_root))
        for version in versions:
            pairs.add((module, version))
    return pairs


def unpublished_versions(modules_root, published):
    modules_root = pathlib.Path(modules_root)
    unpublished = {}
    for metadata in sorted(modules_root.glob("*/metadata.json")):
        declared = json.loads(metadata.read_text()).get("versions", [])
        module_dir = metadata.parent
        module = module_dir.name
        current = []
        seen = set()
        for version in declared:
            if (module, version) in published:
                continue
            current.append(version)
            seen.add(version)
        for version_dir in sorted(path.name for path in module_dir.iterdir() if path.is_dir()):
            if version_dir in seen or (module, version_dir) in published:
                continue
            current.append(version_dir)
            seen.add(version_dir)
        if current:
            unpublished[module] = current
    return unpublished


def prune_plan(modules_root, published):
    plan = []
    for module, versions in unpublished_versions(modules_root, published).items():
        for version in versions[:-1]:
            plan.append((module, version))
    return [
        {"module": module, "version": version}
        for module, version in sorted(plan)
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modules-root", default="modules")
    parser.add_argument("--published-ref", default="")
    parser.add_argument(
        "--prune-plan",
        action="store_true",
        help="Print superseded unpublished versions to remove")
    args = parser.parse_args()
    try:
        published = published_pairs(args.published_ref, args.modules_root)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
    output = (
        prune_plan(args.modules_root, published)
        if args.prune_plan
        else [
            {"module": module, "version": version}
            for module, version in sorted(published)
        ])
    json.dump(output, sys.stdout, separators=(",", ":"))


if __name__ == "__main__":
    main()
