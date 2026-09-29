# Book ExportPDF

把电子书平台上的整本书导出为 **文字可选中 / 可复制** 的 PDF。

支持的平台：

| 平台 | 地址 | 协议 |
|------|------|------|
| HUB Scuola | `young.hubscuola.it` | Nutrient / PSPDFKit |
| bSmart | `books.bsmart.it` | Nutrient / PSPDFKit |
| Sanoma / LibroMedia 6.0 | `ebook.sanoma.it` | 自研（SVG + 加密 HTML） |
| myLIM / Loescher | `mylim.loescher.it` | pdf.js + 原版 PDF（presigned S3） |

> 仅供导出你本人有权访问的内容。

## 原理

导出的难点是：网页上文字能选中，是因为阅读器在图像层之上叠了一层**透明文字层**。
本工具会分别获取「页面图像」和「文字层」，再把文字按坐标以
**不可见渲染模式**叠加到 PDF 上，从而既保留画面又能选中复制。

- **HUB / bSmart（PSPDFKit）**
  - 图像分块：`…/page-{i}-dimensions-{W}-{H}-tile-{x}-{y}-{tw}-{th}`
  - 文字层：`…/page-{i}-text-content-v-1`（JSON，含每段文字的坐标）
  - 页尺寸/总页数：`document.json`
  - 鉴权：`X-PSPDFKit-Token` / `X-PSPDFKit-Image-Token`
- **Sanoma（LibroMedia）**
  - 资源走 CloudFront 签名 Cookie
  - 每页 `{p}.data` 是加密 HTML：`base64 → JS unescape(%XX 与 %uXXXX) → 逐位相减`
  - 解出后是绝对定位的文字 `<span>` + `<object>` 嵌入的矢量页 `{p}/{p}.svg`
  - 把文字设为透明后 `printToPDF`，得到「矢量画面 + 可选中文字」
- **myLIM（Loescher）**
  - 阅读器是 pdf.js，直接渲染出版社自己的原版 PDF，无需拼页/嵌字
  - `GET loeda.loescher.it/mialim2/api/v1/book/pdf/<isbn>/` 返回**预签名 S3 直链**（有效期 5 分钟）
  - 鉴权：`Authorization: JWT <token>`，token 存在 `mylim.loescher.it` 的 `localStorage.token`
  - 直接下载即得完整 PDF：矢量、带可选中文字、与纸质书一致
  - 另可从 `…/book/sommari/<isbn>/` 拿到书名/作者/目录（用于默认文件名）

## 环境准备

```bash
# Python 依赖
pip3 install --break-system-packages pillow reportlab pypdf

# Node.js（提供 npx）与 ego-browser
node --version
```

所有脚本通过 [ego-browser](https://www.npmjs.com/package/ego-browser) 复用你**已登录**的真实浏览器，
因此无需手动复制 Cookie/Token。使用前请先在 ego 浏览器里登录对应平台。

## 快速开始（一键）

```bash
# HUB Scuola
python3 export_book.py "https://young.hubscuola.it/viewer/7358681?page=1"

# bSmart
python3 bsmart_export.py "https://books.bsmart.it/books/20315?page=0" \
        --out "output/InfoComm.pdf"

# Sanoma / LibroMedia
python3 sanoma_export.py "https://ebook.sanoma.it/open-book"

# myLIM / Loescher
python3 loescher_export.py "https://mylim.loescher.it/#!/reader/9788858335604" \
        --out "output/loescher/Il tempo, l'uomo, il lavoro.pdf"
```

产物默认在 `output/` 下：
- HUB / bSmart：`output/<bookId>.pdf`（可用 `--out` 指定名称）
- Sanoma：`output/sanoma/<productId>.pdf`
- myLIM：`output/loescher/<isbn>.pdf`（默认用书名，也可用 `--out` 指定）

## 常用参数

```bash
--limit 5        只导出前 N 页（先验收）
--scale 2        清晰度倍数（默认 2 ≈150dpi）        # HUB / bSmart
--quality 86     JPEG 质量                            # HUB / bSmart
--workers 12     并发线程数                           # HUB / bSmart
--batch 40       Sanoma 分批打印的每批页数（大书用）
--out NAME.pdf   指定输出文件名
```

示例：先导 5 页验收

```bash
python3 export_book.py "https://young.hubscuola.it/viewer/7358681?page=1" --limit 5
```

## 分步执行

HUB / bSmart（同一套 PSPDFKit 流程）：

```bash
python3 capture_session.py "https://young.hubscuola.it/viewer/<id>?page=1"   # HUB 抓 token
python3 bsmart_capture.py "https://books.bsmart.it/books/<id>?page=0" 0     # bSmart 抓 token
python3 download_book.py <id>          # 下载图像分块 + 文字层（可断点续传）
python3 build_book_pdf.py <id> --out output/<name>.pdf
```

Sanoma：

```bash
python3 sanoma_capture.py "https://ebook.sanoma.it/open-book" 9
python3 sanoma_fetch.py <productId>    # 抓取并解密所有页 -> combined.html
python3 sanoma_build.py <productId>    # 浏览器分批打印并合并
```

myLIM / Loescher：

```bash
python3 loescher_capture.py "https://mylim.loescher.it/#!/reader/<isbn>"  # 抓 token + 元数据 + PDF 直链
python3 loescher_export.py <isbn> --out output/loescher/<name>.pdf       # 下载原版 PDF
```

## 文件说明

| 文件 | 作用 |
|------|------|
| `export_book.py` / `bsmart_export.py` / `sanoma_export.py` / `loescher_export.py` | 各平台一键入口 |
| `capture_session.py` / `bsmart_capture.py` | 从已登录浏览器抓 PSPDFKit token |
| `sanoma_capture.py` | 抓 Sanoma CloudFront 签名 Cookie + 资源基址 |
| `loescher_capture.py` | 抓 myLIM JWT + 书名/作者 + 原版 PDF 直链 |
| `download_book.py` | 下载页面分块与文字层（HUB / bSmart 通用，支持续传） |
| `build_book_pdf.py` | 拼图 + 叠加不可见文字，生成 PDF（HUB / bSmart） |
| `sanoma_fetch.py` | 抓取并解密 Sanoma 页面数据 |
| `sanoma_build.py` | Sanoma 分批 `printToPDF` 并合并 |
| `TUTORIAL.md` | 详细教程（含三平台差异与原理） |
| `PROCESS.md` | HUB 导出流程规则说明 |

> `stitch.py`、`stitch_text.py`、`build_pdf.py`、`download_all.py` 为早期试验脚本，保留作参考。

## 产物结构

```
output/
  7358681.pdf                     # 导出结果
  7358681/
    session.json                  # 会话凭证（已 gitignore，勿提交）
    document.json                 # 页数、页尺寸、标题
    tiles/p0001/…                 # 每页图像分块
    text/p0001.json               # 每页文字层
  sanoma/
    1118992.pdf
    1118992/…
  loescher/
    Il tempo, l'uomo, il lavoro.pdf   # 原版 PDF（矢量 + 可选中文字）
    9788858335604/
      session.json                    # JWT + 书名/作者 + 预签名直链
```

## 常见问题

| 现象 | 解决 |
|------|------|
| `you are probably NOT logged in` | 重新登录 ego 浏览器 |
| `token expired` | 重新运行一键脚本（会自动重抓） |
| Sanoma 某页空白 | 原书该页可能本身空白 |
| PDF 太大 | HUB/bSmart 用 `--scale 1.5`；Sanoma 用 `--batch` 调小每批 |
| bSmart 抓不到 token | 确认书已在 bSmart 标签页打开且已登录 |
| myLIM 阅读器报「Impossibile caricare il libro」 | 不影响导出：PDF 直链来自 API，照常可用 |
| myLIM `API refused the PDF url` | 重新登录 myLIM（token 过期或该书不在账号书架里） |
| myLIM 下载中断 | 直链 5 分钟过期，重跑 `loescher_export.py` 会自动换新直链 |

## 免责声明

本项目仅用于导出用户本人合法拥有访问权限的内容，请遵守各平台的服务条款与版权规定。
