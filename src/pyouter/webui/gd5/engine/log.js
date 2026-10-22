/**
 * LogProvider — structured logging for the engine.
 *
 * Configure once at the app root, then inject the logger into components:
 *
 *   const logs = new LogProvider({
 *     level: 'info',
 *     sink: 'console',
 *     context: { machId: 'local', userId: 'demo' },
 *   });
 *   const app = new ComponentRender({ logProvider: logs });
 *
 *   this.logger.info('mounted');
 *   this.logger.child({ page: 'editor' }).warn('slow paint', { ms: 42 });
 *
 * Levels: debug < info < warn < error < silent
 * Sinks:  'console' | 'noop' | 'alert' | (record) => void
 */

/** @typedef {'debug'|'info'|'warn'|'error'} LogLevelName */
/** @typedef {'console'|'noop'|'alert'|((record: LogRecord) => void)} LogSinkOption */

/**
 * @typedef {object} LogRecord
 * @property {LogLevelName} level
 * @property {number} levelValue
 * @property {number} time
 * @property {string} message
 * @property {Record<string, unknown>} context
 */

export const LogLevel = Object.freeze({
  debug: 10,
  info: 20,
  warn: 30,
  error: 40,
  silent: 100,
});

const LEVEL_NAME = Object.freeze({
  [LogLevel.debug]: 'debug',
  [LogLevel.info]: 'info',
  [LogLevel.warn]: 'warn',
  [LogLevel.error]: 'error',
});

const NAME_TO_LEVEL = Object.freeze({
  debug: LogLevel.debug,
  info: LogLevel.info,
  warn: LogLevel.warn,
  error: LogLevel.error,
  silent: LogLevel.silent,
});

/**
 * Legacy environment names. Prefer `LogProvider` `{ level, sink }`.
 * @deprecated
 */
export const LogEnv = Object.freeze({
  disable: 'disable',
  chrome: 'chrome',
  wechat: 'wechat',
});

/**
 * @param {number|string|undefined} level
 * @returns {number}
 */
export function resolveLogLevel(level) {
  if (typeof level === 'number' && Number.isFinite(level)) return level;
  if (typeof level === 'string' && level in NAME_TO_LEVEL) return NAME_TO_LEVEL[level];
  return LogLevel.info;
}

/**
 * @param {Record<string, unknown>|null|undefined} ctx
 * @returns {string}
 */
function formatContext(ctx) {
  if (!ctx || typeof ctx !== 'object') return '';
  return Object.entries(ctx)
    .filter(([, v]) => v != null && v !== '')
    .map(([k, v]) => `${k}=${typeof v === 'object' ? JSON.stringify(v) : v}`)
    .join(' ');
}

/**
 * @param {LogRecord} record
 * @returns {string}
 */
export function formatLogRecord(record) {
  const ctx = formatContext(record.context);
  const tag = String(record.level || 'info').toUpperCase();
  return ctx ? `[${tag}] ${ctx} | ${record.message}` : `[${tag}] ${record.message}`;
}

/** @returns {(record: LogRecord) => void} */
export function createConsoleSink() {
  return (record) => {
    const line = formatLogRecord(record);
    if (record.level === 'error') {
      console.error(line);
      console.assert(false, record.message);
    } else if (record.level === 'warn') {
      console.warn(line);
    } else if (record.level === 'debug') {
      (console.debug || console.log).call(console, line);
    } else {
      console.log(line);
    }
  };
}

/** @returns {(record: LogRecord) => void} */
export function createNoopSink() {
  return () => {};
}

/** @returns {(record: LogRecord) => void} */
export function createAlertSink() {
  return (record) => {
    if (typeof globalThis.alert === 'function') {
      globalThis.alert(formatLogRecord(record));
    }
  };
}

/**
 * @param {LogSinkOption|string|undefined} sink
 * @returns {(record: LogRecord) => void}
 */
export function resolveLogSink(sink) {
  if (typeof sink === 'function') return sink;
  if (sink === 'noop' || sink === LogEnv.disable) return createNoopSink();
  if (sink === 'alert' || sink === LogEnv.wechat) return createAlertSink();
  return createConsoleSink();
}

/**
 * Normalize legacy context lists and plain objects into a context map.
 * @param {Record<string, unknown>|string[]|string|null|undefined} contexts
 * @returns {Record<string, unknown>}
 */
export function normalizeLogContext(contexts) {
  if (contexts == null) return {};
  if (typeof contexts === 'object' && !Array.isArray(contexts)) {
    return { ...contexts };
  }
  if (!Array.isArray(contexts)) {
    return { ctx: String(contexts) };
  }

  const out = {};
  contexts.forEach((item, i) => {
    if (item != null && typeof item === 'object' && !Array.isArray(item)) {
      Object.assign(out, item);
      return;
    }
    const s = String(item ?? '');
    if (!s) return;

    // "machId:local, userId:demo, token:" (legacy ComponentRender prefix)
    if (s.includes(':') && s.includes(',')) {
      s.split(',').forEach((part) => {
        const trimmed = part.trim();
        const idx = trimmed.indexOf(':');
        if (idx > 0) {
          out[trimmed.slice(0, idx).trim()] = trimmed.slice(idx + 1).trim();
        } else if (trimmed) {
          out[`ctx${i}`] = trimmed;
        }
      });
      return;
    }

    if (s.includes('=') && !s.includes(' ')) {
      const idx = s.indexOf('=');
      out[s.slice(0, idx)] = s.slice(idx + 1);
      return;
    }

    const colon = s.indexOf(':');
    if (colon > 0 && !s.includes(' ')) {
      out[s.slice(0, colon)] = s.slice(colon + 1);
      return;
    }

    out[`ctx${i}`] = s;
  });
  return out;
}

/**
 * Scoped logger bound to a {@link LogProvider}.
 */
export class Logger {
  /**
   * @param {LogProvider} provider
   * @param {Record<string, unknown>} [context]
   */
  constructor(provider, context = {}) {
    this._provider = provider;
    this._context = { ...context };
  }

  /** @returns {Record<string, unknown>} */
  get context() {
    return { ...this._context };
  }

  /** @returns {LogProvider} */
  get provider() {
    return this._provider;
  }

  /**
   * Child logger with merged context. Parent context is not mutated.
   * @param {Record<string, unknown>} [extra]
   * @returns {Logger}
   */
  child(extra = {}) {
    return new Logger(this._provider, { ...this._context, ...extra });
  }

  /** Alias of {@link Logger#child} with no extra fields (copy). */
  fork() {
    return this.child();
  }

  /**
   * Mutate this logger's context (prefer {@link Logger#child} in new code).
   * @param {Record<string, unknown>|string} value
   */
  pushContext(value) {
    if (value != null && typeof value === 'object' && !Array.isArray(value)) {
      Object.assign(this._context, value);
      return;
    }
    if (value != null) {
      this._context[`ctx${Object.keys(this._context).length}`] = value;
    }
  }

  /** Remove the last context key (pairs with legacy {@link Logger#pushContext}). */
  popContext() {
    const keys = Object.keys(this._context);
    if (keys.length) delete this._context[keys[keys.length - 1]];
  }

  /** Legacy env name from the owning provider. */
  env() {
    return this._provider.env;
  }

  /**
   * @param {unknown} message
   * @param {Record<string, unknown>} [fields]
   */
  debug(message, fields) {
    this._emit(LogLevel.debug, message, fields);
  }

  /**
   * @param {unknown} message
   * @param {Record<string, unknown>} [fields]
   */
  info(message, fields) {
    this._emit(LogLevel.info, message, fields);
  }

  /**
   * @param {unknown} message
   * @param {Record<string, unknown>} [fields]
   */
  warn(message, fields) {
    this._emit(LogLevel.warn, message, fields);
  }

  /**
   * @param {unknown} message
   * @param {Record<string, unknown>} [fields]
   */
  error(message, fields) {
    this._emit(LogLevel.error, message, fields);
  }

  /** @param {unknown} message @param {Record<string, unknown>} [fields] */
  i(message, fields) {
    this.info(message, fields);
  }

  /** @param {unknown} message @param {Record<string, unknown>} [fields] */
  w(message, fields) {
    this.warn(message, fields);
  }

  /** @param {unknown} message @param {Record<string, unknown>} [fields] */
  e(message, fields) {
    this.error(message, fields);
  }

  /**
   * @param {number} level
   * @param {unknown} message
   * @param {Record<string, unknown>} [fields]
   */
  _emit(level, message, fields) {
    this._provider.emit(level, message, this._context, fields);
  }
}

/**
 * App-level logging configuration. Create one per runtime and pass it to
 * {@link import('./component-render.js').ComponentRender}.
 */
export class LogProvider {
  /**
   * @param {object} [options]
   * @param {number|string} [options.level='info']
   * @param {LogSinkOption|string} [options.sink='console']
   * @param {Record<string, unknown>} [options.context]
   * @param {string} [options.env] legacy {@link LogEnv} name exposed via `env`
   */
  constructor(options = {}) {
    this._level = resolveLogLevel(options.level ?? LogLevel.info);
    this._sink = resolveLogSink(options.sink ?? 'console');
    this._context = { ...(options.context || {}) };
    this._env = options.env || inferEnvName(options);
    this._root = new Logger(this, this._context);
  }

  /**
   * Build a provider from a legacy {@link LogEnv} value.
   * @param {string} [env]
   * @param {Record<string, unknown>|string[]} [contexts]
   * @returns {LogProvider}
   */
  static fromEnv(env = LogEnv.chrome, contexts) {
    const context = normalizeLogContext(contexts);
    if (env === LogEnv.disable) {
      return new LogProvider({
        level: LogLevel.silent,
        sink: 'noop',
        context,
        env: LogEnv.disable,
      });
    }
    if (env === LogEnv.wechat) {
      return new LogProvider({
        level: LogLevel.info,
        sink: 'alert',
        context,
        env: LogEnv.wechat,
      });
    }
    return new LogProvider({
      level: LogLevel.info,
      sink: 'console',
      context,
      env: LogEnv.chrome,
    });
  }

  /** @returns {number} */
  get level() {
    return this._level;
  }

  /** @returns {string} */
  get env() {
    return this._env;
  }

  /** Root logger for this provider. */
  get logger() {
    return this._root;
  }

  /**
   * @param {Record<string, unknown>} [extra]
   * @returns {Logger}
   */
  child(extra) {
    return this._root.child(extra || {});
  }

  /**
   * @param {number|string} level
   */
  setLevel(level) {
    this._level = resolveLogLevel(level);
  }

  /**
   * @param {LogSinkOption|string} sink
   */
  setSink(sink) {
    this._sink = resolveLogSink(sink);
  }

  /**
   * @param {number} level
   * @param {unknown} message
   * @param {Record<string, unknown>} [baseContext]
   * @param {Record<string, unknown>} [fields]
   */
  emit(level, message, baseContext, fields) {
    if (level < this._level) return;
    const name = /** @type {LogLevelName} */ (LEVEL_NAME[level] || 'info');
    const context = { ...(baseContext || {}) };
    if (fields != null && typeof fields === 'object' && !Array.isArray(fields)) {
      Object.assign(context, fields);
    }
    this._sink({
      level: name,
      levelValue: level,
      time: Date.now(),
      message: message == null ? '' : String(message),
      context,
    });
  }
}

/**
 * @param {object} options
 * @returns {string}
 */
function inferEnvName(options) {
  const sink = options.sink;
  const level = resolveLogLevel(options.level);
  if (sink === 'noop' || sink === LogEnv.disable || level >= LogLevel.silent) {
    return LogEnv.disable;
  }
  if (sink === 'alert' || sink === LogEnv.wechat) return LogEnv.wechat;
  return LogEnv.chrome;
}

/**
 * Legacy `new Log(env, contexts)`. Prefer `new LogProvider(...).logger`.
 */
export class Log extends Logger {
  /**
   * @param {string} [env]
   * @param {Record<string, unknown>|string[]} [contexts]
   */
  constructor(env = LogEnv.chrome, contexts) {
    const provider = LogProvider.fromEnv(env, contexts);
    super(provider, provider.logger.context);
  }
}
