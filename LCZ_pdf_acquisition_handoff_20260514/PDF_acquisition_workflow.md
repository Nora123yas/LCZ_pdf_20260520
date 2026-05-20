# LCZ 文献 PDF 获取与全文抽取流程

## 1. 目标

根据 `LCZliterature.xlsx` / `LCZliterature_screened_stage1.xlsx` 中的文献清单，合法获取可访问的全文 PDF，并保存到统一目录，供后续自动抽取 LCZ 制图方法、制图精度和数据产品信息。

本流程不绕过期刊或数据库访问控制。若出版商页面需要机构登录、VPN、Shibboleth/OpenAthens 或浏览器会话，请由具备访问权限的人员在浏览器中完成登录后下载。

## 2. 目录结构

建议工作目录：

```text
解压后的 LCZ_pdf_acquisition_handoff_YYYYMMDD 文件夹
```

本包内脚本使用“脚本所在目录”作为工作目录，不依赖固定绝对路径。因此可以把整个文件夹移动到其他位置后继续运行。

关键文件：

```text
LCZliterature.xlsx                         # WOS 原始文章列表
LCZliterature_screened_stage1.xlsx          # Stage 1 自动筛查结果
acquire_fulltext_pdfs.py                    # 自动访问 DOI 并尝试下载 PDF
fulltext_extract_lcz_evidence.py            # 从 PDF 中抽取 LCZ 方法/精度/产品证据
fulltext_manual_download_queue.xlsx         # 人工下载队列
```

关键文件夹：

```text
fulltext_pdfs/      # PDF 最终保存位置
fulltext_pages/     # 自动脚本保存的出版商落地页 HTML
fulltext_text/      # PDF 抽取出的全文文本缓存
```

## 3. Python 运行环境

推荐使用带有 `pandas`、`openpyxl`、`pypdf` 的 Python 环境。

在 Codex 当前机器上，可使用 Codex 自带 Python：

```bash
/Users/jiyao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
```

如果工作路径发生变化，先进入解压后的包目录：

```bash
cd /path/to/LCZ_pdf_acquisition_handoff_YYYYMMDD
```

也可以通过环境变量指定 Python：

```bash
PYTHON=/path/to/python3 ./run_pdf_acquisition_batch.sh 0 100 high,medium 1
```

## 4. 自动尝试获取 PDF

先小批量测试：

```bash
python3 acquire_fulltext_pdfs.py \
  --priority high,medium \
  --limit 20 \
  --sleep 1
```

参数说明：

```text
--priority high,medium   只处理 Stage 1 中 high/medium 优先级文献
--limit 20               本轮最多处理 20 篇；设为 0 表示不限制
--start 0                从筛选后列表的第几条开始
--sleep 1                每次请求之间暂停 1 秒，避免过快请求
--no-download            只解析 PDF 候选链接，不实际下载
--email                  可选；用于 Unpaywall 开放获取接口，例如 name@example.com
```

示例：只生成候选链接，不下载：

```bash
python3 acquire_fulltext_pdfs.py \
  --priority high,medium \
  --limit 100 \
  --no-download
```

示例：从第 100 条开始处理 100 篇：

```bash
python3 acquire_fulltext_pdfs.py \
  --priority high,medium \
  --start 100 \
  --limit 100 \
  --sleep 1
```

输出文件：

```text
fulltext_acquisition_log.csv
fulltext_acquisition_log.xlsx
```

日志字段：

```text
record_id
title
doi
landing_url
landing_status
pdf_candidate_count
pdf_candidates
download_status
downloaded_pdf
download_error
```

`download_status` 常见取值：

```text
downloaded           已成功下载 PDF
no_pdf_downloaded    找到 PDF 候选链接，但程序化下载失败，常见于 403/机构登录
no_pdf_candidate     没有在 DOI 落地页解析到 PDF 链接
missing_doi          文献缺 DOI
candidates_only      使用 --no-download 时，只生成候选链接
```

## 5. 人工下载流程

如果自动下载失败，使用：

```text
fulltext_manual_download_queue.xlsx
```

该表包含 high/medium 文献的人工下载队列：

```text
record_id
screening_priority
title
authors
year
doi
doi_url
target_pdf_filename
save_to_folder
download_status
notes
```

人工处理步骤：

1. 打开 `fulltext_manual_download_queue.xlsx`
2. 优先处理 `first_100` 或 `queue_high_medium` 中的 high 文献
3. 在具备数据库权限的浏览器中打开 `doi_url`
4. 如需登录，使用机构入口、VPN、Shibboleth/OpenAthens 或图书馆数据库完成认证
5. 下载 PDF
6. 保存到：

```text
解压后包目录/fulltext_pdfs
```

7. 文件名优先使用 `target_pdf_filename`

如果保存文件名不完全一致，也可以继续处理；后续脚本会尝试按 DOI、标题、作者和年份匹配 PDF。

## 6. 命名规范

推荐 PDF 文件名：

```text
{record_id}_{DOI清洗后}.pdf
```

示例：

```text
WOS0010_10.1016_j.buildenv.2021.107879.pdf
```

不要在文件名中使用：

```text
/
:
?
*
|
<
>
```

## 7. 全文抽取

当 `fulltext_pdfs/` 中已有一批 PDF 后，运行：

```bash
python3 fulltext_extract_lcz_evidence.py
```

输出：

```text
LCZliterature_fulltext_extraction_draft.xlsx
LCZliterature_fulltext_extraction_draft.csv
```

新增字段包括：

```text
fulltext_pdf_file
fulltext_match_score
fulltext_checked
fulltext_sections_detected
fulltext_method_hits
fulltext_accuracy_hits
fulltext_accuracy_values
fulltext_product_hits
fulltext_product_access_candidate
fulltext_links
evidence_method_fulltext
evidence_accuracy_fulltext
evidence_data_availability_fulltext
```

重点检查：

```text
fulltext_match_score              PDF 与文献记录的匹配分数，越高越可靠
fulltext_accuracy_values          自动识别到的 OA/Kappa/F1 等精度值
fulltext_links                    Zenodo/Figshare/GitHub/GEE 等候选链接
evidence_*_fulltext               支撑判断的全文证据片段
```

## 8. 推荐工作分批

建议按批次处理，避免一次性请求过多出版商页面：

```bash
# 第 1 批
python3 acquire_fulltext_pdfs.py --priority high,medium --start 0 --limit 100 --sleep 1

# 第 2 批
python3 acquire_fulltext_pdfs.py --priority high,medium --start 100 --limit 100 --sleep 1

# 第 3 批
python3 acquire_fulltext_pdfs.py --priority high,medium --start 200 --limit 100 --sleep 1
```

每批结束后查看：

```text
fulltext_acquisition_log.xlsx
```

把 `no_pdf_downloaded` 和 `no_pdf_candidate` 的文献交给人工浏览器下载。

## 9. 质量控制

人工下载后请抽查：

1. PDF 是否是正文全文，不是 supplementary、cover page 或 abstract page
2. PDF 是否对应正确 DOI/标题
3. 文件是否能正常打开
4. 若同一文献有 article PDF 和 supplementary PDF，正文 PDF 放入 `fulltext_pdfs/`；补充材料可另建：

```text
supplementary_files/
```

## 10. 合规说明

允许：

```text
通过机构订阅、图书馆数据库、出版社页面、开放获取仓库下载有权限访问的 PDF。
保存用于本项目文献综述和信息提取的研究副本。
记录 DOI、数据链接、证据片段和元数据。
```

不允许：

```text
绕过出版社或数据库访问控制。
使用盗版论文库。
共享超出许可范围的 PDF。
批量高频请求导致数据库或出版社服务异常。
```

