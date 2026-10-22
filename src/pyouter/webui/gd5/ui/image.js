import { cx, el, omit } from './util.js';

/**
 * Image — img with optional preview click (antd Image).
 * Wire preview via onPreview (e.g. open Lightbox).
 * @param {object} [props]
 * @param {string} [props.src]
 * @param {string} [props.alt]
 * @param {number|string} [props.width]
 * @param {boolean} [props.preview]
 * @param {function} [props.onPreview]
 */
export function Image(props = {}) {
  const {
    src,
    alt = '',
    width,
    height,
    preview = true,
    onPreview,
    className,
    style,
  } = props;

  const dim = { ...(typeof style === 'object' ? style : {}) };
  if (width != null) dim.width = typeof width === 'number' ? `${width}px` : width;
  if (height != null) dim.height = typeof height === 'number' ? `${height}px` : height;

  return el(
    'div',
    {
      className: cx('gd-image', preview && 'gd-image--previewable', className),
      style: dim,
      onClick: preview
        ? () => onPreview?.({ src, alt })
        : undefined,
    },
    el('img', {
      ...omit(props, ['preview', 'onPreview', 'className', 'style', 'width', 'height']),
      className: 'gd-image__img',
      src,
      alt,
    }),
    preview
      ? el('span', { className: 'gd-image__mask', text: 'Preview' })
      : null
  );
}
