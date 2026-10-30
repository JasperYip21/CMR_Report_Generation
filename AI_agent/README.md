# CMR non-stress report classification

The program reads measurements and available demographics from a selectable-text
clinical report PDF, selects a supplied CMR reference profile, and fills only
the template's `[]` classification placeholders. It writes a `.docx` based on
the original Word template. Lines and placeholders without a supported
measurement/reference match are preserved exactly; the generator does not
write inferred clinical history or unsupported normal/abnormal findings.

## Run

Install dependencies and run from the repository root:

```powershell
python -m pip install -r AI_agent\requirements.txt
python AI_agent\autofill.py --input path\to\clinical-report.pdf --output path\to\report.docx
```

By default, the supplied example PDF and CMR non-stress template are used. Use
`--template` to select another compatible Word template. The input PDF must
contain selectable text; scanned PDFs need OCR before they can be parsed.
Repeated identical values are accepted, while conflicting repeated values are
treated as ambiguous and not used. The CLI reports which classification
placeholders remain unchanged; it stops with an error when the PDF contains no
recognized CMR measurements.

## Reference matching and classification

The parser uses available demographics; it never supplies a default sex, age,
height, weight, or BSA. Sex and age must be recognized to select a ventricle
profile. The supplied ranges currently cover:

| Profile | Population |
|---|---|
| Female / male 8–17 | Pediatric reference documents |
| Female / male 18–59 | Adult reference documents for age below 60 |
| Female / male 60+ | Adult reference documents for age 60 and above |
| Female / male Chinese | Chinese reference documents, selected only when the PDF explicitly identifies Chinese ethnicity and age is at least 18 |

No supplied ventricle profile covers children under 8. Unknown/ambiguous sex,
missing age, or an unsupported age leaves the associated placeholders
unchanged. The Chinese source documents do not provide age-stratified tables;
the implementation uses them only for explicitly identified adults and leaves
atrial classifications subject to their separate age/view requirements.

For ventricular function, all measurements listed in the selected profile must
be present before the function placeholder is classified. Each reported
measurement is checked against its corresponding range; a value outside any
applicable range makes the classification abnormal. LV mass is classified
separately when all mass measures available in the selected profile are
present. Missing or unsupported thresholds, including wall thickness, remain
unclassified.

Atrial classification requires an applicable adult age, known sex, and an
explicitly identified measurement type/view. LA area references differ by
2-, 3-, or 4-chamber view; atrial volume references are used only for the LA
and within their documented ages. An unlabeled contour area is not assumed to
be a specific chamber view. The supplied references do not provide a supported
RA classification, so right atrial placeholders remain unchanged. Aortic and
pulmonary artery line lengths are not treated as diameters. Other anatomical,
tissue, valve, pericardial, and clinical-history lines are left unchanged
unless a supported classification is added to the reference data.

The ranges are transcribed from the reference documents in
`AI_agent/attachments` and the supplied LA reference image in
`AI_agent/reference_numbers.png`. This tool is intended to assist
report preparation, not replace clinical review; confirm that the selected
reference population and measurement method are appropriate before use.

## Tests

Run the focused synthetic and sample-data tests from the repository root:

```powershell
python -m unittest AI_agent.test_report_generation
```
