/**
 * gd5 UI — component library on top of the engine.
 * Catalog: NameThatUI web elements + Ant Design component coverage.
 *
 * Primitives return real-DOM Elements for ensureShell / bind trees.
 * Overlay widgets are Components (portal mount).
 *
 *   import { loadUi, Button, Input, Modal } from '../ui/index.js';
 *   await loadUi();
 */

export { loadUi, ensureUiStyles, cx } from './util.js';
export {
  themes,
  setTheme,
  getTheme,
  isThemeName,
  resolveThemeInput,
  THEME_ATTR,
} from './theme.js';
export {
  setJelly,
  getJelly,
  JellySwitch,
  ensureJelly,
  applyRememberedJelly,
  scaleJellyConfig,
  JELLY_ATTR,
  JELLY_HOST_ATTR,
  JELLY_KEY,
} from './jelly.js';
export { JELLY_REVIEW } from './jelly-review.js';

export { Button, ButtonIndicator, onceAsync } from './button.js';
export { LoadingButton, AsyncButton, createLoadingButton } from './LoadingButton.js';
export { Input, TextArea, Select, Field } from './input.js';
export { InputNumber } from './input-number.js';
export { Checkbox, Switch, Badge } from './control.js';
export { Radio, RadioGroup } from './radio.js';
export { Rate } from './rate.js';
export { Chip, Pill } from './chip.js';
export { Space, Divider } from './space.js';
export { Flex, Row, Col } from './flex.js';
export { Title, Text } from './typography.js';
export { Truncate, PasswordInput, OrDivider, SignInForm } from './text-extra.js';
export { Card } from './card.js';
export { Tag, Alert, Spin, Empty } from './feedback.js';
export { Banner, Callout } from './banner.js';
export { ProgressBar, ProgressRing, Meter } from './progress.js';
export { Skeleton, SkeletonParagraph } from './skeleton.js';
export { Avatar, AvatarGroup, StatusDot } from './avatar.js';
export { Accordion, Collapse } from './accordion.js';
export { Tabs, ToggleGroup, SegmentedControl } from './tabs.js';
export { Breadcrumbs } from './breadcrumbs.js';
export { Steps, QuantityStepper } from './steps.js';
export { Pagination, PageControl } from './pagination.js';
export {
  Navbar,
  SiteHeader,
  BottomNav,
  Sidebar,
  Toolbar,
  HamburgerButton,
  Scrollspy,
  SplitButton,
} from './navigation.js';
export {
  Scrim,
  Tooltip,
  Popover,
  DropdownMenu,
  HoverCard,
  ContextMenu,
  OverflowMenu,
} from './overlay.js';
export {
  SearchInput,
  Combobox,
  TagInput,
  MultiSelect,
  Transfer,
  Slider,
  ColorWell,
  DatePicker,
  TimeField,
} from './form-extra.js';
export { Cascader } from './cascader.js';
export { Upload, Mentions } from './upload.js';
export { TreeSelect } from './tree-select.js';
export { Form, FormItem } from './form.js';
export { Table, DataTable } from './table.js';
export { List, ListItem, Descriptions, Statistic } from './list.js';
export { Calendar } from './calendar.js';
export { Image } from './image.js';
export { Result, Popconfirm } from './result.js';
export { Timeline } from './timeline.js';
export { ChatBubble } from './chat.js';
export { Carousel } from './carousel.js';
export {
  CoverFlow,
  Coverflow,
  CoverflowCarousel,
  createCoverFlow,
  normalizeCoverFlowItems,
  coverFlowDragSlots,
  coverFlowSettleIndex,
  coverFlowOffset,
} from './CoverFlow.js';
export {
  TodoList,
  TodoListView,
  Todos,
  Todo,
  createTodoList,
  normalizeTodoItems,
  normalizeTodoStatus,
  countTodoProgress,
  nextTodoStatus,
} from './todo.js';
export {
  EChart,
  EChartView,
  createEChart,
  loadEcharts,
} from './EChart.js';
export {
  ThreeView,
  ThreeViewView,
  ThreeScene,
  createThreeView,
  loadThree,
} from './ThreeView.js';
export {
  SparkView,
  SparkViewView,
  SplatView,
  createSparkView,
  loadSpark,
  loadSparkThree,
  ensureSparkImportMap,
  DEFAULT_SPARK_URL,
  DEFAULT_SPLAT_URL,
  DEFAULT_SPARK_THREE_URL,
} from './SparkView.js';
export {
  PeleView,
  PeleViewView,
  MermaidView,
  createPeleView,
  loadPele,
  DEFAULT_PELE_URL,
  DEFAULT_PELE_SOURCE,
} from './PeleView.js';
export {
  BentoGrid,
  BentoTile,
  Masonry,
  Marquee,
  Sticky,
  Fixed,
  ScrollArea,
  ResizeHandle,
  Splitter,
  SplitView,
} from './layout-extra.js';
export {
  Layout,
  LayoutHeader,
  LayoutSider,
  LayoutContent,
  LayoutFooter,
} from './layout.js';
export { Menu } from './menu.js';
export { Affix, Anchor } from './affix.js';
export { Icon } from './icon.js';
export { ConfigProvider } from './config.js';
export { Watermark } from './watermark.js';
export { Fab, ChatLauncher, BackToTop } from './float.js';
export { PieChart, DonutChart } from './chart.js';
export {
  Tree,
  OutlineView,
  DisclosureTriangle,
  treePathKeys,
  nextTreeExpandedKeys,
} from './tree.js';
export { DragHandle, DropZone } from './drag.js';

export { Modal } from './Modal.js';
export { Drawer, Sheet } from './Drawer.js';
export { Toast } from './Toast.js';
export { Notification, messageApi } from './Notification.js';
export { Lightbox } from './Lightbox.js';
export { CommandPalette } from './CommandPalette.js';
export { WorkflowDAG, WorkflowBoard } from './WorkflowDAG.js';
export {
  JsonTree,
  createJsonTree,
  flattenJsonTree,
  jsonValueType,
  jsonChildPath,
  JSON_TREE_ROW_H,
} from './JsonTree.js';
export {
  CodeBlock,
  Code,
  DiffBlock,
  Diff,
  parseDiffLines,
  parseUnifiedDiff,
  splitCodeLines,
  countCodeLines,
  tokenizeCode,
  tokensToLineNodes,
  codeToHighlightedLines,
  copyTextFromCodeSelection,
} from './code.js';
export {
  MarkdownEditor,
  createMarkdownEditor,
  renderMarkdown,
  escapeHtml,
  wrapSelection,
  insertAtCursor,
  prefixLines,
} from './markdown.js';
