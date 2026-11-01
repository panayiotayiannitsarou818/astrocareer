"""
client.py -- AstroCheck Career: ΣΕΛΙΔΑ ΠΕΛΑΤΗ (v22.25).

Ίδιος κώδικας με το app.py (ίδια μηχανή, κείμενα, αναφορά), αλλά καθαρή σελίδα για τον πελάτη:
χωρίς Διαχείριση και χωρίς πλαϊνή στήλη. Στο Streamlit Cloud: δεύτερη εφαρμογή από το ίδιο
αποθετήριο, με «Main file path» = client.py. Τα Secrets ορίζονται χωριστά για κάθε εφαρμογή.
"""
import os
import runpy

runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py"),
               init_globals={"CLIENT_PAGE": True}, run_name="__main__")
