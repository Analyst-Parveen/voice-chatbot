import type { ChatLanguage } from "./types";

/** Languages available in Ask a Query mode (Hindi + English only). */
export const CHAT_LANGUAGES: ChatLanguage[] = [
  {
    id: "en-IN",
    label: "English",
    nativeLabel: "English",
    sttCode: "en",
    replyLanguage: "English",
  },
  {
    id: "hi-IN",
    label: "Hindi",
    nativeLabel: "हिंदी",
    sttCode: "hi",
    replyLanguage: "Hindi",
  },
];
