# Αλλαγές v15 — Διαχωρισμός σε 3 εφαρμογές

> **ΙΣΤΟΡΙΚΟ ΑΡΧΕΙΟ** — περιγράφει τον διαχωρισμό σε τρεις εφαρμογές
> (Home.py, AstroCheck_Analysis.py, AstroCheck_Career.py). Αυτό το πακέτο
> περιέχει μόνο το AstroCheck Career· τα άλλα δύο entry points δεν
> υπάρχουν εδώ. Το `core/` όμως παραμένει ενεργό και τρέχον.

## Νέα δομή

Το ενιαίο "AstroCheck Pro" (7 tabs) χωρίστηκε σε:

- **Home.py** — κεντρική σελίδα-κατάλογος υπηρεσιών (νέο)
- **AstroCheck_Analysis.py** — πλήρης ανάλυση 12 Οίκων (πρώην tabs 1–6 του app.py)
- **AstroCheck_Career.py** — επαγγελματικός προσανατολισμός (πρώην tab7)

Ο κοινός κώδικας μετακινήθηκε στο `core/` ως πραγματικό Python πακέτο
(`core/__init__.py` + όλα τα πρώην modules ρίζας), με τα internal imports
προσαρμοσμένα σε σχετικά (`from .astrology import ...` κ.λπ.). Τα κοινά
.docx πρότυπα μετακινήθηκαν στο `references/`.

## Ουσιαστική αλλαγή λειτουργικότητας: AstroCheck Career

Στο παλιό `app.py`, το tab7 (επαγγελματικός προσανατολισμός) απαιτούσε
υποχρεωτικά ολοκληρωμένη ΚΑΙ ελεγμένη ανάλυση 12 Οίκων πριν επιτρέψει
οτιδήποτε:

```python
if not (chart and st.session_state.analysis and st.session_state.validation and st.session_state.validation.ok):
    st.warning("Πρώτα ολοκλήρωσε και έλεγξε την τεχνική ανάλυση στις καρτέλες 4–5.")
    st.stop()
```

Αυτός ο περιορισμός **αφαιρέθηκε**. Το νέο `AstroCheck_Career.py` χρειάζεται
μόνο το ανεβασμένο Astrodienst PDF (`chart`) — τίποτα άλλο. Αυτό ήταν εφικτό
χωρίς κίνδυνο επειδή το `build_orientation_source(chart)` στο `prompts.py`
ήταν ήδη σχεδιασμένο να αντλεί δεδομένα απευθείας από το chart, ανεξάρτητα
από την αφηγηματική ανάλυση των 12 Οίκων — απλώς δεν χρησιμοποιούνταν έτσι
πριν.

Η υπόλοιπη λογική του tab7 (επιλογή υπηρεσίας/παρουσίασης, ερώτηση για
κυπριακό εκπαιδευτικό σύστημα, δημιουργία εντολής, μηχανικός έλεγχος μέσω
`validate_orientation`) παρέμεινε ίδια — μόνο η πύλη εισόδου άλλαξε.

## Cross-linking μεταξύ apps

Επειδή τα 3 apps είναι πραγματικά ξεχωριστά Streamlit deployments (τρία
διαφορετικά URLs), δεν μπορούν να χρησιμοποιήσουν `st.page_link` μεταξύ
τους. Προστέθηκε `core/site_config.py` που διαβάζει τα URLs των άλλων apps
από Streamlit Secrets (`HOME_URL`, `ANALYSIS_URL`, `CAREER_URL`), με
placeholder τιμές μέχρι να γίνει το πρώτο deploy. Κάθε app δείχνει στην
κορυφή του `st.link_button` προς τα άλλα δύο.

## Tests

- `test_parser.py` ενημερώθηκε ώστε να εισάγει από `core.parser` αντί για
  `parser`.
- `pytest.ini` παρέμεινε λειτουργικά ίδιο (`pythonpath = .`, `testpaths =
  tests`) — δουλεύει αμετάβλητο επειδή το `core/` είναι υποφάκελος του ίδιου
  repo root.
- Επιβεβαιώθηκε με headless εκκίνηση και των τριών apps (`streamlit run
  ... --server.headless true`) ότι φορτώνουν χωρίς σφάλμα εισαγωγής ή
  runtime στο πρώτο render.

## Τι ΔΕΝ άλλαξε

- Οι κανόνες του validator (Κανόνας 6Β, υποχρεωτικές σύνοδοι με γωνίες,
  Rule 0Γ για τη σύντομη έκδοση ενηλίκου, κ.λπ.) παρέμειναν ακριβώς ίδιοι —
  δεν έγινε καμία αλλαγή μέσα στο `validator.py` πέρα από το import path.
- Η ροή του AstroCheck Analysis (tabs 1–6) παρέμεινε ίδια βήμα-προς-βήμα.
