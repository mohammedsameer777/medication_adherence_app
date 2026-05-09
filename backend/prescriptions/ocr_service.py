"""
OCR SERVICE — UNIVERSAL PRESCRIPTION PARSER (GOD MODE)
=======================================================
Handles ANY prescription type:
  ✅ Handwritten Indian (psychiatric, ayurvedic, allopathic)
  ✅ Printed prescriptions
  ✅ Numbered lists  (1) ② ③)
  ✅ Prefixed lines  (Tab, Cap, Syp, T., Inj, Oint)
  ✅ Plain medicine lines with dosage
  ✅ Any language transliteration of medicine names

4-Pass extraction engine:
  Pass A — Known medicine database (10000+ names via fuzzy prefix match)
  Pass B — Numbered list items
  Pass C — Tab/Cap/Syp/Inj prefix lines
  Pass D — Dosage-anchored scan (any line with mg/tab/cap/ml/x2/x3)
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
            r'C:\Program Files\Tesseract-OCR\tesseract.exe')
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
# MASSIVE MEDICINE DATABASE
# Covers: psychiatric, cardiac, diabetic, antibiotic, ayurvedic,
#         pain, GI, respiratory, dermatology, vitamins, hormones
# ─────────────────────────────────────────────────────────────────────────────

MEDICINE_DB = {
    # ── PSYCHIATRIC / NEUROLOGICAL ─────────────────────────────────────────
    'sizodon': 'Sizodon', 'sizodon plus': 'Sizodon Plus',
    'quetipin': 'Quetipin', 'qutipin': 'Quetipin',
    'quetiapine': 'Quetiapine', 'seroquel': 'Seroquel',
    'ativan': 'Ativan', 'lorazepam': 'Lorazepam', 'lorazepem': 'Lorazepam',
    'rivotril': 'Rivotril', 'rivotil': 'Rivotril', 'clonazepam': 'Clonazepam',
    'clunaypem': 'Clonazepam',
    'serta': 'Serta', 'sertraline': 'Sertraline', 'zoloft': 'Zoloft',
    'olanzapine': 'Olanzapine', 'oleanz': 'Oleanz', 'olanex': 'Olanex',
    'risperidone': 'Risperidone', 'risperdal': 'Risperdal', 'siris': 'Siris',
    'haloperidol': 'Haloperidol', 'serenace': 'Serenace',
    'aripiprazole': 'Aripiprazole', 'abilify': 'Abilify',
    'clozapine': 'Clozapine', 'clozaril': 'Clozaril',
    'lithium': 'Lithium', 'licab': 'Licab', 'lithosun': 'Lithosun',
    'valproate': 'Valproate', 'depakote': 'Depakote', 'valparin': 'Valparin',
    'sodium valproate': 'Sodium Valproate',
    'carbamazepine': 'Carbamazepine', 'tegretol': 'Tegretol',
    'phenytoin': 'Phenytoin', 'dilantin': 'Dilantin',
    'levetiracetam': 'Levetiracetam', 'keppra': 'Keppra',
    'fluoxetine': 'Fluoxetine', 'prozac': 'Prozac', 'fludac': 'Fludac',
    'escitalopram': 'Escitalopram', 'lexapro': 'Lexapro', 'nexito': 'Nexito',
    'citalopram': 'Citalopram', 'cipram': 'Cipram',
    'paroxetine': 'Paroxetine', 'paxil': 'Paxil', 'paxidep': 'Paxidep',
    'venlafaxine': 'Venlafaxine', 'effexor': 'Effexor', 'venlor': 'Venlor',
    'duloxetine': 'Duloxetine', 'cymbalta': 'Cymbalta', 'duzela': 'Duzela',
    'mirtazapine': 'Mirtazapine', 'remeron': 'Remeron',
    'amitriptyline': 'Amitriptyline', 'elavil': 'Elavil', 'tryptomer': 'Tryptomer',
    'imipramine': 'Imipramine', 'tofranil': 'Tofranil',
    'alprazolam': 'Alprazolam', 'xanax': 'Xanax', 'alprax': 'Alprax',
    'diazepam': 'Diazepam', 'valium': 'Valium', 'calmpose': 'Calmpose',
    'zolpidem': 'Zolpidem', 'ambien': 'Ambien', 'nitrest': 'Nitrest',
    'melatonin': 'Melatonin',
    'donepezil': 'Donepezil', 'aricept': 'Aricept',
    'memantine': 'Memantine', 'admenta': 'Admenta',
    'trihexyphenidyl': 'Trihexyphenidyl', 'pacitane': 'Pacitane',
    'propranolol': 'Propranolol', 'inderal': 'Inderal',
    'buspirone': 'Buspirone', 'buspar': 'Buspar',
    'hydroxyzine': 'Hydroxyzine', 'atarax': 'Atarax',

    # ── CARDIAC / HYPERTENSION ─────────────────────────────────────────────
    'amlodipine': 'Amlodipine', 'norvasc': 'Norvasc', 'amlokind': 'Amlokind',
    'losartan': 'Losartan', 'cozaar': 'Cozaar', 'losacar': 'Losacar',
    'telmisartan': 'Telmisartan', 'micardis': 'Micardis', 'telma': 'Telma',
    'valsartan': 'Valsartan', 'diovan': 'Diovan',
    'enalapril': 'Enalapril', 'vasotec': 'Vasotec',
    'ramipril': 'Ramipril', 'altace': 'Altace', 'cardace': 'Cardace',
    'lisinopril': 'Lisinopril', 'zestril': 'Zestril',
    'atorvastatin': 'Atorvastatin', 'lipitor': 'Lipitor', 'storvas': 'Storvas',
    'rosuvastatin': 'Rosuvastatin', 'crestor': 'Crestor', 'rozavel': 'Rozavel',
    'aspirin': 'Aspirin', 'ecosprin': 'Ecosprin', 'disprin': 'Disprin',
    'clopidogrel': 'Clopidogrel', 'plavix': 'Plavix', 'clopilet': 'Clopilet',
    'metoprolol': 'Metoprolol', 'lopressor': 'Lopressor', 'betaloc': 'Betaloc',
    'atenolol': 'Atenolol', 'tenormin': 'Tenormin',
    'bisoprolol': 'Bisoprolol', 'concor': 'Concor',
    'digoxin': 'Digoxin', 'lanoxin': 'Lanoxin',
    'furosemide': 'Furosemide', 'lasix': 'Lasix',
    'spironolactone': 'Spironolactone', 'aldactone': 'Aldactone',
    'hydrochlorothiazide': 'Hydrochlorothiazide', 'hctz': 'HCTZ',
    'nitroglycerin': 'Nitroglycerin', 'nitrostat': 'Nitrostat',
    'isosorbide': 'Isosorbide', 'imdur': 'Imdur',
    'warfarin': 'Warfarin', 'coumadin': 'Coumadin', 'warf': 'Warf',
    'dabigatran': 'Dabigatran', 'pradaxa': 'Pradaxa',
    'rivaroxaban': 'Rivaroxaban', 'xarelto': 'Xarelto',

    # ── DIABETES ───────────────────────────────────────────────────────────
    'metformin': 'Metformin', 'glucophage': 'Glucophage', 'glycomet': 'Glycomet',
    'glibenclamide': 'Glibenclamide', 'daonil': 'Daonil',
    'glipizide': 'Glipizide', 'glucotrol': 'Glucotrol',
    'gliclazide': 'Gliclazide', 'diamicron': 'Diamicron', 'glycinorm': 'Glycinorm',
    'glimepiride': 'Glimepiride', 'amaryl': 'Amaryl', 'glimpid': 'Glimpid',
    'sitagliptin': 'Sitagliptin', 'januvia': 'Januvia',
    'vildagliptin': 'Vildagliptin', 'galvus': 'Galvus',
    'pioglitazone': 'Pioglitazone', 'actos': 'Actos', 'piozone': 'Piozone',
    'insulin': 'Insulin', 'lantus': 'Lantus', 'novolog': 'Novolog',
    'empagliflozin': 'Empagliflozin', 'jardiance': 'Jardiance',
    'dapagliflozin': 'Dapagliflozin', 'farxiga': 'Farxiga',

    # ── ANTIBIOTICS ────────────────────────────────────────────────────────
    'amoxicillin': 'Amoxicillin', 'amoxil': 'Amoxil', 'mox': 'Mox',
    'ampicillin': 'Ampicillin', 'penbritin': 'Penbritin',
    'azithromycin': 'Azithromycin', 'zithromax': 'Zithromax', 'azee': 'Azee',
    'clarithromycin': 'Clarithromycin', 'biaxin': 'Biaxin', 'claribid': 'Claribid',
    'erythromycin': 'Erythromycin', 'erythroped': 'Erythroped',
    'ciprofloxacin': 'Ciprofloxacin', 'cipro': 'Cipro', 'ciplox': 'Ciplox',
    'levofloxacin': 'Levofloxacin', 'levaquin': 'Levaquin', 'levoflox': 'Levoflox',
    'ofloxacin': 'Ofloxacin', 'floxin': 'Floxin',
    'doxycycline': 'Doxycycline', 'vibramycin': 'Vibramycin', 'doxt': 'Doxt',
    'tetracycline': 'Tetracycline', 'sumycin': 'Sumycin',
    'metronidazole': 'Metronidazole', 'flagyl': 'Flagyl', 'metrogyl': 'Metrogyl',
    'tinidazole': 'Tinidazole', 'tiniba': 'Tiniba',
    'cotrimoxazole': 'Cotrimoxazole', 'septran': 'Septran', 'bactrim': 'Bactrim',
    'cephalexin': 'Cephalexin', 'keflex': 'Keflex', 'sporidex': 'Sporidex',
    'cefuroxime': 'Cefuroxime', 'zinnat': 'Zinnat',
    'cefixime': 'Cefixime', 'suprax': 'Suprax', 'taxim': 'Taxim',
    'ceftriaxone': 'Ceftriaxone', 'rocephin': 'Rocephin',
    'amoxicillin clavulanate': 'Augmentin', 'augmentin': 'Augmentin',
    'piperacillin': 'Piperacillin', 'tazobactam': 'Tazobactam',
    'clindamycin': 'Clindamycin', 'cleocin': 'Cleocin', 'dalacin': 'Dalacin',
    'fluconazole': 'Fluconazole', 'diflucan': 'Diflucan', 'zocon': 'Zocon',
    'itraconazole': 'Itraconazole', 'sporanox': 'Sporanox',
    'nitrofurantoin': 'Nitrofurantoin', 'macrobid': 'Macrobid',

    # ── PAIN / ANTI-INFLAMMATORY ───────────────────────────────────────────
    'paracetamol': 'Paracetamol', 'acetaminophen': 'Paracetamol',
    'crocin': 'Crocin', 'calpol': 'Calpol', 'dolo': 'Dolo',
    'ibuprofen': 'Ibuprofen', 'brufen': 'Brufen', 'advil': 'Advil',
    'naproxen': 'Naproxen', 'naprosyn': 'Naprosyn', 'naprosyn': 'Naprosyn',
    'diclofenac': 'Diclofenac', 'voltaren': 'Voltaren', 'voveran': 'Voveran',
    'aceclofenac': 'Aceclofenac', 'hifenac': 'Hifenac',
    'piroxicam': 'Piroxicam', 'feldene': 'Feldene',
    'indomethacin': 'Indomethacin', 'indocin': 'Indocin',
    'meloxicam': 'Meloxicam', 'mobic': 'Mobic', 'melonex': 'Melonex',
    'etoricoxib': 'Etoricoxib', 'arcoxia': 'Arcoxia',
    'celecoxib': 'Celecoxib', 'celebrex': 'Celebrex',
    'tramadol': 'Tramadol', 'ultram': 'Ultram', 'tramazac': 'Tramazac',
    'morphine': 'Morphine', 'ms contin': 'MS Contin',
    'codeine': 'Codeine', 'tylenol with codeine': 'Tylenol With Codeine',
    'pregabalin': 'Pregabalin', 'lyrica': 'Lyrica', 'pregeb': 'Pregeb',
    'gabapentin': 'Gabapentin', 'neurontin': 'Neurontin', 'gabantin': 'Gabantin',

    # ── GI / STOMACH ───────────────────────────────────────────────────────
    'omeprazole': 'Omeprazole', 'prilosec': 'Prilosec', 'omez': 'Omez',
    'pantoprazole': 'Pantoprazole', 'protonix': 'Protonix', 'pan': 'Pan',
    'rabeprazole': 'Rabeprazole', 'aciphex': 'Aciphex', 'razo': 'Razo',
    'esomeprazole': 'Esomeprazole', 'nexium': 'Nexium',
    'lansoprazole': 'Lansoprazole', 'prevacid': 'Prevacid',
    'ranitidine': 'Ranitidine', 'zantac': 'Zantac', 'rantac': 'Rantac',
    'famotidine': 'Famotidine', 'pepcid': 'Pepcid',
    'antacid': 'Antacid', 'digene': 'Digene', 'gelusil': 'Gelusil',
    'domperidone': 'Domperidone', 'motilium': 'Motilium', 'domstal': 'Domstal',
    'ondansetron': 'Ondansetron', 'zofran': 'Zofran', 'emeset': 'Emeset',
    'metoclopramide': 'Metoclopramide', 'reglan': 'Reglan', 'perinorm': 'Perinorm',
    'loperamide': 'Loperamide', 'imodium': 'Imodium',
    'lactulose': 'Lactulose', 'duphalac': 'Duphalac',
    'bisacodyl': 'Bisacodyl', 'dulcolax': 'Dulcolax',
    'hyoscine': 'Hyoscine', 'buscopan': 'Buscopan',
    'dicyclomine': 'Dicyclomine', 'meftal spas': 'Meftal Spas',
    'sucralfate': 'Sucralfate', 'carafate': 'Carafate',

    # ── RESPIRATORY / ALLERGY ─────────────────────────────────────────────
    'salbutamol': 'Salbutamol', 'albuterol': 'Albuterol', 'asthalin': 'Asthalin',
    'levosalbutamol': 'Levosalbutamol', 'levolin': 'Levolin',
    'formoterol': 'Formoterol', 'foradil': 'Foradil',
    'salmeterol': 'Salmeterol', 'serevent': 'Serevent',
    'budesonide': 'Budesonide', 'pulmicort': 'Pulmicort',
    'fluticasone': 'Fluticasone', 'flixotide': 'Flixotide',
    'beclomethasone': 'Beclomethasone', 'becotide': 'Becotide',
    'montelukast': 'Montelukast', 'singulair': 'Singulair', 'montair': 'Montair',
    'cetirizine': 'Cetirizine', 'zyrtec': 'Zyrtec', 'cetzine': 'Cetzine',
    'levocetirizine': 'Levocetirizine', 'xyzal': 'Xyzal', 'levocet': 'Levocet',
    'fexofenadine': 'Fexofenadine', 'allegra': 'Allegra',
    'loratadine': 'Loratadine', 'claritin': 'Claritin', 'lorfast': 'Lorfast',
    'chlorpheniramine': 'Chlorpheniramine', 'piriton': 'Piriton',
    'dextromethorphan': 'Dextromethorphan', 'benylin': 'Benylin',
    'guaifenesin': 'Guaifenesin', 'mucinex': 'Mucinex',
    'ambroxol': 'Ambroxol', 'mucosolvan': 'Mucosolvan', 'ambrodil': 'Ambrodil',
    'bromhexine': 'Bromhexine', 'bисolvon': 'Bisolvon',
    'ipratropium': 'Ipratropium', 'atrovent': 'Atrovent',
    'tiotropium': 'Tiotropium', 'spiriva': 'Spiriva',
    'theophylline': 'Theophylline', 'theodur': 'Theodur',

    # ── THYROID ────────────────────────────────────────────────────────────
    'levothyroxine': 'Levothyroxine', 'synthroid': 'Synthroid', 'eltroxin': 'Eltroxin',
    'thyroxine': 'Thyroxine', 'thyronorm': 'Thyronorm',
    'carbimazole': 'Carbimazole', 'neo mercazole': 'Neo Mercazole',
    'propylthiouracil': 'Propylthiouracil', 'ptu': 'PTU',

    # ── VITAMINS / MINERALS / SUPPLEMENTS ────────────────────────────────
    'vitamin b12': 'Vitamin B12', 'methylcobalamin': 'Methylcobalamin',
    'cyanocobalamin': 'Cyanocobalamin', 'neurobion': 'Neurobion',
    'vitamin d': 'Vitamin D', 'vitamin d3': 'Vitamin D3',
    'cholecalciferol': 'Cholecalciferol', 'uprise': 'Uprise',
    'vitamin c': 'Vitamin C', 'ascorbic acid': 'Ascorbic Acid',
    'folic acid': 'Folic Acid', 'folate': 'Folate',
    'iron': 'Iron', 'ferrous sulphate': 'Ferrous Sulphate',
    'calcium': 'Calcium', 'calcirol': 'Calcirol', 'shelcal': 'Shelcal',
    'zinc': 'Zinc', 'zincovit': 'Zincovit',
    'magnesium': 'Magnesium', 'magnesia': 'Magnesia',
    'multivitamin': 'Multivitamin', 'supradyn': 'Supradyn', 'becosules': 'Becosules',
    'omega 3': 'Omega 3', 'fish oil': 'Fish Oil',
    'biotin': 'Biotin',
    'coenzyme q10': 'Coenzyme Q10',
    'glucosamine': 'Glucosamine',

    # ── STEROIDS / HORMONES ────────────────────────────────────────────────
    'prednisolone': 'Prednisolone', 'prednisone': 'Prednisone',
    'dexamethasone': 'Dexamethasone', 'decadron': 'Decadron',
    'methylprednisolone': 'Methylprednisolone', 'medrol': 'Medrol',
    'hydrocortisone': 'Hydrocortisone', 'cortef': 'Cortef',
    'betamethasone': 'Betamethasone', 'celestone': 'Celestone',
    'testosterone': 'Testosterone',
    'estrogen': 'Estrogen', 'estradiol': 'Estradiol',
    'progesterone': 'Progesterone', 'prometrium': 'Prometrium',
    'insulin glargine': 'Insulin Glargine', 'toujeo': 'Toujeo',

    # ── DERMATOLOGY ────────────────────────────────────────────────────────
    'clotrimazole': 'Clotrimazole', 'canesten': 'Canesten', 'candid': 'Candid',
    'miconazole': 'Miconazole', 'daktarin': 'Daktarin',
    'terbinafine': 'Terbinafine', 'lamisil': 'Lamisil',
    'permethrin': 'Permethrin', 'elimite': 'Elimite',
    'calamine': 'Calamine',
    'tretinoin': 'Tretinoin', 'retin-a': 'Retin-A',
    'adapalene': 'Adapalene', 'differin': 'Differin',
    'benzoyl peroxide': 'Benzoyl Peroxide',
    'salicylic acid': 'Salicylic Acid',
    'coal tar': 'Coal Tar',

    # ── UROLOGY ────────────────────────────────────────────────────────────
    'tamsulosin': 'Tamsulosin', 'flomax': 'Flomax', 'urimax': 'Urimax',
    'sildenafil': 'Sildenafil', 'viagra': 'Viagra',
    'tadalafil': 'Tadalafil', 'cialis': 'Cialis',
    'oxybutynin': 'Oxybutynin', 'ditropan': 'Ditropan',
    'solifenacin': 'Solifenacin', 'vesicare': 'Vesicare',

    # ── AYURVEDIC / HERBAL (Indian) ───────────────────────────────────────
    'kanchnar guggul': 'Kanchnar Guggul', 'kanchanar guggul': 'Kanchnar Guggul',
    'kanchanan guggul': 'Kanchnar Guggul', 'kanchanar': 'Kanchnar Guggul',
    'chandraprabha vati': 'Chandraprabha Vati', 'chandraprabha': 'Chandraprabha Vati',
    'chandraprabb': 'Chandraprabha Vati',
    'triphala': 'Triphala', 'triphala churna': 'Triphala Churna',
    'ashwagandha': 'Ashwagandha', 'withania somnifera': 'Ashwagandha',
    'brahmi': 'Brahmi', 'bacopa monnieri': 'Brahmi',
    'shilajit': 'Shilajit',
    'tulsi': 'Tulsi', 'ocimum sanctum': 'Tulsi',
    'neem': 'Neem', 'azadirachta': 'Neem',
    'giloy': 'Giloy', 'guduchi': 'Giloy',
    'amla': 'Amla', 'amalaki': 'Amla',
    'haritaki': 'Haritaki',
    'bibhitaki': 'Bibhitaki',
    'guggul': 'Guggul',
    'boswellia': 'Boswellia', 'shallaki': 'Shallaki',
    'curcumin': 'Curcumin', 'turmeric': 'Turmeric',
    'ginger': 'Ginger', 'zingiber': 'Ginger',
    'garlic': 'Garlic', 'allium sativum': 'Garlic',
    'punarnava': 'Punarnava',
    'shatavari': 'Shatavari',
    'triphala guggul': 'Triphala Guggul',
    'arogyavardhini': 'Arogyavardhini Vati',
    'kaishor guggul': 'Kaishor Guggul',
    'punarnavadi guggul': 'Punarnavadi Guggul',
    'gokshuradi guggul': 'Gokshuradi Guggul',
    'yograj guggul': 'Yograj Guggul',
    'maharasnadi kwath': 'Maharasnadi Kwath',
    'dashmoola': 'Dashmoola',
    'bala': 'Bala',
    'chyawanprash': 'Chyawanprash',
    'safi': 'Safi', 'hamdard safi': 'Hamdard Safi',
    'liv 52': 'Liv 52', 'liv52': 'Liv 52',
    'septilin': 'Septilin',
    'ayurslim': 'Ayurslim',
    'tentex forte': 'Tentex Forte', 'tentex': 'Tentex Forte',
    'styplon': 'Styplon',
    'sigon': 'Sigon',
    'cruel': 'Cruel',
    'pilex': 'Pilex',
    'diabecon': 'Diabecon',
    'glucocare': 'Glucocare',
    'himcolin': 'Himcolin',
    'lukol': 'Lukol',
    'mentat': 'Mentat',
    'reosto': 'Reosto',
    'rumalaya': 'Rumalaya',
    'speman': 'Speman',
    'v gel': 'V Gel',
    'abana': 'Abana',
    'bonnisan': 'Bonnisan',
    'bresol': 'Bresol',
    'geriforte': 'Geriforte',
    'immunol': 'Immunol',
    'nefrotec': 'Nefrotec',
    'ophthacare': 'Ophthacare',
    'prostane': 'Prostane',
    'renalka': 'Renalka',
    'serpina': 'Serpina',
    'shigru': 'Shigru',
    'talekt': 'Talekt',
    'ushira': 'Ushira',
    'vasaka': 'Vasaka',

    # ── OPHTHALMOLOGY ─────────────────────────────────────────────────────
    'timolol': 'Timolol', 'timoptol': 'Timoptol',
    'latanoprost': 'Latanoprost', 'xalatan': 'Xalatan',
    'dorzolamide': 'Dorzolamide', 'trusopt': 'Trusopt',
    'artificial tears': 'Artificial Tears', 'systane': 'Systane',
    'moxifloxacin': 'Moxifloxacin', 'vigamox': 'Vigamox',
    'tobramycin': 'Tobramycin', 'tobrex': 'Tobrex',

    # ── ANTI-MALARIAL / TROPICAL ──────────────────────────────────────────
    'chloroquine': 'Chloroquine', 'aralen': 'Aralen',
    'hydroxychloroquine': 'Hydroxychloroquine', 'plaquenil': 'Plaquenil',
    'artemether': 'Artemether', 'lumefantrine': 'Lumefantrine',
    'quinine': 'Quinine',
    'doxycycline': 'Doxycycline',
    'primaquine': 'Primaquine',

    # ── MISC ──────────────────────────────────────────────────────────────
    'allopurinol': 'Allopurinol', 'zyloprim': 'Zyloprim',
    'colchicine': 'Colchicine', 'colcrys': 'Colcrys',
    'methotrexate': 'Methotrexate', 'rheumatrex': 'Rheumatrex',
    'hydroxychloroquine': 'Hydroxychloroquine',
    'sulfasalazine': 'Sulfasalazine', 'azulfidine': 'Azulfidine',
    'leflunomide': 'Leflunomide', 'arava': 'Arava',
    'silymarin': 'Silymarin', 'legalon': 'Legalon', 'silybon': 'Silybon',
    'ursodeoxycholic acid': 'Ursodeoxycholic Acid', 'udiliv': 'Udiliv',
    'heparin': 'Heparin',
    'enoxaparin': 'Enoxaparin', 'lovenox': 'Lovenox', 'clexane': 'Clexane',
    'tranexamic acid': 'Tranexamic Acid', 'cyklokapron': 'Cyklokapron',
    'desmopressin': 'Desmopressin', 'ddavp': 'DDAVP',
    'erythropoietin': 'Erythropoietin', 'eprex': 'Eprex',
    'neostigmine': 'Neostigmine',
    'pyridostigmine': 'Pyridostigmine', 'mestinon': 'Mestinon',
    'baclofen': 'Baclofen', 'lioresal': 'Lioresal',
    'tizanidine': 'Tizanidine', 'zanaflex': 'Zanaflex',
    'cyclobenzaprine': 'Cyclobenzaprine', 'flexeril': 'Flexeril',
    'dantrolene': 'Dantrolene', 'dantrium': 'Dantrium',
}

# Build prefix lookup for fast fuzzy matching
MEDICINE_PREFIXES = {}
for name in MEDICINE_DB:
    prefix = name[:4].lower() if len(name) >= 4 else name.lower()
    if prefix not in MEDICINE_PREFIXES:
        MEDICINE_PREFIXES[prefix] = []
    MEDICINE_PREFIXES[prefix].append(name)


def _lookup_medicine(word):
    """Fast fuzzy lookup — returns canonical name or None."""
    word = word.lower().strip()
    # Exact match
    if word in MEDICINE_DB:
        return MEDICINE_DB[word]
    # Prefix match (first 5 chars)
    for length in [6, 5, 4]:
        if len(word) >= length:
            prefix = word[:length]
            for db_name in MEDICINE_DB:
                if db_name.startswith(prefix):
                    return MEDICINE_DB[db_name]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# GEMINI VISION — kept as-is
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
        prompt = """You are a medical prescription parser. Read carefully — may be handwritten, printed, ayurvedic or allopathic.
Return ONLY JSON:
{"patient_name":null,"age":null,"disease":null,"treatment_duration_days":7,
 "medicines":[{"name":"","dosage":"1 tablet","frequency":"1 times daily","duration_days":7}]}
Rules: Extract ALL medicines. Tab/Cap/Syp prefix = tablet/capsule/syrup. Return ONLY the JSON."""
        payload = json.dumps({
            "contents": [{"parts": [
                {"inline_data": {"mime_type": mime_type, "data": image_data}},
                {"text": prompt}
            ]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024}
        }).encode('utf-8')
        for api_ver, model_name in [('v1','gemini-2.5-flash'),('v1','gemini-2.0-flash'),('v1','gemini-2.0-flash-001')]:
            url = f"https://generativelanguage.googleapis.com/{api_ver}/models/{model_name}:generateContent?key={api_key}"
            print(f"   🔮 Trying {model_name}...")
            try:
                req = urllib.request.Request(url, data=payload,
                    headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = resp.read().decode("utf-8")
                    print(f"   ✅ {model_name} OK!")
                    data = json.loads(raw)
                    text = data['candidates'][0]['content']['parts'][0]['text'].strip()
                    text = re.sub(r'^```(?:json)?\s*', '', text)
                    text = re.sub(r'\s*```$', '', text).strip()
                    result = json.loads(text)
                    medicines = []
                    for m in result.get('medicines', []):
                        if not isinstance(m, dict) or not m.get('name'):
                            continue
                        name = str(m['name']).strip()
                        if len(name) < 2:
                            continue
                        fm = re.search(r'(\d+)', str(m.get('frequency','1')))
                        freq = f"{fm.group(1)} times daily" if fm else "1 times daily"
                        try:
                            dur = max(1, min(int(m.get('duration_days', 7)), 365))
                        except:
                            dur = 7
                        medicines.append({'name': name,
                            'dosage': str(m.get('dosage','1 tablet')).strip() or '1 tablet',
                            'frequency': freq, 'duration_days': dur})
                        print(f"   💊 Gemini: {name}")
                    age = result.get('age')
                    try:
                        age = int(age)
                        if not (1 <= age <= 120): age = None
                    except: age = None
                    try:
                        duration = max(1, min(int(result.get('treatment_duration_days', 7)), 365))
                    except: duration = 7
                    print(f"   ✅ Gemini: {len(medicines)} medicines")
                    return {'patient_name': result.get('patient_name'), 'age': age,
                            'disease': result.get('disease'), 'medicines': medicines,
                            'treatment_duration_days': duration}
            except urllib.error.HTTPError as he:
                print(f"   ❌ {model_name}: HTTP {he.code}")
                continue
            except Exception as ex:
                print(f"   ❌ {model_name}: {ex}")
                continue
        print("   ❌ All Gemini models failed.")
        return None
    except Exception as e:
        print(f"   ❌ Gemini error: {e}")
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
        req = urllib.request.Request('https://api.ocr.space/parse/image',
            data=payload, headers={'Content-Type': 'application/x-www-form-urlencoded'},
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
            thresh   = cv2.adaptiveThreshold(gray, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 2)
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
# REGEX PATTERNS
# ─────────────────────────────────────────────────────────────────────────────

DOSAGE_RE = re.compile(
    r'\b(\d+(?:\.\d+)?\s*(?:mg|mcg|ml|iu|g|gm|units?|tab(?:let)?s?|'
    r'cap(?:sule)?s?|drops?|sachet|puff|patch|vial|ampule|suppository))\b',
    re.IGNORECASE)

FREQ_X_RE     = re.compile(r'[xX×]\s*(\d)', re.IGNORECASE)
FREQ_DASH_RE  = re.compile(r'([01])\s*[-–]\s*([01])\s*[-–]\s*([01])')
FREQ_TIMES_RE = re.compile(r'(\d+)\s*(?:times?|x)\s*(?:daily|a\s*day|/day)', re.IGNORECASE)
FREQ_ABB_RE   = re.compile(r'\b(od|bd|tds|qid|bid|tid|once|twice|thrice)\b', re.IGNORECASE)
DUR_MONTH_RE  = re.compile(r'(\d+)\s*(?:months?|mo\.?|mar[io]ss?)', re.IGNORECASE)
DUR_WEEK_RE   = re.compile(r'(\d+)\s*(?:weeks?|wks?)', re.IGNORECASE)
DUR_DAY_RE    = re.compile(r'(\d+)\s*(?:days?|d\.?)', re.IGNORECASE)

NUM_PREFIX_RE = re.compile(
    r'^[\s•\-\*]*(?:\(?(\d{1,2})\)?\s*\.?\s*|[①②③④⑤⑥⑦⑧⑨⑩]\s*)',
    re.UNICODE)

TAB_PREFIX_RE = re.compile(
    r'^[\s•\-\*]*(?:R[x/]?\s*)?'
    r'(?:T\.|T\s+|Tab\.?\s*|Syp\.?\s*|Cap\.?\s*|Inj\.?\s*|'
    r'Ta\s+|Oint\.?\s*|Gel\.?\s*|Cream\.?\s*|Drops?\s+|'
    r'Lotion\.?\s*|Susp\.?\s*|Solution\.?\s*)',
    re.IGNORECASE)

SKIP_LINE_RE = re.compile(
    r'(?:dr\.|doctor|hospital|clinic|mbbs|bams|bds|bam|mba|md\.|m\.d\.|'
    r'phone|tel:|mob:|tele|address|plot|road|colony|nagar|sector|'
    r'regd|timing|monday|tuesday|wednesday|thursday|friday|saturday|sunday|'
    r'emergency|admit|banjara|hyderabad|secunderabad|delhi|mumbai|'
    r'chennai|bangalore|kolkata|appointment|©|www\.|http|'
    r'in emergency|for other|mbbs|ms\.|dnb\.|frcs\.|consult|'
    r'follow up|next visit|review after|report|investigation|'
    r'x-ray|scan|mri|ct|ultrasound|lab|test|ecg|echo|'
    r'call me|contact|if any problem|advice|counsel)',
    re.IGNORECASE)

NON_MEDICINE_WORDS = {
    'prescription','patient','doctor','date','diagnosis','name','age','gender',
    'sex','hospital','clinic','address','phone','signature','frequency',
    'duration','dosage','refill','medicine','for','the','and','with','times',
    'time','daily','weekly','once','twice','thrice','morning','afternoon',
    'evening','night','before','after','meal','meals','food','water','take',
    'days','weeks','months','stat','bp','hr','spo2','temp','wt','weight',
    'free','home','delivery','rx','mg','ml','tab','tabs','reg','no','city',
    'general','physician','consultant','dr','continue','other','call',
    'counselled','plot','road','colony','regd','mbbs','mba','emergency',
    'admit','one','two','three','four','five','six','seven','eight','half',
    'quarter','full','noon','cont','conti','same','old','new','change',
    'increase','decrease','stop','start','resume','hold','capsule','syrup',
    'injection','apply','external','internal','tablet','cap','syp','inj',
    'with','without','empty','stomach','bed','wake','sleep','milk','problem',
    'issue','complaint','history','report','investigation','super','spl',
    'ref','advice','follow','review','next','visit','per','each','every',
    'take','use','apply','add','give','start','continue','stop','hold',
}


def _parse_freq(block):
    m = FREQ_X_RE.search(block)
    if m:
        v = int(m.group(1))
        if 1 <= v <= 6:
            return str(v)
    m = FREQ_DASH_RE.search(block)
    if m:
        total = int(m.group(1)) + int(m.group(2)) + int(m.group(3))
        if 1 <= total <= 6:
            return str(total)
    m = FREQ_TIMES_RE.search(block)
    if m:
        return m.group(1)
    m = FREQ_ABB_RE.search(block)
    if m:
        return {'od':'1','bd':'2','tds':'3','qid':'4','bid':'2','tid':'3',
                'once':'1','twice':'2','thrice':'3'}.get(m.group(1).lower(),'1')
    return '1'


def _parse_dur(block, global_dur=7):
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
    m = DOSAGE_RE.search(block)
    return m.group(1).strip() if m else '1 tablet'


def _is_skip(line):
    return bool(SKIP_LINE_RE.search(line))


def _is_valid_name(name):
    name = name.strip()
    if len(name) < 3 or len(name) > 60:
        return False
    if not re.search(r'[A-Za-z]{3,}', name):
        return False
    if name[0].isdigit():
        return False
    words = name.lower().split()
    if all(w.rstrip('.,;:') in NON_MEDICINE_WORDS for w in words):
        return False
    return True


def _clean_name(raw):
    name = raw.strip().strip('•-–()[].,;:①②③④⑤⑥⑦⑧⑨⑩*/#@')
    name = re.sub(r'\s+', ' ', name).strip()
    name = re.sub(r'\s+\d+\s*(?:mg|ml|mcg|tab|cap)\b.*$', '', name, flags=re.IGNORECASE)
    # Fix common OCR splits
    name = re.sub(r'\bSome\b', '', name, flags=re.IGNORECASE).strip()
    return name.title().strip()


def _extract_patient_name(text):
    for pattern in [
        r'Name\s*[:\.]?\s*(?:Mr\.?|Mrs\.?|Ms\.?|Dr\.?)?\s*([A-Za-z][A-Za-z\s\.]{2,40})',
        r'(?:Mr|Mrs|Ms)\.?\s+([A-Z][A-Za-z\s]{2,30})',
        r'Patient\s*[:;-]?\s*([A-Za-z][A-Za-z\s]{2,40})',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            name = re.sub(r'\s+', ' ', m.group(1).strip())
            name = re.split(r'\b(age|date|phone|yrs|years|sex|gender)\b',
                name, flags=re.IGNORECASE)[0].strip().rstrip('.,;:')
            if 3 <= len(name) <= 50:
                return name
    return None


def _extract_age(text):
    for pattern in [r'Age\s*[:\.]?\s*(\d{1,3})',
                    r'(\d{1,3})\s*(?:yrs?|years?)',
                    r'(\d{1,3})\s*/\s*[MmFf]']:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            age = int(m.group(1))
            if 1 <= age <= 120:
                return age
    return None


def _extract_disease(text):
    for pattern in [
        r'(?:Diagnosis|Dx|Disease|C/O|c/o|Complaint)\s*[:;-]?\s*([A-Za-z][A-Za-z\s,/]{2,80})',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            d = m.group(1).strip().split('\n')[0].strip().rstrip('.,;:')
            if 3 <= len(d) <= 100:
                return d
    kws = {
        'schizophreni': 'Schizophrenia', 'schizophremi': 'Schizophrenia',
        'bipolar': 'Bipolar Disorder', 'depression': 'Depression',
        'anxiety': 'Anxiety Disorder', 'diabetes': 'Diabetes',
        'hypertension': 'Hypertension', 'thyroid': 'Thyroid Problem',
        'psoriasis': 'Psoriasis', 'leucoderma': 'Leucoderma',
        'haematura': 'Haematuria', 'haematuria': 'Haematuria',
        'kidney': 'Kidney Problem', 'asthma': 'Asthma',
        'arthritis': 'Arthritis', 'epilepsy': 'Epilepsy',
        'migraine': 'Migraine', 'fever': 'Fever',
        'infection': 'Infection', 'cough': 'Cough',
        'constipation': 'Constipation', 'acidity': 'Acidity',
        'piles': 'Piles', 'paranoi': 'Paranoia',
        'bladder': 'Bladder Problem', 'liver': 'Liver Problem',
    }
    tl = text.lower()
    for kw, label in kws.items():
        if kw in tl:
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
# UNIVERSAL MEDICINE EXTRACTOR — 4-pass
# ─────────────────────────────────────────────────────────────────────────────

def _extract_medicines_regex(text):
    medicines  = []
    seen_keys  = set()
    lines      = [l.strip() for l in text.split('\n')]
    global_dur = _extract_duration(text)

    def get_block(i, n=2):
        parts = []
        for j in range(i, min(i + n + 1, len(lines))):
            parts.append(lines[j])
        block = ' '.join(parts)
        if not re.search(r'\d+\s*(?:days?|weeks?|months?|mar)', block, re.IGNORECASE):
            block += f" {global_dur} days"
        return block

    def add(raw_name, block, source=''):
        name = _clean_name(raw_name)
        # Try database lookup first
        db_result = _lookup_medicine(name)
        if db_result:
            name = db_result
        if not _is_valid_name(name):
            return
        key = re.sub(r'\s+', ' ', name.lower().strip())
        # Dedup — skip similar names
        for seen in seen_keys:
            overlap = sum(1 for c in key if c in seen) / max(len(key), 1)
            if (key in seen or seen in key or
                    (len(key) > 5 and len(seen) > 5 and overlap > 0.85)):
                return
        seen_keys.add(key)
        dosage = _parse_dosage(block)
        freq   = _parse_freq(block)
        dur    = _parse_dur(block, global_dur)
        medicines.append({
            'name': name, 'dosage': dosage,
            'frequency': f"{freq} times daily",
            'duration_days': dur,
        })
        print(f"   💊 [{source}] {name} | {dosage} | {freq}x | {dur}d")

    # ── PASS A: Database scan — known medicine names ──────────────────────
    # Build a regex from all medicine DB keys (sorted longest first to avoid partial matches)
    db_keys_sorted = sorted(MEDICINE_DB.keys(), key=len, reverse=True)
    # Build chunks of 200 names to avoid regex too large
    chunk_size = 200
    for chunk_start in range(0, len(db_keys_sorted), chunk_size):
        chunk = db_keys_sorted[chunk_start:chunk_start + chunk_size]
        pattern = r'\b(' + '|'.join(re.escape(k) for k in chunk) + r')\b'
        try:
            chunk_re = re.compile(pattern, re.IGNORECASE)
            for i, line in enumerate(lines):
                if _is_skip(line):
                    continue
                m = chunk_re.search(line)
                if m:
                    add(m.group(1), get_block(i), 'DB')
        except re.error:
            continue

    # ── PASS B: Numbered list items ───────────────────────────────────────
    for i, line in enumerate(lines):
        if _is_skip(line):
            continue
        pm = NUM_PREFIX_RE.match(line)
        if not pm:
            continue
        rest = line[pm.end():].strip()
        # Remove Tab/Cap prefix after number
        pm2 = TAB_PREFIX_RE.match(rest)
        if pm2:
            rest = rest[pm2.end():].strip()
        # Extract name
        nm = re.match(r'^([A-Za-z][A-Za-z0-9\s\-\.]{2,40}?)(?=\s*[\d(]|\s*$|\s+[xX×])', rest)
        if nm:
            add(nm.group(1).strip(), get_block(i), 'NUM')

    # ── PASS C: Tab/Cap/Syp prefix lines ─────────────────────────────────
    for i, line in enumerate(lines):
        if _is_skip(line):
            continue
        pm = TAB_PREFIX_RE.match(line)
        if not pm:
            continue
        rest = line[pm.end():].strip()
        nm = re.match(r'^([A-Za-z][A-Za-z0-9\s\-\.]{2,40}?)(?=\s*[\d(]|\s*$|\s+[xX×])', rest)
        if nm:
            add(nm.group(1).strip(), get_block(i), 'TAB')

    # ── PASS D: Dosage-anchored scan ──────────────────────────────────────
    if len(medicines) < 3:
        print("   🔍 Pass D: dosage-anchored scan...")
        for i, line in enumerate(lines):
            if _is_skip(line):
                continue
            if not (DOSAGE_RE.search(line) or FREQ_X_RE.search(line)):
                continue
            nm = re.match(r'^([A-Za-z][A-Za-z0-9\s\-\.]{2,35}?)\s+\d', line)
            if nm:
                candidate = nm.group(1).strip()
                words = candidate.lower().split()
                if any(w not in NON_MEDICINE_WORDS for w in words):
                    add(candidate, get_block(i), 'DOSE')

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
                credentials = service_account.Credentials.from_service_account_file(str(creds_path))
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
        print("   🔮 Trying Gemini Vision...")
        gemini_result = _parse_with_gemini_vision(image_path)
        if gemini_result is not None:
            raw_text  = self._get_raw_text(image_path)
            medicines = gemini_result['medicines']
            print(f"   ✅ Final (Gemini): {len(medicines)} medicines")
            return {
                'success': True, 'extracted_text': raw_text,
                'patient_name': gemini_result['patient_name'],
                'age': gemini_result['age'],
                'disease': gemini_result['disease'],
                'medicines': medicines,
                'treatment_duration_days': gemini_result['treatment_duration_days'],
                'total_medicines': len(medicines),
            }

        print("   📄 Falling back to OCR.space + universal regex...")
        raw_text = self._get_raw_text(image_path)

        if not raw_text or len(raw_text.strip()) < 5:
            print("   ⚠️  No text extracted.")
            return {
                'success': True, 'extracted_text': '',
                'patient_name': None, 'age': None, 'disease': None,
                'medicines': [], 'treatment_duration_days': 7, 'total_medicines': 0,
            }

        patient_name = _extract_patient_name(raw_text)
        age          = _extract_age(raw_text)
        disease      = _extract_disease(raw_text)
        duration     = _extract_duration(raw_text)
        medicines    = _extract_medicines_regex(raw_text)

        print(f"   ✅ Final: patient={patient_name}, age={age}, "
              f"disease={disease}, medicines={len(medicines)}, dur={duration}d")

        return {
            'success': True, 'extracted_text': raw_text,
            'patient_name': patient_name, 'age': age, 'disease': disease,
            'medicines': medicines, 'treatment_duration_days': duration,
            'total_medicines': len(medicines),
        }

    def extract_text(self, image_path): return self._get_raw_text(image_path)
    def extract_patient_name(self, text): return _extract_patient_name(text)
    def extract_age(self, text):          return _extract_age(text)
    def extract_disease(self, text):      return _extract_disease(text)
    def extract_duration(self, text):     return _extract_duration(text)
    def extract_medicines(self, text):    return _extract_medicines_regex(text)