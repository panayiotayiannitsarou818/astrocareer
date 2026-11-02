"""
core/talent_report.py -- AstroCheck Career (v22)

Αναφορά από τη ΜΗΧΑΝΗ ΤΑΛΕΝΤΩΝ (υβριδική μέθοδος, επιλογή Γ):
  * ποια ταλέντα / ποιοι τομείς      -> core/talent_engine.py (κανόνες, χωρίς AI)
  * τι γράφει για το καθένα          -> core/data/talent_texts.json (έτοιμα κείμενα, χωρίς AI)
  * εσωτερικό δελτίο ελέγχου         -> όλοι οι δείκτες, η βάση τεκμηρίωσης, ο φραγμός υγείας
Κόστος AI: μηδέν. Ο ίδιος χάρτης δίνει πάντα την ίδια αναφορά.
"""
from __future__ import annotations

from dataclasses import dataclass

from .docx_builder import build_orientation_audit_docx, build_orientation_client_docx
from .pipeline import AUDIT_TITLE, audit_docx_filename, client_docx_filename, service_title
from .talent_map import colour_phrases
from .talent_engine import EngineResult, run_engine
from .talent_growth import PHRASES as GROWTH_PHRASES, SEPARATOR
from .talent_texts import field_text, talent_text
from .teaser import pick_teaser

RANKS = ("κυρίαρχο", "βασικό", "αναδυόμενο")

TXT = {
    "el": {
        "intro": ("Η αναφορά αυτή παρουσιάζει τα ταλέντα και τις κλίσεις που φαίνονται στον γενέθλιο χάρτη, και "
                  "τους επαγγελματικούς τομείς όπου μπορούν να αξιοποιηθούν. Περιγράφει δυνατότητες, όχι "
                  "βεβαιότητες: τι θα γίνει, εξαρτάται από τις επιλογές, την προσπάθεια και τις ευκαιρίες σου."),
        "who": "Τι σε χαρακτηρίζει",
        "talents": "Τα ταλέντα σου",
        "rank": {"κυρίαρχο": "Κυρίαρχα ταλέντα", "βασικό": "Βασικά ταλέντα", "αναδυόμενο": "Ταλέντα που αναδύονται"},
        "rank_note": {
            "κυρίαρχο": "Τα πιο έντονα ταλέντα σου: αυτά που φαίνονται πιο καθαρά και μπορεί να τα αναγνωρίζεις ήδη στον εαυτό σου.",
            "βασικό": ("Ταλέντα με καλή, σταθερή βάση. Είναι λιγότερο έντονα από τα κυρίαρχα, αλλά είναι πραγματικές "
                       "δυνάμεις σου και αξίζει να τα αξιοποιήσεις."),
            "αναδυόμενο": "Ταλέντα που φαίνονται πιο αχνά για την ώρα και χρειάζονται περισσότερη εξάσκηση για να αναπτυχθούν.",
        },
        # v22.31: όταν ΟΛΑ τα ταλέντα είναι αναδυόμενα, ουδέτερη επικεφαλίδα (χωρίς σύγκριση «πιο αχνά»).
        "all_emerging": ("Τα ταλέντα σου",
                         "Ταλέντα που φαίνονται στον χάρτη σου και δυναμώνουν όσο τα δοκιμάζεις στην πράξη."),
        "develop": "Πώς να το καλλιεργήσεις:",
        "summary": "Συνοπτικά, τα ταλέντα σου",
        # v22.34: εξηγείται και η ΣΕΙΡΑ των ταλέντων (ιδιοκτήτρια).
        "summary_note": ("Η σειρά δεν είναι τυχαία: πρώτα είναι τα ταλέντα που φαίνονται πιο έντονα στον χάρτη σου. "
                         "Όλα αυτά είναι δυνατότητες. Το πόσο θα αναπτυχθεί το καθένα εξαρτάται από τις επιλογές και "
                         "την εξάσκησή σου."),
        # v22.18/v22.45: 6 διατυπώσεις ανά τρόπο ανάπτυξης -- σε κάθε αναφορά δεν επαναλαμβάνεται η ίδια πρόταση.
        "growth_long": {
            "easy": ["Συχνά το κάνεις χωρίς ιδιαίτερη προσπάθεια, σχεδόν από ένστικτο.",
                     "Είναι από τα πράγματα που ίσως σου έρχονται φυσικά, χωρίς να το σκεφτείς πολύ.",
                     "Μπορεί να το χρησιμοποιείς ήδη, συχνά χωρίς καν να το προσέχεις.",
                     "Οι άλλοι ίσως το βλέπουν σε σένα πριν το αναγνωρίσεις εσύ.",
                     "Ίσως είναι κάτι που κάνεις τόσο φυσικά, ώστε να μην το θεωρείς καν ταλέντο.",
                     "Μπορεί να είναι ένα από τα σημεία όπου νιώθεις πιο άνετα με τον εαυτό σου."],
            "mixed": ["Ξεκινά από μια φυσική ευκολία, και η εξάσκηση μπορεί να το κάνει ακόμη πιο δυνατό.",
                      "Έχεις μια καλή αφετηρία· με λίγη δουλειά μπορεί να γίνει πραγματική δύναμη.",
                      "Κάποια κομμάτια του ίσως σου βγαίνουν εύκολα, ενώ άλλα θέλουν περισσότερη προσπάθεια — και τα δύο μετρούν.",
                      "Η φυσική κλίση υπάρχει· η τριβή με την πράξη μπορεί να την ακονίσει.",
                     "Η βάση είναι καλή· ό,τι λείπει ακόμη μπορεί να συμπληρωθεί με την εμπειρία.",
                     "Εκεί όπου σου βγαίνει εύκολα, μπορείς να πατήσεις για να δυναμώσεις και τα υπόλοιπα."],
            "opportunity": ["Δυναμώνει όταν του δίνονται αφορμές, γι' αυτό αξίζει να αναζητάς περιστάσεις για να το δοκιμάσεις.",
                            "Κάθε ευκαιρία να το χρησιμοποιήσεις μπορεί να το κάνει πιο σταθερό.",
                            "Αξίζει να του δίνεις χώρο· όσο περισσότερο το χρησιμοποιείς, τόσο πιο καθαρά μπορεί να φαίνεται.",
                            "Μια κατάλληλη αφορμή, όπως ένα έργο ή μια ομάδα, μπορεί να το φέρει στην επιφάνεια.",
                     "Χρειάζεται το κατάλληλο περιβάλλον· όταν το βρει, μπορεί να σε εκπλήξει.",
                     "Μπορεί να κρύβεται μέχρι να βρεθεί η σωστή περίσταση για να εκφραστεί."],
            "practice": [("Ίσως χρειαστεί λίγος χρόνος μέχρι να αναπτυχθεί· αν δεν σου βγαίνει ακόμη εύκολα, αυτό δεν "
                          "σημαίνει ότι λείπει το ταλέντο, και με τον καιρό συχνά γίνεται από τα πιο δυνατά σου σημεία."),
                         "Μπορεί να μη σου βγαίνει πάντα εύκολα· η σταθερή εξάσκηση συχνά το μετατρέπει σε πραγματική δύναμη.",
                         "Οι δυσκολίες στην αρχή είναι φυσικές για αυτό το ταλέντο και δεν σημαίνουν ότι δεν το έχεις.",
                         "Με υπομονή και επανάληψη, ό,τι τώρα ίσως θέλει κόπο μπορεί αργότερα να γίνει δεύτερη φύση σου.",
                     "Είναι ταλέντο που ωριμάζει σιγά σιγά· κάθε μικρό βήμα μετρά.",
                     "Ό,τι χτίζεται με κόπο συχνά κρατά περισσότερο από ό,τι έρχεται εύκολα."],
            "open": ["Η πραγματική του δύναμη θα φανεί όταν το δοκιμάσεις σε πραγματικές καταστάσεις.",
                     "Αξίζει να το δοκιμάσεις στην πράξη, για να δεις πόσο σου ταιριάζει.",
                     "Η εμπειρία μπορεί να σου δείξει πόσο μακριά μπορεί να φτάσει.",
                     "Αν το δοκιμάσεις σε κάτι συγκεκριμένο, θα καταλάβεις καλύτερα τι μπορεί να σου δώσει.",
                     "Μένει να το ανακαλύψεις: οι πραγματικές καταστάσεις θα δείξουν τη μορφή του.",
                     "Μια πρώτη δοκιμή, ακόμη και μικρή, μπορεί να σου δείξει πολλά για αυτό."],
        },
        "fields": "Επαγγελματικοί τομείς που αξίζει να εξερευνήσεις",
        # v22.47 (σημειώσεις αστρολόγου): πώς μαθαίνεις -- από τα στοιχεία των 5 προσωπικών πλανητών
        "learn": "Πώς μαθαίνεις καλύτερα",
        "learn_note": "Ο τρόπος που μαθαίνεις πιο εύκολα μπορεί να βοηθήσει κάθε ταλέντο σου να αναπτυχθεί.",
        "learn_items": {
            "fire": "**Μέσα από τη δράση:** όταν δοκιμάζεις στην πράξη, με κίνηση, προκλήσεις και άμεσο αποτέλεσμα.",
            "earth": "**Βήμα βήμα:** με σαφή οργάνωση, πρακτικά παραδείγματα και σταθερό ρυθμό, χτίζοντας το ένα πάνω στο άλλο.",
            "air": "**Μέσα από την αλληλεπίδραση:** συζητώντας, ρωτώντας και ανταλλάσσοντας ιδέες με άλλους.",
            "water": ("**Μέσα από τη συναισθηματική σύνδεση:** όταν κάτι σε αγγίζει, όταν βλέπεις το νόημά του για "
                      "τους ανθρώπους ή όταν εμπιστεύεσαι αυτόν που σε διδάσκει."),
        },
        "play": "Τι να παρατηρήσεις στο παιχνίδι",
        "play_note": "Για τον γονιό: μικρές ενδείξεις στο παιχνίδι του παιδιού που μπορεί να επιβεβαιώνουν τα παραπάνω.",
        "play_items": {
            "fire": "**Εξερεύνηση και κίνηση:** αν ζητά να βγει έξω, να εξερευνήσει και να δοκιμάσει καινούργια πράγματα.",
            "earth": "**Δομημένες δραστηριότητες:** αν χαίρεται τις κατασκευές, τους κανόνες και ό,τι γίνεται με σαφή βήματα.",
            "air": "**Γρίφοι και παιχνίδια λογικής:** αν το τραβούν οι γρίφοι, οι ερωτήσεις και τα παιχνίδια με λέξεις.",
            "water": "**Παιχνίδι φαντασίας:** αν φτιάχνει ιστορίες, ρόλους και φανταστικούς κόσμους.",
        },
        # v22.28: εξηγείται και η ΣΕΙΡΑ των τομέων (ιδιοκτήτρια).
        "fields_note": ("Τομείς όπου συναντιούνται δύο ή περισσότερα από τα ταλέντα σου. Η σειρά δεν είναι τυχαία: "
                        "πρώτοι είναι οι τομείς όπου συναντιούνται τα περισσότερα και πιο δυνατά ταλέντα σου."),
        "fields_note_g": ("Οι περισσότεροι είναι τομείς όπου συναντιούνται δύο ή περισσότερα από τα ταλέντα σου· "
                          "όπου ένα ταλέντο δεν συναντιέται με άλλο, προστίθεται ο πιο ταιριαστός τομέας γι' αυτό. "
                          "Η σειρά δεν είναι τυχαία: πρώτοι είναι οι τομείς όπου συναντιούνται τα περισσότερα και πιο "
                          "δυνατά ταλέντα σου, και τελευταίοι όσοι ταιριάζουν σε ένα μόνο ταλέντο."),
        "best_for": "Ο πιο ταιριαστός τομέας για το ταλέντο «{t}».",
        "glance": "Με μια ματιά",
        "glance_note": "Κάθε ● είναι ένα από τα ταλέντα σου που οδηγεί σε αυτόν τον τομέα.",
        "based_on": "Στηρίζεται σε",
        "other": "Άλλες κατευθύνσεις",
        "other_note": "Τομείς που συνδέονται με ένα από τα ταλέντα σου και αξίζει να τους έχεις υπόψη.",
        "next": "Επόμενα βήματα",
        "next_lines": [
            "Διάλεξε ένα ή δύο από τα κυρίαρχα ταλέντα σου και βρες μια μικρή δραστηριότητα για να τα δοκιμάσεις στην πράξη.",
            "Μίλησε με ανθρώπους που δουλεύουν στους τομείς που σε ενδιαφέρουν και ρώτα πώς είναι η καθημερινότητά τους.",
            "Συζήτησε την αναφορά με έναν σύμβουλο επαγγελματικού προσανατολισμού, μαζί με τα ενδιαφέροντα και τις σπουδές σου.",
        ],
        "closing": ("Η αναφορά είναι εργαλείο αυτογνωσίας και έμπνευσης. Δεν αντικαθιστά τον επαγγελματικό "
                    "προσανατολισμό, τα τεστ ικανοτήτων ή τη γνώμη ανθρώπων που σε γνωρίζουν."),
        "dynasai": ("Η αναφορά αυτή δεν είναι υπόσχεση για το τι θα γίνεις· είναι υπενθύμιση ότι δύνασαι "
                    "να δοκιμάσεις, να επιλέξεις και να εξελιχθείς."),
    },
    "en": {
        "intro": ("This report presents the talents and inclinations shown in the birth chart, and the career fields "
                  "where they can be put to use. It describes possibilities, not certainties: what happens depends on "
                  "your choices, your effort and the opportunities you meet."),
        "who": "What characterises you",
        "talents": "Your talents",
        "rank": {"κυρίαρχο": "Leading talents", "βασικό": "Core talents", "αναδυόμενο": "Emerging talents"},
        "rank_note": {
            "κυρίαρχο": "Your most pronounced talents: the ones that show most clearly and that you may already recognise in yourself.",
            "βασικό": ("Talents with a good, steady base. They are less pronounced than the leading ones, but they are "
                       "real strengths and worth putting to use."),
            "αναδυόμενο": "Talents that show more faintly for now and need more practice to develop.",
        },
        "all_emerging": ("Your talents", "Talents that show in your chart and grow stronger as you try them out in practice."),
        "develop": "How to develop it:",
        "summary": "Your talents at a glance",
        "summary_note": ("The order is not random: the talents that show most strongly in your chart come first. "
                         "All of these are possibilities. How far each one develops depends on your choices and practice."),
        "growth_long": {
            "easy": ["You often do it without much effort, almost by instinct.",
                     "It is one of the things that may come naturally to you, without much thought.",
                     "You may already use it, often without even noticing.",
                     "Others may see it in you before you recognise it yourself.",
                     "It may come so naturally that you do not even think of it as a talent.",
                     "It may be one of the areas where you feel most at ease with yourself."],
            "mixed": ["It starts from a natural ease, and practice can make it even stronger.",
                      "You have a good starting point; with a little work it can become a real strength.",
                      "Some parts of it may come easily while others take more effort — and both count.",
                      "The natural inclination is there; practice can sharpen it.",
                     "The foundation is good; whatever is still missing can be filled in with experience.",
                     "Where it comes easily, you can build on that to strengthen the rest."],
            "opportunity": ["It grows when it is given a chance, so it is worth looking for situations to try it out.",
                            "Every chance to use it can make it steadier.",
                            "It is worth giving it room; the more you use it, the more clearly it may show.",
                            "The right occasion, such as a project or a team, can bring it to the surface.",
                     "It needs the right environment; once it finds it, it may surprise you.",
                     "It may stay hidden until the right situation lets it show."],
            "practice": [("It may take some time to develop; if it does not come easily yet, that does not mean the "
                          "talent is missing, and over time it often becomes one of your strongest points."),
                         "It may not always come easily; steady practice often turns it into a real strength.",
                         "Early difficulties are natural for this talent and do not mean you lack it.",
                         "With patience and repetition, what takes effort now may later become second nature.",
                     "It is a talent that matures gradually; every small step counts.",
                     "What is built with effort often lasts longer than what comes easily."],
            "open": ["Its real strength will show when you try it in real situations.",
                     "It is worth trying it in practice, to see how well it suits you.",
                     "Experience can show you how far it can go.",
                     "If you try it on something specific, you will better understand what it can give you.",
                     "It is still to be discovered: real situations will show its shape.",
                     "A first try, even a small one, can show you a lot about it."],
        },
        "fields": "Career fields worth exploring",
        "learn": "How you learn best",
        "learn_note": "The way you learn most easily can help each of your talents grow.",
        "learn_items": {
            "fire": "**Through action:** when you try things out in practice, with movement, challenges and quick results.",
            "earth": "**Step by step:** with clear organisation, practical examples and a steady pace, building one thing on another.",
            "air": "**Through interaction:** by discussing, asking questions and exchanging ideas with others.",
            "water": ("**Through emotional connection:** when something moves you, when you see what it means for people, "
                      "or when you trust the person teaching you."),
        },
        "play": "What to notice in play",
        "play_note": "For the parent: small signs in the child's play that may confirm the above.",
        "play_items": {
            "fire": "**Exploring and moving:** whether they ask to go outside, explore and try new things.",
            "earth": "**Structured activities:** whether they enjoy building, rules and anything done in clear steps.",
            "air": "**Puzzles and logic games:** whether they are drawn to puzzles, questions and word games.",
            "water": "**Imaginative play:** whether they make up stories, roles and imaginary worlds.",
        },
        "fields_note": ("Fields where two or more of your talents meet. The order is not random: the fields where "
                        "the most and strongest of your talents meet come first."),
        "fields_note_g": ("Most are fields where two or more of your talents meet; where a talent does not meet "
                          "another one, the field that suits it best is added. The order is not random: the fields "
                          "where the most and strongest of your talents meet come first, and those that suit a single "
                          "talent come last."),
        "best_for": "The field that best suits the talent \"{t}\".",
        "glance": "At a glance",
        "glance_note": "Each ● is one of your talents that leads to this field.",
        "based_on": "Draws on",
        "other": "Other directions",
        "other_note": "Fields linked to one of your talents that are worth keeping in mind.",
        "next": "Next steps",
        "next_lines": [
            "Pick one or two of your leading talents and find a small activity to try them out in practice.",
            "Talk to people who work in the fields that interest you and ask what their everyday work is like.",
            "Discuss the report with a career guidance counsellor, together with your interests and studies.",
        ],
        "closing": ("This report is a tool for self-knowledge and inspiration. It does not replace career guidance, "
                    "aptitude tests or the views of people who know you."),
        "dynasai": ("This report is not a promise of who you will become; it is a reminder that you may try, "
                    "choose and grow."),
    },
}


@dataclass
class EngineReport:
    result: EngineResult
    client_text: str                  # τελικό κείμενο πελάτη (Β αν πέτυχε, αλλιώς Α)
    audit_text: str
    client_docx: bytes
    audit_docx: bytes
    client_name: str
    audit_name: str
    engine_text: str = ""             # εκδοχή Α (για σύγκριση στη Διαχείριση)
    engine_docx: bytes = b""
    polish: object = None             # PolishOutcome ή None (εκδοχή Α χωρίς δοκιμή AI)


def _shown_growth(t) -> str:
    """v22.27: ένα ΑΝΑΔΥΟΜΕΝΟ ταλέντο («φαίνεται πιο αχνά») δεν περιγράφεται ως «βγαίνει αβίαστα» -- θα ήταν
    αντίφαση (αναφορά Β, 11/2026). Τα μόνο-αρμονικά αναδυόμενα δείχνονται ως «ανθίζει όταν βρει ευκαιρία»."""
    from .talent_growth import EASY, OPPORTUNITY
    return OPPORTUNITY if t.growth == EASY and t.rank == "αναδυόμενο" else t.growth


def client_markdown(result: EngineResult, lang: str = "el", ai: dict | None = None) -> str:
    """Η αναφορά πελάτη. Χωρίς `ai`: εκδοχή Α. Με `ai` (εκδοχή Β, v22.4): η ΕΦΑΡΜΟΓΗ συνθέτει τη δομή
    -- τίτλους, προτάσεις καλλιέργειας, τομείς, επιφύλαξη -- και το AI δίνει μόνο: την εισαγωγή
    «Τι σε χαρακτηρίζει», 1-2 προτάσεις σύνδεσης για κάθε ΕΠΙΛΕΓΜΕΝΟ ταλέντο (μετά τη σταθερή περιγραφή της
    βιβλιοθήκης) και μία πρόταση σύνδεσης ανά κύριο τομέα. Η αρίθμηση των ταλέντων γίνεται από την εφαρμογή."""
    tx = TXT.get(lang, TXT["el"])
    ai = ai or {}
    out = [tx["intro"], ""]
    if ai.get("intro"):
        out += [f"## {tx['who']}", ai["intro"], ""]
    out += [f"## {tx['talents']}", "", f"**{tx['summary']}:**"]
    phrases = GROWTH_PHRASES.get(lang, GROWTH_PHRASES["el"])
    out += [f"- {talent_text(t.theme, lang)['title']}{SEPARATOR}*{phrases[_shown_growth(t)]}*" for t in result.talents]
    out += ["", tx["summary_note"]]
    number = 0
    growth_used: dict[str, int] = {}
    for rank in RANKS:
        talents = [t for t in result.talents if t.rank == rank]
        if not talents:
            continue
        if len(talents) == len(result.talents) and rank == "αναδυόμενο":
            head, note = tx["all_emerging"]
        else:
            head, note = tx["rank"][rank], tx["rank_note"][rank]
        out += ["", f"### {head}", f"*{note}*", ""]
        for t in talents:
            text = talent_text(t.theme, lang)
            number += 1   # η ΕΦΑΡΜΟΓΗ αριθμεί: όσα βρήκε η μηχανή, τόσα και στην αναφορά
            out.append(f"**{number}. {text['title']}**")
            colours = colour_phrases(t, lang)   # v22.15-21: «πώς φαίνεται σε σένα» -- από τη μηχανή, έως 4
            if colours:
                out.append("*" + " · ".join(colours) + "*")
            # Η περιγραφή της βιβλιοθήκης μένει ΣΤΑΘΕΡΗ· το AI (εκδοχή Β) προσθέτει μόνο σύνδεση.
            link = ai.get("talents", {}).get(t.theme, "")
            g = _shown_growth(t)
            options = tx["growth_long"][g]
            n = growth_used.get(g, 0)
            growth_used[g] = n + 1
            out.append(text["text"] + " " + options[n % len(options)] + (f" {link}" if link else ""))
            # v22.48: για ενήλικες, προτάσεις καλλιέργειας για ενήλικες (develop_adult)· για ανήλικους οι αρχικές
            develop = text["develop"] if getattr(result, "minor", False) else text.get("develop_adult", text["develop"])
            out.append(f"*{tx['develop']}* {develop}")
            out.append("")
    learning = getattr(result, "learning", None) or []
    if learning:   # v22.47: πώς μαθαίνεις (και, για ανήλικο, τι να προσέξει ο γονιός στο παιχνίδι)
        out += [f"## {tx['learn']}", f"*{tx['learn_note']}*", ""]
        out += [f"- {tx['learn_items'][e]}" for e in learning]
        out.append("")
        if getattr(result, "minor", False):
            out += [f"## {tx['play']}", f"*{tx['play_note']}*", ""]
            out += [f"- {tx['play_items'][e]}" for e in learning]
            out.append("")
    main = [f for f in result.fields if f.decision == "ΕΠΙΛΕΓΕΤΑΙ"]
    other = [f for f in result.fields if f.decision != "ΕΠΙΛΕΓΕΤΑΙ"]
    if main:
        note = tx["fields_note_g"] if any(f.guarantee for f in main) else tx["fields_note"]
        out += [f"## {tx['fields']}", f"*{note}*", ""]
        # v22.34: «με μια ματιά» -- πόσα ταλέντα οδηγούν σε κάθε τομέα (λίστα, όχι πίνακας: Κανόνας 3).
        out += [f"**{tx['glance']}**"]
        out += [f"- {field_text(f.name, lang)['name']}  {'●' * len(f.talents)}" for f in main]
        out += [f"*{tx['glance_note']}*", ""]
        for f in main:
            ft = field_text(f.name, lang)
            names = ", ".join(talent_text(th, lang)["title"] for th in f.talents)
            why = (tx["best_for"].format(t=names) if f.guarantee and len(f.talents) == 1
                   else f"{tx['based_on']}: {names}.")
            link = ai.get("fields", {}).get(f.name, "")
            out.append(f"- **{ft['name']}**: {ft['desc']}" + (f" {link}" if link else "") + f" {why}")
        out.append("")
    if other:
        out += [f"## {tx['other']}", f"*{tx['other_note']}*", ""]
        for f in other:
            ft = field_text(f.name, lang)
            out.append(f"- **{ft['name']}**: {ft['desc']}")
        out.append("")
    # v22.8: αφαιρέθηκαν «Επόμενα βήματα» και η πρόταση «Δεν αντικαθιστά…» (ζήτημα της ιδιοκτήτριας)·
    # η αναφορά κλείνει με τη γραμμή «Δύνασαι». Η επισήμανση «συμβολικό εργαλείο…» μένει στη σελίδα.
    out += [f"**{tx['dynasai']}**"]
    return "\n".join(out)


def audit_markdown(chart, result: EngineResult) -> str:
    """Εσωτερικό δελτίο (πάντα ελληνικά): από πού βγήκε κάθε ταλέντο και κάθε τομέας."""
    head = " · ".join(x for x in (chart.name, chart.date, chart.time, chart.place) if x)
    out = ["## Στοιχεία", f"Χάρτης: {head or '—'}",
           "Μέθοδος: μηχανή ταλέντων v22 (κανόνες εντολής v13, χωρίς AI). Πίνακες και κείμενα: ΠΡΟΧΕΙΡΑ μέχρι έγκριση αστρολόγου.",
           "", "## Ταλέντα"]
    for t in result.talents:
        out.append(f"### {t.title_el} ({t.rank}, βαθμός {t.score}, βάση: {t.basis}, ανάπτυξη: {t.growth})")
        for (key, _, src), phrase in zip(t.colours, colour_phrases(t)):
            out.append(f"- Απόχρωση: «{phrase}» από {key} ({src})")
        for i in t.indicators:
            out.append(f"- {i.kind}: {i.label}" + (f" | {i.weight}" if i.weight else ""))
        for i in t.supporting:
            out.append(f"- Υποστηρικτικό (μετρά 1/4): {i.kind}: {i.label}" + (f" | {i.weight}" if i.weight else ""))
        out.append(f"- Τομείς: {', '.join(t.fields) or '—'}")
    out += ["", "## Τομείς (Κανόνας 12)"]
    for f in result.fields:
        extra = " (εγγύηση: ο καλύτερος τομέας ταλέντου χωρίς συνάντηση)" if f.guarantee else ""
        out.append(f"- {f.name}: {f.decision}{extra} | βαθμός {f.score} | ταλέντα: {', '.join(f.talents)}")
    health = [f for f in result.fields if f.health_basis]
    if health:
        out += ["", "## ΡΗΤΗ ΤΕΚΜΗΡΙΩΣΗ ΤΟΜΕΑ ΥΓΕΙΑΣ"]
        for f in health:
            out.append(f"### {f.name}")
            out += [f"- {line}" for line in f.health_basis]
    if result.candidates_rejected:
        out += ["", "## Δεν εγκρίθηκαν"]
        out += [f"- {k}: {v}" for k, v in result.candidates_rejected.items()]
    teaser = pick_teaser(chart)
    if teaser:
        out += ["", "## Δωρεάν ταλέντο",
                f"- «{teaser.title}» από {teaser.pair[0]}–{teaser.pair[1]} ({teaser.aspect}, orb {teaser.orb_text}), "
                f"status {teaser.status}"]
    return "\n".join(out)


def build_engine_report(chart, display_name: str, lang: str = "el", *, generate_fn=None, cost=None,
                        model_name: str = "") -> EngineReport:
    """Εκδοχή Α (χωρίς generate_fn) ή Β («δέσιμο» από AI, με αυτόματη επιστροφή στην Α)."""
    result = run_engine(chart)
    engine = client_markdown(result, lang)
    title = service_title(lang)
    engine_docx = build_orientation_client_docx(title, display_name, engine)
    polish, client, client_docx = None, engine, engine_docx
    if generate_fn is not None:
        from .talent_polish import polish_report
        polish = polish_report(engine, result, lang, generate_fn, name=display_name, cost=cost, model_name=model_name)
        if polish.used_ai:
            client = polish.text
            client_docx = build_orientation_client_docx(title, display_name, client)
    audit = audit_markdown(chart, result)
    if polish is not None:
        audit += "\n\n## Εκδοχή Β (δέσιμο από AI)\n"
        audit += (f"- Χρησιμοποιήθηκε η εκδοχή Β (προσπάθεια {polish.attempts})." if polish.used_ai else
                  f"- Δόθηκε η εκδοχή Α (μετά από {polish.attempts} προσπάθεια/ες)." +
                  (f" Σφάλμα AI: {polish.error}" if polish.error else ""))
        audit += "".join(f"\n- Απορρίφθηκε: {x}" for x in (polish.issues if not polish.used_ai else []))
    return EngineReport(
        result, client, audit, client_docx,
        build_orientation_audit_docx(AUDIT_TITLE, display_name or "AstroCheck", audit),
        client_docx_filename(display_name), audit_docx_filename(display_name),
        engine, engine_docx, polish,
    )
