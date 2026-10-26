# Question CSV — schema v1

The standard for bulk-authoring a test. One file, one fixed set of columns, one
meaning per column. Written for whoever is preparing the paper, not just for
whoever maintains the importer.

- **Schema version:** `1` (`courses.csv_import.SCHEMA_VERSION`)
- **Machine-readable contract:** `GET /api/staff/import-jobs/schema/`
- **Downloadable template:** `GET /api/staff/import-jobs/template/`
- **Importer:** `courses/csv_import.py`
- **Spec:** `docs/FEATURE_SPEC_TEST_SERIES.md` §4

The template and the parser are generated from the same constant, so a file
downloaded today is still accepted by the importer tomorrow.

---

## 1. How a file is delivered

The backend **never accepts an upload** and **never stores the file**. You host
the CSV somewhere that serves it over HTTPS and give the system its URL.

| Rule | Value |
|---|---|
| Scheme | `https://` only — plain `http` is refused |
| Host | Public addresses only; loopback, private, link-local and metadata addresses are refused |
| Redirects | Not followed; a redirect is an error |
| Encoding | UTF-8 (a BOM is tolerated and stripped) |
| Size | ≤ 2 MiB |
| Rows | ≤ 2,000 data rows |
| Store | The URL, a SHA-256 of the exact bytes, row counts and a capped error summary |

What is persisted are ordinary `Question`, `Choice` rows — the CSV itself is
never kept, in the database or on disk.

---

## 2. Columns

Header names are matched case-insensitively and the order does not matter. A
column outside this list is a **whole-file rejection**, so a typo cannot silently
drop a field. `question_text`, `option_a`, `option_b` and `correct_option` must
be present.

| Column | Required | Stored as | Rules |
|---|---|---|---|
| `section` | no | `Question.topic` (max 120) | Blank ⇒ `General`. This is the section the exam window groups by. |
| `question_type` | no | `Question.question_type` | `single_choice` (default), `multiple_choice`, `true_false`. Anything else is rejected, never downgraded. |
| `question_text` | **yes** | `Question.prompt` | ≤ 5,000 characters. Must be unique within the file (ignoring case and repeated spaces). |
| `option_a` | **yes** | `Choice.text` of position 0 | ≤ 400 characters |
| `option_b` | **yes** | `Choice.text` of position 1 | ≤ 400 characters |
| `option_c` | no | `Choice.text` of position 2 | ≤ 400 characters |
| `option_d` | no | `Choice.text` of position 3 | ≤ 400 characters |
| `option_e` | no | `Choice.text` of position 4 | ≤ 400 characters |
| `correct_option` | **yes** | `Choice.is_correct` | `B` for one answer; `A\|C` or `A,C` for several. Must name an option that exists on **that row**. |
| `explanation` | no | `Question.explanation` | Shown after submission. |
| `marks` | no | `Question.marks` | Decimal ≥ 0. Blank ⇒ the test's `marks_per_question`. |
| `negative_marks` | no | `Question.negative_marks` | Decimal ≥ 0 (a penalty *amount*, always positive). Blank ⇒ the test's `negative_marks_per_wrong`. |
| `difficulty` | no | `Question.difficulty` | `easy`, `medium` or `hard`. Blank ⇒ unset. |

`difficulty` is authoring metadata only today; it does not change scoring.

### Option rules

- Options must be **contiguous**: if `option_c` is filled, `option_a` and
  `option_b` must be too. A gap would shift the letters and mis-score the paper,
  so it is an error rather than a guess.
- At least two options per question.
- `true_false` must carry exactly two options (usually `True` / `False`) and one
  correct key.
- `single_choice` must carry exactly one correct key. Use `multiple_choice` for
  several — the importer will not quietly keep the first key.

### A worked example

```csv
section,question_type,question_text,option_a,option_b,option_c,option_d,option_e,correct_option,explanation,marks,negative_marks,difficulty
Reasoning,single_choice,"Which number completes 3, 6, 12, 24?",36,48,30,42,,B,Each term doubles.,2,0.5,easy
Reasoning,multiple_choice,Which of these are prime numbers?,2,3,4,6,,A|B,2 and 3 are prime.,2,0.5,medium
```

Quote any cell that contains a comma, a quote or a line break — ordinary CSV
rules apply.

---

## 3. Rejection codes

Every row problem is returned with its Excel row number (the header is row 1),
the offending column and a stable code:

| Code | Meaning |
|---|---|
| `missing_prompt` | `question_text` is empty |
| `prompt_too_long` | over 5,000 characters |
| `section_too_long` | over 120 characters |
| `bad_question_type` | not one of the three supported types |
| `bad_difficulty` | not `easy` / `medium` / `hard` |
| `option_too_long` | an option over 400 characters |
| `option_gap` | an empty option sits before a filled one |
| `too_few_options` | fewer than two options |
| `true_false_options` | `true_false` with more or fewer than two options |
| `missing_correct` | no `correct_option` |
| `bad_correct_key` | a key that is not `A`–`E` |
| `correct_without_option` | the key names an empty option |
| `duplicate_key` | `A|A` |
| `too_many_correct` | several keys on a `single_choice` |
| `true_false_correct` | more than one key on a `true_false` |
| `duplicate_prompt` | the same question text appears twice in the file |
| `bad_number` | `marks` / `negative_marks` is not a decimal |
| `negative_number` | a negative mark or penalty value |

Whole-file rejections happen before any row work: empty file, no data rows,
unknown / missing / duplicate / blank header, too many rows, too large, not
UTF-8, non-HTTPS URL, private host, unresolvable host, redirect, HTTP error.

Messages are deliberately short and never echo the question text back in bulk,
so an error report cannot become a copy of the paper.

---

## 4. The workflow

1. **Create a job** — `POST /api/staff/import-jobs/` with `{"quiz": <id>, "source_url": "https://…"}`.
2. **Validate** — `POST /api/staff/import-jobs/{id}/validate/`. The file is
   downloaded, parsed and fully validated. The response carries counts, every
   error, warnings, a preview of the parsed questions, and the SHA-256 digest.
   **Nothing is written** to the question bank.
3. **Confirm** — `POST /api/staff/import-jobs/{id}/confirm_import/` with
   `{"mode": "append"}` or `{"mode": "replace"}`. The file is re-fetched; if its
   digest no longer matches, the import is refused and the job goes back to
   `failed`, so the file imported is always the file previewed.
4. **Result** — `201` with `imported_rows`, or `409` when a `replace` is refused
   because the test already has attempts.

### Append vs replace

| Mode | Behaviour | When |
|---|---|---|
| `append` (default) | Existing questions kept; new ones continue the position numbering. | Adding questions to a paper. |
| `replace` | Existing questions deleted first, positions restart at 1. | Re-importing a corrected draft. |

`replace` is refused when the test has any attempt: answers reference questions
with `ON DELETE CASCADE`, so deleting questions would destroy submitted answer
sheets. Create a new test for a new version of a published paper. The override
(`allow_replace_with_attempts: true`) exists for a genuine reset and is
deliberately explicit.

A second import of the same job is refused — one job is one import. Importing
the same file through a fresh job is allowed and shows an `already_on_test`
warning per matching question, so a double import is at least deliberate.

### All or nothing

A file with **one** bad row imports **zero** questions. Validation and writing
are separate steps, the write runs inside one transaction and takes a row lock
on the test, and the command exits non-zero rather than half-filling a paper.

---

## 5. Export

`GET /api/staff/import-jobs/export/?quiz=<id>` returns the test's questions in
the same v1 schema, so an export can be edited and re-imported. Export covers
questions only — never student attempts or answers — and a cell beginning with
`=`, `+`, `-` or `@` is prefixed with `'` so a spreadsheet cannot execute it.
Negative numbers are left alone because they are numbers, not formulas.

---

## 6. Command line

For a paper prepared on disk, the same validator is available without the API:

```bash
# print the template
python manage.py import_questions --template

# check a file, write nothing
python manage.py import_questions --quiz 12 --file questions.csv --dry-run

# import it
python manage.py import_questions --quiz 12 --file questions.csv

# replace a draft test, or pull a test back out as CSV
python manage.py import_questions --quiz 12 --file questions.csv --mode replace
python manage.py import_questions --quiz 12 --export questions.csv
```

`--url` accepts an HTTPS link instead of `--file`, using the same SSRF-guarded
fetcher as the API. The command prints the same row errors, so what passes here
passes in the API.

### From Django admin

There is no staff console in the frontend yet, so `/admin/ → CSV import jobs`
carries two actions that call the same importer:

- **Validate the selected files** — fetches and validates, stores the counts and
  digest, writes nothing.
- **Import the selected files** — imports *validated* jobs only, append mode
  only, and refuses a job whose file no longer matches the digest recorded at
  validation.

`replace` is deliberately not offered from the admin: it is a destructive
operation that belongs behind an explicit API call or the command flag.

---

## 7. Changing the schema

The columns live in one tuple, `csv_import.COLUMNS`, with `(name, required,
help)`. Adding, removing or renaming a column is a schema change:

1. bump `SCHEMA_VERSION`;
2. update the tuple (the template, the parser, the schema endpoint and the
   export all follow automatically);
3. keep the previous version readable, or document the migration for hosts that
   are still hosting v1 files;
4. extend `courses/tests/test_csv_import.py` with a test for the new column.

`test_template_is_itself_valid` fails if the shipped template stops parsing, so
the template can never drift from the importer.
