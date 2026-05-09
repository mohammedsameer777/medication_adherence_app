"""
OCR SERVICE
Priority:
  1. Gemini Vision  — kept as-is (disabled in India, but code stays)
  2. OCR.space      — free text OCR (25k/month) with IMPROVED regex
  3. Tesseract      — local fallback

IMPROVED: medicine extraction now handles Indian handwritten prescriptions
with patterns like "Tab Sizodon Plus", "Tab Quetipin 300mg", etc.
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
        mime_map = {
            '.jpg':  'image/jpeg', '.jpeg': 'image/jpeg',
            '.png':  'image/png',  '.bmp':  'image/bmp',
            '.tiff': 'image/tiff', '.tif':  'image/tiff',
        }
        mime_type = mime_map.get(ext, 'image/jpeg')

        prompt = """You are a medical prescription parser. Read this prescription carefully.
It may be handwritten, printed, or mixed.

Return ONLY a JSON object, no markdown, no explanation:

{
  "patient_name": "full name or null",
  "age": integer_or_null,
  "disease": "diagnosis or null",
  "treatment_duration_days": integer_default_7,
  "medicines": [
    {
      "name": "medicine name",
      "dosage": "e.g. 500mg or 1 tablet",
      "frequency": "N times daily",
      "duration_days": integer
    }
  ]
}

Rules:
- Extract ONLY actual medicine/drug names
- T. or Tab. prefix before a medicine name means tablet — include the name after it
- Do NOT include doctor name, hospital, patient name, address
- frequency = "N times daily" where N is a number
- If dosage unclear: "1 tablet"
- If duration unclear: 7
- Return [] if no medicines found
- Return ONLY the JSON"""

        payload = json.dumps({
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": mime_type, "data": image_data}},
                    {"text": prompt}
                ]
            }],
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
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
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
            medicines.append({
                'name': name, 'dosage': dosage,
                'frequency': freq, 'duration_days': dur,
            })
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
        return {
            'patient_name':            result.get('patient_name'),
            'age':                     age,
            'disease':                 result.get('disease'),
            'medicines':               medicines,
            'treatment_duration_days': duration,
        }

    except Exception as e:
        print(f"   ❌ Gemini error: {type(e).__name__}: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# TEXT EXTRACTION helpers
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
        mime_map = {
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.png': 'image/png',  '.bmp':  'image/bmp',
        }
        mime_type = mime_map.get(ext, 'image/jpeg')
        payload   = urllib.parse.urlencode({
            'base64Image':       f"data:{mime_type};base64,{image_data}",
            'apikey':            api_key,
            'language':          'eng',
            'isOverlayRequired': 'false',
            'detectOrientation': 'true',
            'scale':             'true',
            'OCREngine':         '2',
            'isTable':           'false',
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://api.ocr.space/parse/image', data=payload,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            method='POST'
        )
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
                print(f"   📄 OCR raw:\n{text}\n---")
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
# FIELD EXTRACTORS
# ─────────────────────────────────────────────────────────────────────────────

NON_MEDICINE = {
    'prescription', 'patient', 'doctor', 'date', 'diagnosis', 'name',
    'age', 'gender', 'hospital', 'clinic', 'address', 'phone',
    'signature', 'frequency', 'duration', 'dosage', 'refill', 'medicine',
    'for', 'the', 'and', 'with', 'times', 'time', 'daily', 'weekly',
    'once', 'twice', 'thrice', 'morning', 'evening', 'night', 'before',
    'after', 'meal', 'meals', 'food', 'water', 'take', 'days', 'weeks',
    'months', 'stat', 'bp', 'hr', 'spo2', 'temp', 'wt', 'weight',
    'free', 'home', 'delivery', 'r', 'rx', 'mg', 'ml', 'tab',
    'reg', 'no', 'city', 'general', 'physician', 'consultant',
    'continue', 'other', 'call', 'counselled', 'phone', 'plot',
    'road', 'colony', 'regd', 'mbbs', 'md', 'dr', 'emergency',
}


def _extract_patient_name(text):
    # Look for "Mr/Mrs/Ms Name" pattern common in Indian prescriptions
    for pattern in [
        r'Mr\.?\s+([A-Z][A-Za-z\s]{2,30})',
        r'Mrs\.?\s+([A-Z][A-Za-z\s]{2,30})',
        r'Ms\.?\s+([A-Z][A-Za-z\s]{2,30})',
        r'Patient\s*Name\s*[:;-]?\s*([A-Za-z][A-Za-z\s]{2,40})',
        r'Name\s*[:;-]?\s*([A-Za-z][A-Za-z\s]{2,40})',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            name = re.sub(r'\s+', ' ', m.group(1).strip())
            name = re.split(
                r'\b(age|date|phone|address|mr|mrs|dr|sex|gender|yrs|years)\b',
                name, flags=re.IGNORECASE)[0].strip()
            if 3 <= len(name) <= 50:
                return name
    return None


def _extract_age(text):
    for pattern in [
        r'(\d{1,3})\s*(?:yrs?|years?)',
        r'Age\s*[:;-]?\s*(\d{1,3})',
        r'(\d{1,3})\s*/\s*[MmFf]',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            age = int(m.group(1))
            if 1 <= age <= 120:
                return age
    return None


def _extract_disease(text):
    for pattern in [
        r'Diagnosis\s*[:;-]?\s*([A-Za-z][A-Za-z\s,]{2,60})',
        r'Dx\s*[:;-]?\s*([A-Za-z][A-Za-z\s,]{2,40})',
        r'(?:C/O|c/o)\s*[:;-]?\s*([A-Za-z][A-Za-z\s,]{2,40})',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            disease = re.sub(r'\s+', ' ', m.group(1).strip()).split('\n')[0].strip()
            if 3 <= len(disease) <= 80:
                return disease

    # Common disease keywords in Indian psychiatry prescriptions
    disease_keywords = [
        'schizophrenia', 'diabetes', 'hypertension', 'fever', 'cold',
        'cough', 'headache', 'infection', 'asthma', 'arthritis',
        'migraine', 'depression', 'anxiety', 'bipolar', 'psychosis',
        'paranoia', 'epilepsy',
    ]
    text_lower = text.lower()
    for d in disease_keywords:
        if d in text_lower:
            return d.title()
    return None


def _extract_duration(text):
    # Look for "6 months", "3 months" etc
    m = re.search(r'(\d+)\s*months?', text, re.IGNORECASE)
    if m:
        months = int(m.group(1))
        return min(months * 30, 365)

    for pattern in [
        r'Duration\s*[:;-]?\s*(\d+)\s*days?',
        r'for\s*(\d+)\s*days?',
        r'(\d+)\s*days?',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            d = int(m.group(1))
            if 1 <= d <= 365:
                return d
    return 7


def _extract_medicines_regex(text):
    """
    IMPROVED medicine extractor for Indian handwritten prescriptions.
    Handles patterns like:
      - "Tab Sizodon Plus"
      - "Tab Quetipin 300mg"
      - "Tab Ativan (Lorazepam) 2mg"
      - "Tab Rivotril 0.5mg (Clonazepam)"
      - "Tab Serta 50mg"
    """
    medicines  = []
    seen_names = set()

    DOSAGE_RE = re.compile(
        r'\b(\d+(?:\.\d+)?\s*(?:mg|mcg|ml|iu|g|gm|units?|tablet|tab|cap|caps))\b',
        re.IGNORECASE)
    DUR_RE    = re.compile(r'(\d+)\s*(?:days?|months?)', re.IGNORECASE)

    # Prefix pattern — Tab, T., Syp, Cap, Inj, numbered list items
    PREFIX_RE = re.compile(
        r'^(?:\(?[\d①②③④⑤⑥⑦⑧⑨]\)?\.?\s*)?'   # optional numbering
        r'(?:T\.|T\s+|Tab\.?\s*|Syp\.?\s*|Cap\.?\s*|Inj\.?\s*)',
        re.IGNORECASE)

    def parse_freq(block):
        """Parse frequency from a block of text (medicine line + next few lines)."""
        # Pattern: 1 - x - 1 or x - x - 1 (morning-afternoon-night)
        timing = re.findall(r'([01x])\s*[-–]\s*([01x])\s*[-–]\s*([01x])', block, re.IGNORECASE)
        if timing:
            m_val, a_val, n_val = timing[0]
            total = sum(1 for v in [m_val, a_val, n_val] if v not in ('x', 'X', '0'))
            if total > 0:
                return str(total)

        if re.search(r'\bbd\b|\btwice\b', block, re.IGNORECASE):
            return '2'
        if re.search(r'\btds\b|\bthrice\b', block, re.IGNORECASE):
            return '3'
        if re.search(r'\bqid\b', block, re.IGNORECASE):
            return '4'
        if re.search(r'\bod\b|\bonce\b', block, re.IGNORECASE):
            return '1'
        return '1'

    def parse_dur(block):
        m = re.search(r'(\d+)\s*months?', block, re.IGNORECASE)
        if m:
            return min(int(m.group(1)) * 30, 365)
        m = re.search(r'(\d+)\s*days?', block, re.IGNORECASE)
        if m:
            d = int(m.group(1))
            if 1 <= d <= 365:
                return d
        return 7

    def clean_name(raw):
        """Clean medicine name — remove bracketed generics if long enough without."""
        # Remove trailing bracket content if name is already meaningful
        name = re.sub(r'\s*\([^)]*\)\s*', ' ', raw).strip()
        name = re.sub(r'\s+', ' ', name).strip().rstrip('.,;:')
        return name

    def is_non_medicine(name):
        words = name.lower().strip().split()
        return all(w.rstrip('.,;:') in NON_MEDICINE for w in words)

    def add(name, block):
        name = clean_name(name)
        if len(name) < 3 or is_non_medicine(name):
            return
        key = name.lower()
        if key in seen_names:
            return
        seen_names.add(key)

        dm     = DOSAGE_RE.search(block)
        dosage = dm.group(1).strip() if dm else '1 tablet'
        freq   = parse_freq(block)
        dur    = parse_dur(block)

        medicines.append({
            'name':          name,
            'dosage':        dosage,
            'frequency':     f"{freq} times daily",
            'duration_days': dur,
        })
        print(f"   💊 Regex: {name} | {dosage} | {freq}x | {dur}d")

    lines = text.split('\n')

    # Pass 1: find lines starting with Tab/T./Cap etc
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        pm   = PREFIX_RE.match(line)
        if pm:
            rest = line[pm.end():].strip()

            # Extract medicine name — up to dosage or bracket
            nm = re.match(
                r'^([A-Za-z][A-Za-z0-9\-\s]{1,40}?)(?:\s+\d|\s+\(|\s*$)',
                rest)
            if nm:
                med_name = nm.group(1).strip()

                # Collect this line + next 2 lines as context for freq/dose
                block_lines = [line]
                for j in range(1, 3):
                    if i + j < len(lines):
                        block_lines.append(lines[i + j].strip())
                block = ' '.join(block_lines)

                add(med_name, block)
        i += 1

    # Pass 2: scan for known medicine name patterns if pass 1 found nothing
    if not medicines:
        print("   ⚠️  Pass 1 found nothing — trying keyword scan...")
        # Common Indian medicine keywords
        KNOWN_PATTERNS = re.compile(
            r'\b(Sizodon|Quetipin|Qutipin|Ativan|Lorazepam|Rivotril|Clonazepam|'
            r'Serta|Sertraline|Olanzapine|Risperidone|Haloperidol|Lithium|'
            r'Depakote|Valproate|Fluoxetine|Escitalopram|Alprazolam|'
            r'Diazepam|Clonazepam|Amitriptyline|Mirtazapine)\b',
            re.IGNORECASE)
        for i, line in enumerate(lines):
            m = KNOWN_PATTERNS.search(line)
            if m:
                med_name = m.group(1)
                block_lines = [line]
                for j in range(1, 3):
                    if i + j < len(lines):
                        block_lines.append(lines[i + j].strip())
                block = ' '.join(block_lines)
                add(med_name, block)

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
                print(f"   ✅ Google Vision text: {len(text)} chars.")
                return text

        text = _text_from_ocrspace(image_path)
        if text and len(text.strip()) > 10:
            return text

        text = _text_from_tesseract(image_path)
        return text or ""

    def parse_prescription(self, image_path):
        # ── Step 1: Gemini Vision ─────────────────────────────────────────
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

        # ── Step 2: OCR.space + improved regex ───────────────────────────
        print("   📄 Falling back to OCR.space + regex...")
        raw_text = self._get_raw_text(image_path)

        if not raw_text or len(raw_text.strip()) < 5:
            print("   ⚠️  No text extracted.")
            return {
                'success':                 True,
                'extracted_text':          '',
                'patient_name':            None,
                'age':                     None,
                'disease':                 None,
                'medicines':               [],
                'treatment_duration_days': 7,
                'total_medicines':         0,
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