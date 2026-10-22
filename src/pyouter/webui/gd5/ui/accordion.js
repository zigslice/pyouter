import { cx, el, omit } from './util.js';

/**
 * Accordion — stacked disclosures (details/summary).
 * @param {object} [props]
 * @param {Array<{key?:string,title:string,content:any,defaultOpen?:boolean}>} [props.items]
 * @param {boolean} [props.multiple]
 */
export function Accordion(props = {}, ...children) {
  const { items = [], multiple = true, className } = props;
  if (children.length) {
    return el('div', { className: cx('gd-accordion', className) }, ...children);
  }
  return el(
    'div',
    {
      ...omit(props, ['items', 'multiple', 'className']),
      className: cx('gd-accordion', className),
    },
    ...items.map((item, i) =>
      Collapse({
        key: item.key || `acc-${i}`,
        title: item.title,
        open: item.defaultOpen,
        name: multiple ? undefined : 'gd-accordion-group',
      }, item.content)
    )
  );
}

/**
 * Collapse / Collapsible — single disclosure panel.
 * @param {object} [props]
 * @param {string} [props.title]
 * @param {boolean} [props.open]
 * @param {string} [props.name] same name → exclusive open (details)
 */
export function Collapse(props = {}, ...children) {
  const { title = 'Section', open = false, name, className } = props;
  return el(
    'details',
    {
      ...omit(props, ['title', 'open', 'name', 'className', 'key']),
      className: cx('gd-collapse', className),
      ...(open ? { open: true } : {}),
      ...(name ? { name } : {}),
    },
    el('summary', { className: 'gd-collapse__trigger', text: title }),
    el('div', { className: 'gd-collapse__panel' }, ...children)
  );
}
