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
        # Antiguo Testamento
        "génesis": "Genesis", "éxodo": "Exodus", "levítico": "Leviticus", "números": "Numbers",
        "deuteronomio": "Deuteronomy",
        "josué": "Joshua", "jueces": "Judges", "rut": "Ruth",
        "1 samuel": "1 Samuel", "2 samuel": "2 Samuel", "1 reyes": "1 Kings", "2 reyes": "2 Kings",
        "1 crónicas": "1 Chronicles", "2 crónicas": "2 Chronicles", "esdras": "Ezra", "nehemías": "Nehemiah",
        "ester": "Esther", "job": "Job", "salmos": "Psalms", "proverbios": "Proverbs", "eclesiastés": "Ecclesiastes",
        "cantares": "Song of Solomon", "isaías": "Isaiah", "jeremías": "Jeremiah", "lamentaciones": "Lamentations",
        "ezequiel": "Ezekiel", "daniel": "Daniel", "oseas": "Hosea", "joel": "Joel", "amós": "Amos",
        "abdías": "Obadiah",
        "jonás": "Jonah", "miqueas": "Micah", "nahúm": "Nahum", "habacuc": "Habakkuk", "sofonías": "Zephaniah",
        "hageo": "Haggai", "zacarías": "Zechariah", "malaquías": "Malachi",

        # Nuevo Testamento
        "mateo": "Matthew", "marcos": "Mark", "lucas": "Luke", "juan": "John", "hechos": "Acts",
        "romanos": "Romans",
        "1 corintios": "1 Corinthians", "2 corintios": "2 Corinthians", "gálatas": "Galatians",
        "efesios": "Ephesians", "filipenses": "Philippians", "colosenses": "Colossians",
        "1 tesalonicenses": "1 Thessalonians", "2 tesalonicenses": "2 Thessalonians",
        "1 timoteo": "1 Timothy", "2 timoteo": "2 Timothy", "tito": "Titus", "filemón": "Philemon",
        "hebreos": "Hebrews", "santiago": "James",
        "1 pedro": "1 Peter", "2 pedro": "2 Peter",
        "1 juan": "1 John", "2 juan": "2 John", "3 juan": "3 John",
        "judas": "Jude", "apocalipsis": "Revelation",
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
        regex = r'(?:[\(\[]?)(\d?\s*[A-Za-zñáéíóúÁÉÍÓÚ\s\.]+\s+\d+:\d+(?:-\d+)?(?:(?:\s*,\s*|;\s*|\s+y\s+)\s*(?:\d?\s*[A-Za-zñáéíóúÁÉÍÓÚ\s\.]+\s+)?\d+:\d+(?:-\d+)?)*)(?:[\)\]]?)'
        match = re.search(regex, text.strip(), re.I)
        if match:
            citation_string = match.group(1).strip()
            citation_string = re.sub(r'^[\(\[]|[\)\]]$', '', citation_string).strip()
            temp_string = re.sub(r'(?:,\s*|;\s*|\s+y\s+)', ';', citation_string)
            translated_query_parts = []
            citation_parts_regex = r'(\d?\s*[A-Za-zñáéíóúÁÉÍÓÚ\s\.]*)\s*(\d+:\d+(?:-\d+)?)'
            parts = [p.strip() for p in temp_string.split(';') if p.strip()]
            for part in parts:
                match_part = re.search(citation_parts_regex, part.strip(), re.I)
                if match_part:
                    book_raw = match_part.group(1).strip().lower()
                    reference = match_part.group(2).strip()
                    book_clean = re.sub(r'\.', '', book_raw).strip()
                    book_en = TextUtils.BIBLE_BOOK_MAP.get(book_clean, book_clean.title())
                    translated_query_parts.append(f"{book_en} {reference}")
            query = ";".join(translated_query_parts)
            if not query: return None
            query = query.replace(':', '%3A').replace(' ', '%20')
            BASE_URL = "https://www.biblegateway.com/passage/?search="
            VERSION = "&version=RVR1960"
            
            # API Data for first citation found
            # match.group(1) is "Genesis 1:1" roughly.
            # We need to parse the first translated query part.
            api_data = None
            if translated_query_parts:
                first_part = translated_query_parts[0] # "Genesis 1:1"
                # Regex to split Book and Ref
                m_api = re.match(r'(.+?)\s+(\d+):(\d+)(?:-\d+)?', first_part)
                if m_api:
                    book_en = m_api.group(1).strip()
                    chapter = m_api.group(2)
                    verse = m_api.group(3)
                    # Get Bolls ID (Int)
                    book_id = TextUtils.BIBLE_BOOK_IDS.get(book_en)
                    if book_id:
                        api_data = {
                            "book_id": book_id,
                            "chapter": chapter,
                            "verse": verse
                        }

            return {
                "en": f"{BASE_URL}{query}{VERSION}", 
                "type": "bible",
                "api_data": api_data,
                "match": citation_string
            }
        return None

    @staticmethod
    def get_egw_url(text, lang_code="EN"):
        """
        Generates EGW URL using abb_XX.csv logic.
        Supported formats:
        - Christian Education, 21.1
        - CE 21.1
        - Christian Education, p. 21.1
        - (Christian Education, p. 21.1)
        - {Christian Education, p. 21.1}
        """
        if not text: return {"en": None, "type": "none"}
        
        # Load abbreviations for the specified language
        abbrevs = TextUtils.load_abbreviations(lang_code)

        BASE_URL_EN = "https://m.egwwritings.org/en/search?query="
        GOOGLE_URL = "https://www.google.com/search?q="
        
        query_en = None
        is_google_fallback = False

        # 1. Check for already abbreviated format { CE 21.1 } or CE 21.1
        # Ref must be digits.digits (mandatory dot) to match user req: [ABBR] [00].[0]
        # Regex to catch: (Abbr) (Ref)
        
        # Strip surrounding parens/braces first
        clean_text = re.sub(r'^[\(\[\{]|[\)\]\}]$', '', text.strip()).strip()
        
        # Regex for Title + Ref (Ref must be digits.digits)
        # Handles: "Title, p. 12.3", "Title 12.3", "(Title, 12.3)"
        # Improved: Uses [A-Z] to find start of title to avoid matching long preceding text.
        # Captures: (Title) (Ref)
        regex_full = r'([A-Z][a-zA-Z\s]+?)(?:,\s*|\s+)(?:p\.|pp\.|page|vol\.\s*\d+)?\s*(\d+(?:\:\d+)?\.\d+)'
        match_full = re.search(regex_full, clean_text)

        # Try finding exact abbreviation first (most specific)
        # Iterate words? No, regex with lookahead?
        # Let's try simple regex for Abbr+Ref first, check if valid.
        match_simple = re.search(r'\b([1-9]?[A-Z][A-Za-z]*)\s+(\d+\.\d+)', clean_text)
        if match_simple:
            book = match_simple.group(1)
            ref = match_simple.group(2)
            if book in abbrevs.values():
                query_en = f"{book}+{ref}"
                return {"en": f"{BASE_URL_EN}{query_en}", "type": "egw", "match": match_simple.group(0)}

        # If not simple abbr, try Full Title regex
        if match_full:
            raw_title = match_full.group(1).strip()
            ref = match_full.group(2)
            match_str = match_full.group(0)
            
            # Check in abbreviations (Full Title -> Abbr)
            if raw_title in abbrevs:
                abbr = abbrevs[raw_title]
                query_en = f"{abbr}+{ref}"
            elif raw_title in abbrevs.values():
                 # Should have been caught above, but maybe spacing diff
                 query_en = f"{raw_title}+{ref}"
            else:
                # Fallback to Google
                is_google_fallback = True
                clean_title = raw_title.replace(" ", "+")
                query_en = f"{clean_title}+{ref}+Ellen+White"
        
            if is_google_fallback and query_en:
                return {"en": f"{GOOGLE_URL}{query_en}", "type": "google", "match": match_str}
            elif query_en:
                return {"en": f"{BASE_URL_EN}{query_en}", "type": "egw", "match": match_str}

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
