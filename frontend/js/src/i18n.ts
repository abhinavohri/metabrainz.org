type TranslationCatalog = Record<string, string>;
type Replacements = Record<string, string | number>;

let translations: TranslationCatalog = {};

export function initI18n(globalProps: Record<string, any>) {
  translations = globalProps.translations ?? {};
}

export function interpolate(message: string, replacements: Replacements = {}) {
  return Object.keys(replacements).reduce((text, key) => {
    return text.replace(
      new RegExp(`%\\(${key}\\)s`, "g"),
      String(replacements[key])
    );
  }, message);
}

export function gettext(message: string, replacements?: Replacements) {
  const translated = translations[message] ?? message;
  return replacements ? interpolate(translated, replacements) : translated;
}
