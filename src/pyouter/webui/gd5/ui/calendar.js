import { cx, el, omit } from './util.js';

/**
 * Calendar — month grid (antd Calendar, simplified).
 * @param {object} [props]
 * @param {Date|string} [props.value]
 * @param {function} [props.onChange] (date: Date)
 * @param {function} [props.onSelect]
 */
export function Calendar(props = {}) {
  const { value, onChange, onSelect, className } = props;
  const current = value ? new Date(value) : new Date();
  const year = current.getFullYear();
  const month = current.getMonth();
  const selectedDay = value ? new Date(value).getDate() : null;
  const selectedMonth = value ? new Date(value).getMonth() : null;
  const selectedYear = value ? new Date(value).getFullYear() : null;

  const first = new Date(year, month, 1);
  const startWeekday = first.getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < startWeekday; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  const monthLabel = first.toLocaleString(undefined, { month: 'long', year: 'numeric' });

  const shift = (delta) => {
    const next = new Date(year, month + delta, 1);
    onChange?.(next);
  };

  return el(
    'div',
    {
      ...omit(props, ['value', 'onChange', 'onSelect', 'className']),
      className: cx('gd-calendar', className),
    },
    el(
      'div',
      { className: 'gd-calendar__header' },
      el('button', {
        type: 'button',
        className: 'gd-calendar__nav',
        text: '‹',
        onClick: () => shift(-1),
      }),
      el('div', { className: 'gd-calendar__title', text: monthLabel }),
      el('button', {
        type: 'button',
        className: 'gd-calendar__nav',
        text: '›',
        onClick: () => shift(1),
      })
    ),
    el(
      'div',
      { className: 'gd-calendar__weekdays' },
      ...['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map((w) =>
        el('div', { className: 'gd-calendar__weekday', text: w })
      )
    ),
    el(
      'div',
      { className: 'gd-calendar__grid' },
      ...cells.map((d, i) => {
        if (d == null) return el('div', { className: 'gd-calendar__cell gd-calendar__cell--empty', key: `e-${i}` });
        const selected =
          d === selectedDay && month === selectedMonth && year === selectedYear;
        const today = new Date();
        const isToday =
          d === today.getDate() &&
          month === today.getMonth() &&
          year === today.getFullYear();
        return el('button', {
          type: 'button',
          key: `d-${d}`,
          className: cx(
            'gd-calendar__cell',
            selected && 'gd-calendar__cell--selected',
            isToday && 'gd-calendar__cell--today'
          ),
          text: String(d),
          onClick: () => {
            const date = new Date(year, month, d);
            onSelect?.(date);
            onChange?.(date);
          },
        });
      })
    )
  );
}
