"""OBJ → GLB 转换：保留 object 分组，大幅减小文件体积和加载时间。"""
import os
import sys
import time

import trimesh

INPUT = r"C:\Users\llwxy\Desktop\thermalforge\frontend\public\models\robot-arm\base.obj"
OUTPUT = r"C:\Users\llwxy\Desktop\thermalforge\frontend\public\models\robot-arm\base.glb"

print(f"Loading: {INPUT}")
print(f"Input size: {os.path.getsize(INPUT) / 1024 / 1024:.1f} MB")

t0 = time.time()
scene = trimesh.load(INPUT, group_material=False, process=False)
t1 = time.time()
print(f"Load time: {t1 - t0:.1f}s")
print(f"Type: {type(scene).__name__}")

if isinstance(scene, trimesh.Scene):
    geoms = scene.geometry
    print(f"Geometries: {len(geoms)}")
    total_v = 0
    total_f = 0
    for name, geom in geoms.items():
        v = len(geom.vertices)
        f = len(geom.faces)
        total_v += v
        total_f += f
        print(f"  {name}: {v} verts, {f} faces")
    print(f"Total: {total_v} verts, {total_f} faces")
else:
    print(f"Single mesh: {len(scene.vertices)} verts, {len(scene.faces)} faces")

print(f"\nExporting GLB: {OUTPUT}")
t2 = time.time()
scene.export(OUTPUT, file_type="glb")
t3 = time.time()
print(f"Export time: {t3 - t2:.1f}s")
print(f"Output size: {os.path.getsize(OUTPUT) / 1024 / 1024:.1f} MB")
print(f"Compression ratio: {os.path.getsize(INPUT) / os.path.getsize(OUTPUT):.1f}x")
print("Done")
