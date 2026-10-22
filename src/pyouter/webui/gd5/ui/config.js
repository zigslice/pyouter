import { JELLY_ATTR } from './jelly.js';
import { cx, el, omit } from './util.js';
import { THEME_ATTR, resolveThemeInput } from './theme.js';

/**
 * ConfigProvider — named theme and/or token overrides on a subtree.
 *
 *   ConfigProvider({ theme: 'blue' }, …children)
 *   ConfigProvider({ theme: { name: 'green' } }, …)
 *   ConfigProvider({ theme: { token: { primary: '#e86a17' } } }, …)
 *   ConfigProvider({ jelly: true }, …)  // subtree data-gd-jelly="on"
 */
export function ConfigProvider(props = {}, ...children) {
  const { theme, jelly, className, style } = props;
  const { name, token } = resolveThemeInput(theme);
  const cssVars = { ...(typeof style === 'object' ? style : {}) };

  if (token && typeof token === 'object') {
    for (const [k, v] of Object.entries(token)) {
      if (v == null) continue;
      const varName = k.startsWith('--') ? k : k.startsWith('gd-') ? `--${k}` : `--gd-${k}`;
      cssVars[varName] = v;
    }
  }

  const attrs = {};
  if (name) attrs[THEME_ATTR] = name;
  if (jelly === true) attrs[JELLY_ATTR] = 'on';
  else if (jelly === false) attrs[JELLY_ATTR] = 'off';

  return el(
    'div',
    {
      ...omit(props, ['theme', 'jelly', 'className', 'style']),
      className: cx('gd-config-provider', className),
      style: cssVars,
      attrs,
    },
    ...children
  );
}
