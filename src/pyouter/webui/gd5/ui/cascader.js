import { cx, el, omit } from './util.js';

/**
 * Cascader — multi-level select (antd Cascader).
 * Options: [{ value, label, children? }]
 * @param {object} [props]
 * @param {Array} [props.options]
 * @param {string[]} [props.value] path of values
 * @param {boolean} [props.open]
 * @param {function} [props.onChange]
 * @param {function} [props.onOpenChange]
 */
export function Cascader(props = {}) {
  const {
    options = [],
    value = [],
    open = false,
    onChange,
    onOpenChange,
    placeholder = 'Please select',
    className,
  } = props;

  const columns = [];
  let level = options;
  columns.push(level);
  for (const v of value) {
    const node = level.find((o) => o.value === v);
    if (node?.children?.length) {
      level = node.children;
      columns.push(level);
    } else break;
  }

  const labels = [];
  let walk = options;
  for (const v of value) {
    const node = walk.find((o) => o.value === v);
    if (!node) break;
    labels.push(node.label);
    walk = node.children || [];
  }

  return el(
    'div',
    {
      ...omit(props, ['options', 'value', 'open', 'onChange', 'onOpenChange', 'placeholder', 'className']),
      className: cx('gd-cascader', open && 'gd-cascader--open', className),
    },
    el('button', {
      type: 'button',
      className: 'gd-cascader__trigger',
      text: labels.length ? labels.join(' / ') : placeholder,
      onClick: () => onOpenChange?.(!open),
    }),
    open
      ? el(
          'div',
          { className: 'gd-cascader__menus' },
          ...columns.map((col, depth) =>
            el(
              'div',
              { className: 'gd-cascader__menu' },
              ...col.map((opt) => {
                const selected = value[depth] === opt.value;
                return el('button', {
                  type: 'button',
                  className: cx(
                    'gd-cascader__option',
                    selected && 'gd-cascader__option--active',
                    opt.children?.length && 'gd-cascader__option--parent'
                  ),
                  text: opt.children?.length ? `${opt.label} ›` : opt.label,
                  onClick: () => {
                    const next = [...value.slice(0, depth), opt.value];
                    onChange?.(next, opt);
                    if (!opt.children?.length) onOpenChange?.(false);
                  },
                });
              })
            )
          )
        )
      : null
  );
}
