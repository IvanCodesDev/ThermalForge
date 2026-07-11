"""OBJ → GLB 转换（保留 object 分组）：按 o 定义拆分为多个 mesh。"""
import sys
import time
import os
import numpy as np
import trimesh

INPUT = r"C:\Users\llwxy\Downloads\base.obj"
OUTPUT = r"C:\Users\llwxy\Desktop\thermalforge\frontend\public\models\robot-arm\base.glb"

print(f"Parsing OBJ: {INPUT}")
print(f"Input size: {os.path.getsize(INPUT) / 1024 / 1024:.1f} MB")

t0 = time.time()

vertices: list[list[float]] = []
objects: dict[str, list[list[int]]] = {}
current_obj = None

with open(INPUT, "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        if line.startswith("o "):
            current_obj = line[2:].strip()
            objects[current_obj] = []
        elif line.startswith("v "):
            parts = line[2:].strip().split()
            vertices.append([float(parts[0]), float(parts[1]), float(parts[2])])
        elif line.startswith("f "):
            if current_obj is not None:
                face = [int(p.split("/")[0]) - 1 for p in line[2:].strip().split()]
                objects[current_obj].append(face)

t1 = time.time()
print(f"Parse time: {t1 - t0:.1f}s")
print(f"Vertices: {len(vertices)}")
print(f"Objects: {len(objects)}")

vert_array = np.array(vertices, dtype=np.float32)
meshes: list[trimesh.Trimesh] = []

for name, faces in objects.items():
    if not faces:
        continue
    face_array = np.array(faces, dtype=np.int32)
    mesh = trimesh.Trimesh(vertices=vert_array, faces=face_array, process=False)
    mesh.metadata["name"] = name
    meshes.append(mesh)
    print(f"  {name}: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")

print(f"\nTotal meshes: {len(meshes)}")

scene = trimesh.Scene(meshes)
print(f"Exporting GLB: {OUTPUT}")
t2 = time.time()
scene.export(OUTPUT, file_type="glb")
t3 = time.time()
print(f"Export time: {t3 - t2:.1f}s")
print(f"Output size: {os.path.getsize(OUTPUT) / 1024 / 1024:.1f} MB")
print(f"Compression: {os.path.getsize(INPUT) / os.path.getsize(OUTPUT):.1f}x")
print("Done")
