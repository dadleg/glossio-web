import re
import os
import difflib
import requests
import spacy
import csv
import docx
from flask import current_app
from app.models import db, TranslationMemory, Glossary

# Load Spacy Model (Lazily loaded)
_nlp = None

def get_nlp():
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load("xx_sent_ud_sm")
        except:
             # Try fallback to en_core_web_sm if xx not found, or dummy
            try:
                _nlp = spacy.load("en_core_web_sm")
            except:
                class DummyNLP:
                    def __call__(self, text):
                        class Sent:
                            def __init__(self, t): self.text = t
                        return type('Doc', (), {'sents': [Sent(text)]})()
                _nlp = DummyNLP()
    return _nlp

class TextUtils:
    BIBLE_BOOK_MAP = {
        # Antiguo Testamento (Spanish names & abbreviations)
        "génesis": "Genesis", "gn": "Genesis", "gen": "Genesis", "gén": "Genesis",
        "éxodo": "Exodus", "ex": "Exodus", "exo": "Exodus", "éxo": "Exodus",
        "levítico": "Leviticus", "lv": "Leviticus", "lev": "Leviticus", "leví": "Leviticus",
        "números": "Numbers", "nm": "Numbers", "num": "Numbers", "núm": "Numbers",
        "deuteronomio": "Deuteronomy", "dt": "Deuteronomy", "deut": "Deuteronomy",
        "josué": "Joshua", "jos": "Joshua",
        "jueces": "Judges", "jue": "Judges",
        "rut": "Ruth", "rt": "Ruth",
        "1 samuel": "1 Samuel", "1 s": "1 Samuel", "1 sam": "1 Samuel",
        "2 samuel": "2 Samuel", "2 s": "2 Samuel", "2 sam": "2 Samuel",
        "1 reyes": "1 Kings", "1 r": "1 Kings", "1 re": "1 Kings", "1 rey": "1 Kings",
        "2 reyes": "2 Kings", "2 r": "2 Kings", "2 re": "2 Kings", "2 rey": "2 Kings",
        "1 crónicas": "1 Chronicles", "1 cr": "1 Chronicles", "1 cro": "1 Chronicles",
        "2 crónicas": "2 Chronicles", "2 cr": "2 Chronicles", "2 cro": "2 Chronicles",
        "esdras": "Ezra", "esd": "Ezra",
        "nehemías": "Nehemiah", "neh": "Nehemiah",
        "ester": "Esther", "est": "Esther",
        "job": "Job",
        "salmos": "Psalms", "sl": "Psalms", "sal": "Psalms", "ps": "Psalms",
        "proverbios": "Proverbs", "pr": "Proverbs", "prov": "Proverbs",
        "eclesiastés": "Ecclesiastes", "ec": "Ecclesiastes", "ecl": "Ecclesiastes",
        "cantares": "Song of Solomon", "cnt": "Song of Solomon", "can": "Song of Solomon",
        "isaías": "Isaiah", "is": "Isaiah", "isa": "Isaiah",
        "jeremías": "Jeremiah", "jr": "Jeremiah", "jer": "Jeremiah",
        "lamentaciones": "Lamentations", "lm": "Lamentations", "lam": "Lamentations",
        "ezequiel": "Ezekiel", "ez": "Ezekiel", "eze": "Ezekiel",
        "daniel": "Daniel", "dn": "Daniel", "dan": "Daniel",
        "oseas": "Hosea", "os": "Hosea",
        "joel": "Joel", "jl": "Joel",
        "amós": "Amos", "am": "Amos",
        "abdías": "Obadiah", "ab": "Obadiah", "abd": "Obadiah",
        "jonás": "Jonah", "jon": "Jonah",
        "miqueas": "Micah", "mi": "Micah", "miq": "Micah",
        "nahúm": "Nahum", "na": "Nahum", "nah": "Nahum",
        "habacuc": "Habakkuk", "ha": "Habakkuk", "hab": "Habakkuk",
        "sofonías": "Zephaniah", "so": "Zephaniah", "sof": "Zephaniah",
        "hageo": "Haggai", "hg": "Haggai", "hag": "Haggai",
        "zacarías": "Zechariah", "zc": "Zechariah", "zac": "Zechariah",
        "malaquías": "Malachi", "ml": "Malachi", "mal": "Malachi",

        # Nuevo Testamento
        "mateo": "Matthew", "mt": "Matthew", "mat": "Matthew",
        "marcos": "Mark", "mc": "Mark", "mar": "Mark",
        "lucas": "Luke", "lc": "Luke", "luc": "Luke",
        "juan": "John", "jn": "John",
        "hechos": "Acts", "hch": "Acts",
        "romanos": "Romans", "rm": "Romans", "rom": "Romans",
        "1 corintios": "1 Corinthians", "1 co": "1 Corinthians", "1 cor": "1 Corinthians",
        "2 corintios": "2 Corinthians", "2 co": "2 Corinthians", "2 cor": "2 Corinthians",
        "gálatas": "Galatians", "gl": "Galatians", "gal": "Galatians",
        "efesios": "Ephesians", "ef": "Ephesians", "efe": "Ephesians",
        "filipenses": "Philippians", "flp": "Philippians", "fil": "Philippians",
        "colosenses": "Colossians", "cl": "Colossians", "col": "Colossians",
        "1 tesalonicenses": "1 Thessalonians", "1 ts": "1 Thessalonians", "1 tes": "1 Thessalonians",
        "2 tesalonicenses": "2 Thessalonians", "2 ts": "2 Thessalonians", "2 tes": "2 Thessalonians",
        "1 timoteo": "1 Timothy", "1 tm": "1 Timothy", "1 tim": "1 Timothy",
        "2 timoteo": "2 Timothy", "2 tm": "2 Timothy", "2 tim": "2 Timothy",
        "tito": "Titus", "tt": "Titus", "tit": "Titus",
        "filemón": "Philemon", "flm": "Philemon", "fil": "Philemon",
        "hebreos": "Hebrews", "hb": "Hebrews", "heb": "Hebrews",
        "santiago": "James", "stg": "James", "jac": "James", "jas": "James",
        "1 pedro": "1 Peter", "1 p": "1 Peter", "1 pe": "1 Peter", "1 ped": "1 Peter",
        "2 pedro": "2 Peter", "2 p": "2 Peter", "2 pe": "2 Peter", "2 ped": "2 Peter",
        "1 juan": "1 John", "1 jn": "1 John",
        "2 juan": "2 John", "2 jn": "2 John",
        "3 juan": "3 John", "3 jn": "3 John",
        "judas": "Jude", "jd": "Jude", "jud": "Jude",
        "apocalipsis": "Revelation", "ap": "Apocalipsis", "apo": "Revelation", "rev": "Revelation",

        # English Names & Abbreviations
        "genesis": "Genesis", "gen": "Genesis",
        "exodus": "Exodus", "exo": "Exodus",
        "leviticus": "Leviticus", "lev": "Leviticus",
        "numbers": "Numbers", "num": "Numbers",
        "deuteronomy": "Deuteronomy", "deut": "Deuteronomy",
        "joshua": "Joshua", "josh": "Joshua",
        "judges": "Judges", "judg": "Judges",
        "ruth": "Ruth",
        "1 samuel": "1 Samuel", "1 sam": "1 Samuel",
        "2 samuel": "2 Samuel", "2 sam": "2 Samuel",
        "1 kings": "1 Kings",
        "2 kings": "2 Kings",
        "1 chronicles": "1 Chronicles", "1 chron": "1 Chronicles",
        "2 chronicles": "2 Chronicles", "2 chron": "2 Chronicles",
        "ezra": "Ezra",
        "nehemiah": "Nehemiah", "neh": "Nehemiah",
        "esther": "Esther", "esth": "Esther",
        "job": "Job",
        "psalms": "Psalms", "ps": "Psalms", "psa": "Psalms",
        "proverbs": "Proverbs", "prov": "Proverbs",
        "ecclesiastes": "Ecclesiastes", "eccl": "Ecclesiastes",
        "song of solomon": "Song of Solomon", "song": "Song of Solomon",
        "isaiah": "Isaiah", "isa": "Isaiah",
        "jeremiah": "Jeremiah", "jer": "Jeremiah",
        "lamentations": "Lamentations", "lam": "Lamentations",
        "ezekiel": "Ezekiel", "ezek": "Ezekiel",
        "daniel": "Daniel", "dan": "Daniel",
        "hosea": "Hosea", "hos": "Hosea",
        "joel": "Joel",
        "amos": "Amos",
        "obadiah": "Obadiah", "obad": "Obadiah",
        "jonah": "Jonah",
        "micah": "Micah", "mic": "Micah",
        "nahum": "Nahum", "nah": "Nahum",
        "habakkuk": "Habakkuk", "hab": "Habakkuk",
        "zephaniah": "Zephaniah", "zeph": "Zephaniah",
        "haggai": "Haggai", "hag": "Haggai",
        "zechariah": "Zechariah", "zech": "Zechariah",
        "malachi": "Malachi", "mal": "Malachi",
        "matthew": "Matthew", "matt": "Matthew",
        "mark": "Mark",
        "luke": "Luke",
        "john": "John",
        "acts": "Acts",
        "romans": "Romans", "rom": "Romans",
        "1 corinthians": "1 Corinthians", "1 cor": "1 Corinthians",
        "2 corinthians": "2 Corinthians", "2 cor": "2 Corinthians",
        "galatians": "Galatians", "gal": "Galatians",
        "ephesians": "Ephesians", "eph": "Ephesians",
        "philippians": "Philippians", "phil": "Philippians",
        "colossians": "Colossians", "col": "Colossians",
        "1 thessalonians": "1 Thessalonians", "1 thess": "1 Thessalonians", "1 thes": "1 Thessalonians",
        "2 thessalonians": "2 Thessalonians", "2 thess": "2 Thessalonians", "2 thes": "2 Thessalonians",
        "1 timothy": "1 Timothy", "1 tim": "1 Timothy",
        "2 timothy": "2 Timothy", "2 tim": "2 Timothy",
        "titus": "Titus", "tit": "Titus",
        "philemon": "Philemon", "philem": "Philemon",
        "hebrews": "Hebrews", "heb": "Hebrews",
        "james": "James", "jas": "James",
        "1 peter": "1 Peter", "1 pet": "1 Peter",
        "2 peter": "2 Peter", "2 pet": "2 Peter",
        "1 john": "1 John", "1 jn": "1 John",
        "2 john": "2 John", "2 jn": "2 John",
        "3 john": "3 John", "3 jn": "3 John",
        "jude": "Jude",
        "revelation": "Revelation", "rev": "Revelation",
    }
    
    # Map for Bolls.life API (Integer IDs 1-66)
    BIBLE_BOOK_IDS = {
        "Genesis": 1, "Exodus": 2, "Leviticus": 3, "Numbers": 4, "Deuteronomy": 5,
        "Joshua": 6, "Judges": 7, "Ruth": 8, "1 Samuel": 9, "2 Samuel": 10,
        "1 Kings": 11, "2 Kings": 12, "1 Chronicles": 13, "2 Chronicles": 14,
        "Ezra": 15, "Nehemiah": 16, "Esther": 17, "Job": 18, "Psalms": 19,
        "Proverbs": 20, "Ecclesiastes": 21, "Song of Solomon": 22, "Isaiah": 23,
        "Jeremiah": 24, "Lamentations": 25, "Ezekiel": 26, "Daniel": 27, "Hosea": 28,
        "Joel": 29, "Amos": 30, "Obadiah": 31, "Jonah": 32, "Micah": 33, "Nahum": 34,
        "Habakkuk": 35, "Zephaniah": 36, "Haggai": 37, "Zechariah": 38, "Malachi": 39,
        "Matthew": 40, "Mark": 41, "Luke": 42, "John": 43, "Acts": 44, "Romans": 45,
        "1 Corinthians": 46, "2 Corinthians": 47, "Galatians": 48, "Ephesians": 49,
        "Philippians": 50, "Colossians": 51, "1 Thessalonians": 52, "2 Thessalonians": 53,
        "1 Timothy": 54, "2 Timothy": 55, "Titus": 56, "Philemon": 57, "Hebrews": 58,
        "James": 59, "1 Peter": 60, "2 Peter": 61, "1 John": 62, "2 John": 63,
        "3 John": 64, "Jude": 65, "Revelation": 66
    }

    ABBREVIATIONS = {}

    @staticmethod
    def load_abbreviations(lang_code="EN"):
        """
        Loads abb_XX.csv corresponding to language.
        """
        filename = f"abb_{lang_code}.csv"
        # Look in app/data folder
        file_path = os.path.join(current_app.root_path, 'data', filename)
        
        TextUtils.ABBREVIATIONS = {} # Reset or keep cache? For web app, cache per request or globally? 
        # Global cache is risky if multiple langs are used. 
        # For simplicity in this function, we just load into the static dict, 
        # but in a real concurrent app we should pass the abbreviations dict around or cache by lang.
        # Let's return the dict instead of setting static property to be safe.
        abbrevs = {}

        if not os.path.exists(file_path):
            return abbrevs

        try:
            with open(file_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 2:
                        abbrevs[row[0].strip()] = row[1].strip()
        except Exception as e:
            print(f"Error reading {filename}: {e}")
            
        return abbrevs

    @staticmethod
    def normalize(text):
        if not text: return ""
        return re.sub(r'\s+', ' ', text).strip().lower()

    @staticmethod
    def get_bible_url(text):
        if not text: return None
        
        # New regex: supports abbreviations, optional dots, flexible spacing, and complex verse strings
        # Groups: 1: opt leading number, 2: book name, 3: chapter, 4: verses (range/list)
        regex = r'\b(?:([1-3]\s*)?([A-Z][a-zñáéíóúÁÉÍÓÚ]*)\.?\s*)(\d+):([\d\s\-,]+)'
        
        matches = list(re.finditer(regex, text, re.I))
        if not matches:
            return None
        
        # Filter matches to only include valid bible books
        valid_match = None
        book_en = None
        for match in matches:
            book_raw = (match.group(1) or "") + match.group(2)
            book_clean = book_raw.strip().lower()
            
            # Check if it's a valid book name/abbreviation
            if book_clean in TextUtils.BIBLE_BOOK_MAP:
                book_en = TextUtils.BIBLE_BOOK_MAP[book_clean]
                valid_match = match
                break
        
        if not valid_match:
            return None
        
        # Process the valid match
        citation_string = valid_match.group(0).strip()
        chapter = valid_match.group(3)
        verse_str = valid_match.group(4).strip()
        
        # Build URL query for BibleGateway
        url_ref = f"{chapter}:{verse_str}".replace(' ', '').replace(',', '%2C').replace(':', '%3A')
        query = f"{book_en}%20{url_ref}"
        
        BASE_URL = "https://www.biblegateway.com/passage/?search="
        VERSION = "&version=RVR1960"
        
        # API Data for first citation found
        book_id = TextUtils.BIBLE_BOOK_IDS.get(book_en)
        api_data = None
        if book_id:
            api_data = {
                "book_id": book_id,
                "chapter": chapter,
                "verse": verse_str # Pass the full verse string to frontend
            }

        return {
            "en": f"{BASE_URL}{query}{VERSION}", 
            "type": "bible",
            "api_data": api_data,
            "match": citation_string
        }

    @staticmethod
    def get_egw_url(text, lang_code="EN"):
        """
        Generates EGW URL using abb_XX.csv logic.
        Supported formats:
        - Christian Education, 21.1
        - CE 21.1
        - The Desire of Ages, p. 214.1
        - (Desire of Ages, p. 214.1)
        - {DA 214.1}
        """
        if not text: return {"en": None, "type": "none"}
        
        # Load abbreviations for the specified language
        abbrevs = TextUtils.load_abbreviations(lang_code)
        if not abbrevs:
            return {"en": None, "type": "none"}

        BASE_URL_EN = "https://m.egwwritings.org/en/search?query="
        GOOGLE_URL = "https://www.google.com/search?q="
        
        # Priority 1: Look for abbreviated format: DA 214.1, CE 21.1, 1MCP 23.4
        abbr_regex = r'\b([1-9]?[A-Z][A-Za-z]{1,5})\s+(\d+\.\d+)\b'
        abbr_match = re.search(abbr_regex, text)
        if abbr_match:
            abbr = abbr_match.group(1)
            ref = abbr_match.group(2)
            # Check if this abbreviation exists
            if abbr in abbrevs.values():
                query = f"{abbr}+{ref}"
                return {"en": f"{BASE_URL_EN}{query}", "type": "egw", "match": abbr_match.group(0)}

        # Priority 2: Look for page reference pattern and search backwards for title
        # Matches: digits.digits format like 214.1
        page_regex = r'(\d+\.\d+)'
        page_matches = list(re.finditer(page_regex, text))
        
        for page_match in page_matches:
            ref = page_match.group(1)
            # Look backwards from page ref for title
            prefix = text[:page_match.start()]
            
            # Try to find a title pattern: "Title, p." or "Title,"
            title_regex = r'([A-Z][A-Za-z\s\']+?)(?:,\s*(?:p\.?\s*)?|,?\s+(?:p\.?\s*)?)$'
            title_match = re.search(title_regex, prefix)
            
            if title_match:
                raw_title = title_match.group(1).strip()
                full_match_str = raw_title + text[title_match.end():page_match.end()]
                
                # Try to find this title in abbreviations
                # Check exact match first
                if raw_title in abbrevs:
                    abbr = abbrevs[raw_title]
                    query = f"{abbr}+{ref}"
                    return {"en": f"{BASE_URL_EN}{query}", "type": "egw", "match": full_match_str.strip()}
                
                # Check if it's already an abbreviation
                if raw_title in abbrevs.values():
                    query = f"{raw_title}+{ref}"
                    return {"en": f"{BASE_URL_EN}{query}", "type": "egw", "match": full_match_str.strip()}
                
                # Try partial match - maybe missing "The" prefix
                for full_title, abbr in abbrevs.items():
                    # Check if raw_title is at the end of full_title (e.g., "Desire of Ages" in "The Desire of Ages")
                    if full_title.endswith(raw_title) or raw_title == full_title:
                        query = f"{abbr}+{ref}"
                        return {"en": f"{BASE_URL_EN}{query}", "type": "egw", "match": full_match_str.strip()}
                    # Also try case-insensitive
                    if full_title.lower().endswith(raw_title.lower()):
                        query = f"{abbr}+{ref}"
                        return {"en": f"{BASE_URL_EN}{query}", "type": "egw", "match": full_match_str.strip()}
                
                # Fallback to Google search
                clean_title = raw_title.replace(" ", "+")
                query = f"{clean_title}+{ref}+Ellen+White"
                return {"en": f"{GOOGLE_URL}{query}", "type": "google", "match": full_match_str.strip()}

        return {"en": None, "type": "none"}


    @staticmethod
    def get_mt_translation(text, target_lang="ES", api_key=None):
        if not text.strip(): return ""
        
        # Use provided key or fallback to config
        key_to_use = api_key if api_key else current_app.config.get("DEEPL_API_KEY", "")
        
        if not key_to_use:
             return None # Let caller handle missing key error

        URL = "https://api-free.deepl.com/v2/translate"
        headers = {"Authorization": f"DeepL-Auth-Key {key_to_use}"}
        data = {
            'text': [text],
            'source_lang': 'EN',
            'target_lang': target_lang.upper()
        }
        try:
            response = requests.post(URL, headers=headers, data=data, timeout=10)
            if response.status_code == 403:
                return "Error: Invalid API Key"
            response.raise_for_status()
            result = response.json()
            if 'translations' in result:
                return result['translations'][0]['text']
        except Exception as e:
            return f"Error MT: {e}"
        return "Unknown MT Error"

def lookup_tm(source_text, threshold=0.75, user_id=None):
    norm_source = TextUtils.normalize(source_text)
    if not norm_source: return None, 0.0
    
    # In a real heavy production app, we would use Full Text Search in Postgres or ElasticSearch
    # For now, we fetch all (or limit) and use Python's difflib as in original code
    # Optimization: Filter by length or some rudimentary match if DB grows large
    
    # Naive implementation: Fetch all TMs for user
    # TODO: Improve with SQL LIKE or FTS
    query = TranslationMemory.query
    if user_id:
        query = query.filter_by(user_id=user_id)
    tms = query.all()
    
    best_match = None
    best_score = 0.0
    matcher = difflib.SequenceMatcher(None, norm_source, "")

    for tm in tms:
        tm_src = tm.source_text
        if abs(len(tm_src) - len(norm_source)) / len(norm_source) > 0.4: continue
        matcher.set_seq2(tm_src)
        if matcher.quick_ratio() < threshold: continue
        score = matcher.ratio()
        if score > best_score and score >= threshold:
            best_score = score
            best_match = tm.target_text
            if best_score > 0.99: break
            
    return best_match, int(best_score * 100)

def lookup_glossary(source_text, user_id=None):
    norm_source = TextUtils.normalize(source_text)
    matches = []
    # Naive implementation
    query = Glossary.query
    if user_id:
        query = query.filter_by(user_id=user_id)
    glossary_terms = query.all()
    for g in glossary_terms:
        if TextUtils.normalize(g.source_term) in norm_source:
             matches.append((g.source_term, g.target_term))
    return matches
