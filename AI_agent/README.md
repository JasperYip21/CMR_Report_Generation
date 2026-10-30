# CMR non-stress report generation

The generator reads a cvi42 scientific report export (`.txt`), fills the supplied
`attachments/CMR Non-Stress Template.docx`, and saves a Word report. The output
retains the template paragraphs and measurement table. It reports source
measurements, does not assume unreported findings are normal, and leaves
unsupported measurements explicitly marked as not provided.

From the repository root, install the dependencies and run:

```powershell
python -m pip install -r AI_agent\requirements.txt
python AI_agent\autofill.py --input AI_agent\AI_test_2026-09-22_Scientific_Report_2026-09-23.txt --output AI_agent\CMR_Non_Stress_Report_Final.docx
```

By default, the script uses the sample TXT file and the bundled template. Use
`--template` to select another compatible Word template. A custom template must
contain the same report paragraphs and a six-column physical measurements
table.

The provided `reference_numbers.png` gives adult (20-80 years) sex-specific
reference ranges for indexed maximum left atrial volume and chamber area. The
generator applies the indexed-volume thresholds only when age, sex, and a
compatible indexed LA-volume measurement are all present in the TXT source.
The supplied sample TXT does not contain those inputs, so its LA classification
is reported as unavailable. No LA chamber-area classification is inferred
without a specified imaging view.

Run the focused tests with:

```powershell
python -m unittest AI_agent.test_report_generation
```
