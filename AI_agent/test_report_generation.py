import tempfile
import unittest
from pathlib import Path

from docx import Document

from AI_agent.autofill import (
    DEFAULT_TEMPLATE,
    classify_la_max_volume_bsa,
    generate_non_stress_report,
)
from AI_agent.cvi42_parser import parse_cvi42_report


class Cvi42ParserTests(unittest.TestCase):
    def test_reads_lv_and_rv_metrics_and_metadata_without_cross_assignment(self):
        source = "\n".join(
            (
                "Patient\tExample",
                "Clinical Results LV",
                "EF\t61.4\t%",
                "EDV\t148.8\tml",
                "EDV/BSA\t98.2\tml/m2",
                "MyoMass_diast\t92.5\tg",
                "SAX 3D LV peak wall thickness",
                "all slices, diastolic phase:",
                "slice\tphase\tpeak wall thickness (mm)",
                "total peak wall thickness (all slices, diastolic phase):",
                "5\t25\t11.75",
                "Clinical Results RV",
                "EF\t63.2\t%",
                "EDV\t146.0\tml",
            )
        )

        parsed = parse_cvi42_report(source)

        self.assertEqual(parsed["study_info"]["patient"], "Example")
        self.assertEqual(parsed["lv"]["ejection_fraction_pct"], 61.4)
        self.assertEqual(parsed["lv"]["edv"]["value"], 148.8)
        self.assertEqual(parsed["lv"]["edv_bsa"], 98.2)
        self.assertEqual(parsed["lv"]["myomass_diast"], 92.5)
        self.assertEqual(parsed["lv"]["max_wall_thickness"], 11.75)
        self.assertEqual(parsed["rv"]["ejection_fraction_pct"], 63.2)
        self.assertEqual(parsed["rv"]["edv"]["value"], 146.0)

    def test_reads_real_export_measurements(self):
        source_path = Path(__file__).with_name(
            "AI_test_2026-09-22_Scientific_Report_2026-09-23.txt"
        )
        parsed = parse_cvi42_report(source_path.read_bytes().decode("utf-16"))

        self.assertAlmostEqual(parsed["lv"]["ejection_fraction_pct"], 61.358777)
        self.assertAlmostEqual(parsed["lv"]["edv"]["value"], 148.835882)
        self.assertAlmostEqual(parsed["lv"]["edv_bsa"], 98.228489)
        self.assertAlmostEqual(parsed["lv"]["max_wall_thickness"], 11.749346)
        self.assertAlmostEqual(parsed["lv"]["myomass_diast"], 92.479882)
        self.assertAlmostEqual(parsed["rv"]["ejection_fraction_pct"], 63.233172)
        self.assertAlmostEqual(parsed["rv"]["edv"]["value"], 146.034656)


class ReferenceRangeTests(unittest.TestCase):
    def test_classifies_la_indexed_volume_with_sex_and_age(self):
        self.assertEqual(classify_la_max_volume_bsa(54, "Female", 59), "Mildly enlarged")
        self.assertEqual(classify_la_max_volume_bsa(52, "Male", 40), "Normal")
        self.assertIsNone(classify_la_max_volume_bsa(54, "Female", 81))
        self.assertIsNone(classify_la_max_volume_bsa(54, None, 40))


class ReportGenerationTests(unittest.TestCase):
    def test_fills_template_and_preserves_template_structure(self):
        source = "\n".join(
            (
                "Patient\tExample",
                "Clinical Results LV",
                "EF\t61.4\t%",
                "EDV\t148.8\tml",
                "EDV/BSA\t98.2\tml/m2",
                "MyoMass_diast\t92.5\tg",
                "SAX 3D LV peak wall thickness",
                "total peak wall thickness (all slices, diastolic phase):",
                "5\t25\t11.75",
                "Clinical Results RV",
                "EF\t63.2\t%",
            )
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "measurements.txt"
            output_path = Path(temp_dir) / "report.docx"
            source_path.write_text(source, encoding="utf-8")

            generated = generate_non_stress_report(
                source_path, DEFAULT_TEMPLATE, output_path
            )

            template = Document(DEFAULT_TEMPLATE)
            output = Document(generated)
            self.assertEqual(len(output.paragraphs), len(template.paragraphs))
            self.assertEqual(len(output.tables), len(template.tables))
            for index in (3, 7):
                self.assertEqual(
                    output.paragraphs[index].runs[0].bold,
                    template.paragraphs[index].runs[0].bold,
                )
            output_text = "\n".join(p.text for p in output.paragraphs)
            self.assertNotIn("[]", output_text)
            self.assertIn("EF 61.4 %", output_text)
            self.assertIn("LV mass: 92.5 g", output_text)
            self.assertIn("maximum LV wall thickness: 11.8 mm", output_text)
            self.assertIn("volumes not reported", output_text)
            self.assertIn("LGE or infarct assessment not reported", output_text)
            self.assertEqual(output.tables[-1].cell(0, 0).text, "Height: Not provided")
            self.assertEqual(output.tables[-1].cell(0, 1).text, "cm")
            self.assertEqual(output.tables[-1].cell(0, 2).text, "Weight: Not provided")
            self.assertEqual(output.tables[-1].cell(0, 3).text, "kg")
            self.assertEqual(output.tables[-1].cell(0, 4).text, "BSA: 1.52 (derived)")
            self.assertEqual(output.tables[-1].cell(0, 5).text, "m2")


if __name__ == "__main__":
    unittest.main()
