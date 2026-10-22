import { cx, el, omit } from './util.js';

/**
 * Truncate — ellipsis / line-clamp text.
 * @param {object} [props]
 * @param {string} [props.text]
 * @param {number} [props.lines] 1 = single-line ellipsis
 */
export function Truncate(props = {}, ...children) {
  const { text, lines = 1, className } = props;
  const kids = children.length ? children : text != null ? [text] : [];
  return el(
    'span',
    {
      ...omit(props, ['text', 'lines', 'className']),
      className: cx(
        'gd-truncate',
        lines > 1 ? 'gd-truncate--clamp' : 'gd-truncate--ellipsis',
        className
      ),
      style: lines > 1 ? { WebkitLineClamp: String(lines) } : undefined,
    },
    ...kids
  );
}

/**
 * PasswordInput — sign-in form eye toggle pattern.
 */
export function PasswordInput(props = {}) {
  const { visible = false, onToggleVisible, className, ...rest } = props;
  return el(
    'div',
    { className: cx('gd-password', className) },
    el('input', {
      ...rest,
      type: visible ? 'text' : 'password',
      className: cx('gd-input', 'gd-password__input'),
    }),
    el('button', {
      type: 'button',
      className: 'gd-password__eye',
      text: visible ? 'Hide' : 'Show',
      onClick: onToggleVisible,
    })
  );
}

/**
 * OrDivider — “OR” rule used in sign-in forms.
 */
export function OrDivider(props = {}) {
  const { text = 'OR', className } = props;
  return el(
    'div',
    { className: cx('gd-or-divider', className) },
    el('span', { className: 'gd-or-divider__line' }),
    el('span', { className: 'gd-or-divider__text', text }),
    el('span', { className: 'gd-or-divider__line' })
  );
}

/**
 * SignInForm — labeled anatomy of a login form (composition).
 */
export function SignInForm(props = {}) {
  const {
    className,
    email,
    password,
    passwordVisible,
    onEmail,
    onPassword,
    onToggleVisible,
    onSubmit,
    onContinueWith,
    providers = ['Google', 'GitHub'],
  } = props;

  return el(
    'form',
    {
      className: cx('gd-sign-in', className),
      onSubmit: (e) => {
        e.preventDefault();
        onSubmit?.({ email, password });
      },
    },
    el('label', { className: 'gd-field' },
      el('span', { className: 'gd-field__label', text: 'Email' }),
      el('input', {
        type: 'email',
        className: 'gd-input',
        value: email,
        placeholder: 'you@company.com',
        onInput: (e) => onEmail?.(e.target.value),
      })
    ),
    el('label', { className: 'gd-field' },
      el('span', { className: 'gd-field__label', text: 'Password' }),
      PasswordInput({
        value: password,
        visible: passwordVisible,
        onToggleVisible,
        onInput: (e) => onPassword?.(e.target.value),
      })
    ),
    el('button', {
      type: 'submit',
      className: 'gd-btn gd-btn--primary gd-btn--md gd-btn--block',
      text: 'Sign in',
    }),
    OrDivider({}),
    el(
      'div',
      { className: 'gd-sign-in__providers' },
      ...providers.map((p) =>
        el('button', {
          type: 'button',
          className: 'gd-btn gd-btn--default gd-btn--md gd-btn--block',
          text: `Continue with ${p}`,
          onClick: () => onContinueWith?.(p),
        })
      )
    )
  );
}
