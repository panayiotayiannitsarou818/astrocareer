"""v19 -- βοηθητικό για τα ΠΑΛΙΑ tests (πριν από τα παραρτήματα κάλυψης).

Τα παλιά tests ελέγχουν άλλα χαρακτηριστικά (μήκη, απόλυτες διατυπώσεις,
round-trip, δείκτες...) με ελάχιστα τεχνικά δελτία που δεν έχουν τα νέα
υποχρεωτικά «Παράρτημα Κάλυψης Θέσεων» / «Παράρτημα Κάλυψης Τομέων». Εδώ
προστίθενται αυτόματα, ΕΓΚΥΡΑ και ουδέτερα, ώστε τα παλιά tests να συνεχίσουν
να ελέγχουν αυτό για το οποίο γράφτηκαν. Δεν προστίθενται ποτέ όταν το δελτίο
έχει ήδη δικό του παράρτημα κάλυψης. Τα ίδια τα παραρτήματα ελέγχονται
αυστηρά, χωρίς αυτό το βοηθητικό, στο tests/test_coverage_appendices.py.
"""
import re

from core.astrology import planet_concentrations, wide_aspect_clusters
from core.catalogue import sector_catalogue
from core.validator import (
    _extract_talent_titles, _points_in_block, _talent_blocks, validate_orientation,
)


def add_coverage(chart, audit_text: str, client_text: str) -> str:
    if not audit_text or re.search(r"Παράρτημα\s+Κάλυψης", audit_text, re.IGNORECASE):
        return audit_text
    talents = _extract_talent_titles(client_text) if client_text else []
    raw_titles = re.findall(r"^\s*ΤΑΛΕΝΤΟ\s*:\s*(.+?)\s*$", audit_text, re.MULTILINE)
    blocks = _talent_blocks(audit_text)
    lines = ["Παράρτημα Κάλυψης Θέσεων"]
    for p in chart.points:
        if p.kind == "cusp":
            continue
        target = None
        for raw in raw_titles:
            from core.validator import _norm_title
            if p.name in _points_in_block(blocks.get(_norm_title(raw), ""))[0]:
                target = raw
                break
        house = p.house if p.house is not None else "—"
        decision = (f"ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ — Ταλέντο «{target}»" if target
                    else "ΕΞΑΙΡΕΙΤΑΙ — δεν συνδέεται με κανένα εγκεκριμένο ταλέντο αυτού του σεναρίου")
        lines.append(f"Σημείο: {p.name} | Ζώδιο: {p.sign} | Οίκος: {house} | Απόφαση: {decision}")
    for label, names in planet_concentrations(chart.points):
        lines.append(f"Συγκέντρωση: {label} | Σημεία: {', '.join(names)} | Απόφαση: "
                     "ΕΞΑΙΡΕΙΤΑΙ — δοκιμαστικό σενάριο χωρίς σχετικό ταλέντο")
    for point, members in wide_aspect_clusters(chart.aspects):
        lines.append(f"Κοινό σημείο: {point} | Όψεις: {', '.join(members)} | Απόφαση: "
                     "ΕΞΑΙΡΕΙΤΑΙ — δοκιμαστικό σενάριο χωρίς σχετικό ταλέντο")
    lines.append("Παράρτημα Κάλυψης Τομέων")
    for name in sector_catalogue():
        lines.append(f"Τομέας: {name} | Απόφαση: ΑΠΟΡΡΙΠΤΕΤΑΙ — δοκιμαστικό σενάριο με δικούς του τομείς")
    m = re.search(r"ΕΓΚΕΚΡΙΜΕΝΟΙ\s+ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ\s+ΤΟΜΕΙΣ\s*\n([\s\S]*?)(?=\n\s*(?:ΕΓΚΕΚΡΙΜΕΝΑ|ΡΗΤΗ|Παράρτημα|Τελικός)|\Z)", audit_text)
    # v19.1: κύριος τομέας = 2+ ταλέντα (ή 1 με «εγγύηση»)· κάθε ταλέντο χρειάζεται κύριο τομέα.
    if len(talents) >= 2:
        talent_ref = " — ταλέντα " + ", ".join(f"«{t}»" for t in talents)
    elif talents:
        talent_ref = f" — ταλέντο «{talents[0]}»· εγγύηση: το μοναδικό ταλέντο χρειάζεται κύριο τομέα"
    else:
        talent_ref = ""
    if m:
        for field in m.group(1).splitlines():
            field = re.sub(r"^\s*(?:[-•*]|\d+[.)])\s*", "", field).strip()
            if field:
                lines.append(f"Τομέας: ΝΕΟΣ | Απόφαση: ΕΠΙΛΕΓΕΤΑΙ ως «{field}»{talent_ref}")
    appendix = "\n".join(lines) + "\n"
    final = re.search(r"^\s*Τελικός\s+έλεγχος", audit_text, re.MULTILINE | re.IGNORECASE)
    if final:
        return audit_text[:final.start()] + appendix + audit_text[final.start():]
    return audit_text.rstrip("\n") + "\n" + appendix


def validate_orientation_legacy(chart, text, *args, audit_text=None, **kwargs):
    if audit_text:
        audit_text = add_coverage(chart, audit_text, text)
    return validate_orientation(chart, text, *args, audit_text=audit_text, **kwargs)
