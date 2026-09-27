# PDF 提取与导出规则说明

目标：把 `https://young.hubscuola.it/viewer/7358681` 的整本书（600 页）导出为
**带可选中/可复制文字层**的 PDF。

## 1. 页面结构分析

- 站点是 Angular SPA + Nutrient (PSPDFKit) 阅读器。
- 真正的页面内容渲染在 `.PSPDFKit-Container` 的 **shadow DOM** 里。
- 每个 URL `?page=N` 对应 **第 N 页**（`N` 从 1 开始）。
- 每页由两套数据组成，来自 `ms-pdf.hubscuola.it`：
  1. **图像分块（tiles）**：实际画面，WebP，高清版本 `1191x1645`。
  2. **文字层（text-content）**：每个文本块的文字与坐标，JSON。浏览器把它透明叠在图片上，所以网页里文字可选中。

## 2. 为什么导出的图片 PDF 不能选字

导出的图片版只包含了 tiles（像素），没有文字对象，所以不可选。
要能选字，必须把文字层按坐标以**不可见文字**（text render mode 3）嵌进 PDF。

## 3. 认证方式（关键）

请求 `ms-pdf.hubscuola.it` 需要两个不同 token（登录会话生成，随会话有效）：

| 资源 | 必需 Header |
|------|-------------|
| tiles 图像 | `X-PSPDFKit-Image-Token: <token>` |
| text-content / document.json | `X-PSPDFKit-Token: <token>` |

公共 Header：

```
PSPDFKit-Platform: web
PSPDFKit-Version: protocol=5, client=1.9.1, client-git=2720d87ea9
Referer: https://young.hubscuola.it/
User-Agent: <Chrome UA>
```

获取方式（已登录的浏览器）：
1. 打开 `viewer/7358681?page=1`。
2. 用 CDP `Network.enable` + 刷新，从 `Network.requestWillBeSent` 里读取上述两个 token 与 `/h/<hash>` 基址。
3. 保存到 `output/session.json`。

## 4. 资源 URL 规则

设基址 `BASE = https://ms-pdf.hubscuola.it/i/d/7358681/h/<hash>`，页序号 `idx = N-1`：

**图像分块**（每页固定 12 块）：

```
BASE/page-{idx}-dimensions-1191-1645-tile-{x}-{y}-{w}-{h}
```

网格（列 x 宽 w；行 y 高 h）：

```
列: (0,512) (507,512) (1014,177)
行: (0,512) (507,512) (1014,512) (1521,124)
```

文字层：

```
BASE/page-{idx}-text-content-v-1
```

（若 404 依次尝试 `v-2`、`v-3`。）

另外 `BASE/document.json` 含 `pageCount`（=600）与每页尺寸。

## 5. 拼页规则

- 画布 `1191x1645` 像素，白底。
- 12 块按 `(x, y)` 直接 `paste`（块尺寸与 `(w,h)` 一致，可直接定位）。
- 拼好的整页编码为 JPEG（质量 86）后写入 PDF 页面。

## 6. 文字层坐标规则

`text-content` 是嵌套节点树，叶子节点形如：

```json
{ "bbox": [x, y_top, width, height],
  "element": { "type": "text", "text": "..." } }
```

- 单位：**PDF 点**，页面尺寸 `595.276 x 822.047`。
- 原点：**左上角**，`y_top` 为距顶部距离。
- 提取：递归 `children` / `nodes`，收集 `element.type == "text"` 且文字非空的节点（已验证无重复）。

嵌入到 PDF（原点左下角）：

```
font_size  = height
baseline_y = PT_H - y_top - height * 0.80
x          = bbox.x
水平缩放    = width / 文字在 font_size 下的自然宽度   (限制在 15%~500%)
渲染模式    = 3  (不可见，仅用于选择/复制)
字体        = Arial Unicode (覆盖意大利语重音字符)
```

## 7. 完整流程

```bash
# 1. 从浏览器抓 token -> output/session.json
#    (ego-browser 脚本)

# 2. 并发下载 600 页 tiles + 文字层（可断点续传）
python3 download_all.py        # -> output/full/tiles/pXXXX/ 与 output/full/text/pXXXX.json

# 3. 拼页 + 嵌文字层，生成完整 PDF
python3 build_pdf.py           # -> output/full-600pages.pdf
```

## 8. 产物

- `output/full-600pages.pdf`：600 页，图像 + 可选中文字层。
- 单页约 0.3 MB，总计约 207 MB（JPEG q86）。

## 9. 备注

- token 与登录会话绑定，会话失效后需重新抓取。
- 文字层为原书 PDF 的文本，选择时可复制；排版基于坐标水平缩放，个别行可能有轻微偏差，但不影响阅读与复制。
- 本流程仅用于导出用户本人有权访问的内容。
