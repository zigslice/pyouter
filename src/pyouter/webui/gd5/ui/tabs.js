import { cx, el, omit } from './util.js';

/**
 * Tabs — label row + one active panel.
 * Controlled via `activeKey` + `onChange`.
 * @param {object} [props]
 * @param {Array<{key:string,label:string,content?:any,disabled?:boolean}>} [props.items]
 * @param {string} [props.activeKey]
 * @param {function} [props.onChange]
 */
export function Tabs(props = {}) {
  const { items = [], activeKey, onChange, className } = props;
  const key = activeKey ?? items[0]?.key;
  const active = items.find((it) => it.key === key) || items[0];

  return el(
    'div',
    {
      ...omit(props, ['items', 'activeKey', 'onChange', 'className']),
      className: cx('gd-tabs', className),
    },
    el(
      'div',
      { className: 'gd-tabs__list', role: 'tablist' },
      ...items.map((it) =>
        el('button', {
          type: 'button',
          role: 'tab',
          className: cx('gd-tabs__tab', it.key === key && 'gd-tabs__tab--active'),
          text: it.label,
          disabled: !!it.disabled,
          attrs: {
            'aria-selected': it.key === key ? 'true' : 'false',
          },
          onClick: () => onChange?.(it.key),
        })
      )
    ),
    el(
      'div',
      { className: 'gd-tabs__panel', role: 'tabpanel' },
      active?.content ?? null
    )
  );
}

/**
 * ToggleGroup / SegmentedControl — connected exclusive options.
 * @param {object} [props]
 * @param {Array<{value:string,label:string,disabled?:boolean}>} [props.options]
 * @param {string} [props.value]
 * @param {function} [props.onChange]
 */
export function ToggleGroup(props = {}) {
  const { options = [], value, onChange, className, size = 'md' } = props;
  return el(
    'div',
    {
      ...omit(props, ['options', 'value', 'onChange', 'className', 'size']),
      className: cx('gd-toggle-group', `gd-toggle-group--${size}`, className),
      role: 'group',
    },
    ...options.map((opt) =>
      el('button', {
        type: 'button',
        className: cx(
          'gd-toggle-group__item',
          opt.value === value && 'gd-toggle-group__item--active'
        ),
        text: opt.label,
        disabled: !!opt.disabled,
        onClick: () => onChange?.(opt.value),
      })
    )
  );
}

export const SegmentedControl = ToggleGroup;
