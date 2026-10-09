"""Build a clearly labeled, text-only demo using the unchanged evaluation engine.

No audio recording exists for these authored English examples. No provider is called.
"""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluation.evaluator import evaluate_transcription
from evaluation.profiles import get_cleaning_profile
from evaluation.dashboard import build_dashboard
from reporting import export_overview_report, csv_results
from services.asr_common import build_model_result
from storage import digest


def main() -> None:
    source = json.loads((ROOT / "examples/portfolio/transcripts.json").read_text("utf-8"))
    profile = get_cleaning_profile("en")
    created_at = "2026-10-04T00:00:00+00:00"
    run_id = "synthetic_portfolio"
    cases = []
    for row in source["cases"]:
        models = []
        for key, label, field in (("demo_a", "Demo A - authored text", "a"),
                                  ("demo_b", "Demo B - authored text", "b")):
            model = build_model_result(key, label, row[field], settings={},
                                       provenance="imported",
                                       metadata={"synthetic": True, "inference_performed": False})
            model["evaluation"] = evaluate_transcription(row["reference"], row[field], profile)
            models.append(model)
        cases.append({
            "schema_version": 1, "run_id": run_id, "case_id": row["id"],
            "title": "[Synthetic text] " + row["id"].capitalize(),
            "created_at": created_at,
            "source": {"type": "synthetic_text", "note": source["provenance"]},
            "reference": row["reference"], "reference_hash": digest(row["reference"]),
            "profile": profile, "crop": {"start": 0, "end": None}, "audio": {},
            "models": models, "status": "complete",
            "trace": [{"stage": "Synthetic authored transcripts scored locally. No audio or ASR request.",
                       "at": created_at}],
        })
    jobs = [{"run_id": run_id, "job_id": run_id, "name": "Synthetic English demonstration",
             "mode": "imported", "status": "complete", "created_at": created_at,
             "models": ["demo_a", "demo_b"], "completed": len(cases), "total": len(cases)}]
    output = ROOT / "examples/portfolio/generated"
    output.mkdir(parents=True, exist_ok=True)
    summary = build_dashboard(cases, jobs, "normalized")
    report = export_overview_report(cases, jobs, ROOT)
    banner = ('<aside style="padding:14px 20px;background:#fff8db;color:#3b3200;'
              'font:14px/1.5 system-ui;text-align:center">'
              '<strong>SYNTHETIC TEXT DEMONSTRATION</strong> - '
              'Manually authored candidates, not real model results. No audio or provider calls. '
              'Original ASR Evaluator reporting code; inspect JSON for the recorded scoring engine.</aside>')
    report = report.replace('<div class="main">', '<div class="main">' + banner, 1)
    (output / "report.html").write_text(report, encoding="utf-8")
    (output / "results.json").write_text(json.dumps({"provenance": source["provenance"],
                "inference_performed": False, "cases": cases, "summary": summary},
                ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "results.csv").write_text(csv_results(summary), encoding="utf-8")
    print("Created synthetic HTML/JSON/CSV example. No provider calls.")
    print("Scoring engines:", sorted({m["evaluation"]["metrics"]["normalized"]["words"]["engine"]
                                       for c in cases for m in c["models"]}))
    print("Open:", output / "report.html")


if __name__ == "__main__":
    main()
