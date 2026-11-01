"""
core/talent_map.py -- AstroCheck Career (v22, ΠΡΟΧΕΙΡΟ -- προς έλεγχο από αστρολόγο)

Οι ΠΙΝΑΚΕΣ ΑΝΤΙΣΤΟΙΧΙΣΗΣ της μηχανής ταλέντων (core/talent_engine.py).
Εδώ βρίσκεται όλη η αστρολογική «γνώση» της υβριδικής μεθόδου, σε απλούς πίνακες
ώστε να ελέγχεται και να διορθώνεται χωρίς να αγγίζεται ο κώδικας.

Πηγή: οι Κανόνες 4, 5, 6, 8 και 12 της δεσμευτικής εντολής v13.
"""

# ---------------------------------------------------------------- 1. Θέματα ταλέντων
# id -> (τίτλος el, τίτλος en). Ένα θέμα = μία «λειτουργική δυνατότητα» (Κανόνας
# ενοποίησης: δύο ταλέντα με την ίδια λειτουργία είναι ένα θέμα).
THEMES = {
    "LEAD": ("Ηγεσία και πρωτοβουλία", "Leadership and initiative"),
    "ORG": ("Οργάνωση και συνέπεια", "Organisation and consistency"),
    "ANALYSIS": ("Αναλυτική σκέψη και ακρίβεια", "Analytical thinking and precision"),
    "COMM": ("Επικοινωνία και λόγος", "Communication and expression in words"),
    "TEACH": ("Διδασκαλία και μετάδοση γνώσης", "Teaching and sharing knowledge"),
    "RESEARCH": ("Έρευνα σε βάθος", "In-depth research"),
    "INNOV": ("Πρωτότυπη σκέψη και νέες ιδέες", "Original thinking and new ideas"),   # v22.13: η τεχνολογία είναι τομέας
    "ART": ("Φαντασία και καλλιτεχνική έκφραση", "Imagination and artistic expression"),
    "DESIGN": ("Αισθητική και σχεδιασμός", "Aesthetics and design"),
    "DIPLO": ("Συνεργασία και διπλωματία", "Cooperation and diplomacy"),
    "JUSTICE": ("Αίσθηση του δικαίου", "A sense of fairness and justice"),
    "CARE": ("Ενσυναίσθηση και φροντίδα", "Empathy and care"),
    "HOSP": ("Φιλοξενία και εξυπηρέτηση", "Hospitality and service"),
    "ACTION": ("Δράση και φυσική ενέργεια", "Action and physical energy"),
    "BUILD": ("Πρακτική δημιουργία και κατασκευή", "Practical making and building"),
    "ENTRE": ("Επιχειρηματικότητα και διαχείριση πόρων", "Enterprise and managing resources"),
    "STRAT": ("Στρατηγική σκέψη", "Strategic thinking"),
    "STORY": ("Δημιουργική γραφή και αφήγηση", "Creative writing and storytelling"),
    "COMMUNITY": ("Ομαδικότητα και κοινωνική οργάνωση", "Teamwork and community building"),
    "SUPPORT": ("Υποστήριξη και ενθάρρυνση", "Supporting and encouraging others"),
    "PERFORM": ("Δημόσια παρουσία και έκφραση", "Public presence and self-expression"),
    "EXPLORE": ("Εξερεύνηση και διεθνείς ορίζοντες", "Exploration and wider horizons"),
    # v22.14 (ΠΡΟΧΕΙΡΟ, ερώτηση Ε6): τεχνική/ψηφιακή ευχέρεια -- χωριστά από την πρωτοτυπία.
    "TECH": ("Τεχνολογία, υπολογιστές και δίκτυα", "Technology, computers and networks"),
}

PERSONAL = ("Ήλιος", "Σελήνη", "Ερμής", "Αφροδίτη", "Άρης")
ANGLES = ("Ωροσκόπος", "Μεσουράνημα")
SLOW = ("Δίας", "Κρόνος", "Ουρανός", "Ποσειδώνας", "Πλούτωνας", "Χείρωνας")
NODES = ("Βόρειος Δεσμός", "Νότιος Δεσμός")

# ---------------------------------------------------------------- 2. Πλανήτες (Κανόνες 4–5)
PLANET_THEMES = {
    "Ήλιος": ("LEAD", "PERFORM", "ENTRE"),
    "Σελήνη": ("CARE", "HOSP", "STORY"),
    "Ερμής": ("COMM", "ANALYSIS", "TEACH", "STORY", "TECH"),
    "Αφροδίτη": ("DESIGN", "ART", "DIPLO", "HOSP"),
    "Άρης": ("ACTION", "LEAD", "ENTRE", "BUILD"),
    "Δίας": ("TEACH", "EXPLORE", "JUSTICE", "ENTRE"),
    "Κρόνος": ("ORG", "BUILD", "ANALYSIS", "JUSTICE"),
    "Ουρανός": ("INNOV", "COMMUNITY", "TECH"),
    "Ποσειδώνας": ("ART", "CARE", "STORY"),
    "Πλούτωνας": ("RESEARCH", "STRAT"),
    "Χείρωνας": ("SUPPORT", "TEACH"),
}

# ---------------------------------------------------------------- 3. Ζώδια (Κανόνας 8 + παράδοση)
# Το ΠΡΩΤΟ θέμα κάθε ζωδίου είναι το «κύριο» -- χρησιμοποιείται στις συγκεντρώσεις.
SIGN_THEMES = {
    "Κριός": ("LEAD", "ACTION"),
    "Ταύρος": ("BUILD", "DESIGN", "ENTRE"),
    "Δίδυμοι": ("COMM", "STORY", "TEACH"),
    "Καρκίνος": ("CARE", "HOSP"),
    "Λέων": ("PERFORM", "LEAD", "ART"),
    "Παρθένος": ("ANALYSIS", "ORG", "SUPPORT"),
    "Ζυγός": ("JUSTICE", "DIPLO", "DESIGN"),
    "Σκορπιός": ("RESEARCH", "STRAT"),
    "Τοξότης": ("TEACH", "EXPLORE", "JUSTICE"),
    "Αιγόκερως": ("ORG", "STRAT", "ENTRE"),
    "Υδροχόος": ("INNOV", "COMMUNITY", "TECH"),
    "Ιχθύες": ("ART", "CARE", "STORY"),
}

# ---------------------------------------------------------------- 4. Βασικοί Οίκοι (Κανόνας 6)
HOUSE_THEMES = {
    1: ("LEAD", "ACTION", "PERFORM"),
    2: ("ENTRE", "BUILD"),
    3: ("COMM", "TEACH", "STORY"),
    5: ("ART", "PERFORM", "DESIGN"),
    6: ("ORG", "ANALYSIS", "SUPPORT"),
    9: ("TEACH", "EXPLORE", "RESEARCH", "JUSTICE"),
    10: ("LEAD", "ORG", "PERFORM"),
    11: ("COMMUNITY", "INNOV", "TECH"),
}

# ---------------------------------------------------------------- 5. Όψεις: ζεύγος -> θέμα
# Τα ίδια 59 ζεύγη με τη βιβλιοθήκη του δωρεάν ταλέντου (τουλάχιστον ένα προσωπικό
# σημείο· όχι Δεσμοί· όχι μόνο αργοί πλανήτες -- Κανόνας 5). Ο ΤΥΠΟΣ της όψης δεν
# αλλάζει το θέμα· αλλάζει τη διατύπωση (φυσικά / με εξάσκηση / μέσα από προσπάθεια).
PAIR_THEME = {
    ("Ήλιος", "Σελήνη"): "LEAD", ("Ήλιος", "Άρης"): "LEAD", ("Ήλιος", "Ωροσκόπος"): "PERFORM",
    ("Ήλιος", "Μεσουράνημα"): "LEAD", ("Σελήνη", "Ερμής"): "COMM", ("Σελήνη", "Αφροδίτη"): "HOSP",
    ("Σελήνη", "Άρης"): "ACTION", ("Σελήνη", "Ωροσκόπος"): "CARE", ("Σελήνη", "Μεσουράνημα"): "CARE",
    ("Ερμής", "Άρης"): "COMM", ("Ερμής", "Ωροσκόπος"): "COMM", ("Ερμής", "Μεσουράνημα"): "COMM",
    ("Αφροδίτη", "Άρης"): "ART", ("Αφροδίτη", "Ωροσκόπος"): "DESIGN", ("Αφροδίτη", "Μεσουράνημα"): "DESIGN",
    ("Άρης", "Ωροσκόπος"): "ACTION", ("Άρης", "Μεσουράνημα"): "ENTRE",
    ("Ήλιος", "Δίας"): "TEACH", ("Ήλιος", "Κρόνος"): "ORG", ("Ήλιος", "Ουρανός"): "INNOV",
    ("Ήλιος", "Ποσειδώνας"): "ART", ("Ήλιος", "Πλούτωνας"): "RESEARCH", ("Ήλιος", "Χείρωνας"): "SUPPORT",
    ("Σελήνη", "Δίας"): "HOSP", ("Σελήνη", "Κρόνος"): "CARE", ("Σελήνη", "Ουρανός"): "INNOV",
    ("Σελήνη", "Ποσειδώνας"): "CARE", ("Σελήνη", "Πλούτωνας"): "RESEARCH", ("Σελήνη", "Χείρωνας"): "SUPPORT",
    ("Ερμής", "Δίας"): "TEACH", ("Ερμής", "Κρόνος"): "ANALYSIS", ("Ερμής", "Ουρανός"): "TECH",
    ("Ερμής", "Ποσειδώνας"): "STORY", ("Ερμής", "Πλούτωνας"): "RESEARCH", ("Ερμής", "Χείρωνας"): "TEACH",
    ("Αφροδίτη", "Δίας"): "HOSP", ("Αφροδίτη", "Κρόνος"): "BUILD", ("Αφροδίτη", "Ουρανός"): "DESIGN",
    ("Αφροδίτη", "Ποσειδώνας"): "ART", ("Αφροδίτη", "Πλούτωνας"): "DESIGN", ("Αφροδίτη", "Χείρωνας"): "SUPPORT",
    ("Άρης", "Δίας"): "ACTION", ("Άρης", "Κρόνος"): "BUILD", ("Άρης", "Ουρανός"): "INNOV",
    ("Άρης", "Ποσειδώνας"): "PERFORM", ("Άρης", "Πλούτωνας"): "STRAT", ("Άρης", "Χείρωνας"): "SUPPORT",
    ("Δίας", "Ωροσκόπος"): "EXPLORE", ("Κρόνος", "Ωροσκόπος"): "ORG", ("Ουρανός", "Ωροσκόπος"): "INNOV",
    ("Ποσειδώνας", "Ωροσκόπος"): "ART", ("Πλούτωνας", "Ωροσκόπος"): "STRAT", ("Χείρωνας", "Ωροσκόπος"): "SUPPORT",
    ("Δίας", "Μεσουράνημα"): "TEACH", ("Κρόνος", "Μεσουράνημα"): "ORG", ("Ουρανός", "Μεσουράνημα"): "INNOV",
    ("Ποσειδώνας", "Μεσουράνημα"): "ART", ("Πλούτωνας", "Μεσουράνημα"): "STRAT",
    ("Χείρωνας", "Μεσουράνημα"): "SUPPORT",
}

# ---------------------------------------------------------------- 6. Θέμα -> τομείς (Κανόνας 12)
# Ονόματα ΑΚΡΙΒΩΣ όπως στον κατάλογο της εντολής. Οι τομείς υγείας (*) αποκλείονται
# από τη μηχανή (φραγμός υγείας, Κανόνας 15) -- ΔΕΝ περιλαμβάνονται εδώ.
THEME_FIELDS = {
    "LEAD": ("Επιχειρήσεις και επιχειρηματικότητα", "Δημόσια διοίκηση", "Πολιτική και δημόσια πολιτική"),
    "ORG": ("Οργάνωση και διοίκηση έργων", "Δημόσια διοίκηση", "Οικονομικά και χρηματοοικονομικές υπηρεσίες",
            "Μεταφορές, ναυτιλία και εφοδιαστική"),
    "ANALYSIS": ("Μαθηματικά και δεδομένα", "Έρευνα και ανάπτυξη", "Οικονομικά και χρηματοοικονομικές υπηρεσίες",
                 "Μηχανική και τεχνικές εφαρμογές"),
    "COMM": ("Επικοινωνία και μέσα", "Γλώσσες και ανθρωπιστικές σπουδές", "Εμπόριο και εξυπηρέτηση πελατών"),
    "TEACH": ("Εκπαίδευση και μάθηση", "Γλώσσες και ανθρωπιστικές σπουδές", "Πολιτισμός και πολιτιστική κληρονομιά"),
    "RESEARCH": ("Έρευνα και ανάπτυξη", "Βιοεπιστήμες και βιοτεχνολογία", "Κοινωνικές επιστήμες",
                 "Πολιτισμός και πολιτιστική κληρονομιά"),
    "INNOV": ("Τεχνολογία και ψηφιακά συστήματα", "Παιχνίδια και διαδραστικές εμπειρίες", "Αεροπορία και διάστημα",
              "Περιβάλλον και ενέργεια"),
    "ART": ("Εικαστικές τέχνες και οπτικός σχεδιασμός", "Μουσική και ήχος",
            "Κινηματογράφος και οπτικοακουστικά μέσα", "Παραστατικές τέχνες"),
    "DESIGN": ("Εικαστικές τέχνες και οπτικός σχεδιασμός", "Μόδα και δημιουργικός σχεδιασμός",
               "Αρχιτεκτονική και χωρικός σχεδιασμός", "Ομορφιά και προσωπική φροντίδα"),
    "DIPLO": ("Διεθνείς σχέσεις και ανθρωπιστική δράση", "Νομική και δικαιοσύνη", "Επικοινωνία και μέσα",
              "Εμπόριο και εξυπηρέτηση πελατών"),
    "JUSTICE": ("Νομική και δικαιοσύνη", "Πολιτική και δημόσια πολιτική", "Δημόσια διοίκηση",
                "Διεθνείς σχέσεις και ανθρωπιστική δράση"),
    "CARE": ("Εκπαίδευση και μάθηση", "Κοινωνικές επιστήμες", "Τουρισμός και φιλοξενία"),
    "HOSP": ("Τουρισμός και φιλοξενία", "Εμπόριο και εξυπηρέτηση πελατών", "Τρόφιμα και αγροδιατροφή"),
    "ACTION": ("Αθλητισμός και άσκηση", "Ασφάλεια και υπηρεσίες έκτακτης ανάγκης",
               "Μεταφορές, ναυτιλία και εφοδιαστική", "Αεροπορία και διάστημα"),
    "BUILD": ("Μηχανική και τεχνικές εφαρμογές", "Αρχιτεκτονική και χωρικός σχεδιασμός",
              "Γεωργία, δασολογία και ζωική παραγωγή", "Περιβάλλον και ενέργεια"),
    "ENTRE": ("Επιχειρήσεις και επιχειρηματικότητα", "Εμπόριο και εξυπηρέτηση πελατών",
              "Οικονομικά και χρηματοοικονομικές υπηρεσίες"),
    "STRAT": ("Επιχειρήσεις και επιχειρηματικότητα", "Πολιτική και δημόσια πολιτική",
              "Οικονομικά και χρηματοοικονομικές υπηρεσίες", "Έρευνα και ανάπτυξη"),
    "STORY": ("Επικοινωνία και μέσα", "Κινηματογράφος και οπτικοακουστικά μέσα",
              "Γλώσσες και ανθρωπιστικές σπουδές", "Παιχνίδια και διαδραστικές εμπειρίες"),
    "COMMUNITY": ("Κοινωνικές επιστήμες", "Διεθνείς σχέσεις και ανθρωπιστική δράση",
                  "Πολιτική και δημόσια πολιτική", "Τεχνολογία και ψηφιακά συστήματα"),
    "SUPPORT": ("Εκπαίδευση και μάθηση", "Αθλητισμός και άσκηση", "Κοινωνικές επιστήμες"),
    "PERFORM": ("Παραστατικές τέχνες", "Επικοινωνία και μέσα", "Μουσική και ήχος", "Πολιτική και δημόσια πολιτική"),
    "TECH": ("Τεχνολογία και ψηφιακά συστήματα", "Μαθηματικά και δεδομένα", "Μηχανική και τεχνικές εφαρμογές",
             "Παιχνίδια και διαδραστικές εμπειρίες"),
    "EXPLORE": ("Τουρισμός και φιλοξενία", "Διεθνείς σχέσεις και ανθρωπιστική δράση",
                "Γλώσσες και ανθρωπιστικές σπουδές", "Πολιτισμός και πολιτιστική κληρονομιά"),
}
# Κατάσταση των πινάκων αντιστοίχισης: «draft» μέχρι να τους εγκρίνει αστρολόγος, τότε «approved».
TABLES_STATUS = "draft"

# ---------------------------------------------------------------- 7. Απόχρωση ταλέντου (v22.15-16, ΠΡΟΧΕΙΡΟ, Ε7)
# Δεύτερος τίτλος: «πώς» φαίνεται το ταλέντο σε αυτόν τον άνθρωπο. Βγαίνει από το «άλλο» σημείο
# ενός δείκτη -- τον πλανήτη ή το ζώδιο που ΔΕΝ είναι η πηγή του ταλέντου (π.χ. Ηγεσία από Άρη στον
# Οίκο 10, σε Ζυγό -> «με συνεργατικό πνεύμα»). ΤΡΕΙΣ διατυπώσεις ανά πλανήτη/ζώδιο, με το ίδιο νόημα,
# ώστε όταν το ίδιο σημείο χρωματίζει δύο ή τρία ταλέντα να μην επαναλαμβάνεται η ίδια φράση.
COLOURS = {
    "Ήλιος": (("ως κομμάτι του εαυτού σου", "as part of who you are"),
              ("με το δικό σου προσωπικό στίγμα", "with your own personal touch"),
              ("με όλη σου την καρδιά", "with all your heart")),
    "Σελήνη": (("με ευαισθησία στις ανάγκες των άλλων", "with sensitivity to the needs of others"),
               ("με ζεστασιά και φροντίδα", "with warmth and care"),
               ("νιώθοντας τι χρειάζονται οι άλλοι", "sensing what others need")),
    "Ερμής": (("με καθαρή και γρήγορη σκέψη", "with clear, quick thinking"),
              ("με ευκολία στα λόγια και στις ιδέες", "with an ease with words and ideas"),
              ("με ζωηρό και ευέλικτο μυαλό", "with a lively, flexible mind")),
    "Αφροδίτη": (("με αίσθηση του ωραίου", "with a sense of beauty"),
                 ("με γούστο και αρμονία", "with taste and harmony"),
                 ("με ευγένεια και καλαισθησία", "with grace and good taste")),
    "Άρης": (("με θάρρος και αποφασιστικότητα", "with courage and determination"),
             ("με ενέργεια και δράση", "with energy and action"),
             ("με τόλμη να κάνεις το πρώτο βήμα", "with the nerve to take the first step")),
    "Δίας": (("με ευρύτητα και αισιοδοξία", "with breadth and optimism"),
             ("με γενναιοδωρία και ανοιχτό μυαλό", "with generosity and an open mind"),
             ("βλέποντας τη μεγάλη εικόνα", "seeing the bigger picture")),
    "Κρόνος": (("με σταθερότητα και ποιότητα", "with steadiness and quality"),
               ("με συνέπεια και αντοχή", "with consistency and stamina"),
               ("με σοβαρότητα και υπευθυνότητα", "with seriousness and responsibility")),
    "Ουρανός": (("με πρωτότυπη ματιά", "with an original outlook"),
                ("με απρόσμενες ιδέες", "with unexpected ideas"),
                ("με διάθεση να αλλάζεις τα συνηθισμένα", "with a wish to change the usual way of doing things")),
    "Ποσειδώνας": (("με φαντασία και έμπνευση", "with imagination and inspiration"),
                   ("με διαίσθηση για ό,τι δεν φαίνεται", "with a feel for what is not visible"),
                   ("με όραμα και δημιουργικότητα", "with vision and creativity")),
    "Πλούτωνας": (("με επιμονή και δύναμη", "with persistence and strength"),
                  ("πηγαίνοντας στην ουσία των πραγμάτων", "getting to the heart of things"),
                  ("με δύναμη να αλλάζεις όσα δεν λειτουργούν", "with the strength to change what does not work")),
    "Χείρωνας": (("με κατανόηση για τις δυσκολίες των άλλων", "with understanding for the difficulties of others"),
                 ("με διάθεση να στέκεσαι δίπλα σε όποιον το χρειάζεται", "ready to stand by anyone who needs it"),
                 ("με ευαισθησία για όσους δυσκολεύονται", "with sensitivity to those who struggle")),
    "Κριός": (("με τόλμη και γρήγορη δράση", "with boldness and quick action"),
              ("με ενθουσιασμό για νέα ξεκινήματα", "with enthusiasm for new beginnings"),
              ("με αυθορμητισμό και ζωντάνια", "with spontaneity and liveliness")),
    "Ταύρος": (("με υπομονή και πρακτικότητα", "with patience and practicality"),
               ("με σταθερά βήματα", "with steady steps"),
               ("με αίσθηση για ό,τι έχει αξία και διαρκεί", "with a feel for what has value and lasts")),
    "Δίδυμοι": (("με περιέργεια και ευελιξία", "with curiosity and flexibility"),
                ("με ευκολία να μαθαίνεις και να μοιράζεσαι", "with an ease for learning and sharing"),
                ("με ενδιαφέρον για πολλά πράγματα μαζί", "with an interest in many things at once")),
    "Καρκίνος": (("με φροντίδα και προστατευτικότητα", "with care and protectiveness"),
                 ("με ζεστασιά σαν σε οικογένεια", "with a family-like warmth"),
                 ("δημιουργώντας αίσθημα ασφάλειας", "creating a sense of safety")),
    "Λέων": (("με ζεστασιά και αυτοπεποίθηση", "with warmth and confidence"),
             ("με γενναιοδωρία και κέφι", "with generosity and good spirits"),
             ("με δημιουργική λάμψη", "with a creative spark")),
    "Παρθένος": (("με προσοχή στη λεπτομέρεια", "with attention to detail"),
                 ("με μέθοδο και τάξη", "with method and order"),
                 ("με διάθεση να βελτιώνεις ό,τι πιάνεις", "with a wish to improve whatever you touch")),
    "Ζυγός": (("με διάθεση για συνεργασία και ισορροπία", "with a wish for cooperation and balance"),
              ("με δίκαιη και ισορροπημένη ματιά", "with a fair and balanced view"),
              ("ακούγοντας και τις δύο πλευρές", "listening to both sides")),
    "Σκορπιός": (("με ένταση και βάθος", "with intensity and depth"),
                 ("με αφοσίωση μέχρι το τέλος", "with commitment to the end"),
                 ("με ματιά που βλέπει πίσω από τα φαινόμενα", "seeing beyond appearances")),
    "Τοξότης": (("με ενθουσιασμό και ευρύ ορίζοντα", "with enthusiasm and a broad horizon"),
                ("με αγάπη για τη μάθηση", "with a love of learning"),
                ("με διάθεση για νέες εμπειρίες", "with an appetite for new experiences")),
    "Αιγόκερως": (("με υπευθυνότητα και μακροπρόθεσμο στόχο", "with responsibility and long-term goals"),
                  ("με σχέδιο και πειθαρχία", "with a plan and discipline"),
                  ("χτίζοντας βήμα βήμα κάτι που μένει", "building step by step something that lasts")),
    "Υδροχόος": (("με ανεξάρτητη σκέψη", "with independent thinking"),
                 ("με ματιά στο μέλλον", "with an eye on the future"),
                 ("με ελεύθερο πνεύμα", "with a free spirit")),
    "Ιχθύες": (("με ευαισθησία και διαίσθηση", "with sensitivity and intuition"),
               ("με συμπόνια και φαντασία", "with compassion and imagination"),
               ("με καλοσύνη και κατανόηση", "with kindness and understanding")),
}


# v22.19: ΕΙΔΙΚΗ φράση για συγκεκριμένο συνδυασμό (ταλέντο, πλανήτης/ζώδιο). Προηγείται της γενικής,
# ώστε η απόχρωση να ταιριάζει ακριβώς στο ταλέντο. Όπου δεν υπάρχει, μένει η γενική φράση (COLOURS).
COLOUR_SPECIFIC = {
    ("ACTION", "Δίας"): ("με ενθουσιασμό για νέες προκλήσεις", "with enthusiasm for new challenges"),
    ("ACTION", "Σελήνη"): ("ακολουθώντας το ένστικτό σου", "following your instincts"),
    ("ANALYSIS", "Άρης"): ("με γρήγορο και κοφτερό μυαλό", "with a quick, sharp mind"),
    ("ANALYSIS", "Ήλιος"): ("με προσοχή που είναι κομμάτι σου", "with a care that is part of you"),
    ("ANALYSIS", "Ερμής"): ("με καθαρή λογική", "with clear logic"),
    ("ANALYSIS", "Κρόνος"): ("με υπομονή στη λεπτομέρεια", "with patience for detail"),
    ("ART", "Άρης"): ("με πάθος και ένταση", "with passion and intensity"),
    ("ART", "Ήλιος"): ("με δημιουργικότητα που σε αντιπροσωπεύει", "with creativity that represents you"),
    ("ART", "Αφροδίτη"): ("με αίσθηση για το όμορφο και το αρμονικό", "with a feel for beauty and harmony"),
    ("ART", "Λέων"): ("με χαρά να δημιουργείς και να το μοιράζεσαι", "with joy in creating and sharing it"),
    ("BUILD", "Άρης"): ("με ενέργεια να ξεκινάς και να ολοκληρώνεις", "with energy to start and finish"),
    ("BUILD", "Αφροδίτη"): ("φτιάχνοντας πράγματα όμορφα και χρήσιμα", "creating things that are beautiful and useful"),
    ("BUILD", "Ζυγός"): ("με αίσθηση αναλογίας και ισορροπίας", "with a sense of proportion and balance"),
    ("BUILD", "Κρόνος"): ("με υπομονή και προσοχή στην ποιότητα", "with patience and care for quality"),
    ("CARE", "Ήλιος"): ("με ζεστασιά που βγαίνει από την καρδιά σου", "with warmth that comes from the heart"),
    ("CARE", "Παρθένος"): ("με πρακτική βοήθεια και φροντίδα στη λεπτομέρεια", "with practical help and care in the details"),
    ("CARE", "Ιχθύες"): ("με συμπόνια για όσους δυσκολεύονται", "with compassion for those who struggle"),
    ("CARE", "Κρόνος"): ("με σταθερότητα και υπευθυνότητα", "with steadiness and responsibility"),
    ("CARE", "Ποσειδώνας"): ("με φαντασία για το τι χρειάζεται ο άλλος", "with imagination for what others need"),
    ("COMM", "Άρης"): ("με λόγο άμεσο και πειστικό", "with a direct, persuasive voice"),
    ("COMM", "Ήλιος"): ("με λόγο που βγαίνει από μέσα σου", "with a voice that comes from within"),
    ("COMM", "Αφροδίτη"): ("με ευγένεια και χάρη στον λόγο", "with grace and courtesy when you speak"),
    ("COMM", "Σελήνη"): ("με λόγο ζεστό που αγγίζει", "with a warm tone that touches others"),
    ("COMMUNITY", "Ήλιος"): ("βάζοντας τον εαυτό σου στην ομάδα", "putting yourself into the group"),
    ("COMMUNITY", "Πλούτωνας"): ("με δύναμη να κινητοποιείς ομάδες", "with the power to mobilise groups"),
    ("COMMUNITY", "Κρόνος"): ("με σταθερή δέσμευση στον κοινό στόχο", "with a steady commitment to the shared goal"),
    ("COMMUNITY", "Δίας"): ("με αισιοδοξία για το κοινό καλό", "with optimism for the common good"),
    ("DESIGN", "Αιγόκερως"): ("με λιτή κομψότητα που αντέχει στον χρόνο", "with a simple elegance that lasts"),
    ("DESIGN", "Ουρανός"): ("με πρωτότυπο και μοντέρνο ύφος", "with an original, modern style"),
    ("DESIGN", "Πλούτωνας"): ("με βάθος, πέρα από την επιφάνεια", "with depth, beyond the surface"),
    ("ENTRE", "Άρης"): ("με τόλμη να ρισκάρεις", "with the courage to take risks"),
    ("ENTRE", "Αιγόκερως"): ("με σχέδιο και μακροπρόθεσμο στόχο", "with a plan and long-term goals"),
    ("ENTRE", "Δίας"): ("με όραμα για ανάπτυξη", "with a vision for growth"),
    ("ENTRE", "Παρθένος"): ("με προσοχή στα νούμερα και στη λεπτομέρεια", "with attention to figures and detail"),
    ("ENTRE", "Ταύρος"): ("με σταθερότητα και καλή αίσθηση της αξίας", "with steadiness and a good sense of value"),
    ("EXPLORE", "Δίας"): ("με αγάπη για νέους τόπους και ιδέες", "with a love of new places and ideas"),
    ("HOSP", "Αφροδίτη"): ("με ευγένεια και φιλικό χαμόγελο", "with courtesy and a friendly smile"),
    ("HOSP", "Δίας"): ("με γενναιοδωρία προς όλους", "with generosity towards everyone"),
    ("HOSP", "Καρκίνος"): ("κάνοντας τους άλλους να νιώθουν σαν στο σπίτι τους", "making others feel at home"),
    ("HOSP", "Σελήνη"): ("νιώθοντας τι χρειάζεται ο καθένας", "sensing what each person needs"),
    ("INNOV", "Άρης"): ("με τόλμη να δοκιμάζεις το καινούργιο", "with the nerve to try the new"),
    ("INNOV", "Ήλιος"): ("που φέρει το δικό σου στίγμα", "bearing your own mark"),
    ("INNOV", "Σελήνη"): ("με διαίσθηση για το τι θα λειτουργήσει", "with a feel for what will work"),
    ("JUSTICE", "Άρης"): ("με θάρρος να υπερασπίζεσαι το σωστό", "with the courage to stand up for what is right"),
    ("JUSTICE", "Ήλιος"): ("με αξίες που είναι κομμάτι σου", "with values that are part of you"),
    ("JUSTICE", "Δίας"): ("με ευρύ πνεύμα και ηθική πυξίδα", "with a broad mind and a moral compass"),
    ("JUSTICE", "Ερμής"): ("με επιχειρήματα καθαρά και τεκμηριωμένα", "with clear, well-founded arguments"),
    ("JUSTICE", "Κρόνος"): ("με σεβασμό στους κανόνες και στην ευθύνη", "with respect for rules and responsibility"),
    ("JUSTICE", "Πλούτωνας"): ("με δύναμη να αλλάζεις ό,τι είναι άδικο", "with the strength to change what is unfair"),
    ("LEAD", "Άρης"): ("με θάρρος να μπαίνεις μπροστά", "with the courage to step forward"),
    ("LEAD", "Δίδυμοι"): ("με λόγο που κινητοποιεί", "with words that motivate"),
    ("LEAD", "Ερμής"): ("με καθαρές οδηγίες και ιδέες", "with clear directions and ideas"),
    ("LEAD", "Ζυγός"): ("με συνεργατικό πνεύμα", "with a cooperative spirit"),
    ("LEAD", "Καρκίνος"): ("με προστατευτική φροντίδα για την ομάδα", "with protective care for the team"),
    ("LEAD", "Λέων"): ("με ζεστασιά και αυτοπεποίθηση που εμπνέει", "with warmth and confidence that inspire"),
    ("LEAD", "Παρθένος"): ("με οργάνωση και προσοχή στη λεπτομέρεια", "with organisation and attention to detail"),
    ("LEAD", "Σελήνη"): ("με ευαισθησία στις ανάγκες της ομάδας", "with sensitivity to the team's needs"),
    ("LEAD", "Σκορπιός"): ("με αποφασιστικότητα και βάθος", "with determination and depth"),
    ("LEAD", "Ταύρος"): ("με σταθερότητα και ψυχραιμία", "with steadiness and calm"),
    ("LEAD", "Υδροχόος"): ("με νέες ιδέες για το πώς δουλεύει μια ομάδα", "with new ideas on how a team works"),
    ("ORG", "Ήλιος"): ("με τάξη που είναι κομμάτι του εαυτού σου", "with an order that is part of who you are"),
    ("ORG", "Ερμής"): ("με καθαρό σχέδιο και σωστή σειρά", "with a clear plan and the right order"),
    ("PERFORM", "Άρης"): ("με ενέργεια και τόλμη μπροστά σε κοινό", "with energy and boldness in front of an audience"),
    ("PERFORM", "Ήλιος"): ("με φυσική λάμψη", "with a natural radiance"),
    ("PERFORM", "Αφροδίτη"): ("με χάρη και γοητεία", "with grace and charm"),
    ("PERFORM", "Ερμής"): ("με λόγο ζωντανό και έξυπνο", "with lively, witty words"),
    ("PERFORM", "Ιχθύες"): ("με ευαισθησία που συγκινεί", "with a sensitivity that moves others"),
    ("PERFORM", "Ποσειδώνας"): ("με φαντασία που μαγεύει", "with an imagination that captivates"),
    ("RESEARCH", "Ήλιος"): ("με επιμονή να φτάσεις στην αλήθεια", "with persistence to reach the truth"),
    ("RESEARCH", "Ερμής"): ("με κοφτερές ερωτήσεις και καθαρή σκέψη", "with sharp questions and clear thinking"),
    ("RESEARCH", "Σελήνη"): ("με διαίσθηση για ό,τι κρύβεται", "with an intuition for what is hidden"),
    ("STORY", "Δίδυμοι"): ("με ζωντάνια και ευκολία στις λέξεις", "with liveliness and an ease with words"),
    ("STORY", "Ερμής"): ("με λέξεις που βρίσκουν τον στόχο τους", "with words that hit the mark"),
    ("STORY", "Ιχθύες"): ("με φαντασία και ευαισθησία", "with imagination and sensitivity"),
    ("STORY", "Ποσειδώνας"): ("με εικόνες που ζωντανεύουν στο μυαλό", "with images that come alive in the mind"),
    ("STORY", "Σελήνη"): ("με ιστορίες που αγγίζουν το συναίσθημα", "with stories that touch the heart"),
    ("STRAT", "Άρης"): ("με γρήγορες και τολμηρές κινήσεις", "with quick, bold moves"),
    ("STRAT", "Πλούτωνας"): ("βλέποντας πολλά βήματα μπροστά", "seeing many steps ahead"),
    ("SUPPORT", "Άρης"): ("με θάρρος να στέκεσαι δίπλα στους άλλους", "with the courage to stand by people"),
    ("SUPPORT", "Ήλιος"): ("με προσωπικό παράδειγμα που δίνει κουράγιο", "with a personal example that gives courage"),
    ("SUPPORT", "Αφροδίτη"): ("με ευγένεια και καλή διάθεση", "with kindness and good humour"),
    ("SUPPORT", "Σελήνη"): ("με τρυφερότητα και κατανόηση", "with tenderness and understanding"),
    ("TEACH", "Ήλιος"): ("μοιράζοντας όσα αγαπάς", "sharing what you love"),
    ("TEACH", "Ερμής"): ("με εξηγήσεις απλές και καθαρές", "with simple, clear explanations"),
    ("TEACH", "Υδροχόος"): ("με νέους τρόπους μάθησης", "with new ways of learning"),
    ("TEACH", "Χείρωνας"): ("με υπομονή για όσους δυσκολεύονται να μάθουν", "with patience for those who find learning hard"),
    ("TECH", "Ερμής"): ("με γρήγορη κατανόηση του πώς λειτουργούν τα συστήματα", "with a quick grasp of how systems work"),
    ("TECH", "Ουρανός"): ("με πρωτότυπες ψηφιακές λύσεις", "with original digital solutions"),
}


def colour_phrases(talent, lang: str = "el") -> list[str]:
    """Όλες οι αποχρώσεις ενός ταλέντου (Talent της μηχανής), με τη σειρά εμφάνισης."""
    return [colour_phrase(k, v, lang, talent.theme) for k, v, _ in talent.colours]


def colour_phrase(key: str, variant: int, lang: str = "el", theme: str = "") -> str:
    """Η απόχρωση του ταλέντου `theme` από το σημείο `key`: η ειδική φράση του συνδυασμού αν υπάρχει,
    αλλιώς η διατύπωση `variant` (0, 1, 2) της γενικής. "" αν δεν υπάρχει απόχρωση."""
    specific = COLOUR_SPECIFIC.get((theme, key))
    if specific:
        return specific[0 if lang == "el" else 1]
    options = COLOURS.get(key) or ()
    if not options:
        return ""
    return options[min(variant, len(options) - 1)][0 if lang == "el" else 1]

HEALTH_FIELDS = ("Υγεία και θεραπευτικές υπηρεσίες", "Ψυχολογία και κοινωνική φροντίδα", "Διατροφή και διαιτολογία")

# ---------------------------------------------------------------------------
# ΦΡΑΓΜΟΣ ΥΓΕΙΑΣ (Κανόνας 15) -- ΠΡΟΧΕΙΡΟ για έλεγχο από αστρολόγο.
# Ένας τομέας υγείας προτείνεται ΜΟΝΟ αν ο χάρτης έχει ΔΥΟ διακριτούς δείκτες από τη λίστα του
# (από ΔΙΑΦΟΡΕΤΙΚΑ σημεία, και ο ένας τουλάχιστον Οίκος ή όψη -- όχι δύο ζώδια), ΚΑΙ η μηχανή έχει εγκρίνει τουλάχιστον ένα από τα «σχετικά ταλέντα».
# Τα γενικά ταλέντα (π.χ. Ενσυναίσθηση) ΔΕΝ αρκούν από μόνα τους -- χρειάζονται οι ειδικοί δείκτες.
# Μορφή δεικτών:
#   ("house", σημεία, οίκοι)       -> σημείο στον Οίκο
#   ("sign",  σημεία, ζώδια)       -> σημείο στο ζώδιο
#   ("pair",  σημείο, σημεία)      -> όψη Στενή/ισχυρή με οποιοδήποτε από τα σημεία
# ---------------------------------------------------------------------------
HEALTH_RULES = {
    "Υγεία και θεραπευτικές υπηρεσίες": {
        "related": ("CARE", "SUPPORT", "ANALYSIS", "RESEARCH", "ACTION"),
        "indicators": (
            ("house", ("Ήλιος", "Σελήνη", "Ερμής", "Άρης", "Χείρωνας"), (6,)),
            ("sign", ("Ήλιος", "Μεσουράνημα"), ("Παρθένος", "Σκορπιός")),
            ("pair", "Χείρωνας", ("Ήλιος", "Σελήνη", "Άρης", "Ωροσκόπος", "Μεσουράνημα")),
            ("pair", "Άρης", ("Πλούτωνας",)),
        ),
    },
    "Ψυχολογία και κοινωνική φροντίδα": {
        "related": ("CARE", "SUPPORT", "RESEARCH", "COMMUNITY", "DIPLO"),
        "indicators": (
            ("house", ("Ήλιος", "Σελήνη"), (8, 12)),
            ("sign", ("Ήλιος", "Σελήνη", "Μεσουράνημα"), ("Σκορπιός", "Ιχθύες")),
            ("pair", "Πλούτωνας", ("Ήλιος", "Σελήνη", "Ερμής")),
            ("pair", "Ποσειδώνας", ("Σελήνη",)),
            ("pair", "Χείρωνας", ("Σελήνη", "Ερμής")),
        ),
    },
    "Διατροφή και διαιτολογία": {
        "related": ("CARE", "HOSP", "ANALYSIS", "SUPPORT", "BUILD"),
        "indicators": (
            ("house", ("Σελήνη", "Αφροδίτη", "Ερμής"), (6,)),
            ("sign", ("Σελήνη", "Αφροδίτη"), ("Παρθένος", "Ταύρος")),
            ("pair", "Σελήνη", ("Αφροδίτη", "Χείρωνας")),
            ("pair", "Αφροδίτη", ("Χείρωνας",)),
        ),
    },
}
