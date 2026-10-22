import { cx, el, omit } from './util.js';

const TITLE_TAGS = { 1: 'h1', 2: 'h2', 3: 'h3', 4: 'h4', 5: 'h5' };

/**
 * @param {object} [props]
 * @param {1|2|3|4|5} [props.level]
 * @param {string} [props.text]
 */
export function Title(props = {}, ...children) {
  const { level = 3, className, text } = props;
  const tag = TITLE_TAGS[level] || 'h3';
  const kids = children.length ? children : text != null ? [text] : [];
  return el(
    tag,
    {
      ...omit(props, ['level', 'className', 'text']),
      className: cx('gd-title', `gd-title--${level}`, className),
    },
    ...kids
  );
}

/**
 * @param {object} [props]
 * @param {'default'|'secondary'|'muted'|'danger'} [props.type]
 * @param {boolean} [props.code]
 * @param {boolean} [props.small]
 */
export function Text(props = {}, ...children) {
  const { type = 'default', code, small, className, text, as = 'p' } = props;
  const kids = children.length ? children : text != null ? [text] : [];
  return el(
    as,
    {
      ...omit(props, ['type', 'code', 'small', 'className', 'text', 'as']),
      className: cx(
        'gd-text',
        type !== 'default' && `gd-text--${type}`,
        code && 'gd-text--code',
        small && 'gd-text--small',
        className
      ),
    },
    ...kids
  );
}
