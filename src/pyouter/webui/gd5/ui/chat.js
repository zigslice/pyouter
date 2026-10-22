import { cx, el, omit } from './util.js';
import { Avatar } from './avatar.js';

/**
 * ChatBubble — message bubble (mine / theirs).
 * @param {object} [props]
 * @param {'mine'|'theirs'} [props.side]
 * @param {string} [props.text]
 * @param {string} [props.author]
 * @param {boolean} [props.showAvatar]
 */
export function ChatBubble(props = {}, ...children) {
  const { side = 'theirs', text, author, showAvatar = false, className } = props;
  const kids = children.length ? children : text != null ? [text] : [];
  return el(
    'div',
    {
      ...omit(props, ['side', 'text', 'author', 'showAvatar', 'className']),
      className: cx('gd-chat-row', `gd-chat-row--${side}`, className),
    },
    showAvatar ? Avatar({ name: author || (side === 'mine' ? 'Me' : 'Them'), size: 'sm' }) : null,
    el(
      'div',
      { className: cx('gd-chat-bubble', `gd-chat-bubble--${side}`) },
      author && side === 'theirs'
        ? el('div', { className: 'gd-chat-bubble__author', text: author })
        : null,
      el('div', { className: 'gd-chat-bubble__text' }, ...kids)
    )
  );
}
