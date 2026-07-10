/** Suggested starter questions — keep in sync with backend starter_faqs.py */

export const STARTER_QUESTIONS_EN = [
  "What products do you offer?",
  "What are your business hours?",
  "How do I contact support?",
  "What is your return policy?",
] as const;

export const STARTER_QUESTIONS_HI = [
  "आप कौन से उत्पाद या प्लान ऑफ़र करते हैं?",
  "आपके व्यापारिक घंटे क्या हैं?",
  "मैं सपोर्ट से कैसे संपर्क करूँ?",
  "आपकी रिटर्न पॉलिसी क्या है?",
] as const;

export function starterQuestionsForLanguage(
  replyLanguage?: string | null,
): string[] {
  return replyLanguage === "Hindi"
    ? [...STARTER_QUESTIONS_HI]
    : [...STARTER_QUESTIONS_EN];
}
