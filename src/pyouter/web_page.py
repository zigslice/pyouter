"""HTML shell for the local pyouter web ui (gd5)."""

import json

from pyouter.webui.labels import BOOT_LABELS

PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN" data-gd-theme="orange">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>pyouter</title>
<link rel="stylesheet" href="/webui/gd5/ui/css/ui.css">
<link rel="stylesheet" href="/webui/HomePage.css">
<script>
window.__PYOUTER_BOOT__ = /*__BOOT__*/null || {};
</script>
</head>
<body>
<div id="home"></div>
<script type="module" src="/webui/app.js"></script>
</body>
</html>
"""


def render_page(boot):
    payload = dict(boot or {})
    labels = dict(BOOT_LABELS)
    labels.update(payload.get("labels") or {})
    payload["labels"] = labels
    encoded = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    return PAGE.replace("/*__BOOT__*/null", encoded)
