# CMR non-stress report classification

The program extracts measurements from the supplied cvi42 clinical report PDF
and classifies supported values in the CMR non-stress Word template. It changes
only `[]` placeholders for which both a measurement and an applicable reference
range are available. Every other line, placeholder, and the measurements table
remain exactly as in the template.

Install dependencies and run from the repository root:

```powershell
python -m pip install -r AI_agent\requirements.txt
python AI_agent\autofill.py --input AI_agent\AI_test_2026-09-22_Clinical_Report_2026-09-23.pdf --output AI_agent\CMR_Non_Stress_Report_Final.docx
```

By default, the supplied PDF and template are used. Use `--template` to select
another compatible Word template. A PDF must contain selectable text; scanned
PDFs require OCR before use.

The supplied sample is a female aged 82, so the age- and sex-matched
`Reference Values CMR - FEMALE ABOVE 59yrs.docx` ranges are applied:

| Measurement | Reference range |
|---|---:|
| LV EDV | 78-162 mL |
| LV EDV/BSA | 52-86 mL/m2 |
| LV ESV | 19-57 mL |
| LV stroke volume | 54-110 mL |
| LV ejection fraction | 60-78% |
| LV mass | 74-146 g |
| LV mass/BSA | 48-78 g/m2 |
| RV EDV | 70-158 mL |
| RV EDV/BSA | 48-84 mL/m2 |
| RV ESV | 9-61 mL |
| RV stroke volume | 54-106 mL |
| RV ejection fraction | 58-82% |

For combined ventricle function placeholders, all listed measurements must be
present; when an indexed EDV is reported, its indexed range is also checked.
Any out-of-range value makes the classification abnormal. In the sample, LV
function is abnormal (LV ESV 57.512 mL exceeds 57 mL and LV EDV/BSA 98.228
mL/m2 exceeds 86 mL/m2); RV function is abnormal (RV EDV/BSA 96.380 mL/m2
exceeds 84 mL/m2). LV mass is normal by both reported measures. LV mass is
used for the LV mass/hypertrophy placeholders. Wall thickness is not classified
because the supplied age/sex reference table has no applicable threshold.

The supplied LA reference image covers ages 20-80 and distinguishes measurement
methods/views. The PDF reports a single LA contour area without a view label,
and this sample patient is 82, so the LA placeholder is left unchanged. RA area
also has no compatible view-specific classification. Aortic/MPA line lengths
are not treated as diameters; clinical history, scanner, anatomy, valves,
pericardium, oedema, LGE, and extracardiac findings remain unchanged because no
applicable classification is supported by the PDF and references.

Run the focused tests with:

```powershell
python -m unittest AI_agent.test_report_generation
```
