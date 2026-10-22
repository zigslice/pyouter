/**
 * ProtoLive Engine — 迷你实模式 DOM 组件运行时
 *
 * 产品（ProtoLive 编辑器）应依赖本引擎实现页面导航与视图构建，
 * 而不是绕过 Component / ComponentRender / D。
 */

export { Component } from './component.js';
export { ComponentRender, defaultGetUserInfo } from './component-render.js';
export { Element, D, bind, domEventType, applyDomEvents } from './element.js';
export {
  Log,
  LogEnv,
  LogLevel,
  LogProvider,
  Logger,
  createAlertSink,
  createConsoleSink,
  createNoopSink,
  formatLogRecord,
  normalizeLogContext,
  resolveLogLevel,
  resolveLogSink,
} from './log.js';
export {
  adoptStyles,
  adoptStylesFor,
  adoptedStyleKeys,
  resetAdoptedStyles,
  scopeCssText,
  styleScopeId,
  styleScopeSelector,
  applyStyleScope,
  STYLE_SCOPE_ATTR,
} from './styles.js';
