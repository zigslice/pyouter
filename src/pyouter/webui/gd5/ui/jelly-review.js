/**
 * Suitability of every public UI component for the jelly membrane.
 * The global switch is data-gd-jelly; only `jelly: true` entries are hosts.
 * A new PascalCase export must be added here or the kit test fails.
 */

/** @type {Record<string, { jelly: boolean, reason: string }>} */
export const JELLY_REVIEW = {};

/**
 * @param {string[]} names
 * @param {string} reason
 */
function skip(names, reason) {
  for (const name of names) JELLY_REVIEW[name] = { jelly: false, reason };
}

function host(name, reason) {
  JELLY_REVIEW[name] = { jelly: true, reason };
}

host(
  'Button',
  'Primary and default are solid pressable surfaces. Ghost and danger keep an outline membrane. Text stays flat.'
);
host('LoadingButton', 'Renders Button, so it follows the same solid-type rule.');
host('AsyncButton', 'Alias of LoadingButton.');
host('Chip', 'Interactive pill with a solid fill. Static pills and tags stay rigid.');
host('Fab', 'Round solid floating button. The membrane rests as the same circle.');
host('ChatLauncher', 'Renders Fab.');
host('BackToTop', 'Renders Fab.');

skip(
  ['ButtonIndicator'],
  'Loading dots sit inside the button; the membrane belongs to the button, not the glyph.'
);
skip(
  ['Input', 'TextArea', 'Select', 'Field', 'InputNumber', 'PasswordInput', 'SearchInput', 'Combobox', 'TagInput', 'MultiSelect', 'Transfer', 'DatePicker', 'TimeField', 'Cascader', 'TreeSelect', 'Mentions', 'ColorWell'],
  'Text fields need a stable caret, cursor, and outline. A wobbling membrane fights typing.'
);
skip(
  ['Checkbox', 'Radio', 'RadioGroup', 'Rate', 'Slider', 'QuantityStepper'],
  'The state glyph is the control. A membrane would swallow the mark or the track.'
);
skip(
  ['Switch', 'JellySwitch'],
  'The 22px track and the separate knob are two shapes. The global jelly switch stays rigid.'
);
skip(
  ['ToggleGroup', 'SegmentedControl'],
  'Connected segments share one silhouette and clip overflow. A wobble breaks the group.'
);
skip(
  ['Tabs'],
  'Selection is an underline, not a solid pressable body.'
);
skip(
  ['SplitButton'],
  'The joined pair shares a silhouette. Hosts inside .gd-split-btn stay rigid so the halves remain connected.'
);
skip(
  ['HamburgerButton', 'Navbar', 'SiteHeader', 'BottomNav', 'Sidebar', 'Toolbar', 'Scrollspy', 'Menu', 'Breadcrumbs', 'Steps', 'Pagination', 'PageControl', 'Anchor', 'Affix'],
  'Navigation chrome is a layout of links, not a single solid control.'
);
skip(
  ['Pill', 'Tag', 'Badge', 'Avatar', 'AvatarGroup', 'StatusDot', 'Icon'],
  'Static labels and glyphs. They are read, not pressed as a body of material.'
);
skip(
  ['Card', 'Alert', 'Banner', 'Callout', 'Result', 'Empty', 'Statistic', 'Descriptions', 'List', 'ListItem', 'Timeline', 'Calendar', 'Accordion', 'Collapse', 'Watermark'],
  'Large surfaces hold nested content. A membrane would move the whole layout on an inner click.'
);
skip(
  ['Modal', 'Drawer', 'Sheet', 'Toast', 'Notification', 'Lightbox', 'CommandPalette', 'Popover', 'Tooltip', 'DropdownMenu', 'HoverCard', 'ContextMenu', 'OverflowMenu', 'Scrim', 'Popconfirm'],
  'Overlays contain their own targets. Deforming the shell steals the click from what is inside.'
);
skip(
  ['Table', 'DataTable', 'Tree', 'OutlineView', 'DisclosureTriangle', 'JsonTree', 'WorkflowDAG', 'WorkflowBoard'],
  'Rows, nodes, and edges are information. Physics would make the structure feel unstable.'
);
skip(
  ['CodeBlock', 'Code', 'DiffBlock', 'Diff', 'MarkdownEditor'],
  'Reading and editing need a still surface.'
);
skip(
  ['PieChart', 'DonutChart', 'EChart', 'EChartView', 'ThreeView', 'ThreeViewView', 'ThreeScene', 'SparkView', 'SparkViewView', 'SplatView', 'PeleView', 'PeleViewView', 'MermaidView', 'CoverFlow', 'Coverflow', 'CoverflowCarousel', 'Carousel'],
  'Charts and viewers already own their motion. A second membrane fights the picture.'
);
skip(
  ['ProgressBar', 'ProgressRing', 'Meter', 'Skeleton', 'SkeletonParagraph', 'Spin'],
  'Feedback of progress or waiting. The shape is a status, not a pressable solid.'
);
skip(
  ['Space', 'Divider', 'Flex', 'Row', 'Col', 'Layout', 'LayoutHeader', 'LayoutSider', 'LayoutContent', 'LayoutFooter', 'BentoGrid', 'BentoTile', 'Masonry', 'Marquee', 'Sticky', 'Fixed', 'ScrollArea', 'ResizeHandle', 'Splitter', 'SplitView', 'DragHandle', 'DropZone'],
  'Layout boxes arrange children. They are not a material you press.'
);
skip(
  ['Title', 'Text', 'Truncate', 'OrDivider'],
  'Typography stays still so it can be read.'
);
skip(
  ['Form', 'FormItem', 'SignInForm', 'Upload'],
  'Forms group fields and actions. The solid buttons inside already carry jelly.'
);
skip(
  ['ChatBubble'],
  'Message text must stay still while it is read.'
);
skip(
  ['TodoList', 'TodoListView', 'Todos', 'Todo', 'Image'],
  'Lists and pictures are content. Press targets inside them use Button or Chip on their own.'
);
skip(
  ['ConfigProvider'],
  'Scopes theme and the jelly switch for a subtree. The provider itself is not a surface.'
);
