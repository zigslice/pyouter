import { cx, el, omit } from './util.js';
import { Chip } from './chip.js';
import { Input } from './input.js';

/**
 * SearchInput — search field with clear affordance.
 */
export function SearchInput(props = {}) {
  const { className, value, onClear, placeholder = 'Search…', ...rest } = props;
  return el(
    'div',
    { className: cx('gd-search', className) },
    el('span', { className: 'gd-search__icon', text: '⌕', attrs: { 'aria-hidden': 'true' } }),
    Input({
      ...rest,
      value,
      placeholder,
      className: 'gd-search__input',
      type: 'search',
    }),
    value
      ? el('button', {
          type: 'button',
          className: 'gd-search__clear',
          text: '×',
          attrs: { 'aria-label': 'Clear' },
          onClick: onClear,
        })
      : null
  );
}

/**
 * Combobox — text input + filtered suggestion list.
 * @param {object} [props]
 * @param {string} [props.value]
 * @param {Array<string|{value:string,label:string}>} [props.options]
 * @param {boolean} [props.open]
 * @param {function} [props.onChange]
 * @param {function} [props.onSelect]
 */
export function Combobox(props = {}) {
  const {
    value = '',
    options = [],
    open = false,
    onChange,
    onSelect,
    onOpenChange,
    placeholder = 'Type to search…',
    className,
  } = props;
  const normalized = options.map((o) =>
    typeof o === 'string' ? { value: o, label: o } : o
  );
  const q = String(value).toLowerCase();
  const filtered = normalized.filter((o) => o.label.toLowerCase().includes(q));

  return el(
    'div',
    {
      ...omit(props, [
        'value',
        'options',
        'open',
        'onChange',
        'onSelect',
        'onOpenChange',
        'placeholder',
        'className',
      ]),
      className: cx('gd-combobox', open && 'gd-combobox--open', className),
    },
    Input({
      value,
      placeholder,
      className: 'gd-combobox__input',
      onInput: (e) => {
        onChange?.(e.target.value);
        onOpenChange?.(true);
      },
      onFocus: () => onOpenChange?.(true),
    }),
    open
      ? el(
          'div',
          { className: 'gd-combobox__list', role: 'listbox' },
          filtered.length
            ? filtered.map((o) =>
                el('button', {
                  type: 'button',
                  role: 'option',
                  className: 'gd-combobox__option',
                  text: o.label,
                  onClick: () => {
                    onSelect?.(o.value, o);
                    onOpenChange?.(false);
                  },
                })
              )
            : [el('div', { className: 'gd-combobox__empty', text: 'No matches' })]
        )
      : null
  );
}

/**
 * TagInput / TokenField — chips + text entry.
 * @param {object} [props]
 * @param {string[]} [props.value]
 * @param {function} [props.onChange]
 */
export function TagInput(props = {}) {
  const { value = [], onChange, placeholder = 'Add…', className, id } = props;
  return el(
    'div',
    {
      ...omit(props, ['value', 'onChange', 'placeholder', 'className']),
      className: cx('gd-tag-input', className),
      id,
    },
    ...value.map((v, i) =>
      Chip({
        text: v,
        closable: true,
        onClose: () => onChange?.(value.filter((_, j) => j !== i)),
      })
    ),
    el('input', {
      className: 'gd-tag-input__field',
      placeholder,
      onKeyDown: (e) => {
        if (e.key === 'Enter' || e.key === ',') {
          e.preventDefault();
          const t = e.target.value.trim().replace(/,$/, '');
          if (t && !value.includes(t)) onChange?.([...value, t]);
          e.target.value = '';
        } else if (e.key === 'Backspace' && !e.target.value && value.length) {
          onChange?.(value.slice(0, -1));
        }
      },
    })
  );
}

/**
 * MultiSelect — checkbox dropdown of many values.
 * @param {object} [props]
 * @param {Array<{value:string,label:string}>} [props.options]
 * @param {string[]} [props.value]
 * @param {boolean} [props.open]
 */
export function MultiSelect(props = {}) {
  const {
    options = [],
    value = [],
    open = false,
    onChange,
    onOpenChange,
    placeholder = 'Select…',
    className,
  } = props;
  const label =
    value.length === 0
      ? placeholder
      : value
          .map((v) => options.find((o) => o.value === v)?.label || v)
          .join(', ');

  return el(
    'div',
    {
      ...omit(props, [
        'options',
        'value',
        'open',
        'onChange',
        'onOpenChange',
        'placeholder',
        'className',
      ]),
      className: cx('gd-multi-select', open && 'gd-multi-select--open', className),
    },
    el('button', {
      type: 'button',
      className: 'gd-multi-select__trigger',
      text: label,
      onClick: () => onOpenChange?.(!open),
    }),
    open
      ? el(
          'div',
          { className: 'gd-multi-select__panel' },
          ...options.map((o) => {
            const checked = value.includes(o.value);
            return el(
              'label',
              { className: 'gd-multi-select__option' },
              el('input', {
                type: 'checkbox',
                checked,
                onChange: () => {
                  onChange?.(
                    checked ? value.filter((v) => v !== o.value) : [...value, o.value]
                  );
                },
              }),
              el('span', { text: o.label })
            );
          })
        )
      : null
  );
}

/**
 * Transfer — two-pane multi-select.
 * @param {object} [props]
 * @param {Array<{key:string,title:string}>} [props.dataSource]
 * @param {string[]} [props.targetKeys]
 * @param {function} [props.onChange]
 */
export function Transfer(props = {}) {
  const { dataSource = [], targetKeys = [], onChange, className, titles = ['Source', 'Target'] } =
    props;
  const left = dataSource.filter((d) => !targetKeys.includes(d.key));
  const right = dataSource.filter((d) => targetKeys.includes(d.key));

  const moveRight = (key) => onChange?.([...targetKeys, key]);
  const moveLeft = (key) => onChange?.(targetKeys.filter((k) => k !== key));

  const pane = (title, list, onMove, actionLabel) =>
    el(
      'div',
      { className: 'gd-transfer__pane' },
      el('div', { className: 'gd-transfer__title', text: title }),
      el(
        'div',
        { className: 'gd-transfer__list' },
        ...list.map((item) =>
          el(
            'button',
            {
              type: 'button',
              className: 'gd-transfer__item',
              onClick: () => onMove(item.key),
            },
            el('span', { text: item.title }),
            el('span', { className: 'gd-transfer__action', text: actionLabel })
          )
        )
      )
    );

  return el(
    'div',
    {
      ...omit(props, ['dataSource', 'targetKeys', 'onChange', 'className', 'titles']),
      className: cx('gd-transfer', className),
    },
    pane(titles[0], left, moveRight, '→'),
    pane(titles[1], right, moveLeft, '←')
  );
}

/**
 * Slider — range input with optional label.
 */
export function Slider(props = {}) {
  const { value = 0, min = 0, max = 100, step = 1, onChange, className, showValue = true } =
    props;
  return el(
    'div',
    { className: cx('gd-slider', className) },
    el('input', {
      ...omit(props, ['className', 'showValue', 'onChange']),
      type: 'range',
      className: 'gd-slider__input',
      value,
      min,
      max,
      step,
      onInput: (e) => onChange?.(Number(e.target.value), e),
    }),
    showValue ? el('span', { className: 'gd-slider__value', text: String(value) }) : null
  );
}

/**
 * ColorWell — swatch + native color input.
 */
export function ColorWell(props = {}) {
  const { value = '#e86a17', onChange, className } = props;
  return el(
    'label',
    {
      ...omit(props, ['value', 'onChange', 'className']),
      className: cx('gd-color-well', className),
      title: value,
    },
    el('span', {
      className: 'gd-color-well__swatch',
      style: { background: value },
    }),
    el('input', {
      type: 'color',
      className: 'gd-color-well__input',
      value,
      onInput: (e) => onChange?.(e.target.value, e),
    })
  );
}

/**
 * DatePicker — native date input (calendar popup is browser-provided).
 */
export function DatePicker(props = {}) {
  const { value, onChange, className, type = 'date' } = props;
  return el('input', {
    ...omit(props, ['className', 'onChange']),
    type, // date | datetime-local | month | week
    className: cx('gd-input', 'gd-date-picker', className),
    value,
    onInput: (e) => onChange?.(e.target.value, e),
  });
}

/** TimeField — native time input. */
export function TimeField(props = {}) {
  return DatePicker({ ...props, type: 'time' });
}
