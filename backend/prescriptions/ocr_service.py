"""
OCR SERVICE — Universal Prescription Parser
============================================
Handles ALL prescription types:
  - Indian handwritten (psychiatric, ayurvedic, general)
  - Printed prescriptions
  - Mixed handwritten + printed
  - Numbered lists (1) 2) ① ②)
  - Prefixed (Tab, Cap, Syp, T., Inj)
  - Plain medicine names with dosage

Strategy (no AI needed):
  1. Gemini Vision   — kept, works if available
  2. OCR.space       — extracts raw text
  3. Universal regex — 3-pass extraction:
       Pass A: numbered list items  (① Kanchanan guggul 2 tab x3)
       Pass B: Tab/Cap/Syp prefix   (Tab Sizodon Plus)
       Pass C: dosage-anchored scan (any line with mg/tab/cap/ml)
"""

import re
import os
import json
import base64
import urllib.request
import urllib.error
import urllib.parse
from django.conf import settings

try:
    from google.cloud import vision
    from google.oauth2 import service_account
    GOOGLE_VISION_AVAILABLE = True
except ImportError:
    GOOGLE_VISION_AVAILABLE = False

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
    try:
        pytesseract.pytesseract.tesseract_cmd = getattr(
            settings, 'TESSERACT_CMD',
            r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        )
    except Exception:
        pass
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    import cv2
    USE_OPENCV = True
except ImportError:
    USE_OPENCV = False


# ─────────────────────────────────────────────────────────────────────────────
# GEMINI VISION — kept as-is (not available in India from server)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_with_gemini_vision(image_path):
    api_key = getattr(settings, 'GEMINI_API_KEY', None) or os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return None
    try:
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        ext      = os.path.splitext(image_path)[1].lower()
        mime_map = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                    '.png': 'image/png', '.bmp': 'image/bmp',
                    '.tiff': 'image/tiff', '.tif': 'image/tiff'}
        mime_type = mime_map.get(ext, 'image/jpeg')
        prompt = """You are a medical prescription parser. Read this prescription carefully.
It may be handwritten, printed, or mixed. It could be allopathic or ayurvedic.

Return ONLY a JSON object, no markdown, no explanation:
{
  "patient_name": "full name or null",
  "age": integer_or_null,
  "disease": "diagnosis or null",
  "treatment_duration_days": integer_default_7,
  "medicines": [
    {"name": "medicine name", "dosage": "e.g. 500mg or 1 tablet",
     "frequency": "N times daily", "duration_days": integer}
  ]
}
Rules:
- Extract ALL medicine/drug names including ayurvedic ones
- Tab/Cap/Syp prefix means tablet/capsule/syrup
- frequency = "N times daily" where N is a number
- If dosage unclear: "1 tablet". If duration unclear: 7
- Return ONLY the JSON"""
        payload = json.dumps({
            "contents": [{"parts": [
                {"inline_data": {"mime_type": mime_type, "data": image_data}},
                {"text": prompt}
            ]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024}
        }).encode('utf-8')
        models_to_try = [
            ('v1', 'gemini-2.5-flash'),
            ('v1', 'gemini-2.0-flash'),
            ('v1', 'gemini-2.0-flash-001'),
        ]
        raw_text_response = None
        for api_ver, model_name in models_to_try:
            url = (f"https://generativelanguage.googleapis.com/{api_ver}/models/"
                   f"{model_name}:generateContent?key={api_key}")
            print(f"   🔮 Trying {model_name} ({api_ver})...")
            req = urllib.request.Request(url, data=payload,
                headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw_text_response = resp.read().decode("utf-8")
                    print(f"   ✅ {model_name} responded successfully!")
                    break
            except urllib.error.HTTPError as he:
                err_body = he.read().decode()[:200]
                print(f"   ❌ {model_name} ({api_ver}): HTTP {he.code} — {err_body[:80]}")
                continue
            except Exception as ex:
                print(f"   ❌ {model_name} unexpected error: {ex}")
                continue
        if raw_text_response is None:
            print("   ❌ All Gemini models failed.")
            return None
        data     = json.loads(raw_text_response)
        raw_text = data['candidates'][0]['content']['parts'][0]['text'].strip()
        raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text)
        raw_text = re.sub(r'\s*```$', '', raw_text).strip()
        result   = json.loads(raw_text)
        medicines = []
        for m in result.get('medicines', []):
            if not isinstance(m, dict) or not m.get('name'):
                continue
            name = str(m['name']).strip()
            if len(name) < 2:
                continue
            freq_raw   = str(m.get('frequency', '1 times daily'))
            freq_match = re.search(r'(\d+)', freq_raw)
            freq       = f"{freq_match.group(1)} times daily" if freq_match else "1 times daily"
            try:
                dur = max(1, min(int(m.get('duration_days', 7)), 365))
            except (ValueError, TypeError):
                dur = 7
            dosage = str(m.get('dosage', '1 tablet')).strip() or '1 tablet'
            medicines.append({'name': name, 'dosage': dosage,
                              'frequency': freq, 'duration_days': dur})
            print(f"   💊 Gemini: {name} | {dosage} | {freq} | {dur}d")
        age = result.get('age')
        try:
            age = int(age)
            if not (1 <= age <= 120):
                age = None
        except (ValueError, TypeError):
            age = None
        try:
            duration = max(1, min(int(result.get('treatment_duration_days', 7)), 365))
        except (ValueError, TypeError):
            duration = 7
        print(f"   ✅ Gemini done: {len(medicines)} medicines found")
        return {'patient_name': result.get('patient_name'), 'age': age,
                'disease': result.get('disease'), 'medicines': medicines,
                'treatment_duration_days': duration}
    except Exception as e:
        print(f"   ❌ Gemini error: {type(e).__name__}: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# TEXT EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def _text_from_google_vision(image_path, gv_client):
    try:
        with open(image_path, 'rb') as f:
            content = f.read()
        image    = vision.Image(content=content)
        response = gv_client.document_text_detection(image=image)
        if response.error.message:
            return ""
        if response.full_text_annotation:
            return response.full_text_annotation.text
        texts = response.text_annotations
        return texts[0].description if texts else ""
    except Exception as e:
        print(f"   ❌ Google Vision error: {e}")
        return ""


def _text_from_ocrspace(image_path):
    api_key = getattr(settings, 'OCR_SPACE_API_KEY', None) or os.environ.get('OCR_SPACE_API_KEY')
    if not api_key:
        return ""
    try:
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        ext      = os.path.splitext(image_path)[1].lower()
        mime_map = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                    '.png': 'image/png', '.bmp': 'image/bmp'}
        mime_type = mime_map.get(ext, 'image/jpeg')
        payload   = urllib.parse.urlencode({
            'base64Image': f"data:{mime_type};base64,{image_data}",
            'apikey': api_key, 'language': 'eng',
            'isOverlayRequired': 'false', 'detectOrientation': 'true',
            'scale': 'true', 'OCREngine': '2', 'isTable': 'false',
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://api.ocr.space/parse/image', data=payload,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            method='POST')
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            if result.get('IsErroredOnProcessing'):
                return ""
            parsed = result.get('ParsedResults', [])
            if not parsed:
                return ""
            text = parsed[0].get('ParsedText', '').strip()
            if text:
                print(f"   ✅ OCR.space: {len(text)} chars.")
            return text
    except Exception as e:
        print(f"   ❌ OCR.space error: {e}")
        return ""


def _text_from_tesseract(image_path):
    if not TESSERACT_AVAILABLE:
        return ""
    try:
        if USE_OPENCV:
            img      = cv2.imread(image_path)
            gray     = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            thresh   = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 31, 2)
            denoised = cv2.fastNlMeansDenoising(thresh, None, 10, 7, 21)
            text     = pytesseract.image_to_string(denoised, config='--psm 6 --oem 3')
        else:
            img  = Image.open(image_path).convert('L')
            text = pytesseract.image_to_string(img, config='--psm 6 --oem 3')
        if text:
            print(f"   Tesseract: {len(text)} chars.")
        return text
    except Exception as e:
        print(f"   ❌ Tesseract error: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# UNIVERSAL FIELD EXTRACTORS
# ─────────────────────────────────────────────────────────────────────────────

# Words that are never medicine names
NON_MEDICINE_WORDS = {
    'prescription', 'patient', 'doctor', 'date', 'diagnosis', 'name',
    'age', 'gender', 'sex', 'hospital', 'clinic', 'address', 'phone',
    'signature', 'frequency', 'duration', 'dosage', 'refill', 'medicine',
    'for', 'the', 'and', 'with', 'times', 'time', 'daily', 'weekly',
    'once', 'twice', 'thrice', 'morning', 'afternoon', 'evening', 'night',
    'before', 'after', 'meal', 'meals', 'food', 'water', 'take', 'days',
    'weeks', 'months', 'stat', 'bp', 'hr', 'spo2', 'temp', 'wt', 'weight',
    'free', 'home', 'delivery', 'r', 'rx', 'mg', 'ml', 'tab', 'tabs',
    'reg', 'no', 'city', 'general', 'physician', 'consultant', 'dr',
    'continue', 'other', 'call', 'counselled', 'phone', 'plot', 'road',
    'colony', 'regd', 'mbbs', 'md', 'bams', 'mba', 'ms', 'emergency',
    'admit', 'hospital', 'clinic', 'super', 'spl', 'ref', 'advice',
    'follow', 'review', 'next', 'visit', 'milk', 'water', 'food',
    'with', 'without', 'empty', 'stomach', 'bed', 'wake', 'sleep',
    'problem', 'issue', 'complaint', 'history', 'examination', 'test',
    'report', 'investigation', 'laboratory', 'x-ray', 'scan', 'mri',
    'capsule', 'syrup', 'injection', 'apply', 'external', 'internal',
    'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight',
    'half', 'quarter', 'full', 'morning', 'noon', 'evening', 'night',
    'cont', 'conti', 'continue', 'same', 'old', 'new', 'change',
    'increase', 'decrease', 'stop', 'start', 'resume', 'hold',
}

# Lines to skip — header/footer patterns
SKIP_LINE_RE = re.compile(
    r'(?:dr\.|doctor|hospital|clinic|mbbs|bams|mba|md\.|m\.d\.|'
    r'phone|tel:|mob:|address|plot|road|colony|nagar|sector|'
    r'registration|regd|timing|monday|tuesday|wednesday|thursday|'
    r'friday|saturday|sunday|emergency|admit|banjara|hyderabad|'
    r'secunderabad|delhi|mumbai|chennai|bangalore|kolkata|'
    r'in emergency|for other|appointment|©|www\.|http)',
    re.IGNORECASE
)

# Dosage pattern
DOSAGE_RE = re.compile(
    r'\b(\d+(?:\.\d+)?\s*(?:mg|mcg|ml|iu|g|gm|units?|tab(?:let)?s?|'
    r'cap(?:sule)?s?|drops?|sachet|puff|patch))\b',
    re.IGNORECASE
)

# Frequency patterns
FREQ_X_RE    = re.compile(r'[xX×]\s*(\d)', re.IGNORECASE)   # x3, X2
FREQ_DASH_RE = re.compile(r'(\d)\s*[-–]\s*(\d)\s*[-–]\s*(\d)')  # 1-0-1
FREQ_TIMES_RE = re.compile(r'(\d+)\s*(?:times?|x)\s*(?:daily|a\s*day|/day)', re.IGNORECASE)
FREQ_ABBREV_RE = re.compile(r'\b(od|bd|tds|qid|bid|tid)\b', re.IGNORECASE)

# Duration patterns
DUR_MONTH_RE = re.compile(r'(\d+)\s*(?:months?|mar[io]ss?)', re.IGNORECASE)
DUR_WEEK_RE  = re.compile(r'(\d+)\s*weeks?', re.IGNORECASE)
DUR_DAY_RE   = re.compile(r'(\d+)\s*days?', re.IGNORECASE)

# Number prefix — numbered list items like "1)", "(2)", "①"
NUM_PREFIX_RE = re.compile(
    r'^[\s•\-]*(?:\(?(\d{1,2})\)?\.?\s*|[①②③④⑤⑥⑦⑧⑨⑩])',
    re.UNICODE
)

# Tab/Cap/Syp prefix
TAB_PREFIX_RE = re.compile(
    r'^[\s•\-]*(?:T\.|T\s+|Tab\.?\s*|Syp\.?\s*|Cap\.?\s*|'
    r'Inj\.?\s*|Ta\s+|Oint\.?\s*|Gel\.?\s*|Lotion\.?\s*)',
    re.IGNORECASE
)

# R/ Rx marker (start of prescription list)
RX_RE = re.compile(r'^[\s]*[Rr][xX/]?\s*$')


def _parse_freq(block):
    """Extract frequency count from a text block."""
    # x3, X2 pattern (most common in Indian prescriptions)
    m = FREQ_X_RE.search(block)
    if m:
        val = int(m.group(1))
        if 1 <= val <= 6:
            return str(val)
    # 1-0-1 timing pattern
    m = FREQ_DASH_RE.search(block)
    if m:
        total = int(m.group(1)) + int(m.group(2)) + int(m.group(3))
        if 1 <= total <= 6:
            return str(total)
    # "3 times daily"
    m = FREQ_TIMES_RE.search(block)
    if m:
        return m.group(1)
    # OD/BD/TDS/QID
    m = FREQ_ABBREV_RE.search(block)
    if m:
        return {'od': '1', 'bd': '2', 'tds': '3', 'qid': '4',
                'bid': '2', 'tid': '3'}.get(m.group(1).lower(), '1')
    return '1'


def _parse_dur(block, global_dur=7):
    """Extract duration in days from a text block."""
    m = DUR_MONTH_RE.search(block)
    if m:
        return min(int(m.group(1)) * 30, 365)
    m = DUR_WEEK_RE.search(block)
    if m:
        return min(int(m.group(1)) * 7, 365)
    m = DUR_DAY_RE.search(block)
    if m:
        d = int(m.group(1))
        if 1 <= d <= 365:
            return d
    return global_dur


def _parse_dosage(block):
    """Extract dosage from a text block."""
    m = DOSAGE_RE.search(block)
    return m.group(1).strip() if m else '1 tablet'


def _is_skip_line(line):
    """Return True if this line is a header/footer, not a medicine."""
    return bool(SKIP_LINE_RE.search(line))


def _is_valid_medicine_name(name):
    """Return True if name looks like a real medicine name."""
    name = name.strip()
    if len(name) < 3 or len(name) > 60:
        return False
    words = name.lower().split()
    # All words are non-medicine words → skip
    if all(w.rstrip('.,;:') in NON_MEDICINE_WORDS for w in words):
        return False
    # Starts with digit → not a medicine name
    if name[0].isdigit():
        return False
    # Only digits/symbols → skip
    if not re.search(r'[A-Za-z]{3,}', name):
        return False
    return True


def _clean_medicine_name(raw):
    """Clean up OCR noise from medicine name."""
    # Remove leading/trailing junk
    name = raw.strip().strip('•-–()[].,;:①②③④⑤⑥⑦⑧⑨⑩')
    # Collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    # Remove trailing dosage that got merged into name
    name = re.sub(r'\s+\d+\s*(?:mg|ml|mcg|tab|cap)\b.*$', '', name, flags=re.IGNORECASE)
    # Title case
    name = name.title()
    return name.strip()


def _extract_patient_name(text):
    for pattern in [
        r'Name\s*[:\.]?\s*(?:Mr\.?|Mrs\.?|Ms\.?|Dr\.?)?\s*([A-Za-z][A-Za-z\s\.]{2,40})',
        r'(?:Mr|Mrs|Ms)\.?\s+([A-Z][A-Za-z\s]{2,30})',
        r'Patient\s*[:;-]?\s*([A-Za-z][A-Za-z\s]{2,40})',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            name = re.sub(r'\s+', ' ', m.group(1).strip())
            name = re.split(
                r'\b(age|date|phone|address|yrs|years|sex|gender|mr|mrs|dr)\b',
                name, flags=re.IGNORECASE)[0].strip().rstrip('.,;:')
            if 3 <= len(name) <= 50:
                return name
    return None


def _extract_age(text):
    for pattern in [
        r'Age\s*[:\.]?\s*(\d{1,3})',
        r'(\d{1,3})\s*(?:yrs?|years?)',
        r'(\d{1,3})\s*/\s*[MmFf]',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            age = int(m.group(1))
            if 1 <= age <= 120:
                return age
    return None


def _extract_disease(text):
    # Look for diagnosis labels
    for pattern in [
        r'(?:Diagnosis|Dx|Disease|C/O|c/o|Complaint|Chief\s*Complaint)\s*[:;-]?\s*([A-Za-z][A-Za-z\s,/]{2,80})',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            disease = m.group(1).strip().split('\n')[0].strip()
            disease = re.split(
                r'\b(medicine|dosage|frequency|duration|doctor|physician|tablet|reg|r/)\b',
                disease, flags=re.IGNORECASE)[0].strip().rstrip('.,;:')
            if 3 <= len(disease) <= 100:
                return disease

    # Keyword scan — common diseases
    disease_keywords = {
        'schizophreni': 'Schizophrenia',
        'schizophremi': 'Schizophrenia',
        'bipolar': 'Bipolar Disorder',
        'depression': 'Depression',
        'anxiety': 'Anxiety',
        'diabetes': 'Diabetes',
        'hypertension': 'Hypertension',
        'thyroid': 'Thyroid Problem',
        'psoriasis': 'Psoriasis',
        'leucoderma': 'Leucoderma',
        'haematuria': 'Haematuria',
        'haematura': 'Haematuria',
        'kidney': 'Kidney Problem',
        'asthma': 'Asthma',
        'arthritis': 'Arthritis',
        'epilepsy': 'Epilepsy',
        'migraine': 'Migraine',
        'fever': 'Fever',
        'infection': 'Infection',
        'cough': 'Cough',
        'cold': 'Cold',
        'constipation': 'Constipation',
        'acidity': 'Acidity',
        'piles': 'Piles',
        'paranoi': 'Paranoia',
    }
    text_lower = text.lower()
    for kw, label in disease_keywords.items():
        if kw in text_lower:
            return label
    return None


def _extract_duration(text):
    m = DUR_MONTH_RE.search(text)
    if m:
        return min(int(m.group(1)) * 30, 365)
    m = DUR_WEEK_RE.search(text)
    if m:
        return min(int(m.group(1)) * 7, 365)
    m = DUR_DAY_RE.search(text)
    if m:
        d = int(m.group(1))
        if 1 <= d <= 365:
            return d
    return 7


# ─────────────────────────────────────────────────────────────────────────────
# KNOWN MEDICINE CORRECTIONS (OCR noise fixes)
# ─────────────────────────────────────────────────────────────────────────────

MEDICINE_CORRECTIONS = {
    'sizodon plus': 'Sizodon Plus',
    'sizodon':      'Sizodon Plus',
    'qutipin':      'Quetipin',
    'quetipin':     'Quetipin',
    'ativan':       'Ativan (Lorazepam)',
    'lorazepem':    'Ativan (Lorazepam)',
    'lorazepam':    'Ativan (Lorazepam)',
    'rivotil':      'Rivotril (Clonazepam)',
    'rivotril':     'Rivotril (Clonazepam)',
    'clunaypem':    'Clonazepam',
    'serta some':   'Serta',
    'serta':        'Serta (Sertraline)',
    'styplon':      'Styplon',
    'kanchanan':    'Kanchnar Guggul',
    'kanchanar':    'Kanchnar Guggul',
    'chandraprabha':'Chandraprabha Vati',
    'chandraprabb': 'Chandraprabha Vati',
    'cruel':        'Cruel Cap',
    'sigon':        'Sigon Cap',
}

KNOWN_MEDICINES_RE = re.compile(
    r'\b(Sizodon(?:\s+Plus)?|Qutipin|Quetipin|Ativan|Lorazep[ae]m|'
    r'Rivoti[lr]|Clona[zy]ep[ae]m|Clunaypem|Serta|Sertraline|'
    r'Olanzapine|Risperidone|Haloperidol|Lithium|Fluoxetine|'
    r'Escitalopram|Alprazolam|Diazepam|Amitriptyline|Mirtazapine|'
    r'Kanchan[ae]r?\s*[Gg]ugg[au]l|Chandraprabh[ae]|'
    r'Styplon|Sigon|Cruel|Ayurslim|Septilin|Tentex|Liv\.?\s*52|'
    r'Triphala|Ashwagandha|Brahmi|Shilajit|Tulsi|Neem|'
    r'Paracetamol|Amoxicillin|Azithromycin|Ciprofloxacin|'
    r'Metformin|Atorvastatin|Amlodipine|Losartan|Omeprazole|'
    r'Pantoprazole|Ranitidine|Cetirizine|Montelukast|Salbutamol)\b',
    re.IGNORECASE
)


def _normalize_name(name):
    key = name.lower().strip()
    return MEDICINE_CORRECTIONS.get(key, name.title())


# ─────────────────────────────────────────────────────────────────────────────
# UNIVERSAL MEDICINE EXTRACTOR — 3-pass approach
# ─────────────────────────────────────────────────────────────────────────────

def _extract_medicines_regex(text):
    medicines  = []
    seen_names = set()
    lines      = [l.strip() for l in text.split('\n')]
    global_dur = _extract_duration(text)

    def add(name, block):
        name = _clean_medicine_name(name)
        name = _normalize_name(name)
        if not _is_valid_medicine_name(name):
            return
        key = re.sub(r'\s+', ' ', name.lower().strip())
        # Deduplicate — skip if very similar name already added
        for seen in seen_names:
            if key in seen or seen in key or (
                len(key) > 5 and len(seen) > 5 and
                sum(c in seen for c in key) / max(len(key), 1) > 0.8
            ):
                return
        seen_names.add(key)
        dosage = _parse_dosage(block)
        freq   = _parse_freq(block)
        dur    = _parse_dur(block, global_dur)
        medicines.append({
            'name':          name,
            'dosage':        dosage,
            'frequency':     f"{freq} times daily",
            'duration_days': dur,
        })
        print(f"   💊 Regex: {name} | {dosage} | {freq}x | {dur}d")

    def get_block(i, n=2):
        """Get line i plus next n lines as context."""
        block_lines = []
        for j in range(i, min(i + n + 1, len(lines))):
            block_lines.append(lines[j])
        block = ' '.join(block_lines)
        if not re.search(r'\d+\s*(?:days?|weeks?|months?|mar)', block, re.IGNORECASE):
            block += f" {global_dur} days"
        return block

    # ── PASS A: Known medicine names (handles OCR noise) ──────────────────
    for i, line in enumerate(lines):
        if _is_skip_line(line):
            continue
        m = KNOWN_MEDICINES_RE.search(line)
        if m:
            add(m.group(1), get_block(i))

    # ── PASS B: Numbered list items ───────────────────────────────────────
    # Handles: "① Kanchnar Guggul", "1) Chandraprabha Vati", "(2) Cruel Cap"
    for i, line in enumerate(lines):
        if _is_skip_line(line):
            continue
        pm = NUM_PREFIX_RE.match(line)
        if not pm:
            continue
        rest = line[pm.end():].strip()
        # Remove Tab/Cap/Syp prefix if present after number
        pm2 = TAB_PREFIX_RE.match(rest)
        if pm2:
            rest = rest[pm2.end():].strip()
        # Extract medicine name — stop at dosage digits or end
        nm = re.match(
            r'^([A-Za-z][A-Za-z0-9\s\-\.]{2,40}?)(?=\s*\d|\s*$|\s+[xX×])',
            rest)
        if nm:
            add(nm.group(1).strip(), get_block(i))

    # ── PASS C: Tab/Cap/Syp prefix lines ─────────────────────────────────
    for i, line in enumerate(lines):
        if _is_skip_line(line):
            continue
        pm = TAB_PREFIX_RE.match(line)
        if not pm:
            continue
        rest = line[pm.end():].strip()
        nm = re.match(
            r'^([A-Za-z][A-Za-z0-9\s\-\.]{2,40}?)(?=\s*\d|\s*$|\s+[xX×(])',
            rest)
        if nm:
            add(nm.group(1).strip(), get_block(i))

    # ── PASS D: Dosage-anchored scan (catches anything missed) ────────────
    # If we still have fewer than expected medicines, scan all lines
    # for any line containing a dosage unit (mg, tab, cap etc.)
    if len(medicines) < 3:
        print("   🔍 Pass D: dosage-anchored scan...")
        for i, line in enumerate(lines):
            if _is_skip_line(line):
                continue
            if not DOSAGE_RE.search(line):
                continue
            # Extract word(s) before the dosage as medicine name
            m = re.match(
                r'^([A-Za-z][A-Za-z0-9\s\-\.]{2,35}?)\s+\d',
                line)
            if m:
                candidate = m.group(1).strip()
                # Must have at least one alphabetic word not in non-medicine set
                words = candidate.lower().split()
                if any(w not in NON_MEDICINE_WORDS for w in words):
                    add(candidate, get_block(i))

    return medicines


# ─────────────────────────────────────────────────────────────────────────────
# Main OCR class
# ─────────────────────────────────────────────────────────────────────────────

class PrescriptionOCR:

    def __init__(self):
        self._gv_client = None
        self._init_google_vision()

    def _init_google_vision(self):
        if not GOOGLE_VISION_AVAILABLE:
            return
        try:
            creds_path = getattr(settings, 'GOOGLE_CLOUD_VISION_CREDENTIALS', None)
            if creds_path and os.path.exists(str(creds_path)):
                credentials = service_account.Credentials.from_service_account_file(
                    str(creds_path))
                self._gv_client = vision.ImageAnnotatorClient(credentials=credentials)
                print("✅ Google Cloud Vision: service account.")
            else:
                self._gv_client = vision.ImageAnnotatorClient()
                print("✅ Google Cloud Vision: ADC.")
        except Exception as e:
            self._gv_client = None
            print(f"⚠️  Google Cloud Vision init failed: {e}")

    def _get_raw_text(self, image_path):
        if self._gv_client is not None:
            text = _text_from_google_vision(image_path, self._gv_client)
            if text and len(text.strip()) > 10:
                return text
        text = _text_from_ocrspace(image_path)
        if text and len(text.strip()) > 10:
            return text
        return _text_from_tesseract(image_path) or ""

    def parse_prescription(self, image_path):
        # Step 1: Gemini Vision
        print("   🔮 Trying Gemini Vision...")
        gemini_result = _parse_with_gemini_vision(image_path)
        if gemini_result is not None:
            raw_text  = self._get_raw_text(image_path)
            medicines = gemini_result['medicines']
            print(f"   ✅ Final (Gemini): {len(medicines)} medicines")
            return {
                'success':                 True,
                'extracted_text':          raw_text,
                'patient_name':            gemini_result['patient_name'],
                'age':                     gemini_result['age'],
                'disease':                 gemini_result['disease'],
                'medicines':               medicines,
                'treatment_duration_days': gemini_result['treatment_duration_days'],
                'total_medicines':         len(medicines),
            }

        # Step 2: OCR.space + universal regex
        print("   📄 Falling back to OCR.space + universal regex...")
        raw_text = self._get_raw_text(image_path)

        if not raw_text or len(raw_text.strip()) < 5:
            print("   ⚠️  No text extracted.")
            return {
                'success': True, 'extracted_text': '',
                'patient_name': None, 'age': None, 'disease': None,
                'medicines': [], 'treatment_duration_days': 7,
                'total_medicines': 0,
            }

        patient_name = _extract_patient_name(raw_text)
        age          = _extract_age(raw_text)
        disease      = _extract_disease(raw_text)
        duration     = _extract_duration(raw_text)
        medicines    = _extract_medicines_regex(raw_text)

        print(f"   ✅ Final: patient={patient_name}, age={age}, "
              f"disease={disease}, medicines={len(medicines)}, dur={duration}d")

        return {
            'success':                 True,
            'extracted_text':          raw_text,
            'patient_name':            patient_name,
            'age':                     age,
            'disease':                 disease,
            'medicines':               medicines,
            'treatment_duration_days': duration,
            'total_medicines':         len(medicines),
        }

    def extract_text(self, image_path):
        return self._get_raw_text(image_path)

    def extract_patient_name(self, text): return _extract_patient_name(text)
    def extract_age(self, text):          return _extract_age(text)
    def extract_disease(self, text):      return _extract_disease(text)
    def extract_duration(self, text):     return _extract_duration(text)
    def extract_medicines(self, text):    return _extract_medicines_regex(text)