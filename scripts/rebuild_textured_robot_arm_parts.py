"""Rebuild the 29 robot-arm OBJ parts without dropping UVs or normals.

The existing GLB retains the authoritative 29 connected-component index sets,
while the source OBJ retains the authoritative v/vt/vn face tuples. This tool
joins those two sources and emits compact, texture-ready part OBJ files.
"""
from __future__ import annotations

import json
import shutil
import struct
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_OBJ = ROOT / "frontend/public/models/robot-arm/base.obj"
COMPONENT_GLB = ROOT / "frontend/public/models/robot-arm/base.glb"
OUTPUT = ROOT / "frontend/public/models/robot-arm/parts"
WORK = ROOT / "outputs/textured-part-rebuild"


def read_glb() -> tuple[dict, bytes]:
    raw = COMPONENT_GLB.read_bytes()
    _, _, total = struct.unpack_from("<III", raw, 0)
    if total != len(raw):
        raise ValueError("invalid GLB length")
    json_length, json_type = struct.unpack_from("<II", raw, 12)
    if json_type != 0x4E4F534A:
        raise ValueError("missing GLB JSON chunk")
    document = json.loads(raw[20:20 + json_length].rstrip(b" \0"))
    binary_header = 20 + json_length
    binary_length, binary_type = struct.unpack_from("<II", raw, binary_header)
    if binary_type != 0x004E4942:
        raise ValueError("missing GLB BIN chunk")
    binary = raw[binary_header + 8:binary_header + 8 + binary_length]
    return document, binary


def component_owner() -> list[int]:
    document, binary = read_glb()
    position_accessor = document["accessors"][1]
    owner = [-1] * int(position_accessor["count"])
    formats = {5123: ("H", 2), 5125: ("I", 4)}
    for component, mesh in enumerate(document["meshes"]):
        accessor = document["accessors"][mesh["primitives"][0]["indices"]]
        view = document["bufferViews"][accessor["bufferView"]]
        fmt, width = formats[accessor["componentType"]]
        offset = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
        count = int(accessor["count"])
        for (index,) in struct.iter_unpack("<" + fmt, binary[offset:offset + count * width]):
            owner[index] = component
    return owner


def parse_face(line: str) -> list[tuple[int, int | None, int | None]]:
    values: list[tuple[int, int | None, int | None]] = []
    for token in line.split()[1:]:
        fields = token.split("/")
        values.append((
            int(fields[0]),
            int(fields[1]) if len(fields) > 1 and fields[1] else None,
            int(fields[2]) if len(fields) > 2 and fields[2] else None,
        ))
    return values


def main() -> None:
    owner = component_owner()
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    face_files = [(WORK / f"faces-{i:02d}.txt").open("w", encoding="utf-8") for i in range(29)]
    used = [{"v": set(), "vt": set(), "vn": set()} for _ in range(29)]
    try:
        with SOURCE_OBJ.open(encoding="utf-8", errors="strict") as source:
            for line in source:
                if not line.startswith("f "):
                    continue
                face = parse_face(line)
                component = owner[face[0][0] - 1]
                if component < 0 or any(owner[item[0] - 1] != component for item in face):
                    raise ValueError("face crosses component ownership")
                face_files[component].write(line)
                for vertex, uv, normal in face:
                    used[component]["v"].add(vertex)
                    if uv is not None:
                        used[component]["vt"].add(uv)
                    if normal is not None:
                        used[component]["vn"].add(normal)
    finally:
        for handle in face_files:
            handle.close()

    membership: dict[str, dict[int, list[int]]] = {
        kind: defaultdict(list) for kind in ("v", "vt", "vn")
    }
    for component, groups in enumerate(used):
        for kind, indices in groups.items():
            for index in indices:
                membership[kind][index].append(component)

    coordinate_files = {
        kind: [(WORK / f"{kind}-{i:02d}.txt").open("w", encoding="utf-8") for i in range(29)]
        for kind in ("v", "vt", "vn")
    }
    remap = [{kind: {} for kind in ("v", "vt", "vn")} for _ in range(29)]
    counters = {kind: 0 for kind in ("v", "vt", "vn")}
    try:
        with SOURCE_OBJ.open(encoding="utf-8", errors="strict") as source:
            for line in source:
                kind = line.split(" ", 1)[0]
                if kind not in counters:
                    continue
                counters[kind] += 1
                old_index = counters[kind]
                for component in membership[kind].get(old_index, ()):
                    mapping = remap[component][kind]
                    mapping[old_index] = len(mapping) + 1
                    coordinate_files[kind][component].write(line)
    finally:
        for handles in coordinate_files.values():
            for handle in handles:
                handle.close()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    for component in range(29):
        target = OUTPUT / f"part-{component + 1:02d}.obj"
        with target.open("w", encoding="utf-8", newline="\n") as output:
            output.write(f"# ThermalForge textured exploded part part-{component + 1:02d}\n")
            output.write(f"o part-{component + 1:02d}\n")
            for kind in ("v", "vt", "vn"):
                with (WORK / f"{kind}-{component:02d}.txt").open(encoding="utf-8") as source:
                    shutil.copyfileobj(source, output)
            with (WORK / f"faces-{component:02d}.txt").open(encoding="utf-8") as faces:
                for line in faces:
                    converted = []
                    for vertex, uv, normal in parse_face(line):
                        v = remap[component]["v"][vertex]
                        vt = remap[component]["vt"].get(uv) if uv is not None else None
                        vn = remap[component]["vn"].get(normal) if normal is not None else None
                        converted.append(f"{v}/{vt or ''}/{vn or ''}")
                    output.write("f " + " ".join(converted) + "\n")
        print(target.name, target.stat().st_size)


if __name__ == "__main__":
    main()
