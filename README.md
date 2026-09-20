# AstroCheck Career

Αυτόνομη ιστοσελίδα, αποκλειστικά για την υπηρεσία ανάδειξης ταλέντων και
διερεύνησης επαγγελματικών επιλογών — ενιαία υπηρεσία για κάθε άτομο, χωρίς
διάκριση παιδιού/εφήβου/ενήλικα.
Δεν εξαρτάται από, ούτε συνδέεται με, καμία άλλη υπηρεσία.

**Entry point:** `app.py` (χρειάζεται επίσης τα `core/`, `references/` και `requirements.txt` δίπλα του για να τρέξει)
(Main file path στο Streamlit Community Cloud = `app.py`)

## Χαρακτηριστικά

- Ανάγνωση Astrodienst Natal Chart Data Sheet (PDF) — δεν χρειάζεται καμία
  πλήρης ανάλυση 12 Οίκων.
- **Selectbox γλώσσας πάνω-δεξιά (Ελληνικά/English)** που αλλάζει ολόκληρη
  τη σελίδα ΚΑΙ τη γλώσσα του τελικού παραδοτέου. Προεπιλογή: Ελληνικά.
- Ενιαία, "Απλή και πρακτική" παρουσίαση για όλους — όσα ταλέντα και
  επαγγελματικοί τομείς τεκμηριώνονται πραγματικά από τον χάρτη, χωρίς
  σταθερό ελάχιστο ή ανώτατο αριθμό και χωρίς επιλογή τύπου υπηρεσίας.
- Λήψη πλήρους δεσμευτικής εντολής για ChatGPT/Claude, ή προαιρετική
  αυτόματη δημιουργία με προσωπικό OpenAI API key (χωρίς αντιγραφή/επικόλληση).
- Πλήρης μηχανικός έλεγχος πληρότητας (`core/validator.py`) πριν επιτραπεί η
  λήψη του τελικού Word — για την απλή παρουσίαση, ελέγχει ξεχωριστά το
  καθαρό παραδοτέο πελάτη ΚΑΙ το εσωτερικό τεχνικό δελτίο.

## Deployment (Streamlit Community Cloud)

1. Ανέβασε όλο τον φάκελο σε ένα GitHub repo.
2. Deploy στο https://share.streamlit.io με **Main file path = `app.py`**.

Δεν χρειάζεται κανένα Secret — δεν υπάρχουν πια cross-link URLs προς άλλες
υπηρεσίες.

## Τοπική εκτέλεση

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

## Ο κοινός πυρήνας (`core/`)

Ο κώδικας που κάνει την πραγματική δουλειά — `models.py`, `astrology.py`,
`parser.py`, `validator.py`, `prompts.py`, `docx_builder.py`, `generator.py`,
`reference_loader.py`, `case_state.py` — ζει στο `core/` ως πραγματικό
Python πακέτο. Το κοινό .docx πρότυπο και η δεσμευτική εντολή ζουν στο
`references/`.

## Development / Tests

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
```

Το `tests/fixtures/astro_paradeigma.pdf` (το δημόσιο παράδειγμα "Paradeigma"
του Astrodienst) είναι ήδη μέσα στο repo — τα tests τρέχουν χωρίς καμία
επιπλέον ρύθμιση.

## Σημαντικό

Η εφαρμογή δεν αντιμετωπίζει την αστρολογία ως επιστημονική ή ψυχολογική
διάγνωση — είναι εργαλείο συμβολικής αυτογνωσίας. Η τελική ανάλυση πρέπει να
περνά ανθρώπινο μαθηματικό, γλωσσικό και οπτικό έλεγχο πριν παραδοθεί σε
πελάτη. Το ChatGPT ή το Claude πραγματοποιούν μόνο αυτοέλεγχο· ο πραγματικός
validator εκτελείται αποκλειστικά μέσα στο AstroCheck Career.
