#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent
MODULES = ("common", "fabric", "neoforge")
TEXT_SUFFIXES = {
    ".java",
    ".kt",
    ".kts",
    ".gradle",
    ".properties",
    ".json",
    ".toml",
    ".cfg",
    ".mcmeta",
    ".md",
    ".txt",
}


def read_properties(path: Path) -> dict[str, str]:
    props: dict[str, str] = {}
    if not path.exists():
        raise FileNotFoundError(f"gradle properties file not found: {path}")

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        props[key.strip()] = value.strip()
    return props


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def detect_state(target_group: str, target_main: str, target_mod_id: str) -> tuple[str, str, str]:
    fabric_mod_json = ROOT / "fabric" / "src" / "main" / "resources" / "fabric.mod.json"
    old_package = target_group
    old_main_class = target_main
    found_main_from_entrypoint = False

    if fabric_mod_json.exists():
        text = read_text(fabric_mod_json)
        match = re.search(r'"main"\s*:\s*\[\s*"([A-Za-z0-9_$.]+)"', text)
        if match:
            fqcn = match.group(1)
            if "." in fqcn:
                old_package, old_main_class = fqcn.rsplit(".", 1)
                found_main_from_entrypoint = True

    constants_file = ROOT / "common" / "src" / "main" / "java"
    old_mod_id = target_mod_id
    constants_candidates = list(constants_file.rglob("Constants.java"))
    if constants_candidates:
        constants_text = read_text(constants_candidates[0])
        mod_match = re.search(r'MOD_ID\s*=\s*"([^"]+)"', constants_text)
        if mod_match:
            old_mod_id = mod_match.group(1)
        pkg_match = re.search(r"^\s*package\s+([A-Za-z0-9_.]+)\s*;", constants_text, re.MULTILINE)
        if pkg_match:
            old_package = pkg_match.group(1)

    if not found_main_from_entrypoint:
        java_roots = [ROOT / module / "src" / "main" / "java" for module in MODULES]
        declaration_pattern = re.compile(
            r"^\s*(?:public\s+)?(?:final\s+|abstract\s+)?class\s+([A-Za-z0-9_]+)\b",
            re.MULTILINE,
        )
        for root in java_roots:
            for java_file in root.rglob("*.java"):
                text = read_text(java_file)
                pkg_match = re.search(r"^\s*package\s+([A-Za-z0-9_.]+)\s*;", text, re.MULTILINE)
                class_match = declaration_pattern.search(text)
                if pkg_match and class_match:
                    old_package = pkg_match.group(1)
                    old_main_class = class_match.group(1)
                    break
            if old_main_class:
                break

    return old_package, old_main_class, old_mod_id


def move_tree_merge(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            dst.unlink()
        src.replace(dst)
        return

    dst.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        move_tree_merge(child, dst / child.name)
    if not any(src.iterdir()):
        src.rmdir()


def clean_empty_dirs(path: Path, stop: Path) -> None:
    current = path
    while current != stop and current.exists():
        try:
            next(current.iterdir())
            break
        except StopIteration:
            parent = current.parent
            current.rmdir()
            current = parent


def rename_package_dirs(old_package: str, new_package: str) -> None:
    if old_package == new_package:
        return
    old_rel = Path(*old_package.split("."))
    new_rel = Path(*new_package.split("."))
    for module in MODULES:
        base = ROOT / module / "src" / "main" / "java"
        old_dir = base / old_rel
        new_dir = base / new_rel
        if old_dir.exists():
            move_tree_merge(old_dir, new_dir)
            clean_empty_dirs(old_dir.parent, base)


def rename_main_class_files(old_package: str, new_package: str, old_main: str, new_main: str) -> None:
    if old_main == new_main:
        return

    for module in MODULES:
        base = ROOT / module / "src" / "main" / "java"
        new_dir = base / Path(*new_package.split("."))
        old_dir = base / Path(*old_package.split("."))
        candidates = [
            new_dir / f"{old_main}.java",
            old_dir / f"{old_main}.java",
        ]
        for candidate in candidates:
            if candidate.exists():
                target = candidate.with_name(f"{new_main}.java")
                if target.exists():
                    target.unlink()
                candidate.replace(target)
                break


def rename_modid_files(old_mod_id: str, new_mod_id: str) -> None:
    if old_mod_id == new_mod_id:
        return
    for module in MODULES:
        resources_root = ROOT / module / "src" / "main" / "resources"
        if not resources_root.exists():
            continue
        for file in sorted(resources_root.rglob(f"{old_mod_id}*"), reverse=True):
            if not file.is_file():
                continue
            new_name = new_mod_id + file.name[len(old_mod_id) :]
            target = file.with_name(new_name)
            if target.exists():
                target.unlink()
            file.replace(target)


def rename_service_filename(old_package: str, new_package: str) -> None:
    if old_package == new_package:
        return
    for module in ("fabric", "neoforge"):
        services_dir = ROOT / module / "src" / "main" / "resources" / "META-INF" / "services"
        if not services_dir.exists():
            continue
        old_name = f"{old_package}.platform.services.IPlatformHelper"
        new_name = f"{new_package}.platform.services.IPlatformHelper"
        src = services_dir / old_name
        dst = services_dir / new_name
        if src.exists():
            if dst.exists():
                dst.unlink()
            src.replace(dst)


def iter_text_files() -> Iterable[Path]:
    for module in MODULES:
        module_root = ROOT / module
        if not module_root.exists():
            continue
        for file in module_root.rglob("*"):
            if not file.is_file():
                continue
            if any(part in {"build", ".gradle"} for part in file.parts):
                continue
            if file.suffix in TEXT_SUFFIXES or file.parent.name == "services":
                yield file


def rewrite_contents(
    old_package: str,
    new_package: str,
    old_main: str,
    new_main: str,
    old_mod_id: str,
    new_mod_id: str,
) -> None:
    old_pkg_slash = old_package.replace(".", "/")
    new_pkg_slash = new_package.replace(".", "/")
    old_fqcn = f"{old_package}.{old_main}"
    new_fqcn = f"{new_package}.{new_main}"
    class_word = re.compile(rf"\b{re.escape(old_main)}\b")

    for file in iter_text_files():
        original = read_text(file)
        updated = original
        if old_package != new_package:
            updated = updated.replace(old_package, new_package)
            updated = updated.replace(old_pkg_slash, new_pkg_slash)
        if old_mod_id != new_mod_id:
            updated = updated.replace(old_mod_id, new_mod_id)
        if old_fqcn != new_fqcn:
            updated = updated.replace(old_fqcn, new_fqcn)
        if file.suffix == ".java" and old_main != new_main:
            # Only rewrite simple class-name tokens inside likely entry class files.
            if file.name in {f"{old_main}.java", f"{new_main}.java"}:
                updated = class_word.sub(new_main, updated)
        if updated != original:
            write_text(file, updated)


def ensure_meta_inf() -> None:
    resources = ROOT / "common" / "src" / "main" / "resources"
    meat = resources / "MEAT-INF"
    meta = resources / "META-INF"
    if meat.exists() and not meta.exists():
        meat.replace(meta)


def fetch_standard_license_text(license_name: str) -> str | None:
    if not license_name:
        return None
    candidates = [license_name, license_name.lower()]
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "multiloader-template-sync-script",
    }
    for key in candidates:
        url = f"https://api.github.com/licenses/{urllib.parse.quote(key)}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
                body = payload.get("body", "")
                if body.strip():
                    return body.rstrip() + "\n"
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                continue
        except (urllib.error.URLError, TimeoutError):
            return None
    return None


def update_license_file(license_name: str) -> None:
    text = fetch_standard_license_text(license_name)
    if text is None:
        print(f"[sync] Skip LICENSE sync: '{license_name}' is not a recognized GitHub standard license key.")
        return
    write_text(ROOT / "LICENSE", text)
    print(f"[sync] LICENSE updated from GitHub API using key '{license_name}'.")


def parse_modifier(modifier: str) -> tuple[str, str | None]:
    if modifier.endswith("+f"):
        return modifier[:-2], "+f"
    if modifier.endswith("-f"):
        return modifier[:-2], "-f"
    return modifier, None


def convert_at_line_to_aw(line: str) -> tuple[list[str], str | None]:
    tokens = line.split()
    if len(tokens) < 2:
        return [], "invalid"

    modifier_raw = tokens[0]
    base_modifier, final_flag = parse_modifier(modifier_raw)
    owner_dot = tokens[1]
    owner_slash = owner_dot.replace(".", "/")

    if not owner_dot.startswith("net.minecraft."):
        return [], "non-minecraft"

    directives: list[str] = []

    if len(tokens) == 2:
        if base_modifier in {"public"}:
            if final_flag == "-f":
                directives.append(f"extendable class {owner_slash}")
            else:
                directives.append(f"accessible class {owner_slash}")
            return directives, None
        if base_modifier in {"protected"}:
            directives.append(f"extendable class {owner_slash}")
            return directives, None
        return [], "unsupported-class-modifier"

    member = tokens[2]
    if "(" in member and ")" in member:
        name, desc = member.split("(", 1)
        desc = "(" + desc
        if base_modifier == "public":
            directives.append(f"accessible method {owner_slash} {name} {desc}")
            if final_flag == "-f":
                return directives, "method-final-removal-partial"
            return directives, None
        if base_modifier == "protected":
            directives.append(f"extendable method {owner_slash} {name} {desc}")
            return directives, None
        return [], "unsupported-method-modifier"

    field_name = member
    if len(tokens) < 4:
        return [], "field-missing-descriptor"
    field_desc = tokens[3]
    if base_modifier == "public":
        directives.append(f"accessible field {owner_slash} {field_name} {field_desc}")
    if final_flag == "-f":
        directives.append(f"mutable field {owner_slash} {field_name} {field_desc}")
    if not directives:
        return [], "unsupported-field-modifier"
    return directives, None


def generate_classtweaker(mod_id: str) -> None:
    ensure_meta_inf()
    resources_root = ROOT / "common" / "src" / "main" / "resources"
    at_path = resources_root / "META-INF" / "accesstransformer.cfg"
    if not at_path.exists():
        at_path = resources_root / "MEAT-INF" / "accesstransformer.cfg"
    if not at_path.exists():
        raise FileNotFoundError("Cannot find accesstransformer.cfg under common/src/main/resources/META-INF.")

    output_path = resources_root / f"{mod_id}.classtweaker"
    generated: list[str] = [
        "accessWidener v2 official",
        "# Generated from common/src/main/resources/META-INF/accesstransformer.cfg",
        "# Only Minecraft vanilla (net.minecraft.*) access widening is auto-converted.",
        "# For non-vanilla entries or unsupported directives, handle manually.",
        "",
    ]
    skipped: list[str] = []

    for raw in read_text(at_path).splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        directives, reason = convert_at_line_to_aw(line)
        if directives:
            generated.extend(directives)
        if reason:
            skipped.append(f"# SKIPPED [{reason}] {line}")

    if skipped:
        generated.append("")
        generated.append("# Skipped source lines")
        generated.extend(skipped)

    write_text(output_path, "\n".join(generated).rstrip() + "\n")
    print(f"[classtweaker] generated: {output_path}")


def sync_from_properties() -> None:
    props = read_properties(ROOT / "gradle.properties")
    target_group = props.get("group", "").strip()
    target_mod_id = props.get("mod_id", "").strip()
    target_main = props.get("mainclassname", "").strip()
    target_license = props.get("license", "").strip()

    if not target_group:
        raise ValueError("Missing required 'group' in gradle.properties")
    if not target_mod_id:
        raise ValueError("Missing required 'mod_id' in gradle.properties")
    if not target_main:
        raise ValueError("Missing required 'mainclassname' in gradle.properties")

    ensure_meta_inf()
    old_package, old_main, old_mod_id = detect_state(target_group, target_main, target_mod_id)
    print(f"[sync] package: {old_package} -> {target_group}")
    print(f"[sync] main class: {old_main} -> {target_main}")
    print(f"[sync] mod id: {old_mod_id} -> {target_mod_id}")

    rename_package_dirs(old_package, target_group)
    rename_main_class_files(old_package, target_group, old_main, target_main)
    rename_modid_files(old_mod_id, target_mod_id)
    rename_service_filename(old_package, target_group)
    rewrite_contents(
        old_package=old_package,
        new_package=target_group,
        old_main=old_main,
        new_main=target_main,
        old_mod_id=old_mod_id,
        new_mod_id=target_mod_id,
    )

    if target_license:
        update_license_file(target_license)

    generate_classtweaker(target_mod_id)
    print("[sync] done.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync MultiLoader template from gradle.properties")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("sync", help="Sync package/class/mod_id/license and regenerate classtweaker.")
    sub.add_parser("generate-classtweaker", help="Generate <mod_id>.classtweaker from accesstransformer.cfg.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    props = read_properties(ROOT / "gradle.properties")
    mod_id = props.get("mod_id", "").strip()

    if args.command == "sync":
        sync_from_properties()
        return 0
    if args.command == "generate-classtweaker":
        if not mod_id:
            raise ValueError("Missing required 'mod_id' in gradle.properties")
        generate_classtweaker(mod_id)
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(f"[error] {exc}", file=sys.stderr)
        raise
