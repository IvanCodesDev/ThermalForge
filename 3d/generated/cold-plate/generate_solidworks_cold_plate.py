"""Generate the SpaceClaim cold-plate geometry as a SOLIDWORKS multi-body part.

The geometry intentionally follows the supplied SpaceClaim script exactly:
149 independent rectangular solid bodies, including the 0.05 mm residual gap
at each side of the channel array. No fluid body is generated.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import winreg
from dataclasses import asdict, dataclass
from pathlib import Path

import pythoncom
from win32com.client import VARIANT, gencache, makepy


SKILL_DIR = Path("E:/skills/others/solidworks-automation")
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from sw_connect import (
    connect_solidworks,
    get_com_member,
    new_document,
    open_document,
    save_document,
)
from sw_export import export_to_step
from sw_review import run_review


LENGTH_X_MM = 30.0
LENGTH_Y_MM = 40.0
LAYER_1_MM = 2.0
LAYER_2_MM = 0.25
LAYER_3_MM = 1.0

CHANNEL_WIDTH_MM = 0.10
CHANNEL_GAP_MM = 0.10
CHANNEL_PITCH_MM = CHANNEL_WIDTH_MM + CHANNEL_GAP_MM

SIDE_WALL_X_MM = 1.0
EDGE_WALL_Y_MM = 0.50
MANIFOLD_LENGTH_MM = 4.0

CHANNEL_WALL_PREFIX = "Layer_2_Channel_Wall_"
DEFAULT_CHANNEL_DELAY_MS = 20.0
EXPECTED_BODY_COUNT = 149
EXPECTED_SOLID_VOLUME_MM3 = 3510.725
MM_TO_M = 0.001
GEOMETRY_TOLERANCE_MM = 1e-8
BODY_BOX_TOLERANCE_M = 1e-7

IMODELER_GUID = "{83A33D73-27C5-11CE-BFD4-00400513BB57}"
IPARTDOC_GUID = "{83A33D32-27C5-11CE-BFD4-00400513BB57}"
IMATHUTILITY_GUID = "{F7D97F80-162E-11D4-AEAB-00C04FA0AC51}"


@dataclass(frozen=True)
class BoxSpec:
    name: str
    layer: str
    x0_mm: float
    y0_mm: float
    z0_mm: float
    dx_mm: float
    dy_mm: float
    dz_mm: float

    @property
    def volume_mm3(self) -> float:
        return self.dx_mm * self.dy_mm * self.dz_mm

    @property
    def bounds_mm(self) -> tuple[float, float, float, float, float, float]:
        return (
            self.x0_mm,
            self.y0_mm,
            self.z0_mm,
            self.x0_mm + self.dx_mm,
            self.y0_mm + self.dy_mm,
            self.z0_mm + self.dz_mm,
        )

    @property
    def solidworks_box_data(self) -> tuple[float, ...]:
        """Return CreateBodyFromBox3 data: base center, axis, width, length, height."""
        return (
            (self.x0_mm + self.dx_mm / 2.0) * MM_TO_M,
            (self.y0_mm + self.dy_mm / 2.0) * MM_TO_M,
            self.z0_mm * MM_TO_M,
            0.0,
            0.0,
            1.0,
            self.dx_mm * MM_TO_M,
            self.dy_mm * MM_TO_M,
            self.dz_mm * MM_TO_M,
        )

    @property
    def expected_body_box_m(self) -> tuple[float, ...]:
        return tuple(value * MM_TO_M for value in self.bounds_mm)


def build_geometry() -> tuple[list[BoxSpec], dict]:
    z1 = 0.0
    z2 = LAYER_1_MM
    z3 = LAYER_1_MM + LAYER_2_MM
    z4 = LAYER_1_MM + LAYER_2_MM + LAYER_3_MM

    slot_x0 = SIDE_WALL_X_MM
    slot_x1 = LENGTH_X_MM - SIDE_WALL_X_MM
    slot_x_length = slot_x1 - slot_x0

    inlet_y0 = EDGE_WALL_Y_MM
    inlet_y1 = EDGE_WALL_Y_MM + MANIFOLD_LENGTH_MM
    outlet_y1 = LENGTH_Y_MM - EDGE_WALL_Y_MM
    outlet_y0 = outlet_y1 - MANIFOLD_LENGTH_MM
    channel_y0 = inlet_y1
    channel_y1 = outlet_y0
    channel_length = channel_y1 - channel_y0

    usable_x = slot_x_length
    channel_count = int((usable_x - CHANNEL_WIDTH_MM) / CHANNEL_PITCH_MM) + 1
    channel_band = (channel_count - 1) * CHANNEL_PITCH_MM + CHANNEL_WIDTH_MM
    channel_x_start = slot_x0 + (slot_x_length - channel_band) / 2.0
    channel_x_values = [
        channel_x_start + index * CHANNEL_PITCH_MM for index in range(channel_count)
    ]

    boxes: list[BoxSpec] = []

    def add(
        name: str,
        layer: str,
        x0: float,
        y0: float,
        z0: float,
        dx: float,
        dy: float,
        dz: float,
    ) -> None:
        boxes.append(BoxSpec(name, layer, x0, y0, z0, dx, dy, dz))

    add(
        "Layer_1_Base_Plate",
        "layer_1",
        0.0,
        0.0,
        z1,
        LENGTH_X_MM,
        LENGTH_Y_MM,
        LAYER_1_MM,
    )

    add(
        "Layer_2_Left_Frame",
        "layer_2",
        0.0,
        0.0,
        z2,
        slot_x0,
        LENGTH_Y_MM,
        LAYER_2_MM,
    )
    add(
        "Layer_2_Right_Frame",
        "layer_2",
        slot_x1,
        0.0,
        z2,
        LENGTH_X_MM - slot_x1,
        LENGTH_Y_MM,
        LAYER_2_MM,
    )
    add(
        "Layer_2_Bottom_End_Wall",
        "layer_2",
        slot_x0,
        0.0,
        z2,
        slot_x_length,
        EDGE_WALL_Y_MM,
        LAYER_2_MM,
    )
    add(
        "Layer_2_Top_End_Wall",
        "layer_2",
        slot_x0,
        outlet_y1,
        z2,
        slot_x_length,
        LENGTH_Y_MM - outlet_y1,
        LAYER_2_MM,
    )

    for index in range(channel_count - 1):
        add(
            f"Layer_2_Channel_Wall_{index + 1:03d}",
            "layer_2",
            channel_x_values[index] + CHANNEL_WIDTH_MM,
            channel_y0,
            z2,
            CHANNEL_GAP_MM,
            channel_length,
            LAYER_2_MM,
        )

    add(
        "Layer_3_Cover_Left_Block",
        "layer_3",
        0.0,
        0.0,
        z3,
        slot_x0,
        LENGTH_Y_MM,
        LAYER_3_MM,
    )
    add(
        "Layer_3_Cover_Right_Block",
        "layer_3",
        slot_x1,
        0.0,
        z3,
        LENGTH_X_MM - slot_x1,
        LENGTH_Y_MM,
        LAYER_3_MM,
    )
    add(
        "Layer_3_Cover_Bottom_Edge",
        "layer_3",
        slot_x0,
        0.0,
        z3,
        slot_x_length,
        inlet_y0,
        LAYER_3_MM,
    )
    add(
        "Layer_3_Cover_Center_Block",
        "layer_3",
        slot_x0,
        inlet_y1,
        z3,
        slot_x_length,
        outlet_y0 - inlet_y1,
        LAYER_3_MM,
    )
    add(
        "Layer_3_Cover_Top_Edge",
        "layer_3",
        slot_x0,
        outlet_y1,
        z3,
        slot_x_length,
        LENGTH_Y_MM - outlet_y1,
        LAYER_3_MM,
    )

    metadata = {
        "units": "mm",
        "overall_bounds_mm": [0.0, 0.0, 0.0, LENGTH_X_MM, LENGTH_Y_MM, z4],
        "channel_count": channel_count,
        "channel_wall_count": channel_count - 1,
        "channel_width_mm": CHANNEL_WIDTH_MM,
        "channel_gap_mm": CHANNEL_GAP_MM,
        "channel_pitch_mm": CHANNEL_PITCH_MM,
        "channel_length_mm": channel_length,
        "channel_x_start_mm": channel_x_start,
        "channel_x_last_mm": channel_x_values[-1],
        "channel_band_mm": channel_band,
        "edge_residual_each_mm": (slot_x_length - channel_band) / 2.0,
        "effective_edge_channel_width_mm": (
            CHANNEL_WIDTH_MM + (slot_x_length - channel_band) / 2.0
        ),
        "inlet_bounds_mm": [slot_x0, inlet_y0, z2, slot_x1, inlet_y1, z4],
        "outlet_bounds_mm": [slot_x0, outlet_y0, z2, slot_x1, outlet_y1, z4],
        "fluid_body_generated": False,
    }
    return boxes, metadata


def build_channel_translation_plan(
    boxes: list[BoxSpec],
) -> tuple[BoxSpec, list[tuple[BoxSpec, float]]]:
    """Describe every channel wall as an X translation of the first wall."""
    indexed_walls = [
        (index, box)
        for index, box in enumerate(boxes)
        if box.name.startswith(CHANNEL_WALL_PREFIX)
    ]
    if not indexed_walls:
        raise ValueError("No channel-wall bodies found")

    indices = [index for index, _ in indexed_walls]
    if indices != list(range(indices[0], indices[0] + len(indices))):
        raise ValueError("Channel-wall bodies must be contiguous in the build order")

    seed = indexed_walls[0][1]
    instances: list[tuple[BoxSpec, float]] = []
    seed_shape = (seed.y0_mm, seed.z0_mm, seed.dx_mm, seed.dy_mm, seed.dz_mm)
    for sequence, (_, box) in enumerate(indexed_walls):
        shape = (box.y0_mm, box.z0_mm, box.dx_mm, box.dy_mm, box.dz_mm)
        if shape != seed_shape:
            raise ValueError(f"Channel wall is not a translated seed copy: {box.name}")

        offset_x_mm = box.x0_mm - seed.x0_mm
        expected_offset_mm = sequence * CHANNEL_PITCH_MM
        if not math.isclose(
            offset_x_mm,
            expected_offset_mm,
            rel_tol=0.0,
            abs_tol=GEOMETRY_TOLERANCE_MM,
        ):
            raise ValueError(
                f"Unexpected channel-wall pitch at {box.name}: "
                f"{offset_x_mm} != {expected_offset_mm}"
            )
        instances.append((box, offset_x_mm))

    return seed, instances


def translation_matrix_x(offset_x_mm: float) -> tuple[float, ...]:
    """Return a 16-value SOLIDWORKS transform for an X translation."""
    return (
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        offset_x_mm * MM_TO_M,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
    )


def validate_channel_delay_ms(delay_ms: float) -> float:
    """Reject delays that could hang animation or produce invalid JSON."""
    if not math.isfinite(delay_ms) or delay_ms < 0:
        raise ValueError("channel_delay_ms must be finite and zero or greater")
    return delay_ms


def boxes_overlap_with_positive_volume(left: BoxSpec, right: BoxSpec) -> bool:
    a = left.bounds_mm
    b = right.bounds_mm
    return all(
        min(a[axis + 3], b[axis + 3]) - max(a[axis], b[axis])
        > GEOMETRY_TOLERANCE_MM
        for axis in range(3)
    )


def validate_geometry(boxes: list[BoxSpec], metadata: dict) -> None:
    if len(boxes) != EXPECTED_BODY_COUNT:
        raise ValueError(f"Expected {EXPECTED_BODY_COUNT} boxes, got {len(boxes)}")
    if len({box.name for box in boxes}) != len(boxes):
        raise ValueError("Feature names must be unique")

    overall = metadata["overall_bounds_mm"]
    for box in boxes:
        if min(box.dx_mm, box.dy_mm, box.dz_mm) <= 0:
            raise ValueError(f"Non-positive box dimension: {box}")
        bounds = box.bounds_mm
        for axis in range(3):
            if bounds[axis] < overall[axis] - GEOMETRY_TOLERANCE_MM:
                raise ValueError(f"{box.name} starts outside the overall envelope")
            if bounds[axis + 3] > overall[axis + 3] + GEOMETRY_TOLERANCE_MM:
                raise ValueError(f"{box.name} ends outside the overall envelope")

    for left_index, left in enumerate(boxes):
        for right in boxes[left_index + 1 :]:
            if boxes_overlap_with_positive_volume(left, right):
                raise ValueError(f"Unexpected solid overlap: {left.name} / {right.name}")

    solid_volume = sum(box.volume_mm3 for box in boxes)
    if not math.isclose(
        solid_volume,
        EXPECTED_SOLID_VOLUME_MM3,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise ValueError(
            f"Unexpected solid volume: {solid_volume} != {EXPECTED_SOLID_VOLUME_MM3}"
        )

    expected_index_names = {
        0: "Layer_1_Base_Plate",
        5: "Layer_2_Channel_Wall_001",
        143: "Layer_2_Channel_Wall_139",
        144: "Layer_3_Cover_Left_Block",
        145: "Layer_3_Cover_Right_Block",
        146: "Layer_3_Cover_Bottom_Edge",
        147: "Layer_3_Cover_Center_Block",
        148: "Layer_3_Cover_Top_Edge",
    }
    for index, expected_name in expected_index_names.items():
        if boxes[index].name != expected_name:
            raise ValueError(
                f"Body ordering mismatch at {index}: {boxes[index].name} != {expected_name}"
            )


def get_body_box(body) -> tuple[float, ...]:
    values = get_com_member(body, "GetBodyBox")
    if values is None or len(values) != 6:
        raise RuntimeError("SOLIDWORKS did not return a valid body bounding box")
    return tuple(float(value) for value in values)


def verify_box(actual: tuple[float, ...], expected: tuple[float, ...], name: str) -> None:
    errors = [abs(actual[index] - expected[index]) for index in range(6)]
    if max(errors) > BODY_BOX_TOLERANCE_M:
        raise RuntimeError(
            f"Body bounds mismatch for {name}: actual={actual}, expected={expected}"
        )


def find_solidworks_typelib() -> Path:
    """Locate sldworks.tlb beside the registered SOLIDWORKS executable."""
    with winreg.OpenKey(
        winreg.HKEY_CLASSES_ROOT,
        r"SldWorks.Application\CLSID",
    ) as key:
        application_clsid = winreg.QueryValueEx(key, "")[0]

    with winreg.OpenKey(
        winreg.HKEY_CLASSES_ROOT,
        rf"CLSID\{application_clsid}\LocalServer32",
    ) as key:
        command = str(winreg.QueryValueEx(key, "")[0]).strip()

    match = re.match(r'^\s*"([^"]+\.exe)"', command, flags=re.IGNORECASE)
    if match is None:
        match = re.match(r"^\s*(.+?\.exe)(?:\s|$)", command, flags=re.IGNORECASE)
    if match is None:
        raise RuntimeError(f"Cannot parse SOLIDWORKS executable path: {command}")

    typelib = Path(match.group(1)).with_name("sldworks.tlb")
    if not typelib.is_file():
        raise FileNotFoundError(f"SOLIDWORKS type library not found: {typelib}")
    return typelib


def generated_interface(interface_guid: str, interface_name: str):
    """Load a typed pywin32 wrapper for an interface without relying on IDispatch names."""
    try:
        module = gencache.GetModuleForCLSID(interface_guid)
    except Exception:
        module = None

    if module is None or not hasattr(module, interface_name):
        makepy.GenerateFromTypeLibSpec(
            str(find_solidworks_typelib()),
            bForDemand=1,
        )
        module = gencache.GetModuleForCLSID(interface_guid)

    interface_class = getattr(module, interface_name, None)
    if interface_class is None:
        raise RuntimeError(f"Unable to load typed SOLIDWORKS interface: {interface_name}")
    return interface_class


def typed_solidworks_interfaces(sw, model):
    """Wrap type-info-less IModeler and IPartDoc dispatch objects."""
    raw_modeler = get_com_member(sw, "GetModeler")
    if raw_modeler is None or not hasattr(raw_modeler, "_oleobj_"):
        raise RuntimeError("SOLIDWORKS GetModeler returned an invalid COM object")
    if not hasattr(model, "_oleobj_"):
        raise RuntimeError("SOLIDWORKS part document returned an invalid COM object")

    modeler_class = generated_interface(IMODELER_GUID, "IModeler")
    part_doc_class = generated_interface(IPARTDOC_GUID, "IPartDoc")
    return (
        modeler_class(raw_modeler._oleobj_),
        part_doc_class(model._oleobj_),
    )


def typed_math_utility(sw):
    """Wrap the type-info-less SOLIDWORKS MathUtility object."""
    raw_math_utility = get_com_member(sw, "GetMathUtility")
    if raw_math_utility is None or not hasattr(raw_math_utility, "_oleobj_"):
        raise RuntimeError("SOLIDWORKS GetMathUtility returned an invalid COM object")
    math_utility_class = generated_interface(IMATHUTILITY_GUID, "IMathUtility")
    return math_utility_class(raw_math_utility._oleobj_)


def create_temporary_box_body(modeler, box: BoxSpec):
    """Create and validate one temporary rectangular body."""
    box_data = VARIANT(
        pythoncom.VT_ARRAY | pythoncom.VT_R8,
        box.solidworks_box_data,
    )
    temporary_body = modeler.CreateBodyFromBox3(box_data)
    if temporary_body is None:
        temporary_body = modeler.CreateBodyFromBox(box_data)

    if temporary_body is None:
        raise RuntimeError(f"Failed to create temporary body: {box.name}")

    verify_box(get_body_box(temporary_body), box.expected_body_box_m, box.name)
    return temporary_body


def import_temporary_body(part_doc, temporary_body, box: BoxSpec):
    """Import a temporary body into the part and assign its feature name."""
    feature = part_doc.CreateFeatureFromBody3(temporary_body, False, 1)
    if feature is None:
        raise RuntimeError(f"Failed to import temporary body: {box.name}")
    feature.Name = box.name
    return feature


def create_box_feature(modeler, part_doc, box: BoxSpec):
    """Create a standalone box body and import it into the part."""
    temporary_body = create_temporary_box_body(modeler, box)
    return import_temporary_body(part_doc, temporary_body, box)


def create_translation_transform(math_utility, offset_x_mm: float):
    """Create a typed SOLIDWORKS MathTransform for an X translation."""
    transform_data = VARIANT(
        pythoncom.VT_ARRAY | pythoncom.VT_R8,
        translation_matrix_x(offset_x_mm),
    )
    transform = math_utility.CreateTransform(transform_data)
    if transform is None:
        raise RuntimeError(f"Failed to create X translation: {offset_x_mm} mm")
    return transform


def create_translated_channel_feature(
    seed_body,
    math_utility,
    part_doc,
    box: BoxSpec,
    offset_x_mm: float,
):
    """Copy the seed wall, translate the copy, and import it as a body feature."""
    translated_body = get_com_member(seed_body, "Copy")
    if translated_body is None:
        raise RuntimeError(f"Failed to copy channel-wall seed for {box.name}")

    if not math.isclose(offset_x_mm, 0.0, abs_tol=GEOMETRY_TOLERANCE_MM):
        transform = create_translation_transform(math_utility, offset_x_mm)
        transformed = get_com_member(translated_body, "ApplyTransform", transform)
        if not transformed:
            raise RuntimeError(f"Failed to translate channel wall: {box.name}")

    verify_box(get_body_box(translated_body), box.expected_body_box_m, box.name)
    return import_temporary_body(part_doc, translated_body, box)


def redraw_build_step(model, delay_ms: float) -> None:
    """Force a visible graphics update, then pause briefly for progressive drawing."""
    get_com_member(model, "GraphicsRedraw2")
    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)


def create_progressive_channel_walls(
    seed_body,
    math_utility,
    part_doc,
    instances: list[tuple[BoxSpec, float]],
    model,
    delay_ms: float,
    first_body_index: int,
    total_body_count: int,
) -> list:
    """Translate, import, and visibly redraw every channel-wall instance."""
    created_features = []
    for sequence, (box, offset_x_mm) in enumerate(instances, start=1):
        feature = create_translated_channel_feature(
            seed_body,
            math_utility,
            part_doc,
            box,
            offset_x_mm,
        )
        created_features.append(feature)
        redraw_build_step(model, delay_ms)
        total_index = first_body_index + sequence - 1
        if sequence == 1 or sequence % 10 == 0 or sequence == len(instances):
            print(
                f"Translated channel wall {sequence}/{len(instances)} "
                f"(body {total_index}/{total_body_count}): {box.name}",
                flush=True,
            )
    return created_features


def close_clean_output_document(sw, part_path: Path) -> bool:
    """Close an already-open generated part, but never discard unsaved edits."""
    open_model = get_com_member(sw, "GetOpenDocumentByName", str(part_path))
    if open_model is None:
        return False

    if bool(get_com_member(open_model, "GetSaveFlag")):
        raise RuntimeError(
            "The output part is already open with unsaved changes. "
            "Save or close it manually before using --overwrite."
        )

    title = get_com_member(open_model, "GetTitle")
    sw.CloseDoc(title)
    print(f"Closed clean output document before rebuild: {title}", flush=True)
    return True


def normalized_path(path: str | Path) -> str:
    """Normalize a local Windows path for case-insensitive comparisons."""
    return str(Path(path).resolve()).casefold()


def close_saved_model_for_reopen(sw, model, part_path: Path) -> bool:
    """Close the generated model only when doing so cannot discard edits."""
    if bool(get_com_member(model, "GetSaveFlag")):
        print(
            "Skipped final reopen because the generated model has unsaved changes.",
            flush=True,
        )
        return False

    actual_path = get_com_member(model, "GetPathName")
    if normalized_path(actual_path) != normalized_path(part_path):
        raise RuntimeError(
            f"Refusing to close unexpected document: {actual_path or '<unsaved>'}"
        )

    title = get_com_member(model, "GetTitle")
    sw.CloseDoc(title)
    if get_com_member(sw, "GetOpenDocumentByName", str(part_path)) is not None:
        raise RuntimeError(f"SOLIDWORKS did not close generated part: {part_path}")
    return True


def save_post_review_state(model) -> None:
    """Persist review view changes so final close cannot discard document state."""
    if bool(get_com_member(model, "GetSaveFlag")) and not save_document(model):
        raise RuntimeError("Failed to save post-review SOLIDWORKS document state")


def open_part_document_compat(sw, part_path: Path):
    """Open a part with both typed and dynamic pywin32 dispatch wrappers."""
    errors = 0
    warnings = 0
    try:
        result = sw.OpenDoc6(str(part_path), 1, 0, "", 0, 0)
    except TypeError:
        model = open_document(
            sw,
            str(part_path),
            read_only=False,
            silent=False,
            raise_on_error=True,
        )
    else:
        if isinstance(result, tuple):
            model, errors, warnings = result
        else:
            model = result
    if model is None or errors:
        raise RuntimeError(
            f"Failed to reopen generated part; errors={errors}, warnings={warnings}"
        )

    actual_path = get_com_member(model, "GetPathName")
    if normalized_path(actual_path) != normalized_path(part_path):
        raise RuntimeError(
            f"SOLIDWORKS reopened an unexpected document: {actual_path or '<unknown>'}"
        )
    if warnings:
        print(f"Reopened generated part with warning code {warnings}", flush=True)
    print(f"Reopened generated part: {part_path}", flush=True)
    return model


def aggregate_model_bounds(bodies: list) -> tuple[float, ...]:
    boxes = [get_body_box(body) for body in bodies]
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        min(box[2] for box in boxes),
        max(box[3] for box in boxes),
        max(box[4] for box in boxes),
        max(box[5] for box in boxes),
    )


def output_paths(output_dir: Path) -> dict[str, Path]:
    stem = "layered_microchannel_cold_plate_as_coded"
    return {
        "part": output_dir / f"{stem}.SLDPRT",
        "step": output_dir / f"{stem}.step",
        "manifest": output_dir / f"{stem}_geometry.json",
        "review_dir": output_dir / "review",
    }


def ensure_outputs_available(paths: dict[str, Path], overwrite: bool) -> None:
    existing = [
        str(path)
        for key, path in paths.items()
        if key != "review_dir" and path.exists()
    ]
    if paths["review_dir"].exists():
        existing.append(str(paths["review_dir"]))
    if existing and not overwrite:
        raise FileExistsError(
            "Refusing to overwrite existing outputs:\n" + "\n".join(existing)
        )


def write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def generate(
    output_dir: Path,
    overwrite: bool = False,
    channel_delay_ms: float = DEFAULT_CHANNEL_DELAY_MS,
    reopen_output: bool = True,
) -> dict:
    boxes, metadata = build_geometry()
    validate_geometry(boxes, metadata)
    channel_delay_ms = validate_channel_delay_ms(channel_delay_ms)

    output_dir = output_dir.resolve()
    paths = output_paths(output_dir)
    ensure_outputs_available(paths, overwrite)
    output_dir.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    sw, _ = connect_solidworks(wait_seconds=2, visible=True)
    try:
        sw.UserControl = True
    except Exception:
        pass

    if overwrite:
        close_clean_output_document(sw, paths["part"])

    model = new_document(sw, "part")
    modeler, part_doc = typed_solidworks_interfaces(sw, model)
    math_utility = typed_math_utility(sw)

    channel_seed, channel_instances = build_channel_translation_plan(boxes)
    first_channel_index = boxes.index(channel_seed)
    after_channel_index = first_channel_index + len(channel_instances)

    for index, box in enumerate(boxes[:first_channel_index], start=1):
        create_box_feature(modeler, part_doc, box)
        print(f"Created {index}/{len(boxes)}: {box.name}", flush=True)

    model.ShowNamedView2("", 7)
    model.ViewZoomtofit2()
    redraw_build_step(model, channel_delay_ms)

    print(
        f"Translating {len(channel_instances)} channel walls "
        f"at {CHANNEL_PITCH_MM:.3f} mm pitch...",
        flush=True,
    )
    channel_seed_body = create_temporary_box_body(modeler, channel_seed)
    create_progressive_channel_walls(
        seed_body=channel_seed_body,
        math_utility=math_utility,
        part_doc=part_doc,
        instances=channel_instances,
        model=model,
        delay_ms=channel_delay_ms,
        first_body_index=first_channel_index + 1,
        total_body_count=len(boxes),
    )

    for index, box in enumerate(
        boxes[after_channel_index:],
        start=after_channel_index + 1,
    ):
        create_box_feature(modeler, part_doc, box)
        redraw_build_step(model, channel_delay_ms)
        print(f"Created {index}/{len(boxes)}: {box.name}", flush=True)

    model.ForceRebuild3(False)
    bodies = list(part_doc.GetBodies2(0, False) or [])
    if len(bodies) != EXPECTED_BODY_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_BODY_COUNT} independent bodies, got {len(bodies)}"
        )

    missing_features = [
        box.name for box in boxes if get_com_member(model, "FeatureByName", box.name) is None
    ]
    if missing_features:
        raise RuntimeError("Missing named features: " + ", ".join(missing_features))

    actual_bounds_m = aggregate_model_bounds(bodies)
    expected_bounds_m = tuple(
        value * MM_TO_M for value in metadata["overall_bounds_mm"]
    )
    verify_box(actual_bounds_m, expected_bounds_m, "overall model")

    if not save_document(model, str(paths["part"])):
        raise RuntimeError("Failed to save SOLIDWORKS part")
    if not export_to_step(model, str(paths["step"])):
        raise RuntimeError("Failed to export STEP")

    model.ForceRebuild3(False)
    model.ViewZoomtofit2()

    review_error = None
    review_status = None
    review_report_path = None
    try:
        review_report, review_report_path = run_review(
            model,
            paths["review_dir"],
            basename="cold_plate",
            expected_outputs=[str(paths["part"]), str(paths["step"])],
        )
        review_status = review_report.get("evaluation", {}).get("status")
    except Exception as exc:
        review_error = str(exc)

    if review_error:
        raise RuntimeError(f"SOLIDWORKS review failed: {review_error}")
    if review_status != "pass":
        raise RuntimeError(f"SOLIDWORKS review did not pass: {review_status}")

    reopened_output = False
    reopen_skipped_dirty = False
    if reopen_output:
        save_post_review_state(model)
        if close_saved_model_for_reopen(sw, model, paths["part"]):
            model = open_part_document_compat(sw, paths["part"])
            model.ShowNamedView2("", 7)
            model.ViewZoomtofit2()
            model.GraphicsRedraw2()
            reopened_output = True
        else:
            reopen_skipped_dirty = True

    elapsed = time.perf_counter() - started
    result = {
        **metadata,
        "generator": (
            "SOLIDWORKS seed-body Copy + ApplyTransform + CreateFeatureFromBody3"
        ),
        "channel_generation_method": "seed_copy_x_translation",
        "channel_delay_ms": channel_delay_ms,
        "reopened_output": reopened_output,
        "reopen_skipped_dirty": reopen_skipped_dirty,
        "expected_body_count": EXPECTED_BODY_COUNT,
        "actual_body_count": len(bodies),
        "solid_volume_mm3": sum(box.volume_mm3 for box in boxes),
        "actual_bounds_m": actual_bounds_m,
        "feature_names": [box.name for box in boxes],
        "boxes": [asdict(box) for box in boxes],
        "outputs": {
            "part": str(paths["part"]),
            "step": str(paths["step"]),
            "review_report": str(review_report_path) if review_report_path else None,
        },
        "file_sizes_bytes": {
            "part": paths["part"].stat().st_size if paths["part"].exists() else 0,
            "step": paths["step"].stat().st_size if paths["step"].exists() else 0,
        },
        "review_status": review_status,
        "review_error": review_error,
        "elapsed_seconds": round(elapsed, 3),
    }
    write_manifest(paths["manifest"], result)
    print(json.dumps(result["outputs"], ensure_ascii=False, indent=2))
    print(
        f"Generated {len(bodies)} bodies in {elapsed:.1f}s; "
        f"review={review_status or 'not available'}"
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the supplied layer-by-layer cold plate in SOLIDWORKS."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Output directory for SLDPRT, STEP, manifest, and review files.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting existing generated outputs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print geometry without connecting to SOLIDWORKS.",
    )
    parser.add_argument(
        "--channel-delay-ms",
        type=float,
        default=DEFAULT_CHANNEL_DELAY_MS,
        help=(
            "Pause after each translated channel wall so SOLIDWORKS draws "
            f"progressively (default: {DEFAULT_CHANNEL_DELAY_MS:g} ms; 0 disables)."
        ),
    )
    parser.add_argument(
        "--no-reopen",
        action="store_true",
        help="Do not close and reopen the saved part after review.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    boxes, metadata = build_geometry()
    validate_geometry(boxes, metadata)
    if args.dry_run:
        print(
            json.dumps(
                {
                    **metadata,
                    "body_count": len(boxes),
                    "solid_volume_mm3": sum(box.volume_mm3 for box in boxes),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    generate(
        args.output_dir,
        overwrite=args.overwrite,
        channel_delay_ms=args.channel_delay_ms,
        reopen_output=not args.no_reopen,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
