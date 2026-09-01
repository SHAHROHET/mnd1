# MND Care Assistant — Developer Guidelines & Repository Rules (`AGENTS.md`)

This document defines the rules, folder structures, and coding standards that **must** be strictly followed by all AI assistants and human developers modifying this repository.

---

## 📁 1. Repository Directory Structure

Maintain a clean root directory. Do not add files or folders outside this structure:
- **`backend/`** — Python FastAPI backend code (routers, indexer, guardrails).
- **`data/`** — All knowledge base datasets, scraped content, and metadata JSONL files.
- **`images/`** — Publicly served static image assets (mapped to `/images` StaticFiles).
- **`static/`** — Frontend single page application files (`index.html`, `app.js`, `style.css`).
- **`tests/`** — Backend unit tests and adversarial test suites.
- **`updated.md`** — The developer changelog (to be updated after every single commit).
- **`AGENTS.md`** — This rules and standards directory (do not modify without explicit instruction).

---

## 💻 2. Coding Principles & Standards

### Keep Code Low-Bloat & Minimal
- Write concise, readable code. Avoid writing duplicate helper routines.
- Reuse variables, utilities, and components where possible.
- Avoid introducing large external library dependencies unless absolutely necessary.

### Client-Side Self-Healing Image Matching
- The AI model frequently hallucinates relative paths (e.g. `/static/toilet.png`) or outputs unencoded spaces (e.g. `/images/Over toilet aid.jpg` which breaks markdown).
- **Rule:** Never render images directly from Markdown input without validation. All Markdown images parsed via `marked` must pass through the `findImageInClientMap` matching resolver in [`static/app.js`](file:///c:/Users/User1/Downloads/MND%20DATA/static/app.js) to resolve them to the correct, URL-encoded local static asset.

### Offline & Fallback Resilience
- The application must remain fully functional in **Offline RAG Mode** when the `DEEPSEEK_API_KEY` environment variable is not configured.
- Ensure the local vector search indexer compiles successfully and streams structured responses with fallback Markdown images.

### Security & Input Sanitization
- Every input query must pass through [`backend/guardrails.py`](file:///c:/Users/User1/Downloads/MND%20DATA/backend/guardrails.py) (`sanitize_input`) to block prompt injections, rate limit violations, or bad payloads before hitting FastAPI search pathways.

---

## 📝 3. Commit Logging Mandate (`updated.md`)

Immediately after committing any change, you **MUST** update [`updated.md`](file:///c:/Users/User1/Downloads/MND%20DATA/updated.md):
1. Append a new row to the top of the changelog table.
2. Provide:
   - **Commit Hash** (e.g. `e061792`).
   - **Date & Time** in format `YYYY-MM-DD HH:MM:SS`.
   - **Type** (`feat`, `fix`, `style`, `refactor`, `chore`, `docs`).
   - **Technical Description** (summarizing architectural edits).
   - **Plain Language Description** (explaining the user-facing benefit for non-technical users).
   - **Clickable File Links** pointing to the exact modified files in the workspace.

---

## 🧪 4. Testing & Verification

Before pushing any changes:
1. **Clear cache and rebuild index:** Remove `backend/index_cache.pkl` and run tests to ensure database indexing works from scratch.
2. **Run tests:** Verify 100% test pass rate using:
   ```bash
   python tests/test_backend.py
   ```
3. **Browser Check:** Run a browser validation to confirm CSS responsive styling and JS event listeners function without console errors.

---

## ⏱️ 5. Deployment Timestamp Mandate

Because this web application is in active development:
- **Rule:** Every time changes are updated or pushed to GitHub, update the visible deployment timestamp in [`static/index.html`](file:///c:/Users/User1/Downloads/MND%20DATA/static/index.html) inside `<span id="updateTimestampBadge">Updated: YYYY-MM-DD HH:MM</span>`.
- Ensure this timestamp matches the date & time recorded in [`updated.md`](file:///c:/Users/User1/Downloads/MND%20DATA/updated.md).
