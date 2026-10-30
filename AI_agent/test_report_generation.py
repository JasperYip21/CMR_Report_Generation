import tempfile
import unittest
from pathlib import Path

from docx import Document

from AI_agent.autofill import (
    DEFAULT_INPUT,
    DEFAULT_TEMPLATE,
    classify_report_measurements,
    generate_non_stress_report,
)
from AI_agent.clinical_pdf_parser import parse_clinical_report_pdf, parse_clinical_report_text
from AI_agent.cvi42_parser import parse_cvi42_report
from AI_agent.reference_ranges import (
    atrial_max_volume_interval,
    atrial_reference_interval,
    select_reference_profile,
)


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

    def test_extracts_supported_fields_from_supplied_clinical_pdf(self):
        parsed = parse_clinical_report_pdf(DEFAULT_INPUT)

        self.assertEqual(parsed["study_info"]["sex"], "Female")
        self.assertEqual(parsed["study_info"]["age"], 82)
        self.assertEqual(parsed["study_info"]["height_cm"], 145)
        self.assertEqual(parsed["study_info"]["weight_kg"], 57.0)
        self.assertEqual(parsed["study_info"]["bsa_m2"], 1.52)
        self.assertAlmostEqual(parsed["aorta"]["sinus_line_measurement_cm"], 2.67)
        self.assertAlmostEqual(parsed["pulmonary_artery"]["main_line_measurement_cm"], 3.323)
        self.assertAlmostEqual(parsed["la"]["contour_area_cm2"], 31.477)
        self.assertAlmostEqual(parsed["ra"]["contour_area_cm2"], 17.078)
        self.assertAlmostEqual(parsed["lv"]["ejection_fraction_pct"], 61.359)
        self.assertAlmostEqual(parsed["lv"]["edv_bsa"], 98.228)
        self.assertAlmostEqual(parsed["lv"]["myomass_bsa"], 61.035)
        self.assertAlmostEqual(parsed["lv"]["max_wall_thickness"], 11.438)
        self.assertAlmostEqual(parsed["rv"]["ejection_fraction_pct"], 63.233)
        self.assertAlmostEqual(parsed["rv"]["edv"]["value"], 146.035)
        self.assertAlmostEqual(parsed["rv"]["edv_bsa"], 96.380)

    def test_text_parser_handles_inline_layout_variations(self):
        parsed = parse_clinical_report_text(
            "Patient Sex Male    Study Date: 2026-04-03\n"
            "Age 45 years\nHeight : 175 cm\nWeight : 78 kg\nBSA : 1.92 m2\n"
            "SAX 3D Stack LV Function\nEDV 120.0 ml\nESV : 48.0 ml\n"
            "SV : 72 ml\nEF = 60 %\nEDV/BSA : 62.5 ml/m2\n"
            "ESV/BSA : 25 ml/m2\nSV/BSA : 37.5 ml/m2\n"
            "Myo Mass (Diast) : 110 g\nMyo Mass/BSA 57 g/m2\n"
            "SAX3D Stack RV Function\nRVEDV : 130 ml\nRVESV : 50 ml\n"
            "RVSV : 80 ml\nRVEF : 61 %\nRVEDV/BSA : 67.7 ml/m2\n"
        )

        self.assertEqual(parsed["study_info"]["sex"], "Male")
        self.assertEqual(parsed["study_info"]["age"], 45)
        self.assertEqual(parsed["study_info"]["bsa_m2"], 1.92)
        self.assertEqual(parsed["lv"]["edv"]["value"], 120)
        self.assertEqual(parsed["lv"]["ejection_fraction_pct"], 60)
        self.assertEqual(parsed["lv"]["edv_bsa"], 62.5)
        self.assertEqual(parsed["lv"]["myomass_diast"], 110)
        self.assertEqual(parsed["lv"]["myomass_bsa"], 57)
        self.assertEqual(parsed["rv"]["edv"]["value"], 130)
        self.assertEqual(parsed["rv"]["ejection_fraction_pct"], 61)

    def test_extracts_only_unambiguous_explicit_atrial_views(self):
        parsed = parse_clinical_report_text(
            "LA 4ch Area: 28 cm2\nLA 4ch Area: 28 cm2\n"
            "LA 4ch Area/BSA: 14.0 cm2/m2\n"
            "RA 4ch Area: 25 cm2"
        )
        self.assertEqual(parsed["la"]["area_view"], "4ch")
        self.assertEqual(parsed["la"]["area_cm2"], 28)
        self.assertEqual(parsed["la"]["area_bsa"], 14)
        self.assertEqual(parsed["ra"]["area_view"], "4ch")

        conflicting = parse_clinical_report_text(
            "LA 4ch Area: 20 cm2\nLA 4ch Area: 28 cm2"
        )
        self.assertNotIn("area_view", conflicting["la"])

    def test_conflicting_repeated_demographics_and_metrics_are_not_guessed(self):
        parsed = parse_clinical_report_text(
            "Patient Sex: Female\nPatient Sex: Male\nAge: 42 years\nAge: 47 years\n"
            "SAX3D Stack LV Function\nEDV: 120 ml\nEDV: 130 ml\n"
        )

        self.assertNotIn("sex", parsed["study_info"])
        self.assertNotIn("age", parsed["study_info"])
        self.assertNotIn("edv", parsed["lv"])


class ReferenceRangeTests(unittest.TestCase):
    def test_selects_sex_age_and_ethnicity_specific_profiles(self):
        cases = {
            ("Female", 12, None): "female_8_17",
            ("Male", 17, None): "male_8_17",
            ("F", 18, None): "female_under_60",
            ("Male", 59, None): "male_under_60",
            ("Female", 60, None): "female_60_plus",
            ("Male", 90, None): "male_60_plus",
            ("Female", 45, "Chinese"): "female_chinese",
            ("M", 30, "Chinese"): "male_chinese",
            ("Female", 45, "Non-Chinese"): "female_under_60",
        }
        for (sex, age, ethnicity), expected in cases.items():
            with self.subTest(sex=sex, age=age, ethnicity=ethnicity):
                self.assertEqual(
                    select_reference_profile(
                        {"sex": sex, "age": age, "ethnicity": ethnicity}
                    ),
                    expected,
                )
        self.assertIsNone(select_reference_profile({"sex": "Female", "age": 7}))
        self.assertIsNone(select_reference_profile({"sex": "Female", "age": 17.5}))
        self.assertIsNone(select_reference_profile({"sex": "Unknown", "age": 45}))
        self.assertIsNone(select_reference_profile({"sex": "Male", "age": None}))
        self.assertIsNone(
            select_reference_profile(
                {"sex": "Female", "age": 17, "ethnicity": "Chinese"}
            )
        )

    def test_classifies_sample_using_its_matched_female_60_plus_profile(self):
        parsed = parse_clinical_report_pdf(DEFAULT_INPUT)
        classifications = classify_report_measurements(parsed)

        self.assertEqual(
            classifications,
            {
                "Left Atrium": [None],
                "Right Atrium": [None],
                "Left Ventricle": ["abnormal", "normal", None, "normal"],
                "Right Ventricle": ["abnormal"],
                "Conclusion": ["abnormal", None],
            },
        )

    def test_does_not_classify_when_sex_or_age_reference_does_not_match(self):
        data = {
            "study_info": {"sex": "Female", "age": 59},
            "lv": {
                "edv": {"value": 148.8},
                "esv": {"value": 40},
                "sv": {"value": 90},
                "ejection_fraction_pct": 60,
                "myomass_diast": 100,
            },
            "rv": {
                "edv": {"value": 100},
                "esv": {"value": 30},
                "sv": {"value": 70},
                "ejection_fraction_pct": 60,
            },
        }

        classifications = classify_report_measurements(data)
        self.assertTrue(classifications)
        self.assertIsNone(classifications["Left Ventricle"][0])
        self.assertIsNone(classifications["Right Ventricle"][0])
        self.assertIsNone(classifications["Conclusion"][0])

        data["study_info"] = {"sex": "Male", "age": 82}
        self.assertEqual(classify_report_measurements(data)["Left Ventricle"], [None, None, None, None])

    def test_requires_full_profile_metrics_before_calling_ventricle_normal(self):
        data = {
            "study_info": {"sex": "Female", "age": 59},
            "lv": {
                "edv": {"value": 120},
                "edv_bsa": 70,
                "esv": {"value": 40},
                "sv": {"value": 80},
                "ejection_fraction_pct": 66,
                "myomass_diast": 100,
                "myomass_bsa": 52,
            },
            "rv": {
                "edv": {"value": 120},
                "edv_bsa": 70,
                "esv": {"value": 40},
                "sv": {"value": 80},
                "ejection_fraction_pct": 60,
            },
        }
        classifications = classify_report_measurements(data)

        self.assertEqual(classifications["Left Ventricle"], ["normal", "normal", None, "normal"])
        self.assertEqual(classifications["Right Ventricle"], ["normal"])
        self.assertEqual(classifications["Conclusion"], ["normal", None])

    def test_missing_metric_keeps_combined_classification_unsupported(self):
        data = {
            "study_info": {"sex": "Female", "age": 60},
            "lv": {
                "edv": {"value": 120},
                "edv_bsa": 70,
                "esv": {"value": 40},
                "sv": {"value": 80},
                "ejection_fraction_pct": 66,
                "myomass_diast": 100,
                "myomass_bsa": 52,
            },
            "rv": {
                "edv": {"value": 100},
                "esv": {"value": 30},
                "sv": {"value": 70},
                "ejection_fraction_pct": 60,
            },
        }

        classifications = classify_report_measurements(data)

        self.assertEqual(classifications["Left Ventricle"], ["normal", "normal", None, "normal"])
        self.assertEqual(classifications["Right Ventricle"], [None])
        self.assertEqual(classifications["Conclusion"], [None, None])

    def test_chinese_reference_profile_uses_separately_supplied_ranges(self):
        data = {
            "study_info": {"sex": "Female", "age": 45, "ethnicity": "Chinese"},
            "lv": {
                "edv": {"value": 100},
                "edv_bsa": 70,
                "esv": {"value": 40},
                "esv_bsa": 25,
                "sv": {"value": 60},
                "ejection_fraction_pct": 60,
                "co": 4.0,
                "ci": 2.8,
                "myomass_diast": 55,
                "myomass_bsa": 40,
            },
            "rv": {
                "edv": {"value": 120},
                "edv_bsa": 70,
                "esv": {"value": 50},
                "sv": {"value": 70},
                "ejection_fraction_pct": 60,
            },
        }

        classifications = classify_report_measurements(data)

        self.assertEqual(classifications["Left Ventricle"], ["normal", "normal", None, "normal"])
        self.assertEqual(classifications["Right Ventricle"], ["normal"])

    def test_atrial_ranges_require_known_age_sex_and_method(self):
        self.assertEqual(atrial_max_volume_interval("Female", 40), (38, 98))
        self.assertEqual(atrial_max_volume_interval("Male", 40, indexed=True), (26, 52))
        self.assertIsNone(atrial_max_volume_interval("Female", 81))
        self.assertEqual(
            atrial_reference_interval(
                chamber="la", view="4ch", sex="Female", age=40
            ),
            (13, 27),
        )
        self.assertEqual(
            atrial_reference_interval(
                chamber="la", view="2ch", sex="Male", age=40
            ),
            (12, 30),
        )
        self.assertIsNone(
            atrial_reference_interval(
                chamber="la", view="unknown", sex="Female", age=40
            )
        )
        self.assertIsNone(
            atrial_reference_interval(
                chamber="ra", view="4ch", sex="Female", age=40
            )
        )
        self.assertEqual(
            atrial_reference_interval(
                chamber="la",
                view="4ch",
                sex="Female",
                age=40,
            ),
            (13, 27),
        )
        self.assertEqual(atrial_max_volume_interval("Female", 40), (38, 98))

    def test_classifies_only_explicitly_identified_atrial_view(self):
        data = {
            "study_info": {"sex": "Female", "age": 40},
            "la": {"area_view": "4ch", "area_cm2": 28},
            "ra": {"area_view": "4ch", "area_cm2": 25},
        }

        classifications = classify_report_measurements(data)

        self.assertEqual(classifications["Left Atrium"], ["abnormal"])
        self.assertEqual(classifications["Right Atrium"], [None])


class ReportGenerationTests(unittest.TestCase):
    def test_fills_template_from_pdf_and_preserves_template_structure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "report.docx"
            generated = generate_non_stress_report(
                DEFAULT_INPUT, DEFAULT_TEMPLATE, output_path
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
            self.assertIn("abnormal LV volumes and systolic function.", output_text)
            self.assertIn("normal LV hypertrophy.", output_text)
            self.assertIn("Maximum LV wall thickness is [] mm", output_text)
            self.assertIn("normal LV mass.", output_text)
            self.assertIn("abnormal RV volumes and systolic function.", output_text)
            self.assertIn("abnormal LV & RV volumes and systolic function.", output_text)
            self.assertIn("[] LGE or infarct", output_text)
            self.assertEqual(
                output.paragraphs[22].text.strip(),
                "Left Ventricle: abnormal LV volumes and systolic function. "
                "normal LV hypertrophy. Maximum LV wall thickness is [] mm in "
                "end-diastole. normal LV mass.",
            )
            self.assertEqual(
                output.paragraphs[24].text,
                "Right Ventricle: abnormal RV volumes and systolic function.",
            )
            self.assertEqual(
                output.paragraphs[43].text,
                "abnormal LV & RV volumes and systolic function.",
            )
            for index, (original, generated_paragraph) in enumerate(
                zip(template.paragraphs, output.paragraphs)
            ):
                if index not in {22, 24, 43}:
                    self.assertEqual(generated_paragraph.text, original.text)
            self.assertEqual(
                [[cell.text for cell in row.cells] for row in output.tables[0].rows],
                [[cell.text for cell in row.cells] for row in template.tables[0].rows],
            )


if __name__ == "__main__":
    unittest.main()
