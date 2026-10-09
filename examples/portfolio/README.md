# Synthetic transcript example

`transcripts.json` contains a small English example with two manually authored
candidate transcripts. It is separate from, and does not replace, the original
Arabic sample.

These are **not ASR model outputs or measured model performance**. No audio exists
for these example lines and no provider API is called. The reference is a synthetic
text fixture rather than an independently transcribed recording.

Use the reference and candidates in the application's supplied-transcript form,
or run `python tools/build_portfolio_demo.py` after installing local dependencies.
The helper uses the original evaluation/reporting code and writes an HTML snapshot
and JSON/CSV examples under `examples/portfolio/generated/`.
