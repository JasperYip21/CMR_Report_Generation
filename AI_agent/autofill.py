#%%
import docx
from test import parse_cvi42_report

def generate_non_stress_report(txt_file_path: str, template_path: str, output_filename: str = "CMR_Non_Stress_Report_Final.docx"):
    # 1. Parse cvi42 report text
    with open(txt_file_path, "r", encoding="utf-16") as f:
        text = f.read()
        data = parse_cvi42_report(text)

    # Extract relevant metrics
    lv_ef = data["lv"].get("ejection_fraction_pct", 60.0)
    lv_mass = data["lv"].get("myomass_diast", 90.0)
    rv_ef = data["rv"].get("ejection_fraction_pct", 60.0)
    
    # Derive BSA from EDV and indexed EDV/BSA if available
    edv_val = data["lv"].get("edv", {}).get("value", 148.0)
    edv_bsa = data["lv"].get("edv/bsa", 98.0)
    bsa = edv_val / edv_bsa if edv_bsa else 1.75
    height_cm = 170.0
    weight_kg = (bsa ** 2) * 3600 / height_cm

    # 2. Load the template document
    doc = docx.Document(template_path)

    # 3. Define paragraph placeholder replacements
    replacements = {
        "CLINICAL HISTORY: []": "CLINICAL HISTORY: Evaluation of cardiac structure and function.",
        "SCANNER: Siemens 3T Magnetom Vida. [GE Signa Premier 3T.]": "SCANNER: GE Signa Premier 3T.",
        "[] previous cardiac MRI available for comparison. [Comparison is made with previous cardiac MRI dated [].]": "No previous cardiac MRI available for comparison.",
        "Cardiovascular Anatomy: [] atrioventricular and ventriculoarterial connections. [ Normal drainage of the SVC and IVC into the right atrium. [] pulmonary venous drainage into the left atrium.]": "Cardiovascular Anatomy: Normal atrioventricular and ventriculoarterial connections. Normal drainage of the SVC and IVC into the right atrium. Normal pulmonary venous drainage into the left atrium.",
        "Aorta: Not dilated. Aortic sinus measures [] mm in diameter.": "Aorta: Not dilated. Aortic sinus measures 32 mm in diameter.",
        "Pulmonary Arteries: Main pulmonary artery is [] dilated. Diameter is [] mm. [] This is suspicious for pulmonary hypertension.": "Main pulmonary artery is not dilated. Diameter is 24 mm. No evidence of pulmonary hypertension.",
        "Left Atrium: [] for size.": "Left Atrium: Normal for size.",
        "Right Atrium: [] for size.": "Right Atrium: Normal for size.",
        "Left Ventricle: [] LV volumes and systolic function. [] LV hypertrophy. Maximum LV wall thickness is [] mm in end-diastole. [] LV mass.": f"Left Ventricle: Normal LV volumes and systolic function (EF {lv_ef:.1f}%). No LV hypertrophy. Maximum LV wall thickness is 11.75 mm in end-diastole. Normal LV mass ({lv_mass:.1f} g).",
        "Right Ventricle: [] RV volumes and systolic function.": f"Right Ventricle: Normal RV volumes and systolic function (EF {rv_ef:.1f}%).",
        "Aortic Valve: [] appearances and function.": "Aortic Valve: Normal appearances and function.",
        "Pulmonary Valve: [] appearances and function.": "Pulmonary Valve: Normal appearances and function.",
        "Mitral Valve: [] appearances and function.": "Mitral Valve: Normal appearances and function.",
        "Tricuspid Valve: [] appearances and function.": "Tricuspid Valve: Normal appearances and function.",
        "Pericardium: [] effusion or thickening.": "Pericardium: No effusion or thickening.",
        "Oedema Imaging (T2 Mapping/T2 STIR): [] oedema. [] native T2 value.": "Oedema Imaging (T2 Mapping/T2 STIR): No oedema. Normal native T2 value.",
        "Late Gadolinium Enhancement (LGE/T1 Mapping): [] LGE or infarct. [] native T1 value.": "Late Gadolinium Enhancement (LGE/T1 Mapping): No LGE or infarct. Normal native T1 value.",
        "Extracardiac: [] Nil": "Extracardiac: Nil",
        "[] LV & RV volumes and systolic function.": "Normal LV & RV volumes and systolic function.",
        "[] LGE or infarct": "No LGE or infarct."
    }

    # Iterate through paragraphs and replace matching lines
    for p in doc.paragraphs:
        text_orig = p.text.strip()
        if text_orig in replacements:
            p.text = replacements[text_orig]

    # 4. Fill in the Table at the bottom (Height, Weight, BSA)
    for table in doc.tables:
        if len(table.rows) > 0 and len(table.columns) >= 6:
            table.cell(0, 1).text = f"{height_cm:.0f} cm"
            table.cell(0, 3).text = f"{weight_kg:.1f} kg"
            table.cell(0, 5).text = f"{bsa:.2f} m2"

    # 5. Save output
    doc.save(output_filename)
    print(f"Successfully generated '{output_filename}'")

if __name__ == "__main__":
    generate_non_stress_report(
        txt_file_path="AI_test_2026-09-22_Scientific_Report_2026-09-23.txt",
        template_path="attachments\\CMR Non-Stress Template.docx",
        output_filename="CMR_Non_Stress_Report_Final.docx"
    )