# LCZ Literature Review Reproducible Workflow

## 1. Goal

Build a reproducible evidence table for the records in `LCZliterature.xlsx` and determine, for each paper:

1. Whether the paper performs Local Climate Zone (LCZ) mapping.
2. Whether the paper provides LCZ mapping results.
3. Whether the paper reports LCZ mapping accuracy.
4. Whether LCZ map/data products are publicly accessible.

The final output should be a reviewed workbook named:

```text
LCZliterature_reviewed.xlsx
```

## 2. Input Data

Input file:

```text
LCZliterature.xlsx
```

Current available source fields:

```text
Publication Type
Authors
Author Full Names
Group Authors
Article Title
Source Title
Conference Title
Conference Date
Conference Location
Conference Host
Abstract
Researcher Ids
ORCIDs
ISSN
eISSN
Publication Date
Publication Year
Volume
Issue
Part Number
Supplement
Special Issue
Start Page
End Page
Article Number
DOI
DOI Link
Early Access Date
Pubmed Id
UT (Unique WOS ID)
Web of Science Record
```

Do not overwrite the original `savedrecs (*.xls)` files. Keep `LCZliterature.xlsx` as the cleaned source table.

## 3. Recommended Output Fields

Add these review fields to the right side of the source table:

```text
screening_priority
is_lcz_related
is_lcz_mapping_paper
mapping_role
has_lcz_map_result
map_result_access
map_result_type
has_accuracy_assessment
accuracy_metrics
accuracy_values
has_confusion_matrix
has_training_samples
has_validation_samples
data_or_map_link
supplementary_link
code_link
evidence_source
evidence_text
review_status
reviewer
review_date
review_notes
```

Use controlled values where possible. This makes later analysis easier.

## 4. Controlled Vocabulary

### `screening_priority`

```text
high
medium
low
exclude
```

### `is_lcz_related`

```text
yes
no
unclear
```

### `is_lcz_mapping_paper`

```text
yes
no
unclear
```

### `mapping_role`

```text
creates_new_lcz_map
improves_lcz_mapping_method
validates_lcz_map
uses_existing_lcz_map
reviews_lcz_mapping
not_lcz_mapping
unclear
```

### `has_lcz_map_result`

```text
yes_public_data
yes_supplementary
yes_figures_only
yes_on_request
no
unclear
```

### `map_result_access`

```text
downloadable
repository
gee_asset
supplementary_file
paper_only
request_required
not_available
unclear
```

### `map_result_type`

```text
global_map
continental_map
national_map
regional_map
city_map
multi_city_maps
patch_dataset
training_areas
classification_result_only
not_applicable
unclear
```

### `has_accuracy_assessment`

```text
yes_quantitative
yes_qualitative
no
unclear
```

### `accuracy_metrics`

Use semicolon-separated values:

```text
OA
Kappa
F1
precision
recall
producer_accuracy
user_accuracy
confusion_matrix
cross_validation
class_accuracy
other
```

Example:

```text
OA; Kappa; confusion_matrix
```

### `review_status`

```text
auto_screened
metadata_reviewed
fulltext_reviewed
data_link_checked
needs_fulltext
needs_second_review
complete
exclude
```

## 5. Automatic Screening Rules

Create an initial screened file named:

```text
LCZliterature_screened.xlsx
```

Use `Article Title` and `Abstract` as the main text fields. Combine them into a temporary text string for matching.

### 5.1 LCZ Core Terms

Mark `is_lcz_related = yes` if the title or abstract contains one or more of:

```text
local climate zone
local climate zones
LCZ
LCZs
WUDAPT
World Urban Database and Access Portal Tools
LCZ Generator
```

If only `LCZ` appears, manually check context because `LCZ` may occasionally be another abbreviation.

### 5.2 Mapping Terms

Mapping evidence terms:

```text
map
maps
mapping
mapped
classification
classify
classifier
random forest
support vector machine
deep learning
convolutional neural network
CNN
object-based
remote sensing
Sentinel
Landsat
training area
training areas
training sample
training samples
```

If a record contains an LCZ core term plus at least one mapping term, set:

```text
screening_priority = high
is_lcz_mapping_paper = unclear
review_status = auto_screened
```

The value is `unclear` at this stage because metadata alone may not prove that the paper created a new LCZ map.

### 5.3 Accuracy Terms

Accuracy evidence terms:

```text
accuracy
accuracies
validation
validated
overall accuracy
OA
kappa
F1
F-score
precision
recall
producer accuracy
user accuracy
confusion matrix
cross-validation
independent validation
```

If a record contains an LCZ core term plus at least one accuracy term, set:

```text
has_accuracy_assessment = unclear
screening_priority = high
```

Do not mark `yes_quantitative` until the paper provides a concrete metric, table, figure, or value.

### 5.4 Data Availability Terms

Data/product evidence terms:

```text
dataset
data set
data availability
available at
supplementary
supplemental
repository
Zenodo
Figshare
Dryad
GitHub
Google Earth Engine
GEE
download
open data
training areas
benchmark
```

If a record contains an LCZ core term plus one or more data/product terms, mark:

```text
screening_priority = high
has_lcz_map_result = unclear
```

### 5.5 Likely User of Existing LCZ Data

Potential existing-data terms:

```text
using local climate zone
based on local climate zone
LCZ map was used
LCZ maps were used
according to LCZ
urban heat island
land surface temperature
thermal environment
heat exposure
```

If these terms appear but mapping/accuracy terms are weak, set:

```text
mapping_role = uses_existing_lcz_map
screening_priority = medium
```

This group still needs review, but it is usually not the main target if the goal is to find LCZ map products or mapping accuracy.

## 6. Manual Review Procedure

Review records in this order:

1. `screening_priority = high`
2. `screening_priority = medium`
3. Any remaining records with suspicious title/abstract matches

For each paper, check these sources in order:

1. `Article Title`
2. `Abstract`
3. Publisher page
4. Full text PDF
5. Supplementary information
6. Data availability statement
7. Linked repositories such as Zenodo, Figshare, GitHub, Google Earth Engine, WUDAPT, or LCZ Generator

## 7. Evidence Standard

Every positive or uncertain decision must include evidence.

### Good Evidence Examples

For `has_lcz_map_result`:

```text
The paper states that LCZ maps for 30 cities are available in the supplementary material.
```

For `has_accuracy_assessment`:

```text
The results section reports an overall accuracy of 84.2% and a Kappa coefficient of 0.78.
```

For `data_or_map_link`:

```text
https://zenodo.org/records/xxxx
```

### Evidence Text Rule

Keep `evidence_text` short. Record only the exact reason needed to support the label. Avoid copying long passages from papers.

## 8. Decision Rules

### 8.1 Is the paper an LCZ mapping paper?

Set `is_lcz_mapping_paper = yes` when the paper creates, improves, evaluates, or validates LCZ classification/mapping.

Examples:

```text
Creates a new LCZ map for one or more cities.
Creates a national, continental, or global LCZ product.
Compares LCZ classification algorithms.
Builds an LCZ benchmark dataset.
Reports accuracy of an LCZ classification.
```

Set `is_lcz_mapping_paper = no` when the paper only uses an existing LCZ map as an explanatory variable or analysis unit.

Examples:

```text
Uses LCZ classes to compare land surface temperature.
Uses an existing WUDAPT/LCZ product to analyze urban heat island intensity.
Discusses LCZ in the introduction but does not map or validate LCZs.
```

### 8.2 Does the paper provide LCZ map results?

Set `has_lcz_map_result = yes_public_data` if a downloadable map, dataset, asset, shapefile, raster, or repository is available.

Set `has_lcz_map_result = yes_supplementary` if LCZ map data are in supplementary files.

Set `has_lcz_map_result = yes_figures_only` if LCZ maps are only shown as figures in the article.

Set `has_lcz_map_result = yes_on_request` if the paper says data are available from authors upon request.

Set `has_lcz_map_result = no` if no map output or data product is provided.

### 8.3 Does the paper report LCZ mapping accuracy?

Set `has_accuracy_assessment = yes_quantitative` if the paper reports at least one numeric accuracy metric.

Common metrics:

```text
Overall accuracy
Kappa
F1 score
Precision
Recall
Producer accuracy
User accuracy
Class-level accuracy
Confusion matrix
Cross-validation accuracy
```

Set `has_accuracy_assessment = yes_qualitative` if validation is only visual, expert-based, or descriptive without numeric metrics.

Set `has_accuracy_assessment = no` if no validation or accuracy assessment is present.

## 9. Data Link Checking

When a paper claims public data availability:

1. Open the link.
2. Confirm the page is reachable.
3. Confirm it contains LCZ-related files, not just the article landing page.
4. Record the link in `data_or_map_link`.
5. Set `review_status = data_link_checked`.

Record file type in `review_notes`, for example:

```text
GeoTIFF LCZ raster available from Zenodo.
Training-area shapefiles available from Figshare.
GEE asset listed but direct download not provided.
Supplementary PDF only; no machine-readable LCZ map found.
```

## 10. Quality Control

Use a two-stage review for high-priority records.

### Stage 1: First Reviewer

The first reviewer fills all review fields and evidence.

### Stage 2: Second Reviewer

The second reviewer checks:

1. All records marked `yes_public_data`
2. All records marked `yes_quantitative`
3. All records marked `unclear`
4. Any record where the title suggests LCZ mapping but the reviewer marked `no`

If reviewers disagree, set:

```text
review_status = needs_second_review
```

Resolve disagreements by checking the full text and data availability statement.

## 11. Suggested File Naming

Use these filenames:

```text
LCZliterature.xlsx
LCZliterature_screened.xlsx
LCZliterature_reviewed.xlsx
LCZliterature_review_log.md
```

Do not rename files during review unless the project owner approves it.

## 12. Review Log Template

Create or update `LCZliterature_review_log.md` with entries like:

```text
## YYYY-MM-DD

Reviewer:
Input file:
Output file:
Records reviewed:
Records marked as LCZ mapping papers:
Records with public LCZ data:
Records with quantitative accuracy:
Notes:
```

## 13. Minimum Deliverables

At the end of the experiment, the intern should provide:

1. `LCZliterature_screened.xlsx`
2. `LCZliterature_reviewed.xlsx`
3. `LCZliterature_review_log.md`
4. A short summary with these counts:

```text
Total records
LCZ-related records
LCZ mapping papers
Papers with public LCZ map/data results
Papers with figure-only LCZ map results
Papers with quantitative LCZ mapping accuracy
Papers needing full-text review
Papers needing second review
```

## 14. Practical Notes

Metadata screening is only a first pass. A paper should not be marked as having public LCZ data or quantitative accuracy unless the reviewer has checked the article page, full text, supplementary material, or repository.

If a paper is behind an institutional login, use legal institutional access to download the PDF. Do not use shadow libraries or bypass publisher access controls.

