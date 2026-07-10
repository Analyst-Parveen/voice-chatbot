"""Curated answers for the widget's suggested starter questions.

These bypass RAG + LLM for instant, consistent replies in English and Hindi.
Content is drawn from company knowledge (sample_data/company.md, faqs.json)
and the helpdesk product/plan catalog.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.hindi_translator import is_hindi_mode

_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class StarterFaq:
    question_en: str
    question_hi: str
    answer_en: str
    answer_hi: str


STARTER_FAQS: tuple[StarterFaq, ...] = (
    StarterFaq(
        question_en="What products do you offer?",
        question_hi="आप कौन से उत्पाद या प्लान ऑफ़र करते हैं?",
        answer_en=(
            "We offer device protection plans for mobile phones and tablets, "
            "laptops and desktops, televisions, and home appliances. Our plans "
            "include Extended Warranty (EW), Screen Damage Protection (SDP), "
            "Accidental Damage Protection (ADP), and Combo Protection Plans "
            "(CPP) so your devices stay covered after the manufacturer warranty "
            "ends."
        ),
        answer_hi=(
            "हम मोबाइल और टैबलेट, लैपटॉप और डेस्कटॉप, टेलीविज़न तथा होम "
            "अप्लायंसेज़ के लिए डिवाइस प्रोटेक्शन प्लान ऑफ़र करते हैं। हमारे "
            "प्लान में Extended Warranty (EW), Screen Damage Protection (SDP), "
            "Accidental Damage Protection (ADP) और Combo Protection Plan (CPP) "
            "शामिल हैं, ताकि निर्माता वारंटी खत्म होने के बाद भी आपके डिवाइस "
            "सुरक्षित रहें।"
        ),
    ),
    StarterFaq(
        question_en="What are your business hours?",
        question_hi="आपके व्यापारिक घंटे क्या हैं?",
        answer_en=(
            "Our business hours are Monday to Friday, 9:00 AM to 6:00 PM. "
            "We are closed on weekends and public holidays."
        ),
        answer_hi=(
            "हमारे व्यापारिक घंटे सोमवार से शुक्रवार, सुबह 9:00 बजे से शाम "
            "6:00 बजे तक हैं। सप्ताहांत और सार्वजनिक अवकाशों पर हम बंद रहते हैं।"
        ),
    ),
    StarterFaq(
        question_en="How do I contact support?",
        question_hi="मैं सपोर्ट से कैसे संपर्क करूँ?",
        answer_en=(
            "You can reach our support team by email at support@acme.example "
            "or by phone at 1-800-555-0100 during business hours. Live chat is "
            "also available on our website whenever you need quick help."
        ),
        answer_hi=(
            "आप हमारी सपोर्ट टीम से support@acme.example पर ईमेल कर सकते हैं, "
            "या व्यापारिक घंटों में 1-800-555-0100 पर कॉल कर सकते हैं। तुरंत "
            "मदद के लिए हमारी वेबसाइट पर लाइव चैट भी उपलब्ध है।"
        ),
    ),
    StarterFaq(
        question_en="What is your return policy?",
        question_hi="आपकी रिटर्न पॉलिसी क्या है?",
        answer_en=(
            "You can return any unused product within 30 days of purchase for a "
            "full refund. Items must be in their original packaging."
        ),
        answer_hi=(
            "आप खरीद के 30 दिनों के भीतर किसी भी अप्रयुक्त उत्पाद को मूल "
            "पैकेजिंग में वापस कर पूर्ण रिफंड प्राप्त कर सकते हैं।"
        ),
    ),
)


def _normalize(text: str) -> str:
    return _WS_RE.sub(" ", text.strip().lower().rstrip("?.!।"))


def lookup_starter_answer(message: str, language: str | None) -> str | None:
    """Return a canned answer when *message* matches a starter question."""
    norm = _normalize(message)
    if not norm:
        return None
    for faq in STARTER_FAQS:
        if norm in (_normalize(faq.question_en), _normalize(faq.question_hi)):
            return faq.answer_hi if is_hindi_mode(language) else faq.answer_en
    return None


def get_starter_questions(language: str | None) -> list[str]:
    """Starter-question labels for the suggestions API."""
    if is_hindi_mode(language):
        return [f.question_hi for f in STARTER_FAQS]
    return [f.question_en for f in STARTER_FAQS]
