"""
batch_run.py -- αυτόματη εκτέλεση χωρίς διεπαφή.

Παίρνει ένα ή περισσότερα Astrodienst PDF (ή έναν φάκελο με PDF) και για
καθένα κάνει ολόκληρη τη διαδικασία: ανάγνωση -> δημιουργία -> έλεγχος ->
διόρθωση μέχρι την έγκριση -> τελικά Word στον φάκελο εξόδου.

Παραδείγματα:
    export ANTHROPIC_API_KEY=sk-ant-...
    python batch_run.py pelates/                     # όλα τα PDF του φακέλου
    python batch_run.py maria.pdf --lang en          # αγγλικό παραδοτέο
    python batch_run.py pelates/ --provider openai --out apotelesmata/

Για κάθε πελάτη δημιουργούνται:
    <Όνομα>_AstroCheck_Anadeixi_Talenton.docx          (εγκεκριμένο -- για τον πελάτη)
    <Όνομα>_Εσωτερικό_Τεχνικό_Δελτίο.docx             (εσωτερικό)
ή, αν ΔΕΝ εγκριθεί, ΠΡΟΣΧΕΔΙΟ_<...>.docx + αρχείο _ΠΡΟΒΛΗΜΑΤΑ.txt.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from core.generator import API_KEY_NAMES, DEFAULT_PROVIDER, PROVIDERS
from core.parser import parse_astrodienst_pdf
from core.costs import CostTracker
from core.generator import default_model
from core.pipeline import (
    Settings, audit_docx_filename, client_docx_filename, make_generate_fn, run_pipeline,
)


def _collect_pdfs(inputs):
    pdfs = []
    for item in inputs:
        path = Path(item)
        if path.is_dir():
            pdfs.extend(sorted(p for p in path.iterdir() if p.suffix.lower() == ".pdf"))
        elif path.suffix.lower() == ".pdf" and path.exists():
            pdfs.append(path)
        else:
            print(f"! Αγνοείται (δεν είναι PDF ή δεν υπάρχει): {item}", file=sys.stderr)
    return pdfs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="AstroCheck Career -- αυτόματη μαζική δημιουργία εντύπων")
    ap.add_argument("inputs", nargs="+", help="PDF αρχεία ή φάκελοι με PDF")
    ap.add_argument("--out", default="apotelesmata", help="φάκελος εξόδου (προεπιλογή: apotelesmata)")
    ap.add_argument("--lang", choices=["el", "en"], default="el", help="γλώσσα παραδοτέου")
    ap.add_argument("--provider", choices=PROVIDERS, default=os.environ.get("AI_PROVIDER", DEFAULT_PROVIDER))
    ap.add_argument("--model", default=None, help="συγκεκριμένο μοντέλο (προαιρετικό)")
    ap.add_argument("--max-attempts", type=int, default=None, help="όριο ασφαλείας προσπαθειών")
    args = ap.parse_args(argv)

    api_key = os.environ.get(API_KEY_NAMES[args.provider])
    if not api_key:
        print(f"Λείπει το {API_KEY_NAMES[args.provider]} (μεταβλητή περιβάλλοντος).", file=sys.stderr)
        return 2

    pdfs = _collect_pdfs(args.inputs)
    if not pdfs:
        print("Δεν βρέθηκε κανένα PDF.", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    generate_fn = make_generate_fn(args.provider, api_key, args.model)
    settings = Settings.from_env()
    if args.max_attempts:
        settings.max_attempts = args.max_attempts
    model_name = args.model or default_model(args.provider)
    total_cost = CostTracker()

    approved = 0
    for pdf in pdfs:
        print(f"\n=== {pdf.name}")
        try:
            chart = parse_astrodienst_pdf(pdf.read_bytes(), pdf.name)
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ Αποτυχία ανάγνωσης PDF: {exc}")
            continue

        def progress(event, **info):
            if event == "checked":
                print(f"  κλήση {info['attempt']}: " + ("ΕΓΚΡΙΘΗΚΕ" if info["count"] == 0 else f"{info['count']} προβλήματα"))
            elif event == "api_retry":
                print(f"  προσωρινό σφάλμα παρόχου, νέα δοκιμή {info['n']}")
            elif event == "new_round":
                print(f"  νέα γραφή από την αρχή ({info['n']})")
            elif event == "truncated":
                print("  κομμένη απάντηση -- ζητείται πιο σύντομη")

        chart_cost = CostTracker()  # το όριο κόστους ισχύει ανά χάρτη
        try:
            result = run_pipeline(chart, chart.name, args.lang, generate_fn=generate_fn, model_name=model_name,
                                  settings=settings, cost=chart_cost, on_progress=progress)
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ Σφάλμα δημιουργίας: {exc}")
            continue
        finally:
            total_cost.calls.extend(chart_cost.calls)
        print(f"  κόστος: {chart_cost.format()}")

        file_label = chart.name or pdf.stem  # χωρίς όνομα στο PDF: το όνομα του αρχείου, ΜΟΝΟ για τα αρχεία εξόδου
        client_name = client_docx_filename(file_label)
        audit_name = audit_docx_filename(file_label)
        if result.raw is None:
            print(f"  ✗ Καμία απόπειρα ({result.stopped_reason}: {result.error_key}) {result.error_detail or ''}")
            if result.stopped_reason == "permanent_error":
                break  # λάθος κλειδί / χωρίς υπόλοιπο: δεν έχει νόημα να συνεχίσει με τα επόμενα
            continue
        if result.ok:
            approved += 1
            (out / client_name).write_bytes(result.client_docx)
            print(f"  ✓ {out / client_name}")
        else:
            (out / f"ΠΡΟΣΧΕΔΙΟ_{client_name}").write_bytes(result.client_docx)
            (out / f"{Path(client_name).stem}_ΠΡΟΒΛΗΜΑΤΑ.txt").write_text(
                "\n".join(result.check.details_lines()), encoding="utf-8")
            print(f"  ⚠ Δεν εγκρίθηκε ({result.stopped_reason}) -- αποθηκεύτηκε ως ΠΡΟΣΧΕΔΙΟ")
        if result.audit_docx:
            (out / audit_name).write_bytes(result.audit_docx)

    print(f"\nΕγκρίθηκαν {approved}/{len(pdfs)}. Συνολικό κόστος: {total_cost.format()}. Αρχεία στο: {out.resolve()}")
    return 0 if approved == len(pdfs) else 1


if __name__ == "__main__":
    sys.exit(main())
