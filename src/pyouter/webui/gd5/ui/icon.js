import { cx, el, omit } from './util.js';

/** Built-in glyph map for common antd-like icons (text/emoji stand-ins). */
const GLYPHS = {
  search: '⌕',
  close: '×',
  check: '✓',
  plus: '+',
  minus: '−',
  edit: '✎',
  delete: '🗑',
  setting: '⚙',
  user: '☺',
  home: '⌂',
  menu: '☰',
  more: '⋯',
  left: '‹',
  right: '›',
  up: '⌃',
  down: '⌄',
  info: 'ℹ',
  warning: '⚠',
  star: '★',
  heart: '♥',
  link: '🔗',
  download: '⇩',
  upload: '⇧',
  calendar: '📅',
  mail: '✉',
};

/**
 * Icon — inline glyph (antd Icon simplified; no @ant-design/icons dependency).
 * @param {object} [props]
 * @param {string} [props.type] key in built-in map, or pass `text`
 * @param {string} [props.text] custom glyph
 * @param {'sm'|'md'|'lg'} [props.size]
 * @param {string} [props.spin]
 */
export function Icon(props = {}) {
  const { type, text, size = 'md', spin = false, className, rotate } = props;
  const glyph = text ?? GLYPHS[type] ?? type ?? '•';
  return el('span', {
    ...omit(props, ['type', 'text', 'size', 'spin', 'className', 'rotate']),
    className: cx(
      'gd-icon',
      `gd-icon--${size}`,
      spin && 'gd-icon--spin',
      className
    ),
    text: glyph,
    style: rotate != null ? { transform: `rotate(${rotate}deg)` } : undefined,
    attrs: { 'aria-hidden': 'true' },
  });
}

Icon.glyphs = GLYPHS;
