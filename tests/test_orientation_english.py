"""
Νέο test, ύστερα από την κριτική: το validate_orientation() ήλεγχε ΜΟΝΟ
ελληνικές επικεφαλίδες στο ΚΑΘΑΡΟ κείμενο πελάτη, ακόμη κι όταν η εφαρμογή
ζητούσε ρητά αγγλικό παραδοτέο (site_language = English). Ένα σωστό αγγλικό
κείμενο απορριπτόταν πάντα.

Το εσωτερικό τεχνικό δελτίο παραμένει σκόπιμα πάντα ελληνικό (βλ.
CAREER_CONSISTENCY_RULE_EN στο core/prompts.py) -- μόνο το κείμενο πελάτη
χρειάζεται να αναγνωρίζεται και στα αγγλικά.
"""
from core.models import Chart, Point
from core.validator import validate_orientation

CHART = Chart(
    name="Gavriela Doe", date="1 Jan 2000", time="12:00", place="Nicosia",
    house_system="Placidus",
    points=[Point("G", "Κρόνος", "Αιγόκερως", 10, 0, 0, 280.0, house=6)],
    cusps=[], aspects=[], warnings=[],
)

_CLIENT_EN = """Brief Profile
Gavriela Doe, this is a short overview in plain everyday language, describing the general orientation without technical terms.

Talents to Explore
Analytical thinking
Why it may fit: draws on two documented indicators. This is a short paragraph describing how analytical thinking might show up in everyday life, without any technical astrological terms, just plain descriptive language for the reader to recognize in themselves.

In summary, the talents to explore are:
- Analytical thinking

Career Fields to Explore
1. Technology and innovation
Why it may fit: leverages two documented talents.
Example Careers per Field: software developer, data analyst.

Final Synthesis
These options need real-world exploration before any decision. The final choice always remains yours, as an expression of free will.

What to Remember
Grades and real performance should always be checked before confirming a direction.
"""

_AUDIT_EN = """ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ
- Technology and innovation
ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ
- software developer, data analyst
Παράρτημα τεκμηρίωσης ελέγχου
ΤΑΛΕΝΤΟ: Analytical thinking
Δείκτης 1: Τύπος: Θέση | Σημείο: Saturn | Οίκος: 6
Δείκτης 2: Τύπος: Θέση | Σημείο: Saturn | Ζώδιο: Capricorn
Ιεράρχηση βαρύτητας: Κανονική.
Τελικός έλεγχος: ολοκληρώθηκε.
"""


def test_valid_english_client_deliverable_passes():
    result = validate_orientation(
        CHART, _CLIENT_EN, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=_AUDIT_EN, format_issues=[],
    )
    assert result.ok, result.details_lines()


def test_english_client_text_still_rejects_leaked_english_jargon():
    leaking = _CLIENT_EN.replace(
        "Why it may fit: leverages two documented talents.",
        "Why it may fit: Saturn forms a square aspect here (orb 3°30').",
    )
    result = validate_orientation(
        CHART, leaking, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=_AUDIT_EN, format_issues=[],
    )
    assert not result.ok
    assert any("τεχνικά αστρολογικά δεδομένα" in line for line in result.details_lines())


def test_english_client_text_still_rejects_forbidden_analytical_section():
    with_forbidden = _CLIENT_EN + "\nSuitable Work Environment\nOpen-plan, collaborative teams.\n"
    result = validate_orientation(
        CHART, with_forbidden, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=_AUDIT_EN, format_issues=[],
    )
    assert not result.ok
    assert any("αναλυτικές ενότητες" in line for line in result.details_lines())

