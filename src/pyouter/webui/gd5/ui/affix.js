import { cx, el, omit } from './util.js';

/**
 * Affix — sticky wrapper with offset (antd Affix simplified via CSS sticky).
 * @param {object} [props]
 * @param {number} [props.offsetTop]
 * @param {number} [props.offsetBottom]
 */
export function Affix(props = {}, ...children) {
  const { offsetTop = 0, offsetBottom, className, style } = props;
  const s = { ...(typeof style === 'object' ? style : {}) };
  if (offsetBottom != null) {
    s.bottom = typeof offsetBottom === 'number' ? `${offsetBottom}px` : offsetBottom;
    s.top = 'auto';
  } else {
    s.top = typeof offsetTop === 'number' ? `${offsetTop}px` : offsetTop;
  }
  return el(
    'div',
    {
      ...omit(props, ['offsetTop', 'offsetBottom', 'className', 'style']),
      className: cx('gd-affix', className),
      style: s,
    },
    ...children
  );
}

/**
 * Anchor — in-page link list (antd Anchor). Similar to Scrollspy with ink.
 * @param {object} [props]
 * @param {Array<{key:string,href?:string,title:string}>} [props.items]
 * @param {string} [props.activeKey]
 * @param {function} [props.onChange]
 */
export function Anchor(props = {}) {
  const { items = [], activeKey, onChange, className, offsetTop = 0 } = props;
  return el(
    'div',
    {
      ...omit(props, ['items', 'activeKey', 'onChange', 'className', 'offsetTop']),
      className: cx('gd-anchor', className),
      style: { top: typeof offsetTop === 'number' ? `${offsetTop}px` : offsetTop },
    },
    el('div', { className: 'gd-anchor__ink' }),
    ...items.map((it) =>
      el('a', {
        className: cx('gd-anchor__link', it.key === activeKey && 'gd-anchor__link--active'),
        text: it.title,
        href: it.href || `#${it.key}`,
        onClick: (e) => {
          if (onChange) {
            e.preventDefault();
            onChange(it.key);
          }
        },
      })
    )
  );
}
