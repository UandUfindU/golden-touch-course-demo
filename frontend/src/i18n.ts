import { createContext, useContext } from 'react';

export type Language = 'en' | 'zh';

export const LanguageContext = createContext<Language>('en');

export function useText() {
  const language = useContext(LanguageContext);
  return (en: string, zh: string) => language === 'zh' ? zh : en;
}
