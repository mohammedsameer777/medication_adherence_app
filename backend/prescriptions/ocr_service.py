import pytesseract
from PIL import Image
import re
from django.conf import settings

try:
    import cv2
    import numpy as np
    USE_OPENCV = True
except ImportError:
    USE_OPENCV = False
    print("OpenCV not available, using PIL only for OCR")


class PrescriptionOCR:

    def __init__(self):
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

    def preprocess_image_opencv(self, image_path):
        img = cv2.imread(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        denoised = cv2.fastNlMeansDenoising(thresh, None, 10, 7, 21)
        return denoised

    def preprocess_image_pil(self, image_path):
        img = Image.open(image_path)
        img = img.convert('L')
        return img

    def extract_text(self, image_path):
        try:
            if USE_OPENCV:
                processed_img = self.preprocess_image_opencv(image_path)
                text = pytesseract.image_to_string(processed_img)
            else:
                processed_img = self.preprocess_image_pil(image_path)
                text = pytesseract.image_to_string(processed_img)
            return text
        except Exception as e:
            print(f"OCR Error: {str(e)}")
            return ""

    def extract_patient_name(self, text):
        patterns = [
            r'Patient\s*Name\s*[:;-]?\s*([A-Za-z][A-Za-z\s]{2,40})',
            r'Name\s*[:;-]?\s*([A-Za-z][A-Za-z\s]{2,40})',
            r'Patient\s*[:;-]?\s*([A-Za-z][A-Za-z\s]{2,40})',
            r'FOR\s*[^\n]*\n\s*([A-Za-z][A-Za-z\s.,]{2,40})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                name = re.sub(r'\s+', ' ', name)
                # Remove trailing junk words
                name = re.split(r'\b(age|date|phone|address|mr|mrs|dr)\b', name, flags=re.IGNORECASE)[0].strip()
                if 3 <= len(name) <= 50:
                    return name
        return None

    def extract_age(self, text):
        patterns = [
            r'Age\s*[:;-]?\s*(\d{1,3})',
            r'(\d{1,3})\s*years?',
            r'(\d{1,3})\s*yrs?',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                age = int(match.group(1))
                if 1 <= age <= 120:
                    return age
        return None

    def extract_disease(self, text):
        patterns = [
            r'Diagnosis\s*[:;-]?\s*([A-Za-z][A-Za-z\s]{2,60})',
            r'Disease\s*[:;-]?\s*([A-Za-z][A-Za-z\s]{2,60})',
            r'Condition\s*[:;-]?\s*([A-Za-z][A-Za-z\s]{2,60})',
            r'(?:C/O|Complaint)\s*[:;-]?\s*([A-Za-z][A-Za-z\s]{2,60})',
        ]
        common_diseases = [
            'diabetes', 'hypertension', 'asthma', 'arthritis', 'thyroid',
            'fever', 'cold', 'cough', 'infection', 'blood pressure',
            'heart disease', 'kidney disease', 'liver disease', 'headache',
            'migraine', 'pneumonia', 'tuberculosis', 'anaemia', 'anemia',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                disease = match.group(1).strip()
                disease = re.sub(r'\s+', ' ', disease)
                disease = disease.split('\n')[0].strip()
                if 3 <= len(disease) <= 100:
                    return disease
        text_lower = text.lower()
        for disease in common_diseases:
            if disease in text_lower:
                return disease.title()
        return None

    def extract_medicines(self, text):
        """
        Extract ONLY real medicine names — not headers or frequency words.
        A real medicine line must contain a dosage marker (mg, ml, tablet, cap, mcg, iu)
        OR follow an Rx / medicine-list section.
        """
        medicines = []

        # ── Words that are NEVER medicine names ──────────────────────────────
        SKIP_WORDS = {
            'prescription', 'patient', 'doctor', 'date', 'diagnosis', 'name',
            'age', 'gender', 'hospital', 'clinic', 'address', 'phone', 'sig',
            'signature', 'rx', 'inscription', 'subscription', 'superscription',
            'frequency', 'duration', 'dosage', 'refill', 'filled', 'lot',
            'exp', 'mfgr', 'ndc', 'dea', 'for', 'the', 'and', 'with',
            'times', 'time', 'daily', 'weekly', 'once', 'twice', 'thrice',
            'morning', 'evening', 'night', 'afternoon', 'before', 'after',
            'meal', 'meals', 'food', 'water', 'take', 'tablet', 'tablets',
            'capsule', 'capsules', 'syrup', 'injection', 'drop', 'drops',
            'apply', 'use', 'days', 'weeks', 'months', 'sos', 'stat',
            'medical', 'facility', 'rank', 'degree', 'edition', 'sample',
            'images', 'copyright', 'researchgate', 'google', 'www',
        }

        # ── Dosage markers that confirm a line has a real medicine ────────────
        DOSAGE_MARKERS = re.compile(
            r'\b(\d+\s*(?:mg|mcg|ml|iu|g|gm|units?|tablet|cap|tab|caps))\b',
            re.IGNORECASE
        )

        # ── Frequency patterns ────────────────────────────────────────────────
        FREQ_PATTERN = re.compile(
            r'(\d+)\s*(?:times?\s*(?:a\s*)?daily|x\s*daily|\/day|OD|BD|TDS|QID)',
            re.IGNORECASE
        )
        FREQ_WORDS = re.compile(
            r'\b(once|twice|thrice|1|2|3|4)\s*(?:times?\s*(?:a\s*)?)?(?:daily|a\s*day)\b',
            re.IGNORECASE
        )

        # ── Duration pattern ──────────────────────────────────────────────────
        DURATION_PATTERN = re.compile(r'(\d+)\s*days?', re.IGNORECASE)

        # ── Medicine name pattern: starts with capital, has 2+ chars ─────────
        MED_NAME_PATTERN = re.compile(r'^([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)')

        lines = text.split('\n')

        for line in lines:
            line = line.strip()
            if len(line) < 4:
                continue

            # Skip lines whose FIRST word is a known skip word
            first_word = line.split()[0].lower().rstrip('.:,;')
            if first_word in SKIP_WORDS:
                continue

            # Skip lines that are ONLY frequency/time words (no dosage marker)
            if not DOSAGE_MARKERS.search(line):
                continue

            # Skip lines that start with a digit (usually dosage lines, not names)
            if re.match(r'^\d', line):
                continue

            # Try to extract medicine name from start of line
            name_match = MED_NAME_PATTERN.match(line)
            if not name_match:
                continue

            medicine_name = name_match.group(1).strip()

            # Reject if the name itself is a skip word
            if medicine_name.lower() in SKIP_WORDS:
                continue

            # Must be at least 3 chars and not all digits
            if len(medicine_name) < 3 or medicine_name.isdigit():
                continue

            # Extract dosage
            dosage_match = DOSAGE_MARKERS.search(line)
            dosage = dosage_match.group(1).strip() if dosage_match else '1 tablet'

            # Extract frequency
            freq = '1'
            freq_match = FREQ_PATTERN.search(line)
            if freq_match:
                freq = freq_match.group(1)
            else:
                freq_word_match = FREQ_WORDS.search(line)
                if freq_word_match:
                    word = freq_word_match.group(1).lower()
                    freq = {'once': '1', 'twice': '2', 'thrice': '3',
                            '1': '1', '2': '2', '3': '3', '4': '4'}.get(word, '1')
                elif re.search(r'\bBD\b', line, re.IGNORECASE):
                    freq = '2'
                elif re.search(r'\bTDS\b', line, re.IGNORECASE):
                    freq = '3'
                elif re.search(r'\bQID\b', line, re.IGNORECASE):
                    freq = '4'

            # Extract duration
            duration = 7
            dur_match = DURATION_PATTERN.search(line)
            if dur_match:
                d = int(dur_match.group(1))
                if 1 <= d <= 365:
                    duration = d

            medicines.append({
                'name':         medicine_name,
                'dosage':       dosage,
                'frequency':    f"{freq} times daily",
                'duration_days': duration,
            })

        return medicines

    def extract_duration(self, text):
        patterns = [
            r'Duration\s*[:;-]?\s*(\d+)\s*days?',
            r'for\s*(\d+)\s*days?',
            r'(\d+)\s*days?',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                duration = int(match.group(1))
                if 1 <= duration <= 365:
                    return duration
        return 7

    def parse_prescription(self, image_path):
        text = self.extract_text(image_path)

        if not text:
            return {
                'success': False,
                'error': 'Failed to extract text from image'
            }

        patient_name = self.extract_patient_name(text)
        age          = self.extract_age(text)
        disease      = self.extract_disease(text)
        medicines    = self.extract_medicines(text)
        duration     = self.extract_duration(text)

        return {
            'success':                True,
            'extracted_text':         text,
            'patient_name':           patient_name,
            'age':                    age,
            'disease':                disease,
            'medicines':              medicines,
            'treatment_duration_days': duration,
            'total_medicines':        len(medicines),
        }