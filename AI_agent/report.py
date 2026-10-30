#%%
import json
from dataclasses import dataclass
from typing import Optional
import docx
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

# Import your cvi42 parser from test.py
from test import parse_cvi42_report


@dataclass
class PatientInfo:
    sex: str  # 'Male' or 'Female'
    age: int
    height_cm: float
    weight_kg: float

    @property
    def bsa(self) -> float:
        """Calculates Body Surface Area using Mosteller formula."""
        return ((self.height_cm * self.weight_kg) / 3600) ** 0.5


class CMRReportGenerator:

    def __init__(self, patient: PatientInfo):
        self.patient = patient

    def categorize_la_volume(
        self, volume_indexed: float, sex: str = "Male"
    ) -> str:
        """Categorizes Left Atrial Size using SCMR Reference Standards (Table 5)."""
        sex_is_male = sex.lower() in ["m", "male"]

        # Thresholds for Max LA Volume/BSA (mL/m²) based on Table 5
        if sex_is_male:
            if volume_indexed < 26:
                return "Small"
            elif 26 <= volume_indexed <= 52:
                return "Normal"
            elif 53 <= volume_indexed <= 59:
                return "Mildly enlarged"
            elif 60 <= volume_indexed <= 66:
                return "Moderately enlarged"
            else:
                return "Severely enlarged"
        else:
            if volume_indexed < 27:
                return "Small"
            elif 27 <= volume_indexed <= 53:
                return "Normal"
            elif 54 <= volume_indexed <= 60:
                return "Mildly enlarged"
            elif 61 <= volume_indexed <= 67:
                return "Moderately enlarged"
            else:
                return "Severely enlarged"

    def create_cmr_docx_report(
        self,
        measurements: dict,
        output_filename: str = "CMR_Report_Final.docx",
    ):
        doc = Document()

        # Set default style font
        style = doc.styles["Normal"]
        style.font.name = "Arial"
        style.font.size = Pt(10.5)

        # Header
        p = doc.add_paragraph()
        p.add_run("CARDIAC MRI:").bold = True

        # History & Technique
        p_hist = doc.add_paragraph()
        p_hist.add_run("CLINICAL HISTORY: ").bold = True
        p_hist.add_run(measurements.get("clinical_history", ""))

        p_tech = doc.add_paragraph()
        p_tech.add_run("TECHNIQUE: ").bold = True
        p_tech.add_run(
            "Localisers, multi-planar cine images, late gadolinium enhancement, T1 and T2 mapping images were acquired."
        )

        p_scan = doc.add_paragraph()
        p_scan.add_run("SCANNER: ").bold = True
        p_scan.add_run(
            measurements.get("scanner", "Siemens 3T Magnetom Vida.", "GE Signa Premier 3T.")
        )

        # Findings Header
        p_find = doc.add_paragraph()
        p_find.add_run("FINDINGS:").bold = True

        # Section Helper
        def add_finding_line(label: str, value_text: str):
            p_line = doc.add_paragraph()
            p_line.add_run(f"{label}: ").bold = True
            p_line.add_run(value_text)

        # Comparison
        comp_text = measurements.get(
            "comparison_text",
            "No previous cardiac MRI available for comparison.",
            "Comparison is made with previous cardiac MRI dated []",
        )
        doc.add_paragraph(comp_text)

        # Structured Findings Lines
        add_finding_line(
            "Cardiovascular Anatomy",
            f"{measurements.get('anatomy_adj', 'Normal')} atrioventricular and ventriculoarterial connections. "
            f"Normal drainage of the SVC and IVC into the right atrium. "
            f"{measurements.get('pulm_venous_adj', 'Normal')} pulmonary venous drainage into the left atrium.",
        )

        aortic_sinus = measurements.get("aortic_sinus_mm", "N/A")
        add_finding_line(
            "Aorta",
            f"Not dilated. Aortic sinus measures {aortic_sinus} mm in diameter.",
        )

        pa_diam = measurements.get("pa_diameter_mm", 0)
        pa_dilated_adj = (
            "moderately"
            if pa_diam > 30
            else ("mildly" if pa_diam > 25 else "not")
        )
        pa_susp = (
            "This is suspicious for pulmonary hypertension."
            if pa_diam > 29
            else "No evidence of pulmonary hypertension."
        )
        add_finding_line(
            "Pulmonary Arteries",
            f"Main pulmonary artery is {pa_dilated_adj} dilated. Diameter is {pa_diam} mm. {pa_susp}",
        )

        # LA Volume evaluation based on SCMR Table 5
        la_vol_indexed = measurements.get("la_max_vol_indexed")
        la_adj = (
            self.categorize_la_volume(la_vol_indexed, self.patient.sex)
            if la_vol_indexed is not None
            else "Normal"
        )
        add_finding_line("Left Atrium", f"{la_adj} for size.")
        add_finding_line(
            "Right Atrium",
            f"{measurements.get('ra_adj', 'Normal')} for size.",
        )

        max_lv_thick = measurements.get("max_lv_thickness_mm", "N/A")
        add_finding_line(
            "Left Ventricle",
            f"{measurements.get('lv_vol_func_adj', 'Normal')} LV volumes and systolic function. "
            f"{measurements.get('lv_hypertrophy_adj', 'No')} LV hypertrophy. "
            f"Maximum LV wall thickness is {max_lv_thick} mm in end-diastole. "
            f"{measurements.get('lv_mass_adj', 'Normal')} LV mass.",
        )

        add_finding_line(
            "Right Ventricle",
            f"{measurements.get('rv_vol_func_adj', 'Normal')} RV volumes and systolic function.",
        )

        # Valves
        add_finding_line(
            "Aortic Valve",
            f"{measurements.get('aortic_valve_adj', 'Normal')} appearances and function.",
        )
        add_finding_line(
            "Pulmonary Valve",
            f"{measurements.get('pulm_valve_adj', 'Normal')} appearances and function.",
        )
        add_finding_line(
            "Mitral Valve",
            f"{measurements.get('mitral_valve_adj', 'Normal')} appearances and function.",
        )
        add_finding_line(
            "Tricuspid Valve",
            f"{measurements.get('tricuspid_valve_adj', 'Normal')} appearances and function.",
        )

        add_finding_line(
            "Pericardium",
            f"{measurements.get('pericardium_adj', 'No')} effusion or thickening.",
        )
        add_finding_line(
            "Oedema Imaging (T2 Mapping/T2 STIR)",
            f"{measurements.get('oedema_adj', 'No')} oedema. {measurements.get('native_t2_adj', 'Normal')} native T2 value.",
        )
        add_finding_line(
            "Late Gadolinium Enhancement (LGE/T1 Mapping)",
            f"{measurements.get('lge_adj', 'No')} LGE or infarct. {measurements.get('native_t1_adj', 'Normal')} native T1 value.",
        )
        add_finding_line(
            "Extracardiac", measurements.get("extracardiac_text", "Nil")
        )

        # Conclusion
        p_conc = doc.add_paragraph()
        p_conc.add_run("CONCLUSION:").bold = True

        p_c1 = doc.add_paragraph()
        p_c1.add_run(
            f"{measurements.get('lv_vol_func_adj', 'Normal')} LV & RV volumes and systolic function."
        )

        p_c2 = doc.add_paragraph()
        p_c2.add_run(f"{measurements.get('lge_adj', 'No')} LGE or infarct")

        # Physical Table at Bottom
        table = doc.add_table(rows=2, cols=2)
        table.style = "Table Grid"

        table.cell(0, 0).paragraphs[
            0
        ].text = f"Height:\n | {self.patient.height_cm} cm"
        table.cell(0, 1).paragraphs[
            0
        ].text = f"Weight:\n | {self.patient.weight_kg} kg"
        table.cell(1, 0).paragraphs[0].text = f"BSA:\n | {self.patient.bsa:.2f} m2"

        doc.save(output_filename)
        print(f"Report saved successfully as '{output_filename}'")

def create_patient_info_from_parsed(parsed_data: dict) -> PatientInfo:
    """Extracts demographic info from parsed study_info or top-level keys."""
    # Look into study_info or fallback to the top-level measurements dictionary
    info = parsed_data.get("study_info", parsed_data)

    return PatientInfo(
        sex=info.get("sex", "Male"),
        age=int(info.get("age", 0)),
        height_cm=float(info.get("height_cm", 170.0)),
        weight_kg=float(info.get("weight_kg", 70.0)),
    )

# ==========================================
# EXECUTION
# ==========================================

# 2. Read cvi42 Export File
file_path = "AI_test_2026-09-22_Scientific_Report_2026-09-23.txt"

with open(file_path, "r", encoding="utf-16") as file:
    report_text = file.read()
    parsed_data = parse_cvi42_report(report_text)
    print("Parsed cvi42 Data:\n", json.dumps(parsed_data, indent=4))

# 3. Generate Word Document Report
patient_info = create_patient_info_from_parsed(parsed_data)
generator = CMRReportGenerator(patient_info)
generator.create_cmr_docx_report(parsed_data, "CMR_Report_Final.docx")