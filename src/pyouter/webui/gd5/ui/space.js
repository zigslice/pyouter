import { cx, el, omit } from './util.js';

/**
 * Flex stack / row — antd Space analogue.
 *
 * @param {object} [props]
 * @param {'horizontal'|'vertical'} [props.direction]
 * @param {'sm'|'md'|'lg'} [props.size]
 * @param {'start'|'center'|'end'} [props.align]
 * @param {'start'|'center'|'end'|'between'} [props.justify]
 */
export function Space(props = {}, ...children) {
  const {
    direction = 'horizontal',
    size = 'md',
    align,
    justify,
    className,
  } = props;

  return el(
    'div',
    {
      ...omit(props, ['direction', 'size', 'align', 'justify', 'className']),
      className: cx(
        'gd-space',
        direction === 'vertical' && 'gd-space--vertical',
        `gd-space--gap-${size}`,
        align && `gd-space--align-${align}`,
        justify && `gd-space--justify-${justify}`,
        className
      ),
    },
    ...children
  );
}

export function Divider(props = {}) {
  const { type = 'horizontal', className } = props;
  return el('hr', {
    ...omit(props, ['type', 'className']),
    className: cx('gd-divider', type === 'vertical' && 'gd-divider--vertical', className),
  });
}
