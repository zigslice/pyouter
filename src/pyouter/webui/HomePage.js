import { Component } from "./gd5/engine/index.js";
import {
  Alert,
  Breadcrumbs,
  Button,
  Card,
  Empty,
  Layout,
  LayoutContent,
  LayoutHeader,
  LayoutSider,
  SearchInput,
  Space,
  StatusDot,
  Tag,
  Toast,
  Tree,
  loadUi,
  setTheme,
} from "./gd5/ui/index.js";
import { el } from "./gd5/ui/util.js";
import {
  BOOT,
  STATUS_LABEL,
  UI_LABEL,
  activeOwner,
  childStats,
  commandFor,
  expandAll,
  fetchSnapshot,
  findNode,
  formatDuration,
  formatTime,
  kindName,
  layerKind,
  nodeState,
  pollEvents,
  runPath,
  runtimeMode,
  selectPath,
  state,
  statusDot,
  stopPath,
  subscribe,
  tagColor,
  toTreeData,
} from "./store.js";

function pathKey(path) {
  return path === "" ? "__root__" : path;
}

function fromKey(key) {
  return key === "__root__" ? "" : key;
}

export class HomePage extends Component {
  static styles = new URL("./HomePage.css", import.meta.url);

  constructor(deps = {}) {
    super(deps);
    this._unsub = null;
    this._pollTimer = 0;
    this._mapTimer = 0;
    this._durationTimer = 0;
    this._toast = null;
    this._lastClick = { path: "", at: 0 };
    this.state.data.booted = false;
  }

  async componentDidMount() {
    setTheme("orange");
    await loadUi();
    this._toast = new Toast({});
    await this._toast.mount(document.body);
    this._unsub = subscribe(() => this.refresh());
    try {
      const snap = await fetchSnapshot();
      expandAll(state.tree);
      const focus = snap.here || BOOT.focus || snap.focus || "";
      if (focus && !findNode(state.tree, focus)) {
        this.toast("未找到路径 " + focus);
        selectPath("");
      } else {
        selectPath(focus);
      }
      this.setData({ booted: true });
    } catch (_error) {
      this.toast("无法加载路由");
    }
    const tick = async () => {
      await pollEvents();
      this._pollTimer = window.setTimeout(tick, 400);
    };
    this._pollTimer = window.setTimeout(tick, 400);
    this._mapTimer = window.setInterval(() => {
      fetchSnapshot().catch(() => {});
    }, 3000);
    this._durationTimer = window.setInterval(() => {
      const info = nodeState(state.selected);
      if (info.status !== "running" && info.status !== "pending") return;
      const el = this.host()?.querySelector("[data-duration]");
      if (el) {
        el.textContent = formatDuration(info.started_at, null);
      }
    }, 500);
    this.on(window, "keydown", (event) => {
      if (
        event.key === "/" &&
        document.activeElement &&
        document.activeElement.tagName !== "INPUT" &&
        document.activeElement.tagName !== "TEXTAREA"
      ) {
        event.preventDefault();
        const input = this.host()?.querySelector(".gd-search input, input[type='search']");
        if (input) input.focus();
      }
    });
  }

  componentDidUnMount() {
    if (this._unsub) this._unsub();
    this._unsub = null;
    window.clearTimeout(this._pollTimer);
    window.clearInterval(this._mapTimer);
    window.clearInterval(this._durationTimer);
    if (this._toast) {
      this._toast.unmount();
      this._toast = null;
    }
  }

  toast(message, type = "info") {
    if (this._toast) this._toast.show({ message, type, duration: 2400 });
  }

  async runSelected(path) {
    try {
      await runPath(path);
    } catch (error) {
      this.toast(error.message || "执行失败", "error");
    }
  }

  async stopSelected(path) {
    try {
      await stopPath(path);
    } catch (error) {
      this.toast(error.message || "无法停止", "error");
    }
  }

  copyCommand(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard
        .writeText(text)
        .then(() => this.toast(UI_LABEL.copied, "success"))
        .catch(() => this.toast(text));
      return;
    }
    this.toast(text);
  }

  onTreeSelect(key, item) {
    const path = item?.path != null ? item.path : fromKey(key);
    const now = Date.now();
    const double =
      !runtimeMode() &&
      this._lastClick.path === path &&
      now - this._lastClick.at < 350;
    this._lastClick = { path, at: now };
    selectPath(path);
    if (double) this.runSelected(path);
  }

  renderMapCard(node, depth) {
    const info = nodeState(node.path);
    const selected = node.path === state.selected;
    const kids = node.children || [];
    const body = [
      Space(
        { size: "sm" },
        StatusDot({
          status: statusDot(info.status),
          title: STATUS_LABEL[info.status] || info.status,
        }),
        Tag({
          text: STATUS_LABEL[info.status] || info.status,
          color: tagColor(info.status),
        }),
        node.here ? Tag({ text: UI_LABEL.here, color: "primary" }) : null,
        node.reach === "up" ? Tag({ text: "可达", color: "primary" }) : null,
        node.reach === "down" ? Tag({ text: "不可达", color: "danger" }) : null
      ),
    ];
    const card = Card(
      {
        className: "po-map-card" + (selected ? " is-selected" : ""),
        title: node.name || "(root)",
        extra: runtimeMode()
          ? null
          : Button({
              type: "text",
              size: "sm",
              text: "▶",
              title: "执行",
              onClick: (event) => {
                event.stopPropagation();
                selectPath(node.path);
                this.runSelected(node.path);
              },
            }),
        onClick: () => selectPath(node.path),
      },
      Space(
        { direction: "vertical", size: "sm" },
        Tag({ text: kindName(node) || node.type || "" }),
        ...body.filter(Boolean)
      )
    );
    if (kids.length && depth < 2) {
      const wrap = document.createElement("div");
      wrap.className = "po-map__kids";
      kids.forEach((child) => wrap.appendChild(this.renderMapCard(child, depth + 1).dom()));
      card.dom().querySelector(".gd-card__body")?.appendChild(wrap);
    } else if (kids.length) {
      const note = document.createElement("div");
      note.className = "po-signature";
      note.textContent = "还有 " + kids.length + " 个子节点，可在左侧目录继续查看";
      card.dom().querySelector(".gd-card__body")?.appendChild(note);
    }
    return card;
  }

  render() {
    const active = Object.values(state.nodes).filter(
      (node) => node.status === "running" || node.status === "pending"
    ).length;
    const node = findNode(state.tree, state.selected || "");
    const info = node ? nodeState(node.path) : null;
    const status = info?.status || "idle";
    const owner = node ? activeOwner(node.path) : null;
    const stats = node ? childStats(node.path) : {};
    const statBits = [];
    if (stats.running) statBits.push("运行 " + stats.running);
    if (stats.pending) statBits.push("等待 " + stats.pending);
    if (stats.success) statBits.push("成功 " + stats.success);
    if (stats.error) statBits.push("失败 " + stats.error);
    if (stats.cancelled) statBits.push("已取消 " + stats.cancelled);

    let routers = 0;
    let actions = 0;
    const visit = (item) => {
      if (!item) return;
      if (item.type === "router") routers += 1;
      else actions += 1;
      (item.children || []).forEach(visit);
    };
    visit(state.tree);

    const crumbs = [];
    if (state.tree) {
      crumbs.push({
        label: state.tree.name || "(root)",
        onClick: () => selectPath(""),
      });
      if (node && node.path) {
        const parts = node.path.split(".");
        let current = "";
        parts.forEach((part) => {
          current = current ? current + "." + part : part;
          const found = findNode(state.tree, current);
          if (!found) return;
          crumbs.push({
            label: found.name || part,
            onClick:
              found.path === node.path ? undefined : () => selectPath(found.path),
          });
        });
      }
    }

    let mapNode = node;
    let mapNote = "";
    if (node) {
      if (node.type === "router") {
        mapNote = "当前路由及其子节点";
      } else {
        const parentPath = node.path.includes(".")
          ? node.path.slice(0, node.path.lastIndexOf("."))
          : "";
        mapNode = findNode(state.tree, parentPath) || node;
        mapNote = "叶子节点挂在上一级路由下，高亮的是当前节点";
      }
    }

    const command = node ? commandFor(node.path) : "";
    const logs = info?.logs || [];
    const detailTags = [];
    if (node?.here) detailTags.push(Tag({ text: UI_LABEL.here, color: "primary" }));
    const layer = node ? layerKind(node) : "";
    if (layer) detailTags.push(Tag({ text: kindName(node), color: "primary" }));
    if (node?.reach === "up") detailTags.push(Tag({ text: "可达", color: "primary" }));
    if (node?.reach === "down") detailTags.push(Tag({ text: "不可达", color: "danger" }));
    if (node?.runtime && node.runtime !== node.peer_id) {
      detailTags.push(Tag({ text: "runtime " + node.runtime }));
    }
    if (node?.peer_id) detailTags.push(Tag({ text: "peer " + node.peer_id }));
    (node?.sn || []).forEach((item) => detailTags.push(Tag({ text: "sn " + item })));
    if (node?.ip) {
      const address = node.host_port ? node.ip + ":" + node.host_port : node.ip;
      detailTags.push(Tag({ text: "IP " + address }));
    }

    // Layout* / Tag / Button return Elements from their own D. Nest them with
    // el() so bind()'s single root stays #root (bind div children would steal root).
    this.ensureShell((ids) => ids.root, ({ div }) => {
      div(
        { id: "root", className: "po-shell" },
        LayoutHeader(
          { className: "po-header" },
          el(
            "div",
            { className: "po-brand" },
            el("span", { className: "po-brand__name", text: "pyouter" }),
            Tag({
              text: runtimeMode() ? UI_LABEL.here : UI_LABEL.local,
              color: "primary",
            })
          ),
          el(
            "div",
            { className: "po-meta" },
            el("span", {
              text: active ? active + " 个节点执行中" : "空闲",
              style: active ? { color: "var(--gd-primary)" } : undefined,
            }),
            el("span", {
              text: typeof location !== "undefined" ? location.host : "",
            })
          )
        ),
        Layout(
          { hasSider: true, className: "po-layout" },
          LayoutSider(
            { width: 360, className: "po-sider" },
            el(
              "div",
              { className: "po-sider__bar" },
              el("div", {
                className: "po-sider__title",
                text: UI_LABEL.directory,
              }),
              el(
                "div",
                { className: "po-sider__actions" },
                Button({
                  type: "text",
                  size: "sm",
                  text: UI_LABEL.expand,
                  onClick: () => {
                    expandAll(state.tree);
                    this.refresh();
                  },
                }),
                Button({
                  type: "text",
                  size: "sm",
                  text: UI_LABEL.collapse,
                  onClick: () => {
                    state.expanded = new Set();
                    this.refresh();
                  },
                })
              )
            ),
            SearchInput({
              placeholder: UI_LABEL.search,
              value: state.filter,
              onInput: (event) => {
                state.filter = event?.target?.value || "";
                this.refresh();
              },
              onClear: () => {
                state.filter = "";
                this.refresh();
              },
            }),
            el("div", {
              className: "po-sider__foot",
              text:
                "路由 " + Math.max(routers - 1, 0) + " · 动作 " + actions,
            }),
            el("div", { id: "treeHost", className: "po-tree-host" }),
            el("div", {
              className: "po-sider__hint",
              text: runtimeMode()
                ? "单击查看这个节点"
                : "单击查看，双击或详情里执行",
            })
          ),
          LayoutContent(
            { className: "po-main", id: "main" },
            el("div", { id: "detailHost" })
          )
        )
      );
    });

    const meta = this.host()?.querySelector(".po-meta");
    if (meta && meta.children[0]) {
      meta.children[0].textContent = active
        ? active + " 个节点执行中"
        : "空闲";
      meta.children[0].style.color = active ? "var(--gd-primary)" : "";
    }
    const whereTag = this.host()?.querySelector(".po-brand .gd-tag");
    if (whereTag) {
      whereTag.textContent = runtimeMode() ? UI_LABEL.here : UI_LABEL.local;
    }
    const foot = this.host()?.querySelector(".po-sider__foot");
    if (foot) {
      foot.textContent =
        "路由 " + Math.max(routers - 1, 0) + " · 动作 " + actions;
    }
    const hint = this.host()?.querySelector(".po-sider__hint");
    if (hint) {
      hint.textContent = runtimeMode()
        ? "单击查看这个节点"
        : "单击查看，双击或详情里执行";
    }
    const searchInput = this.host()?.querySelector(".gd-search__input, .gd-search input");
    if (searchInput && searchInput.value !== state.filter) {
      searchInput.value = state.filter;
    }

    const root = this.host();
    const treeHost = root?.querySelector("#treeHost");
    if (treeHost) {
      treeHost.textContent = "";
      if (!state.tree) {
        treeHost.appendChild(
          Empty({ title: "加载中", description: "正在加载路由…" }).dom()
        );
      } else {
        const treeData = toTreeData(state.tree, state.filter);
        if (!treeData.length) {
          treeHost.appendChild(
            Empty({ title: "无匹配", description: "没有匹配的路由" }).dom()
          );
        } else {
          const expandedKeys = state.filter
            ? collectAllKeys(treeData)
            : [...state.expanded].map(pathKey);
          const tree = Tree({
            treeData,
            expandedKeys,
            selectedKey: pathKey(state.selected || ""),
            onExpand: (keys) => {
              state.expanded = new Set(keys.map(fromKey));
            },
            onSelect: (key, item) => this.onTreeSelect(key, item),
          });
          treeHost.appendChild(tree.dom());
        }
      }
    }

    const detailHost = root?.querySelector("#detailHost");
    if (!detailHost) return;
    detailHost.textContent = "";

    if (!state.tree) {
      detailHost.appendChild(
        Empty({ title: "加载中", description: "正在加载路由…" }).dom()
      );
      return;
    }
    if (!node) {
      detailHost.appendChild(
        Empty({ title: "未找到", description: "未找到这个节点" }).dom()
      );
      return;
    }

    const fragment = document.createDocumentFragment();
    fragment.appendChild(Breadcrumbs({ items: crumbs }).dom());

    const titleRow = document.createElement("div");
    titleRow.className = "po-title-row";
    const h1 = document.createElement("h1");
    h1.textContent = node.name || "(root)";
    const badges = document.createElement("div");
    badges.className = "po-badges";
    badges.appendChild(Tag({ text: kindName(node) || node.type || "" }).dom());
    badges.appendChild(
      Tag({
        text: STATUS_LABEL[status] || status,
        color: tagColor(status),
      }).dom()
    );
    badges.appendChild(
      StatusDot({
        status: statusDot(status),
        title: STATUS_LABEL[status] || status,
      }).dom()
    );
    detailTags.forEach((tag) => badges.appendChild(tag.dom()));
    titleRow.append(h1, badges);
    fragment.appendChild(titleRow);

    const pathEl = document.createElement("div");
    pathEl.className = "po-path";
    pathEl.textContent = node.path || "(root)";
    fragment.appendChild(pathEl);

    if (node.signature || node.target) {
      const sig = document.createElement("div");
      sig.className = "po-signature";
      sig.textContent = (node.target || "") + (node.signature || "");
      fragment.appendChild(sig);
    }
    if (node.doc) {
      const doc = document.createElement("div");
      doc.className = "po-doc";
      doc.textContent = node.doc;
      fragment.appendChild(doc);
    }

    const statusRow = document.createElement("div");
    statusRow.className = "po-actions";
    const duration = document.createElement("strong");
    duration.dataset.duration = "1";
    duration.textContent = formatDuration(
      info.started_at,
      status === "running" || status === "pending" ? null : info.finished_at
    );
    const childNote = document.createElement("span");
    childNote.className = "po-signature";
    childNote.textContent = statBits.length
      ? "子节点 " + statBits.join(" · ")
      : node.type === "router"
        ? "还没有子节点执行记录"
        : "";
    statusRow.append(duration, childNote);
    fragment.appendChild(statusRow);

    if (info.error) {
      fragment.appendChild(
        Alert({ type: "error", message: info.error }).dom()
      );
    }

    if (!runtimeMode()) {
      const actions = document.createElement("div");
      actions.className = "po-actions";
      if (owner === null) {
        actions.appendChild(
          Button({
            type: "primary",
            text: UI_LABEL.run,
            onClick: () => this.runSelected(node.path),
          }).dom()
        );
      } else {
        actions.appendChild(
          Button({
            type: "danger",
            text: UI_LABEL.stop,
            onClick: () => this.stopSelected(node.path),
          }).dom()
        );
        const note = document.createElement("span");
        note.className = "po-signature";
        note.textContent =
          owner === node.path
            ? "此节点正在执行"
            : "相关节点正在执行：" + (owner || "(root)");
        actions.appendChild(note);
      }
      fragment.appendChild(actions);

      const commandRow = document.createElement("div");
      commandRow.className = "po-command";
      const code = document.createElement("code");
      code.textContent = command;
      commandRow.appendChild(code);
      commandRow.appendChild(
        Button({
          type: "default",
          text: UI_LABEL.copy,
          onClick: () => this.copyCommand(command),
        }).dom()
      );
      fragment.appendChild(commandRow);
    }

    const mapSection = document.createElement("section");
    mapSection.className = "po-section";
    const mapBar = document.createElement("div");
    mapBar.className = "po-section__bar";
    const mapTitle = document.createElement("h3");
    mapTitle.textContent = UI_LABEL.map;
    mapBar.appendChild(mapTitle);
    mapSection.appendChild(mapBar);
    if (mapNote) {
      const note = document.createElement("div");
      note.className = "po-signature";
      note.textContent = mapNote;
      mapSection.appendChild(note);
    }
    const mapHost = document.createElement("div");
    mapHost.className = "po-map";
    if (mapNode) mapHost.appendChild(this.renderMapCard(mapNode, 0).dom());
    mapSection.appendChild(mapHost);
    fragment.appendChild(mapSection);

    const logSection = document.createElement("section");
    logSection.className = "po-log";
    const logBar = document.createElement("div");
    logBar.className = "po-log__bar";
    const logTitle = document.createElement("h3");
    logTitle.textContent = UI_LABEL.logs;
    const logCount = document.createElement("span");
    logCount.className = "po-signature";
    logCount.textContent = logs.length ? logs.length + " 行" : "";
    logBar.append(logTitle, logCount);
    logSection.appendChild(logBar);
    const logBox = document.createElement("div");
    logBox.className = "po-log__box";
    logBox.dataset.log = "1";
    if (!logs.length) {
      const empty = document.createElement("div");
      empty.className = "po-empty";
      empty.style.color = "#8b8680";
      empty.textContent = runtimeMode()
        ? "这个节点正在提供服务。绿色标签是可达，红色标签是不可达。"
        : "还没有日志。执行此节点后，标准输出和标准错误会显示在这里。";
      logBox.appendChild(empty);
    } else {
      logs.forEach((line) => {
        const row = document.createElement("div");
        row.className =
          "po-log__line" +
          (line.stream === "stderr"
            ? " is-stderr"
            : line.stream === "meta"
              ? " is-meta"
              : "");
        const gutter = document.createElement("span");
        gutter.className = "po-log__gutter";
        gutter.textContent =
          line.stream === "stderr" ? "err" : line.stream === "meta" ? "·" : "out";
        const ts = document.createElement("span");
        ts.className = "po-log__ts";
        ts.textContent = formatTime(line.ts);
        const msg = document.createElement("span");
        msg.className = "po-log__msg";
        msg.textContent = line.message;
        row.append(gutter, ts, msg);
        logBox.appendChild(row);
      });
    }
    logSection.appendChild(logBox);
    fragment.appendChild(logSection);
    detailHost.appendChild(fragment);
    logBox.scrollTop = logBox.scrollHeight;
  }
}

function collectAllKeys(nodes, into = []) {
  for (const node of nodes || []) {
    into.push(node.key);
    if (node.children?.length) collectAllKeys(node.children, into);
  }
  return into;
}
