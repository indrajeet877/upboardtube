#!/usr/bin/env python3
"""Build UPBoardTube's 50-chapter UPMSP (UP Board Class 12 & Class 10) YouTube index (data/videos.json).

Pure Python 3 standard library. Run from anywhere:

    python3 scripts/build.py --self-test
    python3 scripts/build.py
    python3 scripts/build.py --fresh

Queries YouTube's public web search endpoint across all 50 canonical UPMSP (उत्तर प्रदेश
माध्यमिक शिक्षा परिषद् — प्रयागराज) Class 12 Intermediate & Class 10 High School chapters
across 6 subject groups using YouTube's native Playlist filter (sp=EgIQAw==) and
Long-Form Lecture filter (sp=EgIYAg==), plus UP Board educator/channel sweeps.
Enforces a strict Verified UP Board & Hindi Medium Board Channel allowlist, bilingual
Devanagari + English chapter matching, Class 10 vs Class 12 isolation, clickbait/rumour
rejection, and 100% pure YouTube audience trend ranking (zero institute bias).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "cache"
OUT_PATH = ROOT / "data" / "videos.json"

INNERTUBE_SEARCH = "https://www.youtube.com/youtubei/v1/search"
SP_PLAYLIST_ONLY = "EgIQAw=="  # YouTube native Type: Playlist protobuf filter
SP_LONG_VIDEOS = "EgIYAg=="    # YouTube native Duration: >20 minutes protobuf filter

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _ssl_context() -> ssl.SSLContext:
    for cafile in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if os.path.exists(cafile):
            return ssl.create_default_context(cafile=cafile)
    return ssl.create_default_context()


SSL_CTX = _ssl_context()
_lock = threading.Lock()
STATS = {"requests": 0, "cached": 0}

# ---------------------------------------------------------------------------
# Complete 50-Chapter Canonical UPMSP (UP Board Class 12 & Class 10) Syllabus
# Tuple:
#   (ch_no, subject, unit, class_level, weightage, syllabus_scope, chapter_name,
#    match_regex, pl_queries, vid_queries)
# IMPORTANT: Python \b fails after Devanagari vowel signs / combining marks
# (ा, ि, ी, ं, ँ, ः, ्). Never wrap Devanagari words in \b; use \b only on ASCII!
# ---------------------------------------------------------------------------
SYLLABUS: list[tuple[int, str, str, str, str, str, str, str, tuple[str, ...], tuple[str, ...]]] = [
    # ================= 1. Class 12 गणित (Maths) — 10 Chapters =================
    (
        1,
        "Class 12 गणित (Maths)",
        "संबंध तथा फलन (Relations & Functions)",
        "Class 12",
        "High",
        "UPMSP Class 12",
        "संबंध एवं फलन / Relations & Functions",
        r"(?:संबंध एवं फलन|संबंध तथा फलन|सम्बद्ध एवं फलन|संबंध और फलन|\b(?:relations?\s*(?:and|&|evam|aur|tatha)\s*functions?|sambandh\s*(?:evam|aur|tatha)\s*(?:phalan|falan))\b)",
        (
            "संबंध एवं फलन Class 12 Maths UP Board",
            "Relations and Functions Class 12 Maths Hindi Medium",
        ),
        (
            "संबंध एवं फलन Class 12 One Shot UP Board",
            "Relations and Functions Class 12 UP Board One Shot",
            "Relations and Functions Class 12 Hindi Medium One Shot",
            "संबंध एवं फलन Class 12 Maths Hindi Medium",
        ),
    ),
    (
        2,
        "Class 12 गणित (Maths)",
        "संबंध तथा फलन (Relations & Functions)",
        "Class 12",
        "Medium",
        "UPMSP Class 12",
        "प्रतिलोम त्रिकोणमितीय फलन / Inverse Trig",
        r"(?:प्रतिलोम त्रिकोणमितीय|प्रतिलोम त्रिकोणमिति|\b(?:inverse\s+trigonometr\w*|pratilom\s+trikonmiti\w*|\bitf\b)\b)",
        (
            "प्रतिलोम त्रिकोणमितीय फलन Class 12 UP Board",
            "Inverse Trigonometric Functions Class 12 Hindi Medium",
        ),
        (
            "प्रतिलोम त्रिकोणमितीय फलन Class 12 One Shot",
            "Inverse Trigonometric Functions Class 12 UP Board One Shot",
            "Inverse Trigonometric Functions Class 12 Hindi Medium One Shot",
            "Pratilom Trikonmitiya Phalan Class 12 Maths UP Board",
        ),
    ),
    (
        3,
        "Class 12 गणित (Maths)",
        "बीजगणित (Algebra)",
        "Class 12",
        "High",
        "UPMSP Class 12",
        "आव्यूह / Matrices",
        r"(?:आव्यूह|\b(?:matri(?:x|ces)|aavyuh|avyuh)\b)",
        (
            "आव्यूह Class 12 Maths UP Board",
            "Matrices Class 12 Maths Hindi Medium",
        ),
        (
            "आव्यूह Class 12 Maths One Shot UP Board",
            "Matrices Class 12 UP Board One Shot",
            "Matrices Class 12 Maths Hindi Medium One Shot",
            "Aavyuh Class 12 Maths Hindi Medium",
        ),
    ),
    (
        4,
        "Class 12 गणित (Maths)",
        "बीजगणित (Algebra)",
        "Class 12",
        "High",
        "UPMSP Class 12",
        "सारणिक / Determinants",
        r"(?:सारणिक|\b(?:determinants?|saranik|sarnik)\b)",
        (
            "सारणिक Class 12 Maths UP Board",
            "Determinants Class 12 Maths Hindi Medium",
        ),
        (
            "सारणिक Class 12 Maths One Shot UP Board",
            "Determinants Class 12 UP Board One Shot",
            "Determinants Class 12 Maths Hindi Medium One Shot",
            "Saranik Class 12 Maths Hindi Medium",
        ),
    ),
    (
        5,
        "Class 12 गणित (Maths)",
        "कलन (Calculus)",
        "Class 12",
        "Very High",
        "UPMSP Class 12",
        "सांतत्य तथा अवकलनीयता / Continuity & Differentiability",
        r"(?:सांतत्य|संततता|सातत्य|अवकलनीयता|अवकलन|\b(?:continuity|differentiability|differentiation|santatya|avkalan|avkalniyata)\b)",
        (
            "सांतत्य तथा अवकलनीयता Class 12 UP Board",
            "Continuity and Differentiability Class 12 Hindi Medium",
        ),
        (
            "सांतत्य तथा अवकलनीयता Class 12 One Shot",
            "Continuity and Differentiability Class 12 UP Board One Shot",
            "Continuity and Differentiability Class 12 Hindi Medium One Shot",
            "अवकलन Class 12 Maths UP Board One Shot",
        ),
    ),
    (
        6,
        "Class 12 गणित (Maths)",
        "कलन (Calculus)",
        "Class 12",
        "Very High",
        "UPMSP Class 12",
        "अवकलज के अनुप्रयोग / Application of Derivatives",
        r"(?:अवकलज के अनुप्रयोग|अवकलजों के अनुप्रयोग|उच्चिष्ठ|निम्निष्ठ|\b(?:applications?\s+of\s+derivatives?|\baod\b|avkalaj\s+ke\s+anuprayog|maxima\s*(?:and|&)?\s*minima)\b)",
        (
            "अवकलज के अनुप्रयोग Class 12 UP Board",
            "Application of Derivatives Class 12 Hindi Medium",
        ),
        (
            "अवकलज के अनुप्रयोग Class 12 One Shot UP Board",
            "Application of Derivatives Class 12 UP Board One Shot",
            "Application of Derivatives Class 12 Hindi Medium One Shot",
            "Avkalaj ke Anuprayog Class 12 Maths",
        ),
    ),
    (
        7,
        "Class 12 गणित (Maths)",
        "कलन (Calculus)",
        "Class 12",
        "Very High",
        "UPMSP Class 12",
        "समाकलन / Integrals",
        r"(?:समाकलन|निश्चित समाकलन|अनिश्चित समाकलन|\b(?:integrals?|integration|definite\s+integration|indefinite\s+integration|samakalan)\b)",
        (
            "समाकलन Class 12 Maths UP Board",
            "Integrals Class 12 Maths Hindi Medium",
        ),
        (
            "समाकलन Class 12 Maths One Shot UP Board",
            "Integrals Class 12 UP Board One Shot",
            "Integration Class 12 Maths Hindi Medium One Shot",
            "Samakalan Class 12 Maths UP Board",
        ),
    ),
    (
        8,
        "Class 12 गणित (Maths)",
        "कलन (Calculus)",
        "Class 12",
        "Very High",
        "UPMSP Class 12",
        "समाकलनों के अनुप्रयोग व अवकल समीकरण / Differential Equations & Area",
        r"(?:समाकलनों के अनुप्रयोग|समाकलन के अनुप्रयोग|अवकल समीकरण|वक्रों से घिरा|\b(?:applications?\s+of\s+integrals?|area\s+under\s+curves?|differential\s+equations?|avkal\s+samikaran|samakalan\w*\s+ke\s+anuprayog)\b)",
        (
            "अवकल समीकरण Class 12 Maths UP Board",
            "समाकलनों के अनुप्रयोग Class 12 Maths Hindi Medium",
        ),
        (
            "अवकल समीकरण Class 12 One Shot UP Board",
            "समाकलनों के अनुप्रयोग Class 12 One Shot UP Board",
            "Differential Equations Class 12 Hindi Medium One Shot",
            "Application of Integrals Class 12 Hindi Medium One Shot",
        ),
    ),
    (
        9,
        "Class 12 गणित (Maths)",
        "सदिश तथा त्रि-विमीय ज्यामिति (Vectors & 3D)",
        "Class 12",
        "Very High",
        "UPMSP Class 12",
        "सदिश बीजगणित व त्रि-विमीय ज्यामिति / Vectors & 3D",
        r"(?:सदिश बीजगणित|सदिश|त्रि-विमीय ज्यामिति|त्रिविमीय ज्यामिति|त्रि-विमीय|\b(?:vector\s+algebra|vectors?\b|3\s*-?\s*d\s+geometry|three\s+dimensional\s+geometry|sadish\s+bijganit|trivimiya\s+jyamiti)\b)",
        (
            "सदिश बीजगणित Class 12 Maths UP Board",
            "त्रिविमीय ज्यामिति Class 12 Maths Hindi Medium",
        ),
        (
            "सदिश बीजगणित Class 12 One Shot UP Board",
            "त्रि-विमीय ज्यामिति Class 12 One Shot UP Board",
            "Vector Algebra Class 12 Hindi Medium One Shot",
            "3D Geometry Class 12 Maths Hindi Medium One Shot",
        ),
    ),
    (
        10,
        "Class 12 गणित (Maths)",
        "रैखिक प्रोग्रामन एवं प्रायिकता (LPP & Probability)",
        "Class 12",
        "High",
        "UPMSP Class 12",
        "रैखिक प्रोग्रामन एवं प्रायिकता / Linear Programming & Probability",
        r"(?:रैखिक प्रोग्रामन|प्रायिकता|बेज प्रमेय|\b(?:linear\s+programming|\blpp\b|probability|bayes\s+theorem|raikhik\s+programan|prayikta)\b)",
        (
            "प्रायिकता Class 12 Maths UP Board",
            "रैखिक प्रोग्रामन Class 12 Maths Hindi Medium",
        ),
        (
            "प्रायिकता Class 12 Maths One Shot UP Board",
            "रैखिक प्रोग्रामन Class 12 Maths One Shot",
            "Probability Class 12 Maths Hindi Medium One Shot",
            "Linear Programming Class 12 Hindi Medium One Shot",
        ),
    ),

    # =============== 2. Class 12 भौतिकी (Physics) — 10 Chapters ===============
    (
        11,
        "Class 12 भौतिकी (Physics)",
        "स्थिरवैद्युतिकी (Electrostatics)",
        "Class 12",
        "Very High",
        "UPMSP Class 12",
        "वैद्युत आवेश तथा क्षेत्र / Electric Charges & Fields",
        r"(?:वैद्युत आवेश|विद्युत आवेश|आवेश तथा क्षेत्र|गॉस की प्रमेय|गाउस की प्रमेय|कूलाम का नियम|\b(?:electric\s+charges?\s*(?:and|&)?\s*fields?|gauss'?s?\s+law|coulomb'?s?\s+law|vaidyut\s+aavesh|vidyut\s+avesh|vaidyut\s+avesh)\b)",
        (
            "वैद्युत आवेश तथा क्षेत्र Class 12 Physics UP Board",
            "Electric Charges and Fields Class 12 Hindi Medium",
        ),
        (
            "वैद्युत आवेश तथा क्षेत्र Class 12 One Shot",
            "Electric Charges and Fields Class 12 UP Board One Shot",
            "Electric Charges and Fields Class 12 Hindi Medium One Shot",
            "Vaidyut Aavesh tatha Kshetra Class 12 Physics",
        ),
    ),
    (
        12,
        "Class 12 भौतिकी (Physics)",
        "स्थिरवैद्युतिकी (Electrostatics)",
        "Class 12",
        "High",
        "UPMSP Class 12",
        "स्थिरवैद्युत विभव तथा धारिता / Potential & Capacitance",
        r"(?:स्थिरवैद्युत विभव|स्थिर वैद्युत विभव|वैद्युत विभव|विद्युत विभव|धारिता|संधारित्र|\b(?:electrostatic\s+potential|electric\s+potential|capacitance|capacitors?|vibhav\s+tatha\s+dharita|sandharitra)\b)",
        (
            "स्थिरवैद्युत विभव तथा धारिता Class 12 UP Board",
            "Electrostatic Potential and Capacitance Class 12 Hindi Medium",
        ),
        (
            "स्थिरवैद्युत विभव तथा धारिता Class 12 One Shot",
            "Electrostatic Potential and Capacitance Class 12 UP Board One Shot",
            "Potential and Capacitance Class 12 Hindi Medium One Shot",
            "Vaidyut Vibhav tatha Dharita Class 12 Physics",
        ),
    ),
    (
        13,
        "Class 12 भौतिकी (Physics)",
        "धारा विद्युत (Current Electricity)",
        "Class 12",
        "Very High",
        "UPMSP Class 12",
        "विद्युत धारा / Current Electricity",
        r"(?:विद्युत धारा|वैद्युत धारा|किरचॉफ|व्हीटस्टोन|विभवमापी|\b(?:current\s+electricity|kirchhoff|wheatstone|meter\s+bridge|vidyut\s+dhara|vaidyut\s+dhara)\b)",
        (
            "विद्युत धारा Class 12 Physics UP Board",
            "Current Electricity Class 12 Physics Hindi Medium",
        ),
        (
            "विद्युत धारा Class 12 Physics One Shot",
            "Current Electricity Class 12 UP Board One Shot",
            "Current Electricity Class 12 Hindi Medium One Shot",
            "Vidyut Dhara Class 12 Physics UP Board",
        ),
    ),
    (
        14,
        "Class 12 भौतिकी (Physics)",
        "धारा का चुंबकीय प्रभाव (Magnetism)",
        "Class 12",
        "Very High",
        "UPMSP Class 12",
        "गतिमान आवेश और चुंबकत्व / Moving Charges & Magnetism",
        r"(?:गतिमान आवेश|चुंबकीय प्रभाव|चुम्बकीय प्रभाव|बायो-सेवर्ट|एम्पियर का परिपथीय|\b(?:moving\s+charges?\s*(?:and|&)?\s*magnetism|magnetic\s+effects?\s+of\s+current|biot[- ]savart|gatiman\s+aavesh|gatiman\s+avesh)\b)",
        (
            "गतिमान आवेश और चुंबकत्व Class 12 UP Board",
            "Moving Charges and Magnetism Class 12 Hindi Medium",
        ),
        (
            "गतिमान आवेश और चुंबकत्व Class 12 One Shot",
            "Moving Charges and Magnetism Class 12 UP Board One Shot",
            "Moving Charges and Magnetism Class 12 Hindi Medium One Shot",
            "Gatiman Aavesh aur Chumbakatva Class 12 Physics",
        ),
    ),
    (
        15,
        "Class 12 भौतिकी (Physics)",
        "चुंबकत्व तथा प्रेरण (Magnetism & EMI)",
        "Class 12",
        "High",
        "UPMSP Class 12",
        "चुंबकत्व एवं वैद्युतचुंबकीय प्रेरण / Magnetism & EMI",
        r"(?:चुंबकत्व एवं द्रव्य|चुम्बकत्व एवं द्रव्य|वैद्युतचुंबकीय प्रेरण|वैद्युत चुंबकीय प्रेरण|विद्युत चुम्बकीय प्रेरण|विद्युतचुंबकीय प्रेरण|फैराडे|लेंज का नियम|स्वप्रेरण|अन्योन्य प्रेरण|\b(?:magnetism\s*(?:and|&)\s*matter|electromagnetic\s+induction|\bemi\b|faraday'?s?\s+law|chumbakatva\s+evam\s+dravya|(?:vaidyut|vidyut)\s*chumbakiya\s+preran)\b)",
        (
            "वैद्युतचुंबकीय प्रेरण Class 12 Physics UP Board",
            "चुंबकत्व एवं द्रव्य Class 12 Physics Hindi Medium",
        ),
        (
            "वैद्युतचुंबकीय प्रेरण Class 12 One Shot",
            "चुंबकत्व एवं द्रव्य Class 12 One Shot",
            "Electromagnetic Induction Class 12 Hindi Medium One Shot",
            "Magnetism and Matter Class 12 Hindi Medium One Shot",
        ),
    ),
    (
        16,
        "Class 12 भौतिकी (Physics)",
        "प्रत्यावर्ती धारा व तरंगें (AC & EM Waves)",
        "Class 12",
        "High",
        "UPMSP Class 12",
        "प्रत्यावर्ती धारा एवं वैद्युतचुंबकीय तरंगें / AC & EM Waves",
        r"(?:प्रत्यावर्ती धारा|ट्रांसफार्मर|वैद्युतचुंबकीय तरंग|वैद्युत चुंबकीय तरंग|विद्युत चुम्बकीय तरंग|विद्युतचुंबकीय तरंग|\b(?:alternating\s+current|electromagnetic\s+waves?|\bem\s+waves?\b|transformer|lcr\s+circuit|pratyavarti\s+dhara|(?:vaidyut|vidyut)\s*chumbakiya\s+tarang\w*)\b)",
        (
            "प्रत्यावर्ती धारा Class 12 Physics UP Board",
            "Alternating Current Class 12 Physics Hindi Medium",
        ),
        (
            "प्रत्यावर्ती धारा Class 12 One Shot UP Board",
            "वैद्युतचुंबकीय तरंगें Class 12 One Shot",
            "Alternating Current Class 12 Hindi Medium One Shot",
            "Electromagnetic Waves Class 12 Hindi Medium One Shot",
        ),
    ),
    (
        17,
        "Class 12 भौतिकी (Physics)",
        "प्रकाशिकी (Optics)",
        "Class 12",
        "Very High",
        "UPMSP Class 12",
        "किरण प्रकाशिकी एवं प्रकाशिक यंत्र / Ray Optics",
        r"(?:किरण प्रकाशिकी|प्रकाशिक यंत्र|सूक्ष्मदर्शी|दूरदर्शी|गोलीय पृष्ठ से अपवर्तन|\b(?:ray\s+optics|geometrical\s+optics|optical\s+instruments?|kiran\s+prakashiki|prakashik\s+yantra)\b)",
        (
            "किरण प्रकाशिकी एवं प्रकाशिक यंत्र Class 12 UP Board",
            "Ray Optics Class 12 Physics Hindi Medium",
        ),
        (
            "किरण प्रकाशिकी एवं प्रकाशिक यंत्र Class 12 One Shot",
            "Ray Optics Class 12 UP Board One Shot",
            "Ray Optics and Optical Instruments Class 12 Hindi Medium One Shot",
            "Kiran Prakashiki Class 12 Physics One Shot",
        ),
    ),
    (
        18,
        "Class 12 भौतिकी (Physics)",
        "प्रकाशिकी (Optics)",
        "Class 12",
        "High",
        "UPMSP Class 12",
        "तरंग प्रकाशिकी / Wave Optics",
        r"(?:तरंग प्रकाशिकी|हाइगेंस|व्यतिकरण|विवर्तन|\b(?:wave\s+optics|huygens|interference|diffraction|\bydse\b|tarang\s+prakashiki)\b)",
        (
            "तरंग प्रकाशिकी Class 12 Physics UP Board",
            "Wave Optics Class 12 Physics Hindi Medium",
        ),
        (
            "तरंग प्रकाशिकी Class 12 One Shot UP Board",
            "Wave Optics Class 12 UP Board One Shot",
            "Wave Optics Class 12 Hindi Medium One Shot",
            "Tarang Prakashiki Class 12 Physics One Shot",
        ),
    ),
    (
        19,
        "Class 12 भौतिकी (Physics)",
        "आधुनिक भौतिकी (Modern Physics)",
        "Class 12",
        "High",
        "UPMSP Class 12",
        "विकिरण तथा द्रव्य की द्वैत प्रकृति व परमाणु / Dual Nature & Atoms",
        r"(?:द्वैत प्रकृति|प्रकाश विद्युत प्रभाव|प्रकाश-विद्युत|विकिरण तथा द्रव्य|परमाणु|बोर का परमाणु|हाइड्रोजन स्पेक्ट्रम|\b(?:dual\s+nature|photoelectric\s+effect|de\s+broglie|atoms?\b|bohr\s+model|vikiran\s+tatha\s+dravya|dwait\s+prakriti|parmanu)\b)",
        (
            "विकिरण तथा द्रव्य की द्वैत प्रकृति Class 12 UP Board",
            "परमाणु Class 12 Physics Hindi Medium",
        ),
        (
            "विकिरण तथा द्रव्य की द्वैत प्रकृति Class 12 One Shot",
            "परमाणु Class 12 Physics One Shot Hindi Medium",
            "Dual Nature of Radiation and Matter Class 12 Hindi Medium One Shot",
            "Atoms Class 12 Physics Hindi Medium One Shot",
        ),
    ),
    (
        20,
        "Class 12 भौतिकी (Physics)",
        "नाभिक व अर्धचालक (Nuclei & Semiconductors)",
        "Class 12",
        "Very High",
        "UPMSP Class 12",
        "नाभिक एवं अर्धचालक इलेक्ट्रॉनिकी / Nuclei & Semiconductors",
        r"(?:नाभिक|अर्धचालक|अर्द्धचालक|पी-एन संधि|डायोड|लॉजिक गेट|दिष्टकारी|\b(?:nuclei\b|nuclear\s+physics|semiconductors?|p-?n\s+junction|diodes?|logic\s+gates?|rectifier|nabhik|ardhchalak)\b)",
        (
            "अर्धचालक इलेक्ट्रॉनिकी Class 12 Physics UP Board",
            "नाभिक Class 12 Physics Hindi Medium",
        ),
        (
            "अर्धचालक इलेक्ट्रॉनिकी Class 12 One Shot",
            "नाभिक Class 12 Physics One Shot UP Board",
            "Semiconductor Electronics Class 12 Hindi Medium One Shot",
            "Nuclei Class 12 Physics Hindi Medium One Shot",
        ),
    ),

    # =============== 3. Class 12 रसायन (Chemistry) — 10 Chapters ===============
    (
        21,
        "Class 12 रसायन (Chemistry)",
        "भौतिक रसायन (Physical Chemistry)",
        "Class 12",
        "Very High",
        "UPMSP Class 12",
        "विलयन / Solutions",
        r"(?:विलयन|अणुसंख्य गुणधर्म|राउल्ट का नियम|मोलरता|परासरण दाब|\b(?:solutions?\b|liquid\s+solutions?|colligative\s+properties|raoult'?s?\s+law|vilayan|vilyan)\b)",
        (
            "विलयन Class 12 Chemistry UP Board",
            "Solutions Class 12 Chemistry Hindi Medium",
        ),
        (
            "विलयन Class 12 Chemistry One Shot",
            "Solutions Class 12 Chemistry UP Board One Shot",
            "Solutions Class 12 Chemistry Hindi Medium One Shot",
            "Vilayan Class 12 Chemistry Hindi Medium",
        ),
    ),
    (
        22,
        "Class 12 रसायन (Chemistry)",
        "भौतिक रसायन (Physical Chemistry)",
        "Class 12",
        "Very High",
        "UPMSP Class 12",
        "वैद्युत रसायन / Electrochemistry",
        r"(?:वैद्युत रसायन|विद्युत रसायन|नर्नस्ट समीकरण|कोलराउश|फैराडे के विद्युत अपघटन|\b(?:electrochemistry|nernst\s+equation|kohlrausch|galvanic|vaidyut\s+rasayan|vidyut\s+rasayan)\b)",
        (
            "वैद्युत रसायन Class 12 Chemistry UP Board",
            "Electrochemistry Class 12 Chemistry Hindi Medium",
        ),
        (
            "वैद्युत रसायन Class 12 Chemistry One Shot",
            "Electrochemistry Class 12 UP Board One Shot",
            "Electrochemistry Class 12 Hindi Medium One Shot",
            "Vaidyut Rasayan Class 12 Chemistry",
        ),
    ),
    (
        23,
        "Class 12 रसायन (Chemistry)",
        "भौतिक रसायन (Physical Chemistry)",
        "Class 12",
        "High",
        "UPMSP Class 12",
        "रासायनिक बलगतिकी / Chemical Kinetics",
        r"(?:रासायनिक बलगतिकी|बलगतिकी|प्रथम कोटि की अभिक्रिया|अभिक्रिया की कोटि|आर्हीनियस|\b(?:chemical\s+kinetics|rasayanik\s+balgatiki|first\s+order\s+reaction|arrhenius)\b)",
        (
            "रासायनिक बलगतिकी Class 12 Chemistry UP Board",
            "Chemical Kinetics Class 12 Chemistry Hindi Medium",
        ),
        (
            "रासायनिक बलगतिकी Class 12 One Shot",
            "Chemical Kinetics Class 12 UP Board One Shot",
            "Chemical Kinetics Class 12 Hindi Medium One Shot",
            "Rasayanik Balgatiki Class 12 Chemistry",
        ),
    ),
    (
        24,
        "Class 12 रसायन (Chemistry)",
        "अकार्बनिक रसायन (Inorganic Chemistry)",
        "Class 12",
        "High",
        "UPMSP Class 12",
        "d एवं f ब्लॉक के तत्व / d & f Block",
        r"(?:d\s*एवं\s*f|d\s*तथा\s*f|d\s*और\s*f|डी\s*एवं\s*एफ|d-?ब्लॉक|संक्रमण तत्व|लैंथेनाइड|लैन्थेनाइड|\b(?:d\s*(?:and|&|evam|aur|tatha)\s*f\s*[- ]?block|d[- ]block\s+elements?|transition\s+elements?|lanthanoids?|lanthanides?)\b)",
        (
            "d एवं f ब्लॉक के तत्व Class 12 UP Board",
            "d and f Block Elements Class 12 Hindi Medium",
        ),
        (
            "d एवं f ब्लॉक के तत्व Class 12 One Shot",
            "d and f Block Elements Class 12 UP Board One Shot",
            "d and f Block Class 12 Chemistry Hindi Medium One Shot",
            "d tatha f Block ke Tatva Class 12 Chemistry",
        ),
    ),
    (
        25,
        "Class 12 रसायन (Chemistry)",
        "अकार्बनिक रसायन (Inorganic Chemistry)",
        "Class 12",
        "High",
        "UPMSP Class 12",
        "उपसहसंयोजन यौगिक / Coordination Compounds",
        r"(?:उपसहसंयोजन|उपसहसंयोजक|वर्नर का सिद्धांत|क्रिस्टल क्षेत्र|\b(?:coordination\s+compounds?|upsahsanyojan|upsahsanyojak|crystal\s+field\s+theory|\bcft\b)\b)",
        (
            "उपसहसंयोजन यौगिक Class 12 UP Board",
            "Coordination Compounds Class 12 Hindi Medium",
        ),
        (
            "उपसहसंयोजन यौगिक Class 12 One Shot",
            "Coordination Compounds Class 12 UP Board One Shot",
            "Coordination Compounds Class 12 Hindi Medium One Shot",
            "Upsahsanyojan Yaugik Class 12 Chemistry",
        ),
    ),
    (
        26,
        "Class 12 रसायन (Chemistry)",
        "कार्बनिक रसायन (Organic Chemistry)",
        "Class 12",
        "High",
        "UPMSP Class 12",
        "हैलोऐल्केन तथा हैलोऐरीन / Haloalkanes & Haloarenes",
        r"(?:हैलोऐल्केन|हैलोएल्केन|हेलोएल्केन|हैलोऐरीन|हैलोएरीन|हेलोएरीन|\b(?:haloalkanes?|haloarenes?|alkyl\s+halides?)\b)",
        (
            "हैलोऐल्केन तथा हैलोऐरीन Class 12 UP Board",
            "Haloalkanes and Haloarenes Class 12 Hindi Medium",
        ),
        (
            "हैलोऐल्केन तथा हैलोऐरीन Class 12 One Shot",
            "Haloalkanes and Haloarenes Class 12 UP Board One Shot",
            "Haloalkanes and Haloarenes Class 12 Hindi Medium One Shot",
            "Haloalkane Haloarene Class 12 Chemistry Hindi Medium",
        ),
    ),
    (
        27,
        "Class 12 रसायन (Chemistry)",
        "कार्बनिक रसायन (Organic Chemistry)",
        "Class 12",
        "High",
        "UPMSP Class 12",
        "ऐल्कोहॉल, फीनॉल एवं ईथर / Alcohols Phenols & Ethers",
        r"(?:ऐल्कोहॉल|एल्कोहल|एल्कोहॉल|फीनॉल|फिनोल|फिनॉल|ईथर|\b(?:alcohols?|phenols?|ethers?)\b)",
        (
            "ऐल्कोहॉल फीनॉल एवं ईथर Class 12 UP Board",
            "Alcohols Phenols and Ethers Class 12 Hindi Medium",
        ),
        (
            "ऐल्कोहॉल फीनॉल एवं ईथर Class 12 One Shot",
            "Alcohol Phenol and Ether Class 12 UP Board One Shot",
            "Alcohols Phenols and Ethers Class 12 Hindi Medium One Shot",
            "Alcohol Phenol Ether Class 12 Chemistry Hindi Medium",
        ),
    ),
    (
        28,
        "Class 12 रसायन (Chemistry)",
        "कार्बनिक रसायन (Organic Chemistry)",
        "Class 12",
        "Very High",
        "UPMSP Class 12",
        "ऐल्डिहाइड, कीटोन एवं कार्बोक्सिलिक अम्ल / Aldehydes Ketones & Carboxylic Acids",
        r"(?:ऐल्डिहाइड|एल्डिहाइड|कीटोन|कार्बोक्सिलिक|\b(?:aldehydes?|ketones?|carboxylic\s+acids?)\b)",
        (
            "ऐल्डिहाइड कीटोन एवं कार्बोक्सिलिक अम्ल Class 12 UP Board",
            "Aldehydes Ketones and Carboxylic Acids Class 12 Hindi Medium",
        ),
        (
            "ऐल्डिहाइड कीटोन एवं कार्बोक्सिलिक अम्ल Class 12 One Shot",
            "Aldehydes Ketones and Carboxylic Acids Class 12 UP Board One Shot",
            "Aldehydes Ketones and Carboxylic Acids Class 12 Hindi Medium One Shot",
            "Aldehyde Ketone Carboxylic Acid Class 12 Hindi Medium",
        ),
    ),
    (
        29,
        "Class 12 रसायन (Chemistry)",
        "कार्बनिक रसायन (Organic Chemistry)",
        "Class 12",
        "Medium",
        "UPMSP Class 12",
        "ऐमीन / Amines",
        r"(?:ऐमीन|एमीन|डाइएजोनियम|नाइट्रोजन युक्त कार्बनिक|\b(?:amines?\b|diazonium|nitrogen\s+containing\s+organic)\b)",
        (
            "ऐमीन Class 12 Chemistry UP Board",
            "Amines Class 12 Chemistry Hindi Medium",
        ),
        (
            "ऐमीन Class 12 Chemistry One Shot",
            "Amines Class 12 UP Board One Shot",
            "Amines Class 12 Chemistry Hindi Medium One Shot",
            "Amine Class 12 Chemistry Hindi Medium",
        ),
    ),
    (
        30,
        "Class 12 रसायन (Chemistry)",
        "कार्बनिक रसायन (Organic Chemistry)",
        "Class 12",
        "High",
        "UPMSP Class 12",
        "जैव-अणु / Biomolecules",
        r"(?:जैव-अणु|जैव अणु|जैवअणु|कार्बोहाइड्रेट|प्रोटीन|न्यूक्लिक अम्ल|\b(?:biomolecules?|jaiv\s*anu|carbohydrates?|amino\s+acids?)\b)",
        (
            "जैव-अणु Class 12 Chemistry UP Board",
            "Biomolecules Class 12 Chemistry Hindi Medium",
        ),
        (
            "जैव अणु Class 12 Chemistry One Shot",
            "Biomolecules Class 12 Chemistry UP Board One Shot",
            "Biomolecules Class 12 Chemistry Hindi Medium One Shot",
            "Jaiv Anu Class 12 Chemistry UP Board",
        ),
    ),

    # ============ 4. Class 12 जीव विज्ञान व भाषा — 8 Chapters ============
    (
        31,
        "Class 12 जीव विज्ञान व भाषा",
        "जीव विज्ञान — जनन (Biology: Reproduction)",
        "Class 12",
        "High",
        "UPMSP Class 12",
        "पुष्पी पादपों में लैंगिक जनन / Sexual Reproduction in Flowering Plants",
        r"(?:पुष्पी पादपों|लैंगिक जनन|परागण|द्विनिषेचन|\b(?:sexual\s+reproduction\s+in\s+flowering\s+plants?|flowering\s+plants?|pushpi\s+padap\w*)\b)",
        (
            "पुष्पी पादपों में लैंगिक जनन Class 12 UP Board",
            "Sexual Reproduction in Flowering Plants Class 12 Hindi Medium",
        ),
        (
            "पुष्पी पादपों में लैंगिक जनन Class 12 One Shot",
            "Sexual Reproduction in Flowering Plants Class 12 UP Board One Shot",
            "Sexual Reproduction in Flowering Plants Class 12 Hindi Medium One Shot",
            "Pushpi Padapon mein Laingik Janan Class 12 Biology",
        ),
    ),
    (
        32,
        "Class 12 जीव विज्ञान व भाषा",
        "जीव विज्ञान — जनन (Biology: Reproduction)",
        "Class 12",
        "High",
        "UPMSP Class 12",
        "मानव जनन एवं जनन स्वास्थ्य / Human Reproduction",
        r"(?:मानव जनन|जनन स्वास्थ्य|युग्मकजनन|शुक्राणुजनन|अण्डजनन|\b(?:human\s+reproduction|reproductive\s+health|manav\s+janan|janan\s+swasthya)\b)",
        (
            "मानव जनन Class 12 Biology UP Board",
            "जनन स्वास्थ्य Class 12 Biology Hindi Medium",
        ),
        (
            "मानव जनन Class 12 Biology One Shot",
            "जनन स्वास्थ्य Class 12 Biology One Shot",
            "Human Reproduction Class 12 Hindi Medium One Shot",
            "Reproductive Health Class 12 Hindi Medium One Shot",
        ),
    ),
    (
        33,
        "Class 12 जीव विज्ञान व भाषा",
        "आनुवंशिकी (Genetics)",
        "Class 12",
        "Very High",
        "UPMSP Class 12",
        "वंशागति तथा आणविक आधार / Principles & Molecular Basis of Inheritance",
        r"(?:वंशागति|आणविक आधार|आनुवंशिकी|मेंडल|\b(?:principles?\s+of\s+inheritance|molecular\s+basis\s+of\s+inheritance|inheritance\s*(?:and|&)\s*variation|vanshagati|anuvanshiki)\b)",
        (
            "वंशागति तथा विविधता के सिद्धांत Class 12 UP Board",
            "वंशागति का आणविक आधार Class 12 Hindi Medium",
        ),
        (
            "वंशागति तथा विविधता के सिद्धांत Class 12 One Shot",
            "वंशागति का आणविक आधार Class 12 One Shot",
            "Principles of Inheritance Class 12 Hindi Medium One Shot",
            "Molecular Basis of Inheritance Class 12 Hindi Medium One Shot",
        ),
    ),
    (
        34,
        "Class 12 जीव विज्ञान व भाषा",
        "विकास व मानव कल्याण (Evolution & Human Welfare)",
        "Class 12",
        "High",
        "UPMSP Class 12",
        "विकास एवं मानव स्वास्थ्य तथा रोग / Evolution & Human Health",
        r"(?:मानव स्वास्थ्य|मानव कल्याण में सूक्ष्मजीव|जैव विकास|विकास|\b(?:human\s+health\s*(?:and|&)\s*diseases?|evolution\b|microbes\s+in\s+human\s+welfare|manav\s+swasthya)\b)",
        (
            "मानव स्वास्थ्य तथा रोग Class 12 Biology UP Board",
            "विकास Class 12 Biology Hindi Medium",
        ),
        (
            "मानव स्वास्थ्य तथा रोग Class 12 One Shot",
            "मानव कल्याण में सूक्ष्मजीव Class 12 One Shot",
            "Human Health and Disease Class 12 Hindi Medium One Shot",
            "Evolution Class 12 Biology Hindi Medium One Shot",
        ),
    ),
    (
        35,
        "Class 12 जीव विज्ञान व भाषा",
        "जैव प्रौद्योगिकी व पारिस्थितिकी (Biotech & Ecology)",
        "Class 12",
        "Very High",
        "UPMSP Class 12",
        "जैव प्रौद्योगिकी एवं पारिस्थितिकी / Biotechnology & Ecology",
        r"(?:जैव प्रौद्योगिकी|पारिस्थितिकी|जीव और समष्टियाँ|जीव और समष्टियां|पारितंत्र|जैव विविधता एवं संरक्षण|जैव विविधता तथा संरक्षण|\b(?:biotechnology|organisms?\s*(?:and|&)\s*populations?|ecosystem\b|biodiversity\s*(?:and|&)\s*conservation|ecology\b|jaiv\s+praudyogiki|paristhitiki)\b)",
        (
            "जैव प्रौद्योगिकी Class 12 Biology UP Board",
            "पारिस्थितिकी Class 12 Biology Hindi Medium",
        ),
        (
            "जैव प्रौद्योगिकी सिद्धांत व प्रक्रम Class 12 One Shot",
            "जीव और समष्टियाँ Class 12 Biology One Shot",
            "Biotechnology Class 12 Hindi Medium One Shot",
            "जैव विविधता एवं संरक्षण Class 12 Biology One Shot",
        ),
    ),
    (
        36,
        "Class 12 जीव विज्ञान व भाषा",
        "हिंदी साहित्य व संस्कृत (Hindi Prose, Poetry & Sanskrit)",
        "Class 12",
        "Very High",
        "UPMSP Class 12",
        "Class 12 सामान्य व साहित्यिक हिंदी — गद्य, पद्य एवं संस्कृत",
        r"(?:गद्य|पद्य|काव्यांजलि|संस्कृत दिग्दर्शिका|सामान्य हिंदी|सामान्य हिन्दी|साहित्यिक हिंदी|साहित्यिक हिन्दी|साहित्यिक परिचय|जीवन परिचय|पवन दूतिका|कैकेयी का अनुताप|श्रद्धा मनु|राष्ट्र का स्वरूप|अशोक के फूल|पंचलाइट|बहादुर|रश्मिरथी|सुभाषितरत्नानि|\b(?:gadya|padya|kavyanjali|sanskrit\s+digdarshika|samanya\s+hindi|sahityik\s+hindi|sahityik\s+parichay|jeevan\s+parichay|panchlight|rashmirathi|pawan\s+dutika|rashtra\s+ka\s+swaroop)\b)",
        (
            "Class 12 सामान्य हिंदी UP Board",
            "Class 12 Hindi गद्य पद्य संस्कृत UP Board",
        ),
        (
            "Class 12 सामान्य हिंदी गद्य पद्य One Shot UP Board",
            "Class 12 Hindi संस्कृत दिग्दर्शिका One Shot UP Board",
            "Class 12 Hindi साहित्यिक परिचय पंचलाइट रश्मिरथी UP Board",
            "Class 12 Samanya Hindi Complete Revision UP Board",
        ),
    ),
    (
        37,
        "Class 12 जीव विज्ञान व भाषा",
        "हिंदी व्याकरण व रचना (Hindi Grammar, Letters & Essays)",
        "Class 12",
        "High",
        "UPMSP Class 12",
        "Class 12 हिंदी व्याकरण, रस-छंद-अलंकार, पत्र व निबंध",
        r"(?:व्याकरण|रस छंद अलंकार|रस, छंद|रस छन्द|अलंकार|छंद|निबंध|पत्र लेखन|संधि|समास|मुहावरे|लोकोक्ति|वाक्यांश के लिए|अपठित गद्यांश|\b(?:hindi\s+grammar|hindi\s+vyakaran|ras\s+chhand\s+alankar|alankar|nibandh|patra\s+lekhan)\b)",
        (
            "Class 12 हिंदी व्याकरण UP Board",
            "Class 12 Hindi Grammar UP Board",
        ),
        (
            "Class 12 हिंदी व्याकरण One Shot UP Board",
            "रस छंद अलंकार Class 12 Hindi UP Board",
            "पत्र लेखन निबंध Class 12 Hindi UP Board",
            "Class 12 Hindi Vyakaran Complete UP Board",
        ),
    ),
    (
        38,
        "Class 12 जीव विज्ञान व भाषा",
        "Class 12 English (Flamingo, Vistas & Grammar)",
        "Class 12",
        "Very High",
        "UPMSP Class 12",
        "Class 12 English — Prose, Poetry, Vistas & Grammar/Writing",
        r"\b(?:flamingo|vistas|english\s+prose|english\s+poetry|central\s+idea|last\s+lesson|lost\s+spring|deep\s+water|rattrap|indigo|my\s+mother\s+at\s+sixty|thing\s+of\s+beauty|third\s+level|tiger\s+king|english\s+grammar|synthesis|transformation|syntax|direct\s*(?:and|&)?\s*indirect|narration|article\s+writing|letter\s+writing|unseen\s+passage|class\s*12(?:th)?\s+english|12th\s+english)\b",
        (
            "Class 12 English UP Board",
            "Class 12 English Grammar UP Board",
        ),
        (
            "Class 12 English Prose Poetry Vistas One Shot UP Board",
            "Class 12 English Grammar One Shot UP Board",
            "Class 12 English Flamingo Vistas Hindi Explanation One Shot",
            "Class 12 English Letter Article Central Idea UP Board",
        ),
    ),

    # ============ 5. Class 10 गणित व विज्ञान — 7 Chapters ============
    (
        39,
        "Class 10 गणित व विज्ञान",
        "संख्या पद्धति व बीजगणित I (Number System & Algebra)",
        "Class 10",
        "High",
        "UPMSP Class 10",
        "Class 10 वास्तविक संख्याएँ, बहुपद व दो चर वाले रैखिक समीकरण",
        r"(?:वास्तविक संख्या|बहुपद|दो चर वाले रैखिक समीकरण|रैखिक समीकरण युग्म|\b(?:real\s+numbers?|polynomials?|pair\s+of\s+linear\s+equations?|linear\s+equations?\s+in\s+two\s+variables?|vastavik\s+sankhya\w*|bahupad|do\s+char\s+wale)\b)",
        (
            "वास्तविक संख्याएँ बहुपद Class 10 Maths UP Board",
            "दो चर वाले रैखिक समीकरण युग्म Class 10 Hindi Medium",
        ),
        (
            "वास्तविक संख्याएँ Class 10 Maths One Shot UP Board",
            "बहुपद Class 10 Maths One Shot Hindi Medium",
            "दो चर वाले रैखिक समीकरण युग्म Class 10 One Shot",
            "Real Numbers Polynomials Class 10 Hindi Medium One Shot",
        ),
    ),
    (
        40,
        "Class 10 गणित व विज्ञान",
        "बीजगणित II (Quadratic & AP)",
        "Class 10",
        "High",
        "UPMSP Class 10",
        "Class 10 द्विघात समीकरण एवं समांतर श्रेढ़ियाँ",
        r"(?:द्विघात समीकरण|समांतर श्रेढ़ी|समांतर श्रेढ़ियाँ|समांतर श्रेणी|समान्तर श्रेणी|\b(?:quadratic\s+equations?|arithmetic\s+progressions?|dwighat\s+samikaran|dvighat\s+samikaran|samantar\s+shreni|samantar\s+shredhi)\b)",
        (
            "द्विघात समीकरण Class 10 Maths UP Board",
            "समांतर श्रेढ़ियाँ Class 10 Maths Hindi Medium",
        ),
        (
            "द्विघात समीकरण Class 10 Maths One Shot UP Board",
            "समांतर श्रेढ़ियाँ Class 10 Maths One Shot Hindi Medium",
            "Quadratic Equations Class 10 Hindi Medium One Shot",
            "Arithmetic Progression Class 10 Hindi Medium One Shot",
        ),
    ),
    (
        41,
        "Class 10 गणित व विज्ञान",
        "ज्यामिति व निर्देशांक ज्यामिति (Geometry & Coordinate)",
        "Class 10",
        "Very High",
        "UPMSP Class 10",
        "Class 10 त्रिभुज, निर्देशांक ज्यामिति एवं वृत्त",
        r"(?:त्रिभुज|थेल्स प्रमेय|निर्देशांक ज्यामिति|वृत्त|\b(?:triangles?\b|coordinate\s+geometry|circles?\b|thales\s+theorem|tribhuj|nirdeshank\s+jyamiti|vritt)\b)",
        (
            "त्रिभुज Class 10 Maths UP Board",
            "निर्देशांक ज्यामिति Class 10 Maths Hindi Medium",
        ),
        (
            "त्रिभुज Class 10 Maths One Shot UP Board",
            "निर्देशांक ज्यामिति Class 10 One Shot Hindi Medium",
            "वृत्त Class 10 Maths One Shot Hindi Medium",
            "Triangles Coordinate Geometry Class 10 Hindi Medium One Shot",
        ),
    ),
    (
        42,
        "Class 10 गणित व विज्ञान",
        "त्रिकोणमिति (Trigonometry & Heights)",
        "Class 10",
        "Very High",
        "UPMSP Class 10",
        "Class 10 त्रिकोणमिति एवं ऊँचाई और दूरी",
        r"(?:त्रिकोणमिति|ऊँचाई और दूरी|ऊंचाई और दूरी|\b(?:introduction\s+to\s+trigonometry|trigonometry|applications?\s+of\s+trigonometry|height\s*(?:and|&)\s*distance|trikonmiti|unchai\s+aur\s+duri)\b)",
        (
            "त्रिकोणमिति का परिचय Class 10 Maths UP Board",
            "त्रिकोणमिति के कुछ अनुप्रयोग Class 10 Hindi Medium",
        ),
        (
            "त्रिकोणमिति का परिचय Class 10 One Shot UP Board",
            "त्रिकोणमिति के कुछ अनुप्रयोग ऊँचाई और दूरी Class 10 One Shot",
            "Trigonometry Class 10 Maths Hindi Medium One Shot",
            "Trikonmiti Class 10 Maths UP Board One Shot",
        ),
    ),
    (
        43,
        "Class 10 गणित व विज्ञान",
        "क्षेत्रमिति, सांख्यिकी व प्रायिकता (Mensuration, Stats & Prob)",
        "Class 10",
        "Very High",
        "UPMSP Class 10",
        "Class 10 पृष्ठीय क्षेत्रफल-आयतन, सांख्यिकी व प्रायिकता",
        r"(?:पृष्ठीय क्षेत्रफल|आयतन|वृत्तों से संबंधित क्षेत्रफल|सांख्यिकी|माध्य, माध्यिका|प्रायिकता|\b(?:surface\s+areas?\s*(?:and|&)?\s*volumes?|areas?\s+related\s+to\s+circles?|statistics|probability|prishthiya\s+kshetrafal|prashthiya\s+kshetrafal|sankhyiki|prayikta)\b)",
        (
            "पृष्ठीय क्षेत्रफल और आयतन Class 10 UP Board",
            "सांख्यिकी Class 10 Maths Hindi Medium",
        ),
        (
            "पृष्ठीय क्षेत्रफल और आयतन Class 10 One Shot",
            "सांख्यिकी Class 10 Maths One Shot UP Board",
            "प्रायिकता Class 10 Maths One Shot Hindi Medium",
            "वृत्तों से संबंधित क्षेत्रफल Class 10 One Shot",
        ),
    ),
    (
        44,
        "Class 10 गणित व विज्ञान",
        "कक्षा 10 रसायन विज्ञान (Class 10 Chemistry)",
        "Class 10",
        "Very High",
        "UPMSP Class 10",
        "Class 10 विज्ञान — रासायनिक अभिक्रियाएँ, अम्ल-क्षार, धातु एवं कार्बन यौगिक (Chemistry)",
        r"(?:रासायनिक अभिक्रिया|अम्ल, क्षारक|अम्ल क्षार|अम्ल, क्षार|धातु एवं अधातु|धातु और अधातु|कार्बन एवं उसके यौगिक|कार्बन तथा उसके यौगिक|\b(?:chemical\s+reactions?\s*(?:and|&)?\s*equations?|acids?[,\s]+bases?\s*(?:and|&)?\s*salts?|metals?\s*(?:and|&)\s*non[- ]?metals?|carbon\s*(?:and|&)\s*its\s+compounds?|rasayanik\s+abhikriya\w*|aml\s+ksharak|dhatu\s+(?:evam|aur)\s+adhatu|carbon\s+evam\s+uske\s+yaugik)\b)",
        (
            "रासायनिक अभिक्रियाएँ एवं समीकरण Class 10 UP Board",
            "कार्बन एवं उसके यौगिक Class 10 Science Hindi Medium",
        ),
        (
            "रासायनिक अभिक्रियाएँ एवं समीकरण Class 10 One Shot",
            "अम्ल क्षारक एवं लवण Class 10 One Shot",
            "धातु एवं अधातु Class 10 Science One Shot",
            "कार्बन एवं उसके यौगिक Class 10 One Shot UP Board",
        ),
    ),
    (
        45,
        "Class 10 गणित व विज्ञान",
        "कक्षा 10 जीव व भौतिक विज्ञान (Class 10 Bio & Physics)",
        "Class 10",
        "Very High",
        "UPMSP Class 10",
        "Class 10 विज्ञान — जैव प्रक्रम, आनुवंशिकता, प्रकाश एवं विद्युत धारा (Bio & Physics)",
        r"(?:जैव प्रक्रम|नियंत्रण एवं समन्वय|जीव जनन कैसे करते|आनुवंशिकता|प्रकाश का परावर्तन|प्रकाश - परावर्तन|प्रकाश परावर्तन|मानव नेत्र|विद्युत धारा के चुंबकीय प्रभाव|विद्युत|हमारा पर्यावरण|\b(?:life\s+processes|control\s*(?:and|&)\s*coordination|how\s+do\s+organisms\s+reproduce|heredity|light\s+reflection\s*(?:and|&)?\s*refraction|human\s+eye|electricity\b|magnetic\s+effects?\s+of\s+electric\s+current|jaiv\s+prakram|prakash\s+ka\s+paravartan|manav\s+netra)\b)",
        (
            "जैव प्रक्रम Class 10 Science UP Board",
            "प्रकाश परावर्तन तथा अपवर्तन Class 10 Hindi Medium",
        ),
        (
            "जैव प्रक्रम Class 10 Science One Shot UP Board",
            "प्रकाश परावर्तन तथा अपवर्तन Class 10 One Shot",
            "विद्युत Class 10 Science Hindi Medium One Shot",
            "मानव नेत्र तथा रंगबिरंगा संसार Class 10 One Shot",
        ),
    ),

    # ======== 6. Class 10 हिंदी, English व सामाजिक विज्ञान — 5 Chapters ========
    (
        46,
        "Class 10 हिंदी, English व सामाजिक विज्ञान",
        "कक्षा 10 हिंदी साहित्य व संस्कृत (Hindi Prose, Poetry & Sanskrit)",
        "Class 10",
        "Very High",
        "UPMSP Class 10",
        "Class 10 हिंदी — गद्य, पद्य व अनिवार्य संस्कृत",
        r"(?:गद्य|पद्य|काव्य|अनिवार्य संस्कृत|संस्कृत परिचायिका|मित्रता|ममता|सूरदास के पद|तुलसीदास|वाराणसी|भारतीय संस्कृति|प्रबुद्धो ग्रामीणः|जीवन परिचय|तुमुल कोलाहल|हिन्दी गद्य|हिंदी गद्य|\b(?:gadya|padya|anivarya\s+sanskrit|mitrata|surdas\s+ke\s+pad|varanasi\s+sanskrit|jeevan\s+parichay|class\s*10(?:th)?\s+hindi|10th\s+hindi)\b)",
        (
            "Class 10 हिंदी गद्य पद्य संस्कृत UP Board",
            "Class 10 Hindi UP Board Complete",
        ),
        (
            "Class 10 हिंदी गद्य पद्य One Shot UP Board",
            "अनिवार्य संस्कृत Class 10 Hindi UP Board One Shot",
            "Class 10 Hindi महत्वपूर्ण जीवन परिचय गद्यांश पद्यांश UP Board",
            "Class 10 Hindi Complete Marathon UP Board",
        ),
    ),
    (
        47,
        "Class 10 हिंदी, English व सामाजिक विज्ञान",
        "कक्षा 10 हिंदी व्याकरण व निबंध (Hindi Grammar & Essay)",
        "Class 10",
        "High",
        "UPMSP Class 10",
        "Class 10 हिंदी व्याकरण, रस-छंद-अलंकार एवं निबंध",
        r"(?:व्याकरण|रस छंद अलंकार|रस, छंद|रस छन्द|अलंकार|छंद|रोला|सोरठा|उपसर्ग|प्रत्यय|समास|तत्सम|पर्यायवाची|वाच्य|निबंध|पत्र लेखन|\b(?:hindi\s+grammar|hindi\s+vyakaran|ras\s+chhand\s+alankar|alankar|samas|upsarg|pratyay|nibandh)\b)",
        (
            "Class 10 हिंदी व्याकरण UP Board",
            "Class 10 Hindi Vyakaran UP Board",
        ),
        (
            "Class 10 हिंदी व्याकरण One Shot UP Board",
            "रस छंद अलंकार Class 10 Hindi UP Board",
            "निबंध लेखन पत्र लेखन Class 10 Hindi UP Board",
            "उपसर्ग प्रत्यय समास वाच्य Class 10 Hindi Vyakaran UP Board",
        ),
    ),
    (
        48,
        "Class 10 हिंदी, English व सामाजिक विज्ञान",
        "Class 10 English (First Flight, Footprints & Grammar)",
        "Class 10",
        "Very High",
        "UPMSP Class 10",
        "Class 10 English — First Flight, Footprints & Grammar",
        r"\b(?:first\s+flight|footprints\s+without\s+feet|letter\s+to\s+god|nelson\s+mandela|anne\s+frank|glimpses\s+of\s+india|dust\s+of\s+snow|fire\s+and\s+ice|triumph\s+of\s+surgery|thief'?s\s+story|bholi|central\s+idea|english\s+prose|english\s+poetry|english\s+grammar|tenses?|narration|direct\s+indirect|active\s+passive|reordering|punctuation|application\s+writing|letter\s+writing|class\s*10(?:th)?\s+english|10th\s+english)\b",
        (
            "Class 10 English UP Board",
            "Class 10 English Grammar UP Board",
        ),
        (
            "Class 10 English First Flight One Shot UP Board",
            "Class 10 English Footprints Without Feet One Shot",
            "Class 10 English Grammar One Shot UP Board",
            "Class 10 English Prose Poetry Central Idea UP Board",
        ),
    ),
    (
        49,
        "Class 10 हिंदी, English व सामाजिक विज्ञान",
        "इतिहास व नागरिक शास्त्र (History & Civics)",
        "Class 10",
        "Very High",
        "UPMSP Class 10",
        "Class 10 सामाजिक विज्ञान — इतिहास एवं नागरिक शास्त्र (History & Civics)",
        r"(?:यूरोप में राष्ट्रवाद|भारत में राष्ट्रवाद|भूमंडलीकृत विश्व|औद्योगीकरण का युग|मुद्रण संस्कृति|सत्ता की साझेदारी|संघवाद|जाति, धर्म और लैंगिक|राजनीतिक दल|लोकतंत्र के परिणाम|इतिहास|नागरिक शास्त्र|\b(?:nationalism\s+in\s+europe|nationalism\s+in\s+india|making\s+of\s+a\s+global\s+world|print\s+culture|power\s+sharing|federalism|political\s+parties|outcomes\s+of\s+democracy|history|civics|yurop\s+mein\s+rashtravad|bharat\s+mein\s+rashtravad|satta\s+ki\s+sajhedari|sanghvad)\b)",
        (
            "इतिहास Class 10 सामाजिक विज्ञान UP Board",
            "नागरिक शास्त्र Class 10 Social Science Hindi Medium",
        ),
        (
            "यूरोप में राष्ट्रवाद का उदय Class 10 One Shot",
            "भारत में राष्ट्रवाद Class 10 Social Science One Shot",
            "सत्ता की साझेदारी संघवाद Class 10 One Shot",
            "Class 10 History Complete One Shot Hindi Medium UP Board",
        ),
    ),
    (
        50,
        "Class 10 हिंदी, English व सामाजिक विज्ञान",
        "भूगोल व अर्थशास्त्र (Geography & Economics)",
        "Class 10",
        "Very High",
        "UPMSP Class 10",
        "Class 10 सामाजिक विज्ञान — भूगोल एवं अर्थशास्त्र (Geography & Economics)",
        r"(?:संसाधन एवं विकास|वन एवं वन्य जीव|जल संसाधन|कृषि|खनिज तथा ऊर्जा|विनिर्माण उद्योग|राष्ट्रीय अर्थव्यवस्था|विकास|भारतीय अर्थव्यवस्था के क्षेत्रक|मुद्रा और साख|वैश्वीकरण और भारतीय अर्थव्यवस्था|उपभोक्ता अधिकार|भूगोल|अर्थशास्त्र|मानचित्र कार्य|\b(?:resources?\s*(?:and|&)\s*development|water\s+resources|agriculture\b|minerals?\s*(?:and|&)\s*energy|manufacturing\s+industries|sectors\s+of\s+(?:the\s+)?indian\s+economy|money\s*(?:and|&)\s*credit|globalisation\s*(?:and|&)\s*the\s+indian\s+economy|geography|economics|sansadhan\s+evam\s+vikas|mudra\s+aur\s+sakh|bhugol|arthashastra|map\s+work)\b)",
        (
            "भूगोल Class 10 सामाजिक विज्ञान UP Board",
            "अर्थशास्त्र Class 10 Social Science Hindi Medium",
        ),
        (
            "संसाधन एवं विकास Class 10 Social Science One Shot",
            "भारतीय अर्थव्यवस्था के क्षेत्रक मुद्रा और साख Class 10 One Shot",
            "Class 10 Geography Complete One Shot Hindi Medium UP Board",
            "Class 10 Economics Complete One Shot Hindi Medium UP Board",
        ),
    ),
]

TEACHER_PLAYLIST_SWEEPS: list[tuple[str, str]] = [
    # Vidyakul (Jay Mahadev Vidyakul & UP Board High School Vidyakul)
    ("Class 12 गणित (Maths)", "Jay Mahadev Vidyakul Class 12 Maths"),
    ("Class 12 भौतिकी (Physics)", "Jay Mahadev Vidyakul Class 12 Physics"),
    ("Class 12 रसायन (Chemistry)", "Jay Mahadev Vidyakul Class 12 Chemistry"),
    ("Class 12 जीव विज्ञान व भाषा", "Jay Mahadev Vidyakul Class 12 Biology"),
    ("Class 12 जीव विज्ञान व भाषा", "Jay Mahadev Vidyakul Class 12 Hindi English"),
    ("Class 10 गणित व विज्ञान", "UP Board High School Vidyakul Class 10 Maths Science"),
    ("Class 10 हिंदी, English व सामाजिक विज्ञान", "UP Board High School Vidyakul Class 10 Hindi English Social Science"),
    ("Class 12 भौतिकी (Physics)", "Science Deewane Vidyakul Class 12 Physics"),
    ("Class 12 रसायन (Chemistry)", "Science Deewane Vidyakul Class 12 Chemistry"),
    # Shubham Classes & Shubham Lecturer
    ("Class 12 गणित (Maths)", "Shubham Classes Class 12 Maths UP Board"),
    ("Class 12 भौतिकी (Physics)", "Shubham Classes Class 12 Physics UP Board"),
    ("Class 12 रसायन (Chemistry)", "Shubham Classes Class 12 Chemistry UP Board"),
    ("Class 12 जीव विज्ञान व भाषा", "Shubham Classes Class 12 Biology Hindi English"),
    ("Class 12 भौतिकी (Physics)", "Shubham Lecturer Class 12 Physics Chemistry"),
    ("Class 10 गणित व विज्ञान", "Shubham Classes Class 10 Maths Science UP Board"),
    ("Class 10 हिंदी, English व सामाजिक विज्ञान", "Shubham Classes Class 10 Hindi Social Science"),
    # Gyansindhu Coaching Classes (UP Board Hindi Legend)
    ("Class 12 जीव विज्ञान व भाषा", "Gyansindhu Coaching Classes Class 12 Hindi"),
    ("Class 10 हिंदी, English व सामाजिक विज्ञान", "Gyansindhu Coaching Classes Class 10 Hindi"),
    # RWA Tuition Classes (Rojgar with Ankit)
    ("Class 12 गणित (Maths)", "RWA Tuition Classes Class 12 Maths UP Board"),
    ("Class 12 भौतिकी (Physics)", "RWA Tuition Classes Class 12 Physics UP Board"),
    ("Class 12 रसायन (Chemistry)", "RWA Tuition Classes Class 12 Chemistry UP Board"),
    ("Class 12 जीव विज्ञान व भाषा", "RWA Tuition Classes Class 12 Biology Hindi English"),
    ("Class 10 गणित व विज्ञान", "RWA Tuition Classes Class 10 Maths Science"),
    ("Class 10 हिंदी, English व सामाजिक विज्ञान", "RWA Tuition Classes Class 10 Hindi English SST"),
    # Ashish Singh Lectures, Learn and Share, Vikram Singh, PW Hindi Medium
    ("Class 12 भौतिकी (Physics)", "Ashish Singh Lectures Class 12 Physics"),
    ("Class 12 रसायन (Chemistry)", "Ashish Singh Lectures Class 12 Chemistry"),
    ("Class 12 रसायन (Chemistry)", "Vikram Singh Class 12 Chemistry Hindi Medium"),
    ("Class 12 गणित (Maths)", "Learn and Share Class 12 Maths"),
    ("Class 12 भौतिकी (Physics)", "Learn and Share Class 12 Physics"),
    ("Class 10 गणित व विज्ञान", "Learn and Share Class 10 Maths Science"),
    ("Class 12 भौतिकी (Physics)", "PW Hindi Medium Class 12 Physics"),
    ("Class 12 रसायन (Chemistry)", "PW Hindi Medium Class 12 Chemistry"),
    ("Class 12 गणित (Maths)", "PW Hindi Medium Class 12 Maths"),
    ("Class 10 गणित व विज्ञान", "PW Hindi Medium Class 10 Maths Science"),
    # XPclasses, Alpha Institute, Gyanoday Ke Guru Ji, MK Sir Inspiration, Shravan Lecturer
    ("Class 12 गणित (Maths)", "XPclasses Class 12 Maths UP Board"),
    ("Class 12 जीव विज्ञान व भाषा", "XPclasses Class 12 English UP Board"),
    ("Class 12 भौतिकी (Physics)", "Alpha Institute Class 12 Physics Chemistry"),
    ("Class 10 गणित व विज्ञान", "Gyanoday Ke Guru Ji Class 10 Science Maths"),
    ("Class 10 हिंदी, English व सामाजिक विज्ञान", "Gyanoday Ke Guru Ji Class 10 Hindi Social Science"),
    ("Class 10 गणित व विज्ञान", "Shravan Lecturer Class 10 Science Maths UP Board"),
    ("Class 10 हिंदी, English व सामाजिक विज्ञान", "Shravan Lecturer Class 10 Hindi Social Science"),
    ("Class 12 भौतिकी (Physics)", "MK Sir Inspiration Class 12 Physics Chemistry"),
]

INSTITUTE_VIDEO_SWEEPS: list[tuple[str, str]] = [
    ("Class 12 गणित (Maths)", "Jay Mahadev Vidyakul Class 12 Maths One Shot"),
    ("Class 12 भौतिकी (Physics)", "Jay Mahadev Vidyakul Class 12 Physics One Shot"),
    ("Class 12 रसायन (Chemistry)", "Jay Mahadev Vidyakul Class 12 Chemistry One Shot"),
    ("Class 12 जीव विज्ञान व भाषा", "Jay Mahadev Vidyakul Class 12 Biology One Shot"),
    ("Class 12 जीव विज्ञान व भाषा", "Gyansindhu Coaching Classes Class 12 Hindi One Shot"),
    ("Class 12 जीव विज्ञान व भाषा", "Shubham Classes Class 12 English Hindi One Shot"),
    ("Class 12 भौतिकी (Physics)", "Ashish Singh Lectures Class 12 Physics One Shot"),
    ("Class 12 रसायन (Chemistry)", "Vikram Singh Class 12 Chemistry One Shot"),
    ("Class 12 भौतिकी (Physics)", "PW Hindi Medium Class 12 Physics One Shot"),
    ("Class 12 रसायन (Chemistry)", "PW Hindi Medium Class 12 Chemistry One Shot"),
    ("Class 12 गणित (Maths)", "RWA Tuition Classes Class 12 Maths One Shot"),
    ("Class 12 भौतिकी (Physics)", "RWA Tuition Classes Class 12 Physics One Shot"),
    ("Class 10 गणित व विज्ञान", "UP Board High School Vidyakul Class 10 Maths One Shot"),
    ("Class 10 गणित व विज्ञान", "UP Board High School Vidyakul Class 10 Science One Shot"),
    ("Class 10 गणित व विज्ञान", "Gyanoday Ke Guru Ji Class 10 Science One Shot"),
    ("Class 10 गणित व विज्ञान", "PW Hindi Medium Class 10 Science Maths One Shot"),
    ("Class 10 हिंदी, English व सामाजिक विज्ञान", "UP Board High School Vidyakul Class 10 Social Science One Shot"),
    ("Class 10 हिंदी, English व सामाजिक विज्ञान", "Gyansindhu Coaching Classes Class 10 Hindi One Shot"),
    ("Class 10 हिंदी, English व सामाजिक विज्ञान", "Shubham Classes Class 10 English Hindi One Shot"),
]

# Curated Allowlist of Legitimate UP Board & Hindi Medium Board Channels
VERIFIED_CHANNEL_PATTERNS = (
    # Dedicated UP Board Giants
    "vidyakul",
    "jay mahadev",
    "up board",
    "shubham classes",
    "shubham lecturer",
    "gyan sindhu",
    "gyansindhu",
    "rwa tuition",
    "rojgar with ankit",
    "xpclasses",
    "xp classes",
    "alpha institute",
    "mk sir inspiration",
    "smart study classes",
    "shravan lecturer",
    "samrat academy",
    "skm study",
    "gyanoday ke guru",
    "shiv coaching",
    "board exam",
    # Major NCERT Hindi Medium Board Channels
    "science sangrah",
    "learn and share",
    "learn & share",
    "ashish singh lectures",
    "vikram singh",
    "vikram hap",
    "disha online",
    "disha science",
    "disha hindi",
    "target board",
    "doubtnut",
    "pw up board",
    "pw hindi medium",
    "physics wallah",
    "udaan",
    "magnet brains",
    "dear sir",
    "english connection",
    "ekaksha",
    "e-kaksha",
    "mission gyan",
    "utkarsh online",
    "science deewane",
    "mathematics analysis",
    "ravikant mani tripathi",
    "diamond academic",
    "mobile par school",
    "pankaj study centre",
    "simran sahni",
    "extraclass",
)

# Reject non-board / news / entertainment / competitive-only channels even if they match a broad token
CHANNEL_REJECT_RE = re.compile(
    r"\b(news|aaj\s*tak|abp|zee\s*news|zee\s*up|ndtv|amar\s*ujala|dainik\s*jagran|hindustan|"
    r"sarkari|job\s*alert|vacancy|result\s*alert|status|gaming|vlog\w*|comedy|roast|music|"
    r"bhajan|astrology|crime|politics|bhojpuri|dj\s+remix|"
    r"bihar\s+board|commerce|doubtnut\s+neet|ncert\s+wallah|"
    r"jee\s+wallah|competition\s+wallah|ssc\s+wallah|upsc\s+wallah|banking\s+wallah|"
    r"defence\s+wallah|ca\s+wallah|gate\s+wallah|law\s+wallah|allen\s+jee|allen\s+neet|"
    r"unacademy\s+jee|unacademy\s+neet)\b",
    re.I,
)

# Strict Rejections: DO NOT reject Class 10! Reject Class 6-9 & Class 11-only, competitive job exams,
# regional non-Hindi/English languages, vlogs, result rumours, copy-checking clickbait, shorts.
HARD_REJECT_RE = re.compile(
    r"(?:\b(?:"
    r"icse|isc\s+board|"
    r"ssc\s+cgl|ssc\s+gd|ssc\s+chsl|ssc\s+mts|up\s+police|delhi\s+police|\bupsi\b|lekhpal|"
    r"upsssc|agniveer|army\s+gd|rrb\s+ntpc|railway\s+group\s+d|ctet|uptet|super\s*tet|bpsc\s*tre|"
    r"dsssb|kvs\b|ibps|sbi\s+po|\bnda\b|\bcds\b|polytechnic|iti\s+exam|"
    r"b\.?sc\b|b\.?tech\b|b\.?com\b|b\.?a\.?\s*(?:1st|2nd|3rd|first|second|semester)|semester\s*[1-6]|"
    r"tamil|telugu|malayalam|kannada|bangla|bengali|marathi|gujarati|odia|punjabi|assamese|"
    r"vlog\w*|prank|controversy|exposed|roast|reaction\s+video|hostel\s+tour|campus\s+tour|"
    r"result\s+date|result\s+kab\s+aayega|kab\s+aayega\s+result|copy\s+checking|copy\s+kaise\s+check|"
    r"roll\s+number|admit\s+card|center\s+list|centre\s+list|grace\s+marks|date\s*sheet\s+202\d|"
    r"time\s*table\s+202\d|scholarship|paper\s+leak|exam\s+cancel\w*|bina\s+padhe\s+pass|"
    r"tukka\s+kaise|toppers?\s+interview|toppers?\s+talk|prize\s+distribution|farewell\s+party|"
    r"unboxing|celebration|motivational\s+video|shorts|ytshorts"
    r")\b|"
    r"#shorts|"
    r"रिजल्ट कब|कॉपी चेकिंग|कॉपी कैसे चेक|रोल नंबर|प्रवेश पत्र|सेंटर लिस्ट|स्कीम 202|"
    r"छात्रवृत्ति|पेपर लीक|परीक्षा रद्द|बिना पढ़े पास|तुक्का कैसे|टॉपर इंटरव्यू|"
    r"यूपी पुलिस|एसएससी|अग्निवीर|लेखपाल|सीटेट|यूपीटेट|सुपर टेट|पॉलिटेक्निक|बीएससी|सेमेस्टर"
    r")",
    re.I,
)


def parse_views(text: str) -> int:
    if not text:
        return 0
    cleaned = text.lower().replace(",", "").strip()
    m = re.search(r"([\d.]+)\s*([kmb]|lakh|cr)?", cleaned)
    if not m:
        return 0
    val = float(m.group(1))
    mult = m.group(2) or ""
    if mult == "k":
        val *= 1_000
    elif mult == "m":
        val *= 1_000_000
    elif mult == "b":
        val *= 1_000_000_000
    elif mult == "lakh":
        val *= 100_000
    elif mult == "cr":
        val *= 10_000_000
    return int(val)


def parse_duration_seconds(text: str) -> int:
    if not text:
        return 0
    parts = [int(p) for p in re.findall(r"\d+", text)]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 1:
        return parts[0]
    return 0


def parse_lesson_count(text: str) -> int:
    if not text:
        return 0
    m = re.search(r"(\d+)", text.replace(",", ""))
    return int(m.group(1)) if m else 0


def search_youtube(query: str, params: str = "", use_cache: bool = True) -> dict:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_id = f"{query}::sp={params}" if params else query
    key = hashlib.sha1(cache_id.encode("utf-8")).hexdigest()
    cpath = CACHE_DIR / f"{key}.json"
    if use_cache and cpath.exists():
        with _lock:
            STATS["cached"] += 1
        return json.loads(cpath.read_text(encoding="utf-8"))

    body: dict = {
        "context": {
            "client": {
                "clientName": "WEB",
                "clientVersion": "2.20250101.00.00",
                "hl": "en",
                "gl": "IN",
            }
        },
        "query": query,
    }
    if params:
        body["params"] = params
    payload = json.dumps(body).encode("utf-8")

    last_err = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                INNERTUBE_SEARCH,
                data=payload,
                headers={"User-Agent": UA, "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15, context=SSL_CTX) as resp:
                data = json.load(resp)
            with _lock:
                STATS["requests"] += 1
            cpath.write_text(json.dumps(data), encoding="utf-8")
            return data
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(0.7 * (attempt + 1))
    print(f"WARN: search failed for {query!r}: {last_err}", flush=True)
    return {}


def extract_candidates(payload: dict) -> list[dict]:
    items = []
    try:
        sections = (
            payload["contents"]["twoColumnSearchResultsRenderer"]["primaryContents"]
            ["sectionListRenderer"]["contents"]
        )
    except (KeyError, TypeError):
        return items

    for sec in sections:
        contents = sec.get("itemSectionRenderer", {}).get("contents", [])
        for entry in contents:
            if "lockupViewModel" in entry:
                parsed = _parse_lockup(entry["lockupViewModel"])
                if parsed:
                    items.append(parsed)
            elif "playlistRenderer" in entry:
                parsed = _parse_legacy_playlist(entry["playlistRenderer"])
                if parsed:
                    items.append(parsed)
            elif "videoRenderer" in entry:
                parsed = _parse_video(entry["videoRenderer"])
                if parsed:
                    items.append(parsed)
    return items


def _parse_lockup(lv: dict) -> dict | None:
    cid = (lv.get("contentId") or "").strip()
    ctype = lv.get("contentType") or ""
    if not cid or ("PLAYLIST" not in ctype and "COURSE" not in ctype and not cid.startswith("PL")):
        return None
    if cid.startswith("RD"):
        return None

    meta_vm = lv.get("metadata", {}).get("lockupMetadataViewModel", {})
    title = (meta_vm.get("title", {}).get("content") or "").strip()
    if not title:
        return None

    rows = (
        meta_vm.get("metadata", {})
        .get("contentMetadataViewModel", {})
        .get("metadataRows", [])
    )
    channel = ""
    channel_url = ""
    sample_lectures: list[dict] = []

    for row in rows:
        parts = row.get("metadataParts") or []
        for part in parts:
            txt_obj = part.get("text") or {}
            content = (txt_obj.get("content") or "").strip()
            if not content or content.lower() in {"playlist", "course", "view full playlist", "view full course", "podcast"}:
                continue
            cmd_runs = txt_obj.get("commandRuns") or []
            web_url = ""
            watch_vid = ""
            if cmd_runs:
                icmd = cmd_runs[0].get("onTap", {}).get("innertubeCommand", {})
                web_url = icmd.get("commandMetadata", {}).get("webCommandMetadata", {}).get("url") or ""
                watch_vid = icmd.get("watchEndpoint", {}).get("videoId") or ""

            if not channel and (web_url.startswith("/@") or web_url.startswith("/channel/") or web_url.startswith("/c/")):
                channel = content
                channel_url = f"https://www.youtube.com{web_url}"
            elif watch_vid and len(sample_lectures) < 4:
                sample_lectures.append(
                    {
                        "video_id": watch_vid,
                        "title": content,
                        "url": f"https://www.youtube.com/watch?v={watch_vid}&list={cid}",
                    }
                )

    if not channel and rows:
        first_parts = rows[0].get("metadataParts") or []
        if first_parts:
            channel = (first_parts[0].get("text", {}).get("content") or "").strip()

    thumb_vm = (
        lv.get("contentImage", {})
        .get("collectionThumbnailViewModel", {})
        .get("primaryThumbnail", {})
        .get("thumbnailViewModel", {})
    )
    sources = thumb_vm.get("image", {}).get("sources") or []
    thumbnail = sources[-1]["url"] if sources else ""

    lesson_count = 0
    for ov in thumb_vm.get("overlays") or []:
        badges = ov.get("thumbnailOverlayBadgeViewModel", {}).get("thumbnailBadges") or []
        for b in badges:
            btxt = b.get("thumbnailBadgeViewModel", {}).get("text") or ""
            cnt = parse_lesson_count(btxt)
            if cnt:
                lesson_count = cnt
                break

    embed_vid = sample_lectures[0]["video_id"] if sample_lectures else ""
    if not embed_vid and thumbnail:
        m = re.search(r"/vi/([A-Za-z0-9_-]{11})/", thumbnail)
        if m:
            embed_vid = m.group(1)

    return {
        "provider": "playlist",
        "video_id": cid,
        "embed_video_id": embed_vid,
        "url": f"https://www.youtube.com/playlist?list={cid}",
        "title": title,
        "channel": channel or "UP Board Faculty",
        "channel_url": channel_url,
        "thumbnail": thumbnail,
        "lesson_count": lesson_count,
        "duration": "",
        "duration_sec": 0,
        "views_text": "",
        "view_count": 0,
        "published": "",
        "sample_lectures": sample_lectures,
    }


def _parse_legacy_playlist(pr: dict) -> dict | None:
    cid = (pr.get("playlistId") or "").strip()
    title = (pr.get("title", {}).get("simpleText") or "").strip()
    if not cid or not title or cid.startswith("RD"):
        return None
    runs = pr.get("shortBylineText", {}).get("runs") or pr.get("longBylineText", {}).get("runs") or []
    channel = (runs[0].get("text") if runs else "").strip() or "UP Board Faculty"
    thumbs = pr.get("thumbnails", [{}])[0].get("thumbnails") or []
    thumbnail = thumbs[-1].get("url", "") if thumbs else ""
    embed_vid = ""
    if thumbnail:
        m = re.search(r"/vi/([A-Za-z0-9_-]{11})/", thumbnail)
        if m:
            embed_vid = m.group(1)
    lesson_count = parse_lesson_count(pr.get("videoCount") or "")
    return {
        "provider": "playlist",
        "video_id": cid,
        "embed_video_id": embed_vid,
        "url": f"https://www.youtube.com/playlist?list={cid}",
        "title": title,
        "channel": channel,
        "channel_url": "",
        "thumbnail": thumbnail,
        "lesson_count": lesson_count,
        "duration": "",
        "duration_sec": 0,
        "views_text": "",
        "view_count": 0,
        "published": "",
        "sample_lectures": [],
    }


def _parse_video(vr: dict) -> dict | None:
    vid = (vr.get("videoId") or "").strip()
    runs = vr.get("title", {}).get("runs") or []
    title = "".join(r.get("text", "") for r in runs).strip()
    if not vid or not title or len(vid) != 11:
        return None

    owner_runs = vr.get("ownerText", {}).get("runs") or vr.get("longBylineText", {}).get("runs") or []
    channel = (owner_runs[0].get("text") if owner_runs else "").strip() or "UP Board Faculty"
    channel_url = ""
    if owner_runs:
        wurl = (
            owner_runs[0]
            .get("navigationEndpoint", {})
            .get("commandMetadata", {})
            .get("webCommandMetadata", {})
            .get("url")
            or ""
        )
        if wurl:
            channel_url = f"https://www.youtube.com{wurl}"

    length_text = (vr.get("lengthText", {}).get("simpleText") or "").strip()
    dur_sec = parse_duration_seconds(length_text)

    views_text = (vr.get("viewCountText", {}).get("simpleText") or "").strip()
    view_count = parse_views(views_text)
    published = (vr.get("publishedTimeText", {}).get("simpleText") or "").strip()

    thumbs = vr.get("thumbnail", {}).get("thumbnails") or []
    thumbnail = thumbs[-1].get("url", "") if thumbs else f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"

    return {
        "provider": "youtube",
        "video_id": vid,
        "embed_video_id": vid,
        "url": f"https://www.youtube.com/watch?v={vid}",
        "title": title,
        "channel": channel,
        "channel_url": channel_url,
        "thumbnail": thumbnail,
        "lesson_count": 0,
        "duration": length_text,
        "duration_sec": dur_sec,
        "views_text": views_text,
        "view_count": view_count,
        "published": published,
        "sample_lectures": [],
    }


def is_verified_upboard_channel(channel: str) -> bool:
    low = channel.casefold()
    if CHANNEL_REJECT_RE.search(low):
        return False
    return any(p in low for p in VERIFIED_CHANNEL_PATTERNS)


def resolve_institute(cand: dict) -> str:
    ch_low = cand["channel"].casefold()

    if any(k in ch_low for k in ("vidyakul", "jay mahadev", "science deewane")):
        return "Vidyakul (Jay Mahadev & UP Board)"
    if "shubham classes" in ch_low or "shubham lecturer" in ch_low:
        return "Shubham Classes & Shubham Lecturer"
    if "gyansindhu" in ch_low or "gyan sindhu" in ch_low or "ravikant mani" in ch_low:
        return "Gyansindhu Coaching Classes"
    if "rwa" in ch_low or "rojgar with ankit" in ch_low:
        return "RWA Tuition Classes"
    if "ashish singh" in ch_low:
        return "Ashish Singh Lectures (ASL)"
    if "learn and share" in ch_low or "learn & share" in ch_low:
        return "Learn and Share"
    if any(k in ch_low for k in ("pw up board", "pw hindi medium", "physics wallah", "udaan")):
        return "PW UP Board & Hindi Medium"
    if "vikram singh" in ch_low or "vikram hap" in ch_low or "doubtnut" in ch_low:
        return "Vikram Singh & Doubtnut Hindi"
    if "xpclasses" in ch_low or "xp classes" in ch_low or "alpha institute" in ch_low or "mathematics analysis" in ch_low or "up board classes" in ch_low:
        return "XPclasses, Alpha & Maths Specialists"
    if "gyanoday" in ch_low or "shravan lecturer" in ch_low or "samrat academy" in ch_low:
        return "Gyanoday Ke Guru Ji & Shravan Lecturer"
    if any(k in ch_low for k in ("mk sir inspiration", "smart study", "skm study", "shiv coaching", "mobile par school", "srishti up board")):
        return "MK Sir, SKM & Smart Study"
    if any(k in ch_low for k in ("science sangrah", "disha online", "disha science", "disha hindi", "target board", "pankaj study")):
        return "Science Sangrah, Disha & Target Board"
    if any(k in ch_low for k in ("utkarsh", "ekaksha", "e-kaksha", "mission gyan", "magnet brains")):
        return "Utkarsh, Ekaksha & Magnet Brains"
    if any(k in ch_low for k in ("dear sir", "english connection", "diamond academic", "simran sahni", "extraclass")):
        return "Dear Sir & English Specialists"
    return "UP Board Specialists"


def resolve_educator(cand: dict, subject: str, unit: str) -> str:
    blob = f"{cand['title']} {cand['channel']}".casefold()
    ch_low = cand["channel"].casefold()

    teacher_rules = [
        (r"gyansindhu|gyan sindhu|arunesh\s*sir", "Arunesh Sir (Gyansindhu Coaching)"),
        (r"ravikant mani tripathi", "Ravikant Mani Tripathi Sir"),
        (r"jay mahadev|up board hindi medium\s*-\s*vidyakul", "Jay Mahadev Vidyakul (UP Board)"),
        (r"up board high school.*vidyakul", "UP Board High School (Vidyakul)"),
        (r"science deewane", "Science Deewane Vidyakul"),
        (r"vidyakul", "Vidyakul UP Board"),
        (r"shubham classes", "Shubham Classes (Sudhir Sir)"),
        (r"shubham lecturer", "Shubham Lecturer"),
        (r"rwa tuition|up board.*rwa|rojgar with ankit", "RWA Tuition Classes"),
        (r"ashish singh lectures", "Ashish Singh Sir (ASL)"),
        (r"learn and share|learn & share", "Learn and Share (Nikhil & Rahul Sir)"),
        (r"vikram singh|vikram hap", "Vikram Singh Sir"),
        (r"pw up board english medium", "PW UP Board (English Medium)"),
        (r"pw up board", "PW UP Board"),
        (r"pw hindi medium", "PW Hindi Medium"),
        (r"udaan", "PW Udaan"),
        (r"physics wallah", "Physics Wallah (Board)"),
        (r"gyanoday ke guru", "Shivam Sir (Gyanoday Ke Guru Ji)"),
        (r"xpclasses|xp classes", "XPclasses UP Board"),
        (r"alpha institute", "Alpha Institute"),
        (r"mk sir inspiration", "MK Sir Inspiration"),
        (r"shravan lecturer", "Shravan Lecturer"),
        (r"smart study classes", "Smart Study Classes"),
        (r"samrat academy", "Samrat Academy"),
        (r"skm study", "SKM Study"),
        (r"shiv coaching", "Shiv Coaching Classes"),
        (r"mathematics analysis", "Mathematics Analysis"),
        (r"up board classes", "UP Board Classes (Balaji Maths)"),
        (r"srishti up board", "Srishti UP Board Toppers"),
        (r"science sangrah", "Anu Sir (Science Sangrah)"),
        (r"disha online|disha science|disha hindi", "Sanjay Sir (Disha Online)"),
        (r"target board", "Prince Sir (Target Board)"),
        (r"doubtnut", "Doubtnut Hindi Medium"),
        (r"utkarsh online", "Utkarsh Online Tuition"),
        (r"ekaksha|e-kaksha|mission gyan", "Mission Gyan (e-Kaksha)"),
        (r"magnet brains", "Magnet Brains Hindi Medium"),
        (r"dear sir", "Dear Sir"),
        (r"english connection", "Kanchan Ma'am (English Connection)"),
        (r"diamond academic", "Diamond Academic Classes"),
        (r"simran sahni", "Simran Sahni"),
        (r"pankaj study centre", "Pankaj Sir (Pankaj Study Centre)"),
    ]
    for pat, label in teacher_rules:
        if re.search(pat, ch_low) or re.search(pat, blob):
            return label

    return cand["channel"]


def resolve_language(cand: dict, ch_no: int) -> str:
    if ch_no in (36, 37, 46, 47):
        return "Hindi Medium"
    title_low = cand["title"].casefold()
    blob = f"{cand['title']} {cand['channel']}".casefold()
    if ch_no in (38, 48) and not re.search(r"हिंदी माध्यम|\bhindi\s+medium\b", title_low):
        return "English"
    if re.search(r"\benglish\s+medium\b|\bin\s+english\b", blob) and not re.search(r"\bhindi\s+medium\b", blob):
        if not re.search(r"[\u0900-\u097F]", cand["title"]):
            return "English"
    return "Hindi Medium"


def classify_exam_and_format(cand: dict, class_lvl: str) -> tuple[str, str]:
    title_low = cand["title"].casefold()

    rev_re = re.compile(
        r"(?:\b(?:pyq\w*|previous\s+year|unsolved|model\s+paper|viral\s+paper|vvi\b|"
        r"most\s+important|objective|mcq\w*|revision|formula|numericals?)\b|"
        r"महत्वपूर्ण प्रश्न|मॉडल पेपर|अनसॉल्वड|बहुविकल्पीय|वायरल|रिवीजन|आंकिक प्रश्न)",
        re.I,
    )

    if cand["provider"] == "playlist":
        fmt = "Revision & PYQs" if rev_re.search(title_low) else "Full Course"
    else:
        if rev_re.search(title_low) and cand["duration_sec"] < 14400 and "one shot" not in title_low and "वन शॉट" not in title_low:
            fmt = "Revision & PYQs"
        else:
            fmt = "One-Shot"

    exam = "UP Board Class 12" if class_lvl == "Class 12" else "UP Board Class 10"
    return exam, fmt


def is_valid_chapter_candidate(
    cand: dict,
    ch_no: int,
    subject: str,
    class_lvl: str,
    chapter_re: re.Pattern[str],
) -> bool:
    title = cand["title"]
    channel = cand["channel"]

    # 1. Must belong to our Verified UP Board / Hindi Medium Board Channel allowlist
    if not is_verified_upboard_channel(channel):
        return False

    # 2. Reject competitive job exams, regional languages, rumours, copy-checking clickbait, shorts
    if HARD_REJECT_RE.search(title):
        return False

    # 3. Strict Class-Level Isolation (Class 12 vs Class 10 vs Class 6/7/8/9/11)
    has_lower = bool(
        re.search(
            r"\b(?:class|kaksha)\s*(?:6|7|8|9|11|6th|7th|8th|9th|11th|ix|xi)\b|"
            r"\b(?:9th|11th)\s+(?:maths|physics|chemistry|biology|science|hindi|english)\b|"
            r"कक्षा\s*(?:6|7|8|9|11)(?!\d)",
            title,
            re.I,
        )
    )
    has_10 = bool(
        re.search(
            r"\b(?:class|kaksha)\s*(?:10|10th|x)\b|\b10th\b|कक्षा\s*10(?!\d)|"
            r"हाई\s*स्कूल|हाईस्कूल|\bhigh\s+school\b|\bmatric\b",
            title,
            re.I,
        )
    )
    has_12 = bool(
        re.search(
            r"\b(?:class|kaksha)\s*(?:12|12th|xii)\b|\b12th\b|कक्षा\s*12(?!\d)|"
            r"इंटरमीडिएट|\bintermediate\b",
            title,
            re.I,
        )
    )

    if "rojgar with ankit" in channel.casefold() and "tuition" not in channel.casefold() and "rwa" not in channel.casefold():
        if not (has_10 or has_12 or re.search(r"\bboard\b|बोर्ड", title, re.I)):
            return False

    if class_lvl == "Class 12":
        if has_lower and not has_12:
            return False
        if has_10 and not has_12:
            return False
        if not has_12 and re.search(r"\b(class\s*10|high\s*school|10th)\b", channel, re.I) and not re.search(r"\b(12|12th)\b", channel, re.I):
            return False
    else:  # Class 10
        if has_lower and not has_10:
            return False
        if has_12 and not has_10:
            return False
        if not has_10 and re.search(r"\b(class\s*12|12th)\b", channel, re.I) and not re.search(r"\b(10|10th)\b", channel, re.I):
            return False

    # Language chapters must carry explicit class cue OR class-specific textbook/chapter cue
    if ch_no in (36, 37, 38):
        c12_lit_cue = bool(
            re.search(
                r"(?:काव्यांजलि|संस्कृत दिग्दर्शिका|सामान्य हिंदी|सामान्य हिन्दी|साहित्यिक हिंदी|"
                r"साहित्यिक परिचय|पवन दूतिका|कैकेयी का अनुताप|श्रद्धा मनु|राष्ट्र का स्वरूप|"
                r"अशोक के फूल|पंचलाइट|बहादुर|रश्मिरथी|\b(?:flamingo|vistas|last\s+lesson|lost\s+spring|"
                r"deep\s+water|rattrap|indigo|tiger\s+king|synthesis)\b)",
                title,
                re.I,
            )
        )
        if not (has_12 or c12_lit_cue or re.search(r"\b12(?:th)?\b", channel, re.I)):
            return False
    elif ch_no in (46, 47, 48):
        c10_lit_cue = bool(
            re.search(
                r"(?:अनिवार्य संस्कृत|संस्कृत परिचायिका|मित्रता|ममता|सूरदास के पद|वाराणसी|"
                r"भारतीय संस्कृति|प्रबुद्धो ग्रामीणः|रोला|सोरठा|\b(?:first\s+flight|footprints|"
                r"letter\s+to\s+god|nelson\s+mandela|bholi|dust\s+of\s+snow|triumph\s+of\s+surgery)\b)",
                title,
                re.I,
            )
        )
        if not (has_10 or c10_lit_cue or re.search(r"\b(?:10(?:th)?|high\s*school)\b", channel, re.I)):
            return False

    # 4. Prevent Cross-Chapter Collisions on Shared Umbrella Terms
    if ch_no == 1 and re.search(r"(?:प्रतिलोम त्रिकोणमितीय|\binverse\s+trigonometr|\bitf\b)", title, re.I):
        return False
    if ch_no == 5 and re.search(r"(?:अवकलज के अनुप्रयोग|अवकलजों के अनुप्रयोग|\bapplications?\s+of\s+derivatives?|अवकल समीकरण|\bdifferential\s+equations?)", title, re.I):
        return False
    if ch_no == 7 and re.search(r"(?:समाकलनों के अनुप्रयोग|समाकलन के अनुप्रयोग|\bapplications?\s+of\s+integrals?|\barea\s+under|अवकल समीकरण|\bdifferential\s+equations?)", title, re.I):
        return False
    if ch_no == 11 and re.search(r"(?:विभव तथा धारिता|\bpotential\s*(?:and|&)\s*capacitance\b)", title, re.I) and not re.search(r"(?:आवेश|\bcharges?\b|\bgauss\b|कूलाम)", title, re.I):
        return False
    if ch_no == 13 and re.search(r"(?:प्रत्यावर्ती धारा|\balternating\s+current\b|चुंबकीय प्रभाव|\bmagnetic\s+effect)", title, re.I):
        return False
    if ch_no == 17 and re.search(r"(?:तरंग प्रकाशिकी|\bwave\s+optics\b)", title, re.I) and not re.search(r"(?:किरण|\bray\b)", title, re.I):
        return False
    if ch_no == 18 and re.search(r"(?:किरण प्रकाशिकी|\bray\s+optics\b)", title, re.I) and not re.search(r"(?:तरंग|\bwave\b)", title, re.I):
        return False
    if ch_no == 21:
        # Guard English word "Solutions" against "Model Paper Solutions" / Maths / Physics solutions
        if not re.search(r"(?:विलयन|\bvilayan\b|\bvilyan\b|\bcolligative\b|\braoult|अणुसंख्य|मोलरता|परासरण)", title, re.I):
            if not re.search(r"(?:रसायन|\bchemistry\b|\brasayan\b)", title, re.I):
                return False
            if re.search(r"\b(?:paper\s+solutions?|unsolved|sample\s+paper|model\s+paper)\b", title, re.I):
                return False
    if ch_no == 41 and re.search(r"(?:वृत्तों से संबंधित क्षेत्रफल|\bareas?\s+related\s+to\s+circles?\b|त्रिकोणमिति|\btrigonometr)", title, re.I):
        return False

    # 5. Reject full-subject megacompilations for playlists unless chapter-specific
    if cand["provider"] == "playlist" and ch_no not in (36, 37, 38, 46, 47, 48):
        if re.search(r"\ball\s+chapters\b|\bcomplete\s+(?:physics|chemistry|maths|biology)\s+playlist\b", title, re.I):
            if not chapter_re.search(title):
                return False

    # 6. Avoid isolated mid-series short lecture fragments ("Part 16", "Lec 14", "L-9") for single videos
    if cand["provider"] == "youtube" and 0 < cand["duration_sec"] < 3600:
        if re.search(r"(?:^|\b)(?:part|lec(?:ture)?|ep(?:isode)?|l)\s*[-#.]?\s*(?:[3-9]|\d{2,})\b|^#\d+\b", title, re.I):
            if not re.search(r"(?:\b(?:one\s*shot|marathon|complete|pyq|model\s*paper|vvi|revision)\b|वन शॉट|मैराथन|सम्पूर्ण|संपूर्ण|महत्वपूर्ण)", title, re.I):
                return False

    # 7. Strict Chapter-Title Keyword Match
    if not chapter_re.search(title):
        return False

    # 8. Cross-Subject Guards (evaluated on hashtag-stripped title so multi-subject channel names never false-reject!)
    title_clean = re.sub(r"#\w+", "", title)
    if subject == "Class 12 गणित (Maths)":
        if re.search(r"(?:भौतिकी|भौतिक विज्ञान|रसायन|जीव विज्ञान|\b(?:physics|chemistry|biology)\b)", title_clean, re.I):
            return False
    elif subject == "Class 12 भौतिकी (Physics)":
        if re.search(r"(?:रसायन विज्ञान|वैद्युत रसायन|जीव विज्ञान|गणित|\b(?:chemistry|electrochemistry|biology|maths|mathematics)\b)", title_clean, re.I):
            return False
    elif subject == "Class 12 रसायन (Chemistry)":
        if re.search(r"(?:भौतिकी|भौतिक विज्ञान|जीव विज्ञान|गणित|\b(?:physics|biology|maths|mathematics)\b)", title_clean, re.I):
            return False
    elif subject == "Class 12 जीव विज्ञान व भाषा":
        if ch_no <= 35:  # Biology
            if re.search(r"(?:भौतिकी|रसायन|गणित|\b(?:physics|chemistry|maths|mathematics)\b)", title_clean, re.I):
                return False
        else:  # Class 12 Hindi & English
            if re.search(
                r"(?:भौतिकी|भौतिक विज्ञान|रसायन|गणित|जीव विज्ञान|वैद्युत|समाकलन|अवकलन|विलयन|"
                r"\b(?:physics|chemistry|maths|mathematics|biology|solutions?\s+class\s*12|electrostatics|calculus)\b)",
                title_clean,
                re.I,
            ):
                return False
    elif subject == "Class 10 गणित व विज्ञान":
        if ch_no <= 43:  # Class 10 Maths
            if re.search(r"(?:सामाजिक विज्ञान|रसायन|जीव विज्ञान|\b(?:science|physics|chemistry|biology|social\s+science|history|geography|civics|economics)\b)", title_clean, re.I):
                return False
        else:  # Class 10 Science
            if re.search(r"(?:सामाजिक विज्ञान|गणित|\b(?:maths|mathematics|social\s+science|history|geography|civics|economics)\b)", title_clean, re.I):
                return False
    elif subject == "Class 10 हिंदी, English व सामाजिक विज्ञान":
        if ch_no in (46, 47):  # Class 10 Hindi
            if re.search(r"(?:सामाजिक विज्ञान|विज्ञान|गणित|\b(?:science|social\s+science|maths|mathematics|physics|chemistry|biology|english\s+grammar)\b)", title_clean, re.I):
                return False
        elif ch_no == 48:  # Class 10 English
            if re.search(r"(?:सामाजिक विज्ञान|विज्ञान|गणित|हिंदी व्याकरण|\b(?:science|social\s+science|maths|mathematics|physics|chemistry|biology|history|geography|civics|economics)\b)", title_clean, re.I):
                return False
        else:  # Class 10 Social Science (Ch 49-50)
            if re.search(r"(?:गणित|रसायन|भौतिकी|जीव प्रक्रम|जैव प्रक्रम|\b(?:maths|mathematics|physics|chemistry|biology)\b)", title_clean, re.I):
                return False

    # 9. Duration & Lesson Count Floor
    if cand["provider"] == "playlist":
        if cand["lesson_count"] == 1:
            return False
    else:
        min_sec = 600 if ch_no in (36, 37, 38, 46, 47, 48) else 900
        if 0 < cand["duration_sec"] < min_sec:
            return False

    return True


def parse_age_months(published_text: str) -> float:
    """Parse YouTube relative published text ('3 weeks ago', 'Streamed 4 months ago') into months."""
    if not published_text:
        return 18.0
    low = published_text.lower()
    m = re.search(r"(\d+)\s*(hour|day|week|month|year)", low)
    if not m:
        return 18.0
    n = float(m.group(1))
    unit = m.group(2)
    if unit == "hour":
        return 0.15
    if unit == "day":
        return max(0.2, n / 30.0)
    if unit == "week":
        return max(0.3, (n * 7.0) / 30.0)
    if unit == "month":
        return max(0.5, n)
    if unit == "year":
        return max(12.0, n * 12.0)
    return 18.0


def compute_trend_metrics(cand: dict, fmt: str) -> tuple[float, int, float, str]:
    """Compute pure YouTube audience trend score with ZERO coaching/institute priority.

    Returns (age_months, views_per_month, trend_score, trend_badge).
    """
    if cand["provider"] == "playlist":
        lessons = cand["lesson_count"]
        t_score = 64.0 + min(lessons, 45) * 0.42 + (3.5 if cand.get("sample_lectures") else 0.0)
        badge = f"📚 {lessons} Lectures" if lessons else "📚 Full Playlist"
        return 12.0, 0, round(t_score, 2), badge

    views = max(int(cand.get("view_count") or 0), 1)
    age_m = parse_age_months(cand.get("published") or "")
    vpm = int(round(views / max(age_m, 0.75)))

    # Pure YouTube traction formula: monthly view velocity + total student reach + freshness
    velocity_pts = math.log10(max(vpm, 1)) * 13.5
    reach_pts = math.log10(views) * 9.5
    freshness_pts = 8.0 if age_m <= 6.0 else (4.5 if age_m <= 14.0 else (2.0 if age_m <= 24.0 else 0.0))
    depth_pts = 3.5 if cand.get("duration_sec", 0) >= 5400 else 1.5
    t_score = round(velocity_pts + reach_pts + freshness_pts + depth_pts, 2)

    if vpm >= 35_000 or (age_m <= 8.0 and views >= 120_000):
        badge = "🔥 Trending"
    elif views >= 1_000_000:
        badge = "⭐ Most Loved"
    elif views >= 250_000 or vpm >= 12_000:
        badge = "📈 Popular"
    else:
        badge = f"⚡ {fmt}"

    return round(age_m, 1), vpm, t_score, badge


def build_pedagogy_note(cand: dict, educator: str, exam: str, fmt: str, chapter_name: str) -> str:
    if cand["provider"] == "playlist":
        lessons = f"{cand['lesson_count']}-lecture " if cand["lesson_count"] else "Complete "
        return f"{lessons}YouTube playlist by {educator} · {exam} ({chapter_name})."
    parts = []
    if cand["duration"]:
        parts.append(f"{cand['duration']} {fmt.lower()}")
    else:
        parts.append(fmt)
    parts.append(f"by {educator}")
    if cand["views_text"]:
        parts.append(f"· {cand['views_text']}")
    return " ".join(parts)


def build_corpus(use_cache: bool = True) -> dict:
    compiled_chapters = []
    chapter_tasks = []
    for row in SYLLABUS:
        ch_no, subject, unit, class_lvl, weightage, scope, ch_name, pat, pl_qs, vid_qs = row
        cre = re.compile(pat, re.I)
        compiled_chapters.append((ch_no, subject, unit, class_lvl, weightage, scope, ch_name, cre))
        for pq in pl_qs:
            chapter_tasks.append(("chapter", ch_no, subject, class_lvl, cre, pq, SP_PLAYLIST_ONLY))
        for vq in vid_qs:
            chapter_tasks.append(("chapter", ch_no, subject, class_lvl, cre, vq, SP_LONG_VIDEOS))

    for subj, tq in TEACHER_PLAYLIST_SWEEPS:
        chapter_tasks.append(("sweep", 0, subj, "", None, tq, SP_PLAYLIST_ONLY))
    for subj, vq in INSTITUTE_VIDEO_SWEEPS:
        chapter_tasks.append(("sweep", 0, subj, "", None, vq, SP_LONG_VIDEOS))

    print(
        f"Executing {len(chapter_tasks)} YouTube InnerTube queries across {len(SYLLABUS)} UPMSP chapters...",
        flush=True,
    )

    raw_results: dict[int, list[dict]] = {row[0]: [] for row in SYLLABUS}
    sweep_candidates: list[tuple[str, dict]] = []

    def worker(task):
        kind, ch_no, subject, class_lvl, cre, query, sp = task
        payload = search_youtube(query, params=sp, use_cache=use_cache)
        cands = extract_candidates(payload)
        if kind == "chapter":
            kept = [c for c in cands if is_valid_chapter_candidate(c, ch_no, subject, class_lvl, cre)]
            return kind, ch_no, subject, kept
        return kind, 0, subject, cands

    with ThreadPoolExecutor(max_workers=24) as pool:
        futures = [pool.submit(worker, t) for t in chapter_tasks]
        for fut in as_completed(futures):
            kind, ch_no, subject, items = fut.result()
            if kind == "chapter":
                raw_results[ch_no].extend(items)
            else:
                for c in items:
                    sweep_candidates.append((subject, c))

    # Route educator-sweep items into matching chapters (check specialized/grammar chapters before umbrella ones)
    specialized_first = {2, 4, 6, 8, 12, 16, 18, 37, 38, 42, 43, 47, 48}
    priority_chapters = sorted(
        compiled_chapters,
        key=lambda c: (0 if c[0] in specialized_first else 1, c[0]),
    )
    for subj, cand in sweep_candidates:
        for ch_no, c_subj, _, c_lvl, _, _, _, cre in priority_chapters:
            if c_subj == subj and is_valid_chapter_candidate(cand, ch_no, c_subj, c_lvl, cre):
                raw_results[ch_no].append(cand)
                break

    processing_order = sorted(
        compiled_chapters,
        key=lambda c: (0 if c[0] in specialized_first else 1, c[0]),
    )

    seen_global: set[tuple[str, str]] = set()
    chapter_records_map: dict[int, list[dict]] = {}
    chapter_meta_map: dict[int, dict] = {}

    for ch_no, subject, unit, class_lvl, weightage, scope, ch_name, _ in processing_order:
        candidates = raw_results[ch_no]

        enriched = []
        seen_local: set[tuple[str, str]] = set()
        for cand in candidates:
            gkey = (cand["provider"], cand["video_id"])
            if gkey in seen_global or gkey in seen_local:
                continue
            seen_local.add(gkey)
            exam, fmt = classify_exam_and_format(cand, class_lvl)
            age_m, vpm, t_score, t_badge = compute_trend_metrics(cand, fmt)
            enriched.append((t_score, age_m, vpm, t_badge, exam, fmt, cand))

        # Pure YouTube Trend & Popularity pools — ZERO artificial institute priority
        videos_pool = sorted(
            [x for x in enriched if x[6]["provider"] == "youtube"],
            key=lambda x: (-x[0], -x[2], -x[6]["view_count"]),
        )
        playlists_pool = sorted(
            [x for x in enriched if x[6]["provider"] == "playlist"],
            key=lambda x: (-x[0], -x[6]["lesson_count"]),
        )

        unique_ch: list[dict] = []
        edu_cap: dict[str, int] = {}

        def _try_take(pool_items: list, limit_count: int, per_edu_max: int) -> None:
            for t_score, age_m, vpm, t_badge, exam, fmt, cand in pool_items:
                if len(unique_ch) >= limit_count:
                    break
                gkey = (cand["provider"], cand["video_id"])
                if gkey in seen_global:
                    continue
                institute = resolve_institute(cand)
                educator = resolve_educator(cand, subject, unit)
                ekey = f"{educator.casefold()}::{cand['provider']}"
                if edu_cap.get(ekey, 0) >= per_edu_max:
                    continue
                seen_global.add(gkey)
                edu_cap[ekey] = edu_cap.get(ekey, 0) + 1
                lang = resolve_language(cand, ch_no)

                unique_ch.append(
                    {
                        "provider": cand["provider"],
                        "video_id": cand["video_id"],
                        "embed_video_id": cand["embed_video_id"],
                        "url": cand["url"],
                        "title": cand["title"],
                        "channel": cand["channel"],
                        "channel_url": cand["channel_url"],
                        "institute": institute,
                        "educator": educator,
                        "language": lang,
                        "thumbnail": cand["thumbnail"],
                        "subject": subject,
                        "unit": unit,
                        "chapter_no": ch_no,
                        "chapter": ch_name,
                        "class_level": class_lvl,
                        "weightage": weightage,
                        "syllabus_scope": scope,
                        "target_exam": exam,
                        "format": fmt,
                        "lesson_count": cand["lesson_count"],
                        "duration": cand["duration"],
                        "duration_sec": cand["duration_sec"],
                        "views_text": cand["views_text"],
                        "view_count": cand["view_count"],
                        "published": cand["published"],
                        "age_months": age_m,
                        "views_per_month": vpm,
                        "trend_score": t_score,
                        "trend_badge": t_badge,
                        "score": t_score,
                        "note": build_pedagogy_note(cand, educator, exam, fmt, ch_name),
                        "sample_lectures": cand.get("sample_lectures") or [],
                    }
                )

        # Balanced selection purely by YouTube Trend & Popularity (12 top trending videos + 10 top playlists)
        _try_take(videos_pool, 12, 2)
        _try_take(playlists_pool, len(unique_ch) + 10, 2)
        if len(unique_ch) < 20:
            _try_take(videos_pool + playlists_pool, 22, 3)
        if len(unique_ch) < 10:
            _try_take(videos_pool + playlists_pool, 16, 5)

        # Sort strictly by pure YouTube trend_score, views_per_month, view_count — ZERO institute bias
        unique_ch.sort(
            key=lambda r: (
                -r["trend_score"],
                -r["views_per_month"],
                -r["view_count"],
                -r["lesson_count"],
            )
        )
        pl_cnt = sum(1 for r in unique_ch if r["provider"] == "playlist")

        yt_pl_q = urllib.parse.quote_plus(f"{ch_name.split('/')[0].strip()} {class_lvl} UP Board")
        yt_os_q = urllib.parse.quote_plus(f"{ch_name.split('/')[0].strip()} {class_lvl} UP Board one shot")

        chapter_records_map[ch_no] = unique_ch
        chapter_meta_map[ch_no] = {
            "chapter_no": ch_no,
            "subject": subject,
            "unit": unit,
            "class_level": class_lvl,
            "weightage": weightage,
            "syllabus_scope": scope,
            "chapter": ch_name,
            "count": len(unique_ch),
            "playlist_count": pl_cnt,
            "video_count": len(unique_ch) - pl_cnt,
            "yt_playlists_url": f"https://www.youtube.com/results?search_query={yt_pl_q}&sp=EgIQAw%253D%253D",
            "yt_oneshots_url": f"https://www.youtube.com/results?search_query={yt_os_q}&sp=EgIYAg%253D%253D",
        }

    # Assemble in canonical UPMSP syllabus order 1..50
    syllabus_out = [chapter_meta_map[n] for n in range(1, len(SYLLABUS) + 1)]
    all_entries: list[dict] = []
    for n in range(1, len(SYLLABUS) + 1):
        all_entries.extend(chapter_records_map[n])

    by_score = sorted(
        all_entries,
        key=lambda x: (-x["trend_score"], -x["views_per_month"], -x["view_count"], x["chapter_no"]),
    )
    for idx, rec in enumerate(by_score, 1):
        rec["global_rank"] = idx

    edu_buckets: dict[str, dict] = {}
    for rec in all_entries:
        edu = rec["educator"]
        if edu not in edu_buckets:
            edu_buckets[edu] = {
                "educator": edu,
                "subjects": Counter(),
                "total": 0,
                "playlists": 0,
                "videos": 0,
                "chapters": set(),
            }
        b = edu_buckets[edu]
        b["subjects"][rec["subject"]] += 1
        b["total"] += 1
        b["chapters"].add(rec["chapter_no"])
        if rec["provider"] == "playlist":
            b["playlists"] += 1
        else:
            b["videos"] += 1

    educators_out = []
    for edu, b in edu_buckets.items():
        primary_subject = b["subjects"].most_common(1)[0][0]
        educators_out.append(
            {
                "educator": edu,
                "subject": primary_subject,
                "total": b["total"],
                "playlists": b["playlists"],
                "videos": b["videos"],
                "chapter_coverage": len(b["chapters"]),
            }
        )
    educators_out.sort(
        key=lambda e: (
            -e["total"],
            -e["playlists"],
            e["educator"],
        )
    )

    inst_buckets: dict[str, dict] = {}
    for rec in all_entries:
        inst = rec["institute"]
        if inst not in inst_buckets:
            inst_buckets[inst] = {
                "institute": inst,
                "total": 0,
                "playlists": 0,
                "videos": 0,
                "chapters": set(),
            }
        ib = inst_buckets[inst]
        ib["total"] += 1
        ib["chapters"].add(rec["chapter_no"])
        if rec["provider"] == "playlist":
            ib["playlists"] += 1
        else:
            ib["videos"] += 1

    institutes_out = [
        {
            "institute": inst,
            "total": ib["total"],
            "playlists": ib["playlists"],
            "videos": ib["videos"],
            "chapter_coverage": len(ib["chapters"]),
        }
        for inst, ib in inst_buckets.items()
    ]
    institutes_out.sort(
        key=lambda i: (
            -i["total"],
            i["institute"],
        )
    )

    playlists_total = sum(1 for x in all_entries if x["provider"] == "playlist")
    chapters_with_pl = sum(1 for c in syllabus_out if c["playlist_count"] > 0)

    output = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "chapters_total": len(SYLLABUS),
            "chapters_populated": sum(1 for c in syllabus_out if c["count"] > 0),
            "chapters_with_playlists": chapters_with_pl,
            "entries_published": len(all_entries),
            "playlists_published": playlists_total,
            "videos_published": len(all_entries) - playlists_total,
            "distinct_institutes": len(institutes_out),
            "distinct_educators": len(educators_out),
            "distinct_channels": len({x["channel"].casefold() for x in all_entries}),
            "queries_executed": len(chapter_tasks),
            "live_requests": STATS["requests"],
            "cached_requests": STATS["cached"],
        },
        "institutes": institutes_out,
        "educators": educators_out,
        "syllabus": syllabus_out,
        "videos": all_entries,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def self_test() -> None:
    assert len(SYLLABUS) == 50, f"Expected 50 canonical UPMSP chapters, got {len(SYLLABUS)}"
    nums = [r[0] for r in SYLLABUS]
    assert nums == list(range(1, 51)), "Chapter numbers must be contiguous 1..50"

    subj_counts = Counter(r[1] for r in SYLLABUS)
    expected_subjects = {
        "Class 12 गणित (Maths)": 10,
        "Class 12 भौतिकी (Physics)": 10,
        "Class 12 रसायन (Chemistry)": 10,
        "Class 12 जीव विज्ञान व भाषा": 8,
        "Class 10 गणित व विज्ञान": 7,
        "Class 10 हिंदी, English व सामाजिक विज्ञान": 5,
    }
    assert dict(subj_counts) == expected_subjects, f"Subject counts mismatch: {dict(subj_counts)}"

    assert parse_views("1.8M views") == 1_800_000
    assert parse_views("425K views") == 425_000
    assert parse_duration_seconds("4:15:10") == 15310

    # Verify Devanagari matra/anusvara regex matching works cleanly (no broken \b on Hindi!)
    cre_prob12 = re.compile(SYLLABUS[9][7], re.I)
    hindi_vid = {
        "provider": "youtube",
        "video_id": "a1b2c3d4e5f",
        "title": "प्रायिकता वन शॉट | Class 12 Maths UP Board 2025",
        "channel": "Jay Mahadev Vidyakul",
        "lesson_count": 0,
        "duration_sec": 7200,
        "view_count": 350000,
        "sample_lectures": [],
    }
    assert is_valid_chapter_candidate(hindi_vid, 10, "Class 12 गणित (Maths)", "Class 12", cre_prob12)
    exam12, fmt12 = classify_exam_and_format(hindi_vid, "Class 12")
    assert exam12 == "UP Board Class 12" and fmt12 == "One-Shot"

    # Verify Class 10 is ACCEPTED on Class 10 chapters and REJECTED on Class 12 chapters
    cre_tri10 = re.compile(SYLLABUS[41][7], re.I)
    c10_vid = {
        "provider": "youtube",
        "video_id": "x1y2z3w4v5u",
        "title": "त्रिकोणमिति का परिचय One Shot | Class 10 Maths UP Board",
        "channel": "UP Board High School - Vidyakul",
        "lesson_count": 0,
        "duration_sec": 5400,
        "view_count": 520000,
        "sample_lectures": [],
    }
    assert is_valid_chapter_candidate(c10_vid, 42, "Class 10 गणित व विज्ञान", "Class 10", cre_tri10)
    assert not is_valid_chapter_candidate(c10_vid, 10, "Class 12 गणित (Maths)", "Class 12", cre_prob12)
    exam10, _ = classify_exam_and_format(c10_vid, "Class 10")
    assert exam10 == "UP Board Class 10"

    # Verify clickbait / result date / copy checking / spam channel rejection
    bad_clickbait = {
        "provider": "youtube",
        "video_id": "badclick123",
        "title": "UP Board Result Kab Aayega 2025 | Copy Checking Live प्रायिकता",
        "channel": "Jay Mahadev Vidyakul",
        "lesson_count": 0,
        "duration_sec": 1800,
        "view_count": 100000,
        "sample_lectures": [],
    }
    assert not is_valid_chapter_candidate(bad_clickbait, 10, "Class 12 गणित (Maths)", "Class 12", cre_prob12)

    bad_unverified = {
        "provider": "youtube",
        "video_id": "spamchan123",
        "title": "प्रायिकता Class 12 Maths One Shot UP Board",
        "channel": "Random Gaming & Vlogs",
        "lesson_count": 0,
        "duration_sec": 3600,
        "view_count": 50000,
        "sample_lectures": [],
    }
    assert not is_valid_chapter_candidate(bad_unverified, 10, "Class 12 गणित (Maths)", "Class 12", cre_prob12)

    print("self-test ok (50 canonical UPMSP Class 12 & 10 chapters, Devanagari regex & pure trend ranking validated)", flush=True)


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        self_test()
        return 0
    self_test()
    use_cache = "--fresh" not in argv
    out = build_corpus(use_cache=use_cache)
    m = out["meta"]
    inst_lines = "\n".join(
        f"  - {i['institute']:<38}: {i['total']:>4} ({i['playlists']:>3} PL, {i['videos']:>3} vids across {i['chapter_coverage']:>2} ch)"
        for i in out["institutes"]
    )
    min_ch = min(out["syllabus"], key=lambda c: c["count"])
    print(
        f"\n=== UPBOARDTUBE 50-CHAPTER CORPUS REPORT ===\n"
        f"Chapters populated      : {m['chapters_populated']} / {m['chapters_total']} (min count = {min_ch['count']} in Ch {min_ch['chapter_no']})\n"
        f"Chapters with playlists : {m['chapters_with_playlists']} / {m['chapters_total']}\n"
        f"Total UPMSP resources   : {m['entries_published']} ({m['playlists_published']} playlists, {m['videos_published']} lectures)\n"
        f"Distinct institutes     : {m['distinct_institutes']}\n"
        f"Distinct educators      : {m['distinct_educators']} ({m['distinct_channels']} verified channels)\n"
        f"Institute Breakdown:\n{inst_lines}\n"
        f"Output written to       : {OUT_PATH}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
