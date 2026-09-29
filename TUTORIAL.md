# 电子书导出教程（HUB Scuola / Sanoma LibroMedia）

给一个图书链接，自动从你**已登录**的浏览器读取凭证，下载并导出为
**文字可选中/可复制**的 PDF。

目前支持两个平台，规则不同：

| | HUB Scuola (`young.hubscuola.it`) | bSmart (`books.bsmart.it`) | Sanoma (`ebook.sanoma.it`) | myLIM (`mylim.loescher.it`) |
|---|---|---|---|---|
| 页面渲染 | Nutrient/PSPDFKit | Nutrient/PSPDFKit | LibroMedia 6.0（Angular） | pdf.js |
| 图像 | 分块 tile（WebP） | 分块 tile（PNG/WebP） | 每页 `{p}/{p}.svg`（矢量页 + 字形） | 原版 PDF 整文件 |
| 文字层 | `{p}-text-content-v-1`（JSON 明文） | 同 HUB | `{p}.data`（加密 HTML，绝对定位 `<span>`） | PDF 自带 |
| 页尺寸/总数 | `document.json` | 同 HUB | `sizes.data`（加密 JSON） | PDF 自带 |
| 认证 | `X-PSPDFKit-Token` / `X-PSPDFKit-Image-Token` | 同 HUB（域名为 `pspdfkit.bsmart.it`） | CloudFront 签名 Cookie | `Authorization: JWT <token>` |
| 导出方式 | 拼图 + 叠加不可见文字 | 同 HUB | 打印 HTML（SVG 视觉 + 透明文字） | 下载原版 PDF |

> HUB 与 bSmart 都是 Nutrient/PSPDFKit 协议，共用 `download_book.py` / `build_book_pdf.py`。
> myLIM 最省事：出版社直接给出原版 PDF 的预签名直链，下载即得。

三个平台都已封装成**一条命令**。

---

## 0. 一次性环境准备

```bash
# Python 依赖
pip3 install --break-system-packages pillow reportlab pypdf

# 需要 Node.js（ego-browser 依赖）与 ego-browser
node --version
```

脚本目录：`/Users/lee/GolandProjects/pdf-export`

---

## 1. 登录一次

打开 ego 浏览器窗口，登录对应平台（HUB Scuola 或 Sanoma/My Place）。
ego-browser 会保存登录态，之后无需重复登录。

> Sanoma 需要**在某个标签页里把书打开**（URL 含 `ebook.sanoma.it/open-book`），
> 抓取脚本会自动在所有 ego 空间里找到这个标签页。

---

## 2. HUB Scuola 一键导出

```bash
cd /Users/lee/GolandProjects/pdf-export
python3 export_book.py "https://young.hubscuola.it/viewer/7358681?page=1"
```

产物：`output/<bookId>.pdf`

常用参数：
- `--limit 5` 先导 5 页验收
- `--scale 2` 清晰度倍数（默认 2 ≈150dpi）
- `--quality 86` JPEG 质量

流程：`capture_session.py` → `download_book.py` → `build_book_pdf.py`

---

## 3. Sanoma / LibroMedia 一键导出

```bash
cd /Users/lee/GolandProjects/pdf-export
python3 sanoma_export.py "https://ebook.sanoma.it/open-book"
```

产物：`output/sanoma/<productId>.pdf`

流程：`sanoma_capture.py` → `sanoma_fetch.py` → `sanoma_build.py`

> - 抓取的是当前打开的这本书（产品号从网络请求里识别）。
> - 若提示找不到资源：确认书已在标签页打开且已登录。

---

## 3b. bSmart 一键导出

```bash
cd /Users/lee/GolandProjects/pdf-export
python3 bsmart_export.py "https://books.bsmart.it/books/20315?page=0" \
        --out output/InfoComm.pdf
```

产物：`output/<bookId>.pdf`（或用 `--out` 指定名字，如上例的 `InfoComm.pdf`）

流程：`bsmart_capture.py` → `download_book.py` → `build_book_pdf.py`

> bSmart 与 HUB Scuola 同为 Nutrient/PSPDFKit 协议，抓 token 后复用同一套下载/合成脚本。
> 需要书已在 bSmart 标签页打开且已登录。

---

## 3c. myLIM / Loescher 一键导出

```bash
cd /Volumes/MAC/book-exportPDF
python3 loescher_export.py "https://mylim.loescher.it/#!/reader/9788858335604" \
        --out "output/loescher/Il tempo, l'uomo, il lavoro.pdf"
```

产物：`output/loescher/<isbn>.pdf`（省略 `--out` 时用书名命名）

流程：`loescher_capture.py` → 下载预签名 S3 直链

> - 只要 ego 浏览器登录了 myLIM 即可，**不需要**先把书打开在标签页里。
> - 拿到的就是出版社的原版 PDF：矢量、带可选中文字、和纸质书排版一致。
> - 直链有效期约 5 分钟；下载中断时重跑本命令会自动申请新直链。

---

## 4. 也可以分步执行

HUB：
```bash
python3 capture_session.py "https://young.hubscuola.it/viewer/<id>?page=1" 9
python3 download_book.py <id>
python3 build_book_pdf.py <id>
```

Sanoma：
```bash
python3 sanoma_capture.py "https://ebook.sanoma.it/open-book" 9
python3 sanoma_fetch.py <productId>
python3 sanoma_build.py <productId>
```

myLIM：
```bash
python3 loescher_capture.py "https://mylim.loescher.it/#!/reader/<isbn>"
# 得到一个预签名直链，直接用 curl/浏览器下载即可
python3 -c "import json;print(json.load(open('output/loescher/<isbn>/session.json'))['pdfUrl'])"
```

---

## 5. 产物目录

```
output/
  7358681.pdf                     # HUB 导出结果
  7358681/                        # HUB 中间数据（tiles/ text/）
  sanoma/
    1118992.pdf                   # Sanoma 导出结果
    1118992/
      session.json                # CloudFront cookies + 资源基址
      p0001.html … combined.html  # 解码后的每页 HTML
  loescher/
    Il tempo, l'uomo, il lavoro.pdf
    9788858335604/
      session.json                # JWT + 书名/作者 + 预签名直链
```

---

## 6. 常见问题

| 现象 | 解决 |
|------|------|
| HUB：`you are probably NOT logged in` | 重新登录 ego 浏览器 |
| HUB：`token expired` | 重新运行 `export_book.py`（自动重抓） |
| Sanoma：`could not find a book asset request` | 确认书已在标签页打开且已登录 |
| Sanoma：某页空白 | 若原书该页本身空白则正常（如样例第 2 页） |
| PDF 太大 | HUB 用 `--scale 1.5`；Sanoma 体积已较小 |
| myLIM：`API refused the PDF url` | 重新登录 myLIM（token 过期或书不在书架） |

---

## 7. 原理（简要）

**HUB Scuola**
- 每页由「图像分块 + 透明文字层」组成。
- 分块：`…/page-{i}-dimensions-{W}-{H}-tile-{x}-{y}-{tw}-{th}`（`X-PSPDFKit-Image-Token`）。
- 文字：`…/page-{i}-text-content-v-1`（`X-PSPDFKit-Token`）。
- 拼图后把文字按坐标以「不可见渲染模式」叠加 → 可选中。

**Sanoma / LibroMedia 6.0**
- 资源在 `npmitaly-pro-apidistribucion.sanoma.it`，用 CloudFront 签名 Cookie 鉴权。
- `{p}.data` 是加密的 HTML：先 `base64` 解码 → JS `unescape`（`%XX` 与 `%uXXXX`）
  → 按固定 key 逐位相减（字符码 Vigenère），解出可读 HTML。
- HTML 里 `<object>` 嵌入矢量页 `{p}/{p}.svg`，`text-container` 是一堆绝对定位的
  `<span>`（真正的文字+坐标）。
- 把 `.t` 文字设为 `color:transparent`（透明但可选中），用浏览器 `printToPDF`
  一次性打印所有页 → 视觉是矢量页，文字可选中复制。

**myLIM / Loescher**
- 阅读器 `mylim.loescher.it` 是 Angular + **pdf.js**，直接渲染出版社的原版 PDF。
- 鉴权 token 存在 `localStorage.token`（JWT），请求时用 `Authorization: JWT <token>`。
- `GET loeda.loescher.it/mialim2/api/v1/book/pdf/<isbn>/` 返回
  `{"url": "https://s3.eu-south-1.amazonaws.com/…?X-Amz-Signature=…"}`，
  即**原版 PDF 的预签名直链**（300 秒有效，下载无需再带 token）。
- `…/book/sommari/<isbn>/` 返回书名、作者、PDF 字节数与目录（用来命名文件）。
- 因此导出＝下载原文件：矢量、可选中、无失真，不需要任何拼页或嵌字处理。
