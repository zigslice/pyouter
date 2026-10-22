/**
 * Built-in UI themes: orange (default), blue, green.
 *
 *   import { setTheme, getTheme, themes } from '../ui/index.js';
 *   setTheme('blue');           // document.documentElement[data-gd-theme]
 *   setTheme('green', rootEl);  // scope to an element
 */

/** @typedef {'orange'|'blue'|'green'} GdThemeName */

/** @type {Record<GdThemeName, {label:string, primary:string, bg:string}>} */
export const themes = {
  orange: {
    label: 'Orange',
    primary: '#e86a17',
    bg: '#ffffff',
  },
  blue: {
    label: 'Blue',
    primary: '#2f6fed',
    bg: '#f3f6fb',
  },
  green: {
    label: 'Green',
    primary: '#2f8f5b',
    bg: '#f3f8f4',
  },
};

export const THEME_ATTR = 'data-gd-theme';

/** @type {GdThemeName} */
let currentTheme = 'orange';

/**
 * @param {string} name
 * @returns {name is GdThemeName}
 */
export function isThemeName(name) {
  return Object.prototype.hasOwnProperty.call(themes, name);
}

/**
 * Apply a named theme. Default target is <html>.
 * @param {GdThemeName|string} name
 * @param {HTMLElement|Document} [target]
 * @returns {GdThemeName}
 */
export function setTheme(name, target) {
  const theme = isThemeName(name) ? name : 'orange';
  const el =
    target && target.nodeType === 9
      ? /** @type {Document} */ (target).documentElement
      : target || (typeof document !== 'undefined' ? document.documentElement : null);

  if (el && el.setAttribute) {
    el.setAttribute(THEME_ATTR, theme);
  }
  currentTheme = theme;
  return theme;
}

/**
 * @param {HTMLElement|Document} [target]
 * @returns {GdThemeName}
 */
export function getTheme(target) {
  const el =
    target && target.nodeType === 9
      ? /** @type {Document} */ (target).documentElement
      : target || (typeof document !== 'undefined' ? document.documentElement : null);
  const fromDom = el?.getAttribute?.(THEME_ATTR);
  if (isThemeName(fromDom)) return fromDom;
  return currentTheme;
}

/**
 * Resolve ConfigProvider / setTheme input to a theme name or token map.
 * @param {string|{name?:string,algorithm?:string,token?:object}|null|undefined} theme
 * @returns {{ name?: GdThemeName, token?: object }}
 */
export function resolveThemeInput(theme) {
  if (theme == null || theme === '') return { name: undefined, token: undefined };
  if (typeof theme === 'string') {
    return { name: isThemeName(theme) ? theme : undefined, token: undefined };
  }
  const name = theme.name || theme.algorithm;
  return {
    name: isThemeName(name) ? name : undefined,
    token: theme.token || undefined,
  };
}
