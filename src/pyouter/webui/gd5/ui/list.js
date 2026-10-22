import { cx, el, omit } from './util.js';

/**
 * List — data list with optional header/footer (antd List).
 * @param {object} [props]
 * @param {Array<object>} [props.dataSource]
 * @param {function} [props.renderItem] (item, index) => Element|string
 * @param {any} [props.header]
 * @param {any} [props.footer]
 * @param {boolean} [props.bordered]
 * @param {'default'|'small'|'large'} [props.size]
 */
export function List(props = {}, ...children) {
  const {
    dataSource = [],
    renderItem,
    header,
    footer,
    bordered = true,
    size = 'default',
    className,
    split = true,
  } = props;

  const items = children.length
    ? children
    : dataSource.map((item, i) => {
        const content = renderItem ? renderItem(item, i) : item.title ?? String(item);
        return ListItem(
          { key: item.key ?? i },
          typeof content === 'string' ? el('span', { text: content }) : content
        );
      });

  return el(
    'div',
    {
      ...omit(props, [
        'dataSource',
        'renderItem',
        'header',
        'footer',
        'bordered',
        'size',
        'className',
        'split',
      ]),
      className: cx(
        'gd-list',
        bordered && 'gd-list--bordered',
        split && 'gd-list--split',
        `gd-list--${size}`,
        className
      ),
    },
    header != null ? el('div', { className: 'gd-list__header' }, header) : null,
    el('ul', { className: 'gd-list__items' }, ...items),
    footer != null ? el('div', { className: 'gd-list__footer' }, footer) : null
  );
}

export function ListItem(props = {}, ...children) {
  const { className, actions, extra } = props;
  return el(
    'li',
    {
      ...omit(props, ['className', 'actions', 'extra', 'key']),
      className: cx('gd-list__item', className),
    },
    el('div', { className: 'gd-list__item-main' }, ...children),
    extra != null ? el('div', { className: 'gd-list__extra' }, extra) : null,
    actions
      ? el(
          'div',
          { className: 'gd-list__actions' },
          ...(Array.isArray(actions) ? actions : [actions])
        )
      : null
  );
}

/**
 * Descriptions — label/value grid (antd Descriptions).
 * @param {object} [props]
 * @param {Array<{label:string,children:any,span?:number}>} [props.items]
 * @param {string} [props.title]
 * @param {number} [props.column]
 * @param {boolean} [props.bordered]
 */
export function Descriptions(props = {}) {
  const { items = [], title, column = 3, bordered = true, className, size = 'default' } = props;
  return el(
    'div',
    {
      ...omit(props, ['items', 'title', 'column', 'bordered', 'className', 'size']),
      className: cx(
        'gd-descriptions',
        bordered && 'gd-descriptions--bordered',
        `gd-descriptions--${size}`,
        className
      ),
    },
    title != null ? el('div', { className: 'gd-descriptions__title', text: title }) : null,
    el(
      'div',
      {
        className: 'gd-descriptions__view',
        style: { gridTemplateColumns: `repeat(${column}, 1fr)` },
      },
      ...items.map((it, i) =>
        el(
          'div',
          {
            className: 'gd-descriptions__item',
            key: it.key || i,
            style: it.span ? { gridColumn: `span ${it.span}` } : undefined,
          },
          el('div', { className: 'gd-descriptions__label', text: it.label }),
          el(
            'div',
            { className: 'gd-descriptions__content' },
            typeof it.children === 'string' || typeof it.children === 'number'
              ? el('span', { text: String(it.children) })
              : it.children
          )
        )
      )
    )
  );
}

/**
 * Statistic — big number display (antd Statistic).
 */
export function Statistic(props = {}) {
  const { title, value, suffix, prefix, className, precision } = props;
  let display = value;
  if (typeof value === 'number' && precision != null) {
    display = value.toFixed(precision);
  }
  return el(
    'div',
    {
      ...omit(props, ['title', 'value', 'suffix', 'prefix', 'className', 'precision']),
      className: cx('gd-statistic', className),
    },
    title != null ? el('div', { className: 'gd-statistic__title', text: title }) : null,
    el(
      'div',
      { className: 'gd-statistic__content' },
      prefix != null ? el('span', { className: 'gd-statistic__prefix', text: String(prefix) }) : null,
      el('span', { className: 'gd-statistic__value', text: String(display ?? '') }),
      suffix != null ? el('span', { className: 'gd-statistic__suffix', text: String(suffix) }) : null
    )
  );
}
