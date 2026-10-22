import { cx, el, omit } from './util.js';
import { Button } from './button.js';

/**
 * Upload — file picker with file list (antd Upload, simplified).
 * @param {object} [props]
 * @param {Array<{uid:string,name:string,status?:string}>} [props.fileList]
 * @param {boolean} [props.multiple]
 * @param {string} [props.accept]
 * @param {function} [props.onChange] ({ fileList, file })
 * @param {function} [props.onRemove]
 */
export function Upload(props = {}) {
  const {
    fileList = [],
    multiple = false,
    accept,
    onChange,
    onRemove,
    className,
    text = 'Click to upload',
    disabled,
  } = props;

  const inputId = props.id || `gd-upload-${Math.random().toString(36).slice(2, 8)}`;

  return el(
    'div',
    {
      ...omit(props, [
        'fileList',
        'multiple',
        'accept',
        'onChange',
        'onRemove',
        'className',
        'text',
        'disabled',
      ]),
      className: cx('gd-upload', className),
    },
    el(
      'label',
      { className: cx('gd-upload__trigger', disabled && 'gd-upload__trigger--disabled'), attrs: { for: inputId } },
      Button({ type: 'default', text, disabled: !!disabled }),
      el('input', {
        id: inputId,
        type: 'file',
        className: 'gd-upload__input',
        multiple: !!multiple,
        accept,
        disabled: !!disabled,
        onChange: (e) => {
          const files = Array.from(e.target.files || []);
          const next = [
            ...fileList,
            ...files.map((f, i) => ({
              uid: `${Date.now()}-${i}`,
              name: f.name,
              status: 'done',
              originFileObj: f,
            })),
          ];
          onChange?.({ fileList: next, file: next[next.length - 1] });
          e.target.value = '';
        },
      })
    ),
    fileList.length
      ? el(
          'ul',
          { className: 'gd-upload__list' },
          ...fileList.map((f) =>
            el(
              'li',
              { className: 'gd-upload__item', key: f.uid },
              el('span', { className: 'gd-upload__name', text: f.name }),
              el('button', {
                type: 'button',
                className: 'gd-upload__remove',
                text: '×',
                onClick: () => {
                  onRemove?.(f);
                  onChange?.({
                    fileList: fileList.filter((x) => x.uid !== f.uid),
                    file: f,
                  });
                },
              })
            )
          )
        )
      : null
  );
}

/**
 * Mentions — textarea with @ trigger suggestions (simplified antd Mentions).
 * @param {object} [props]
 * @param {string} [props.value]
 * @param {string[]} [props.options]
 * @param {boolean} [props.open]
 * @param {function} [props.onChange]
 * @param {function} [props.onOpenChange]
 * @param {function} [props.onSelect]
 */
export function Mentions(props = {}) {
  const {
    value = '',
    options = [],
    open = false,
    onChange,
    onOpenChange,
    onSelect,
    className,
    placeholder = 'Type @ to mention…',
  } = props;

  const at = value.lastIndexOf('@');
  const query = at >= 0 ? value.slice(at + 1).split(/\s/)[0].toLowerCase() : '';
  const filtered =
    at >= 0
      ? options.filter((o) => String(o).toLowerCase().includes(query))
      : [];

  return el(
    'div',
    {
      ...omit(props, [
        'value',
        'options',
        'open',
        'onChange',
        'onOpenChange',
        'onSelect',
        'className',
        'placeholder',
      ]),
      className: cx('gd-mentions', open && filtered.length && 'gd-mentions--open', className),
    },
    el('textarea', {
      className: 'gd-textarea gd-mentions__input',
      value,
      placeholder,
      onInput: (e) => {
        const v = e.target.value;
        onChange?.(v);
        onOpenChange?.(v.includes('@'));
      },
    }),
    open && filtered.length
      ? el(
          'div',
          { className: 'gd-mentions__list', role: 'listbox' },
          ...filtered.map((name) =>
            el('button', {
              type: 'button',
              className: 'gd-mentions__option',
              text: `@${name}`,
              onClick: () => {
                const before = value.slice(0, at);
                const after = value.slice(at + 1 + query.length);
                const next = `${before}@${name} ${after}`;
                onChange?.(next);
                onSelect?.(name);
                onOpenChange?.(false);
              },
            })
          )
        )
      : null
  );
}
