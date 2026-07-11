"""Unit tests for the cold-plate channel translation plan."""

from __future__ import annotations

import importlib.util
import math
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("generate_solidworks_cold_plate.py")
SPEC = importlib.util.spec_from_file_location("cold_plate_generator", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load generator: {MODULE_PATH}")
GENERATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = GENERATOR
SPEC.loader.exec_module(GENERATOR)


class ChannelTranslationPlanTests(unittest.TestCase):
    def test_channel_walls_are_seed_copies_translated_by_pitch(self) -> None:
        boxes, _ = GENERATOR.build_geometry()

        seed, instances = GENERATOR.build_channel_translation_plan(boxes)

        self.assertEqual(seed.name, "Layer_2_Channel_Wall_001")
        self.assertEqual(len(instances), 139)
        for index, (box, offset_x_mm) in enumerate(instances):
            self.assertEqual(box.name, f"Layer_2_Channel_Wall_{index + 1:03d}")
            self.assertTrue(
                math.isclose(
                    offset_x_mm,
                    index * GENERATOR.CHANNEL_PITCH_MM,
                    rel_tol=0.0,
                    abs_tol=1e-9,
                )
            )
            self.assertTrue(
                math.isclose(
                    box.x0_mm,
                    seed.x0_mm + offset_x_mm,
                    rel_tol=0.0,
                    abs_tol=1e-9,
                )
            )
            self.assertEqual(
                (box.y0_mm, box.z0_mm, box.dx_mm, box.dy_mm, box.dz_mm),
                (seed.y0_mm, seed.z0_mm, seed.dx_mm, seed.dy_mm, seed.dz_mm),
            )

    def test_translation_matrix_uses_solidworks_layout_and_metre_units(self) -> None:
        matrix = GENERATOR.translation_matrix_x(0.2)

        self.assertEqual(len(matrix), 16)
        self.assertEqual(matrix[0:9], (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0))
        self.assertTrue(math.isclose(matrix[9], 0.0002, abs_tol=1e-12))
        self.assertEqual(matrix[10:13], (0.0, 0.0, 1.0))
        self.assertEqual(matrix[13:16], (0.0, 0.0, 0.0))

    def test_reopen_accepts_typed_opendoc6_tuple_result(self) -> None:
        class OpenedDocument:
            def GetPathName(self):
                return r"C:\temp\cold_plate.SLDPRT"

        expected_document = OpenedDocument()

        class TypedSolidWorks:
            def OpenDoc6(self, file_path, doc_type, options, configuration, errors, warnings):
                self.arguments = (
                    file_path,
                    doc_type,
                    options,
                    configuration,
                    errors,
                    warnings,
                )
                return expected_document, 0, 0

        solidworks = TypedSolidWorks()
        result = GENERATOR.open_part_document_compat(
            solidworks,
            Path("C:/temp/cold_plate.SLDPRT"),
        )

        self.assertIs(result, expected_document)
        self.assertEqual(solidworks.arguments[1:], (1, 0, "", 0, 0))

    def test_reopen_rejects_nonzero_solidworks_error(self) -> None:
        class OpenedDocument:
            def GetPathName(self):
                return r"C:\temp\cold_plate.SLDPRT"

        class TypedSolidWorks:
            def OpenDoc6(self, *args):
                return OpenedDocument(), 2, 0

        with self.assertRaisesRegex(RuntimeError, "errors=2"):
            GENERATOR.open_part_document_compat(
                TypedSolidWorks(),
                Path("C:/temp/cold_plate.SLDPRT"),
            )

    def test_dynamic_reopen_fallback_still_rejects_path_mismatch(self) -> None:
        class DynamicSolidWorks:
            def OpenDoc6(self, *args):
                raise TypeError("dynamic dispatch requires VARIANT by-ref arguments")

        class WrongDocument:
            def GetPathName(self):
                return r"C:\temp\wrong_part.SLDPRT"

        with (
            patch.object(GENERATOR, "open_document", return_value=WrongDocument()),
            self.assertRaisesRegex(RuntimeError, "unexpected document"),
        ):
            GENERATOR.open_part_document_compat(
                DynamicSolidWorks(),
                Path("C:/temp/cold_plate.SLDPRT"),
            )

    def test_dirty_generated_model_is_not_closed_for_reopen(self) -> None:
        class DirtyDocument:
            def GetSaveFlag(self):
                return True

        class SolidWorks:
            def __init__(self):
                self.closed_titles = []

            def CloseDoc(self, title):
                self.closed_titles.append(title)

        solidworks = SolidWorks()
        closed = GENERATOR.close_saved_model_for_reopen(
            solidworks,
            DirtyDocument(),
            Path("C:/temp/cold_plate.SLDPRT"),
        )

        self.assertFalse(closed)
        self.assertEqual(solidworks.closed_titles, [])

    def test_post_review_changes_are_saved_before_reopen(self) -> None:
        class DirtyDocument:
            def GetSaveFlag(self):
                return True

        model = DirtyDocument()
        with patch.object(GENERATOR, "save_document", return_value=True) as save:
            GENERATOR.save_post_review_state(model)

        save.assert_called_once_with(model)

    def test_channel_delay_must_be_finite_and_nonnegative(self) -> None:
        self.assertEqual(GENERATOR.validate_channel_delay_ms(20.0), 20.0)
        for invalid in (-1.0, math.nan, math.inf, -math.inf):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    GENERATOR.validate_channel_delay_ms(invalid)

    def test_progressive_build_creates_and_redraws_every_channel_wall(self) -> None:
        boxes, _ = GENERATOR.build_geometry()
        _, instances = GENERATOR.build_channel_translation_plan(boxes)
        model = object()
        events = []

        def record_create(*args):
            box = args[3]
            events.append(("create", box.name))
            return object()

        def record_redraw(redraw_model, delay_ms):
            events.append(("redraw", redraw_model, delay_ms))

        with (
            patch.object(
                GENERATOR,
                "create_translated_channel_feature",
                side_effect=record_create,
            ) as create_feature,
            patch.object(
                GENERATOR,
                "redraw_build_step",
                side_effect=record_redraw,
            ) as redraw,
        ):
            created = GENERATOR.create_progressive_channel_walls(
                seed_body=object(),
                math_utility=object(),
                part_doc=object(),
                instances=instances,
                model=model,
                delay_ms=20.0,
                first_body_index=6,
                total_body_count=149,
            )

        self.assertEqual(len(created), 139)
        self.assertEqual(create_feature.call_count, 139)
        self.assertEqual(redraw.call_count, 139)
        for index, (box, _) in enumerate(instances):
            self.assertEqual(events[index * 2], ("create", box.name))
            self.assertEqual(events[index * 2 + 1], ("redraw", model, 20.0))


if __name__ == "__main__":
    unittest.main()
