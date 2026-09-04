# Build Challenges & Technical Obstacles (Phase 10 Build Log)

During the development and testing of **AutoPey-Rescue**, we encountered several real-world engineering obstacles. Below is an honest record of what broke, the root causes, and how each issue was resolved.

---

### Obstacle 1: An Unfair Baseline Made the System Look Better Than It Was

- **What Broke**: Early benchmark runs showed the system outperforming blind retry by an implausibly large margin. The gap wasn't coming from better decision logic — it was coming from an underspecified baseline.

- **Why It Happened**: The naive-retry simulation had not been given category-specific recovery probabilities. As a result, it was implicitly modeled as retrying every failure type with roughly equal (and unrealistically low) odds of success — including categories such as `MANDATE_EXPIRED` and `HARD_DECLINE_OR_CANCELLED`, which structurally cannot recover through repeated retries, since they require customer action (re-authorization) or are terminal by definition. A baseline that can't win on failures it should never have been retrying isn't a fair comparison, and any policy benchmarked against it will look artificially strong.

- **How It Was Fixed**: Replaced the implicit baseline behavior with an explicit, documented recovery-probability table for both the baseline and the system, grounded in how each failure category actually behaves:
  - `MANDATE_EXPIRED`: requires customer re-authorization — blind retry ~5% vs. smart re-auth link ~42%
  - `INSUFFICIENT_BALANCE`: timing-dependent — blind 24h retry ~30% vs. 48h hold + Hinglish nudge ~68%
  - `TECH_TIMEOUT`: transient — resolves at ~88% within a short cooldown auto-retry, similar for both baseline and system
  - `HARD_DECLINE_OR_CANCELLED`: terminal — 0% recovery either way; the system stops contact immediately, the baseline keeps retrying anyway

  These figures are documented as modeled assumptions grounded in known UPI Autopay failure semantics, not values sourced from real transaction data — that distinction is stated explicitly rather than implied, and validating them against an actual merchant's failure logs is the natural next step. With a fair baseline in place, the result held on its own merits: **3.32x higher INR recovered per customer contact, with a 74.1% reduction in customer contacts.**

---

### Obstacle 2: Non-Standard JSON Codeblock Wrapping from LLM Responses

- **What Broke**: In `src/outreach.py`, `parse_promise_to_pay()` occasionally failed with `json.JSONDecodeError` when the model wrapped its response in markdown fences (e.g. a ```` ```json { "status": "PROMISED" } ``` ```` block instead of raw JSON).

- **Why It Happened**: Generative models frequently wrap structured output in markdown code fences even when explicitly prompted for raw JSON.

- **How It Was Fixed**: Added regex sanitization before parsing:
  ```python
  cleaned = re.sub(r"^```json\s*", "", raw_text, flags=re.MULTILINE)
  cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE).strip()
  ```
  Also added defensive fallback heuristics so that a missing API key, exhausted quota, or unparseable response degrades gracefully to `"UNCLEAR"` (or pattern matching) rather than failing the batch.

---

### Obstacle 3: Direct Script Execution vs. Package Import Path Resolution

- **What Broke**: Running `python src/run_batch.py` directly from the project root produced `ModuleNotFoundError: No module named 'src'`.

- **Why It Happened**: Invoking a script directly via `python src/run_batch.py` sets `sys.path[0]` to the script's own directory, omitting the project root. Absolute imports like `from src.diagnosis import diagnose` then fail unless the script is run via `python -m src.run_batch`.

- **How It Was Fixed**: Added dynamic project root resolution at the entry point of all runnable scripts:
  ```python
  sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
  ```
  This lets scripts run correctly whether invoked by direct path or module flag.

---

### Obstacle 4: Windows Console `cp1252` Encoding Crash on Currency Symbols

- **What Broke**: Running `src/data_generator.py` and `src/run_batch.py` from Windows PowerShell crashed with:
  ```
  UnicodeEncodeError: 'charmap' codec can't encode character '\u20b9' in position 31: character maps to <undefined>
  ```

- **Why It Happened**: Python's default stdout encoding on Windows is `cp1252` under certain locales rather than UTF-8, and printing the Unicode Indian Rupee symbol (`₹` / `\u20b9`) without explicitly configuring stream encoding raises an unhandled character-mapping exception.

- **How It Was Fixed**: Standardized console output across all CLI scripts to use ASCII `INR` / `Rs.` denominations in terminal printouts, while preserving full Unicode currency formatting in JSON artifacts and the Streamlit dashboard.
