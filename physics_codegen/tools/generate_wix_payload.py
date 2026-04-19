from __future__ import annotations

import re
import sys
import uuid
from hashlib import sha1
import xml.etree.ElementTree as ET
from pathlib import Path


WIX_NS = "http://wixtoolset.org/schemas/v4/wxs"
ET.register_namespace("", WIX_NS)


def q(tag: str) -> str:
    return f"{{{WIX_NS}}}{tag}"


def make_id(prefix: str, rel: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_]", "_", rel)
    stem = re.sub(r"_+", "_", stem).strip("_") or "root"
    digest = sha1(rel.encode("utf-8")).hexdigest()[:10]
    max_len = 72
    base_prefix = f"{prefix}_"
    keep = max_len - len(base_prefix) - len(digest) - 1
    stem = stem[: max(keep, 8)].rstrip("_")
    candidate = f"{base_prefix}{stem}_{digest}"
    if not re.match(r"^[A-Za-z_]", candidate):
        candidate = f"{prefix}_{candidate}"
    return candidate


def guid_for(rel: str) -> str:
    return str(uuid.uuid5(uuid.UUID("6f3c2a10-7c5e-4d3a-9f1b-2e8a4d5c9b71"), rel))


def add_dir(dirref: ET.Element, root: Path, current: Path, component_ids: list[str]) -> None:
    for child in sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        rel = child.relative_to(root).as_posix()
        if child.is_dir():
            dir_el = ET.SubElement(
                dirref,
                q("Directory"),
                Id=make_id("dir", rel),
                Name=child.name,
            )
            add_dir(dir_el, root, child, component_ids)
            continue

        comp_id = make_id("cmp", rel)
        file_id = make_id("fil", rel)
        comp = ET.SubElement(
            dirref,
            q("Component"),
            Id=comp_id,
            Guid=guid_for(rel),
        )
        source_path = rel.replace("/", "\\")
        ET.SubElement(
            comp,
            q("File"),
            Id=file_id,
            Source=f"$(var.SourceDir)\\{source_path}",
            KeyPath="yes",
        )
        component_ids.append(comp_id)


def indent(elem: ET.Element, level: int = 0) -> None:
    whitespace = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = whitespace + "  "
        for child in elem:
            indent(child, level + 1)
        if not elem[-1].tail or not elem[-1].tail.strip():
            elem[-1].tail = whitespace
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = whitespace


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: generate_wix_payload.py <source_dir> <output_wxs>", file=sys.stderr)
        return 2

    source_dir = Path(argv[1]).resolve()
    output_wxs = Path(argv[2]).resolve()

    if not source_dir.is_dir():
        print(f"source directory not found: {source_dir}", file=sys.stderr)
        return 1

    wix = ET.Element(q("Wix"))
    frag_dirs = ET.SubElement(wix, q("Fragment"))
    dirref = ET.SubElement(frag_dirs, q("DirectoryRef"), Id="INSTALLFOLDER")

    component_ids: list[str] = []
    add_dir(dirref, source_dir, source_dir, component_ids)

    frag_group = ET.SubElement(wix, q("Fragment"))
    group = ET.SubElement(frag_group, q("ComponentGroup"), Id="AppPayload")
    for comp_id in component_ids:
        ET.SubElement(group, q("ComponentRef"), Id=comp_id)

    indent(wix)
    output_wxs.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(wix)
    tree.write(output_wxs, encoding="utf-8", xml_declaration=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
