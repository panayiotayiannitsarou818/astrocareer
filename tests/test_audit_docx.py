"""
Νέο test, ύστερα από την κριτική #3: στο μονοπάτι αυτόματης δημιουργίας το
εσωτερικό τεχνικό δελτίο αποθηκευόταν ως audit_text.encode("utf-8") -- ωμά
bytes απλού κειμένου με επέκταση .docx, όχι πραγματικό αρχείο Word (ένα
.docx είναι στην πραγματικότητα ένα ZIP αρχείο με XML μέσα) -- και δεν
υπήρχε καν κουμπί λήψης γι' αυτό.
"""
import io

from docx import Document

from core.docx_builder import build_orientation_audit_docx


def test_audit_docx_is_a_real_zip_docx_not_raw_text():
    data = build_orientation_audit_docx(
        "Εσωτερικό Τεχνικό Δελτίο Ελέγχου", "Gavriela Doe",
        "ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ\n- Technology and innovation\n",
    )
    # Ένα πραγματικό .docx είναι ZIP -- ξεκινά πάντα με την υπογραφή "PK".
    # Το παλιό audit_text.encode("utf-8") θα απέτυχε εδώ.
    assert data[:2] == b"PK"


def test_audit_docx_is_openable_by_python_docx_and_contains_the_text():
    audit_text = "ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ\n- software developer\nΤελικός έλεγχος: ολοκληρώθηκε.\n"
    data = build_orientation_audit_docx("Εσωτερικό Τεχνικό Δελτίο Ελέγχου", "Gavriela Doe", audit_text)

    doc = Document(io.BytesIO(data))  # θα πετούσε exception αν δεν ήταν έγκυρο docx
    all_text = "\n".join(p.text for p in doc.paragraphs)
    assert "Εσωτερικό" in all_text
    assert "Gavriela Doe" in all_text
    assert "ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ" in all_text
