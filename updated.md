# Chatbot Project Development Log & Rollback Guide

This file documents every major architectural and features change made to the MND Care Assistant project. If you wish to roll back or undo any specific change, refer to the **Git Rollback Reference** section below.

---

## 📜 Git Commit History & Changelog

| Commit Hash | Date & Time | Type | Summary of Changes (Technical) | What this does (Plain Language) | Modified Files |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`ccedb9d`** | `2026-09-01 12:15:00` | `feat` | Implement multi-turn conversation context memory: sanitize and validate history array, expand follow-up queries using previous user turns for better RAG retrieval, deduplicate current user message from history, increase conversation window from 6→10 turns sent to DeepSeek, move chatHistory.push(user) before API call so backend receives full context, increase frontend sliding window from 10→20 messages. | The chatbot now remembers what you said earlier in the conversation. Follow-up questions like "summarize that in one sentence" or "tell me more about that" now work correctly because the AI has the full conversation context. The "New Chat" button clears the memory so you can start fresh. | [`backend/app.py`](file:///c:/Users/User1/Downloads/MND%20DATA/backend/app.py), [`static/app.js`](file:///c:/Users/User1/Downloads/MND%20DATA/static/app.js) |
| **`58103e8`** | `2026-08-31 20:10:53` | `feat` | Merge the second downloaded corpus batch into `data/`, including refreshed category 16 runs and new categories 17-21 for clinical trials/research, culturally accessible and regional support, genetics/family risk testing, epidemiology/registries, and driving/transport/vehicle modification. Refresh active aggregate metadata for category 16 and add aggregate metadata for categories 17-21. | The chatbot now has access to the latest downloaded knowledge areas, including research trials, genetics, regional/cultural support, MND risk/registry information, and transport or vehicle-modification guidance. | [`data/16_forms_templates_directories`](file:///c:/Users/User1/Downloads/MND%20DATA/data/16_forms_templates_directories), [`data/17_clinical_trials_research`](file:///c:/Users/User1/Downloads/MND%20DATA/data/17_clinical_trials_research), [`data/18_culturally_accessible_regional_support`](file:///c:/Users/User1/Downloads/MND%20DATA/data/18_culturally_accessible_regional_support), [`data/19_genetics_family_risk_testing`](file:///c:/Users/User1/Downloads/MND%20DATA/data/19_genetics_family_risk_testing), [`data/20_risk_factors_epidemiology_registries`](file:///c:/Users/User1/Downloads/MND%20DATA/data/20_risk_factors_epidemiology_registries), [`data/21_driving_transport_travel_vehicle_modification`](file:///c:/Users/User1/Downloads/MND%20DATA/data/21_driving_transport_travel_vehicle_modification), [`data/metadata`](file:///c:/Users/User1/Downloads/MND%20DATA/data/metadata) |
| **`4afa7ca`** | `2026-08-31 19:04:02` | `feat` | Move newly uploaded treatment, emergency planning, and forms/template datasets into the canonical `data/` corpus layout; remove obsolete root-level corpus duplicates; add metadata-signature validation so stale `index_cache.pkl` is rebuilt automatically; refine small-talk retrieval suppression and remove fixed custom-guide wording. | The project folder is cleaner and production-style, the chatbot now searches the new uploaded data, stale search caches refresh automatically, and casual greetings no longer show unrelated resource cards or forced tailored-guide text. | [`backend/app.py`](file:///c:/Users/User1/Downloads/MND%20DATA/backend/app.py), [`backend/indexer.py`](file:///c:/Users/User1/Downloads/MND%20DATA/backend/indexer.py), [`tests/test_backend.py`](file:///c:/Users/User1/Downloads/MND%20DATA/tests/test_backend.py), [`data/metadata/14_treatments_medicines_documents.jsonl`](file:///c:/Users/User1/Downloads/MND%20DATA/data/metadata/14_treatments_medicines_documents.jsonl), [`data/metadata/15_emergency_planning_documents.jsonl`](file:///c:/Users/User1/Downloads/MND%20DATA/data/metadata/15_emergency_planning_documents.jsonl), [`data/metadata/16_forms_templates_directories_documents.jsonl`](file:///c:/Users/User1/Downloads/MND%20DATA/data/metadata/16_forms_templates_directories_documents.jsonl) |
| **`c5f37b5`** | `2026-08-31 15:53:49` | `feat` | Add localStorage user profile payload support, validated profile prompt injection for `/api/chat`, dark/light theme persistence, relevant-image gating, duplicate search-result filtering, profile/theming UI controls, cache-busted frontend assets, and focused backend tests. | The assistant can now remember a simple local profile, tailor answers more clearly by role and NSW/VIC/etc. location, switch between dark and light mode, avoid irrelevant images, and reduce repeated search results in chat answers. | [`backend/app.py`](file:///c:/Users/User1/Downloads/MND%20DATA/backend/app.py), [`backend/indexer.py`](file:///c:/Users/User1/Downloads/MND%20DATA/backend/indexer.py), [`static/app.js`](file:///c:/Users/User1/Downloads/MND%20DATA/static/app.js), [`static/index.html`](file:///c:/Users/User1/Downloads/MND%20DATA/static/index.html), [`static/style.css`](file:///c:/Users/User1/Downloads/MND%20DATA/static/style.css), [`tests/test_backend.py`](file:///c:/Users/User1/Downloads/MND%20DATA/tests/test_backend.py) |
| **`d8e8d3a`** | `2026-08-31 11:24:21` | `feat` | Expand greeting fast-path with compiled regex matching 25+ casual patterns (`how are you`, `thanks`, `wassup`, etc.), randomized response pool of 5 templates, and add small-talk brevity rule to `SYSTEM_PROMPT_TEMPLATE`. | Greetings like "how are you?", "thanks", "good morning" now instantly return a short, randomly varied friendly response without burning any API tokens. The AI is also instructed to keep small talk to 1-2 sentences even when the LLM is used. | [`backend/app.py`](file:///c:/Users/User1/Downloads/MND%20DATA/backend/app.py), [`tests/test_backend.py`](file:///c:/Users/User1/Downloads/MND%20DATA/tests/test_backend.py) |
| **`75c328b`** | `2026-08-31 11:12:44` | `feat` | Add greeting fast-path in `backend/app.py` to bypass RAG indexer for simple greetings (`hi`, `hello`, `hey`, etc.) and return a concise welcome message. Added unit test in `tests/test_backend.py`. | When you type a simple greeting like "hi" or "hello", the assistant now replies with a short, friendly welcome instead of a massive wall of text. This makes casual conversations feel natural and fast. | [`backend/app.py`](file:///c:/Users/User1/Downloads/MND%20DATA/backend/app.py), [`tests/test_backend.py`](file:///c:/Users/User1/Downloads/MND%20DATA/tests/test_backend.py) |
| **`58f22f8`** | `2026-08-31 11:00:56` | `feat` | Refactor scroll state tracking in `static/app.js` to use `isUserAtBottom` boolean with 100px threshold check. | Updated the scroll tracking to run a Smart Auto-Scroll system. If you scroll up manually while a message is typing, the automatic scrolling pauses instantly so you can read in peace. A floating "Scroll to Bottom" button also appears to let you jump back down to the active stream. | [`static/app.js`](file:///c:/Users/User1/Downloads/MND%20DATA/static/app.js) |
| **`ef5f553`** | `2026-08-31 10:49:39` | `fix` | Add `position: relative` to `.chat-messages` in `static/style.css` to fix `offsetTop` scroll computations, and version script import. | Fixed a layout bug where the browser calculated scroll positions based on the wrong background container, causing the question bubble to be pushed off-screen. Also added a version update to force browsers to load the fresh code without caching. | [`static/style.css`](file:///c:/Users/User1/Downloads/MND%20DATA/static/style.css), [`static/index.html`](file:///c:/Users/User1/Downloads/MND%20DATA/static/index.html) |
| **`a46aebb`** | `2026-08-31 10:45:23` | `fix` | Change stream completion scroll target to `userRow.offsetTop` (question row) in `static/app.js` to align both bubbles. | Adjusted the automatic scroll behavior so that the page aligns to the top of your question bubble instead of the answer bubble, ensuring your question doesn't get hidden behind the top navigation bar. | [`static/app.js`](file:///c:/Users/User1/Downloads/MND%20DATA/static/app.js) |
| **`afc7bb3`** | `2026-08-31 10:36:55` | `fix` | Add scroll-to-element offset calculation on stream end in `static/app.js` to shift focus to start of response. | Fixed the chatbot scroll behavior so that when the assistant finishes writing a long answer, the screen smoothly slides back up to the start of the answer so you can read it from the beginning without having to manually scroll up. | [`static/app.js`](file:///c:/Users/User1/Downloads/MND%20DATA/static/app.js) |
| **`5de9889`** | `2026-08-31 10:27:52` | `docs` | Add `AGENTS.md` repository rules and developer guidelines. | Created a developer guidelines file (`AGENTS.md`) that commands future developers and AI assistants to write simple code, use the self-healing image map, and log their changes. | [`AGENTS.md`](file:///c:/Users/User1/Downloads/MND%20DATA/AGENTS.md) |
| **`e061792`** | `2026-08-31 10:22:50` | `refactor` | Move content directories and knowledge base datasets to `data/` folder and update `indexer.py` paths. | Cleaned up the main project folder by moving all raw data, text, and knowledge base documents into a single 'data' folder, keeping the project organized and professional. | [`backend/indexer.py`](file:///c:/Users/User1/Downloads/MND%20DATA/backend/indexer.py) |
| **`af282c1`** | `2026-08-31 10:17:08` | `docs` | Add `Date & Time` column to `updated.md` changelog. | Added exact date and time details to the project's modification log. | [`updated.md`](file:///c:/Users/User1/Downloads/MND%20DATA/updated.md) |
| **`41390ea`** | `2026-08-31 10:14:06` | `docs` | Add `updated.md` changelog and rollback guide. | Created this log file to document all changes and provide a reference to restore older versions. | [`updated.md`](file:///c:/Users/User1/Downloads/MND%20DATA/updated.md) |
| **`e449c3a`** | `2026-08-31 09:41:26` | `fix` | Implement client-side self-healing image matching using local `/api/images` map. | Fixed broken images in answers by teaching the browser to automatically correct any misspelled or hallucinated image links using the local image directory. | [`backend/app.py`](file:///c:/Users/User1/Downloads/MND%20DATA/backend/app.py), [`static/app.js`](file:///c:/Users/User1/Downloads/MND%20DATA/static/app.js) |
| **`e39b706`** | `2026-08-31 09:06:22` | `feat` | Implement horizontal resources card deck (`.resources-deck`) for verified items under chat responses. | Added a beautiful, horizontal scrolling card panel under the assistant's answer showing verified equipment options (like wheelchairs) with images, summaries, and links. These choices are saved in your chat history. | [`backend/app.py`](file:///c:/Users/User1/Downloads/MND%20DATA/backend/app.py), [`static/app.js`](file:///c:/Users/User1/Downloads/MND%20DATA/static/app.js), [`static/style.css`](file:///c:/Users/User1/Downloads/MND%20DATA/static/style.css) |
| **`25feabc`** | `2026-08-31 09:04:33` | `fix` | URL-encode image paths with spaces to prevent markdown breaking. Restated System Prompt to restrict LLM from adding external domains. | Fixed a bug where spaces in image names broke their rendering. Guided the AI assistant to use correct local links instead of linking to external websites. | [`backend/app.py`](file:///c:/Users/User1/Downloads/MND%20DATA/backend/app.py) |
| **`0a9a9d1`** | `2026-08-31 00:24:40` | `style`| Add CSS styles for responsive product images container (`.message-content img`) in chat bubbles. | Improved how images look inside message bubbles, ensuring they are perfectly centered, fit cleanly on mobile and desktop screens, and have soft shadows. | [`static/style.css`](file:///c:/Users/User1/Downloads/MND%20DATA/static/style.css) |
| **`c1a81ab`** | `2026-08-31 00:23:37` | `feat` | Mount local `/images` directory, index all 273 product images at startup, remove DeepSeek branding mentions, and replace dev stats sidebar with **Previous Chats** list. | Renamed the assistant to a cleaner "MND Care Assistant" (removing tech jargon and AI branding). Added the "Previous Chats" sidebar to save and load old conversation sessions. | [`backend/app.py`](file:///c:/Users/User1/Downloads/MND%20DATA/backend/app.py), [`static/index.html`](file:///c:/Users/User1/Downloads/MND%20DATA/static/index.html), [`static/app.js`](file:///c:/Users/User1/Downloads/MND%20DATA/static/app.js), [`static/style.css`](file:///c:/Users/User1/Downloads/MND%20DATA/static/style.css) |
| **`e50f480`** | `2026-08-30 23:08:05` | `chore`| Create `.gitignore` and `requirements.txt` for Render deployment, inject `sys.path` to prevent backend startup failure when run from root. | Prepared the configuration files required to host the chatbot online for free, and fixed import bugs to make sure the app launches correctly. | [`.gitignore`](file:///c:/Users/User1/Downloads/MND%20DATA/.gitignore), [`requirements.txt`](file:///c:/Users/User1/Downloads/MND%20DATA/requirements.txt), [`backend/app.py`](file:///c:/Users/User1/Downloads/MND%20DATA/backend/app.py) |

---

## 🛠️ Git Rollback Reference (How to Revert Changes)

Run these commands from your terminal in `C:\Users\User1\Downloads\MND DATA`:

### 1. Undo the last change (Revert the most recent commit)
If you want to keep the git history clean and just undo the last change, create a new commit that reverts `e449c3a`:
```bash
git revert e449c3a --no-edit
git push origin main
```

### 2. Discard all changes and restore workspace to a specific commit
If you want to discard all work done after a specific commit (e.g. go back to before adding images, which is commit `e50f480`):
```bash
# WARNING: This permanently deletes uncommitted files and commits after e50f480
git reset --hard e50f480
git push origin main --force
```

### 3. Restore a single file to a previous version
If you like all commits but want to restore just one file (e.g. `static/app.js`) to its version in a previous commit (e.g. `c1a81ab`):
```bash
# Checkout the file version from commit c1a81ab
git checkout c1a81ab -- static/app.js
# Commit and push the restored version
git commit -m "chore: restore static/app.js to commit c1a81ab version"
git push origin main
```

### 4. View Git Log and Commit Hashes
To check the latest hashes and details in the terminal:
```bash
git log --oneline
```

---

## 📝 Rules for Updating this File

Every AI coding assistant (or human developer) modifying this repository **MUST** update this file immediately after completing their changes. Follow these steps:

1. **Perform your work** and verify it runs successfully.
2. **Stage and commit** your changes to Git.
3. Run `git log --oneline -n 1` to get your new **Commit Hash**.
4. Open this [`updated.md`](file:///c:/Users/User1/Downloads/MND%20DATA/updated.md) file and append a new row to the top of the **Git Commit History** table containing:
   - **Commit Hash:** Your new commit hash.
   - **Date & Time:** Timestamp in format `YYYY-MM-DD HH:MM:SS`.
   - **Type:** Commit type (`feat`, `fix`, `style`, `chore`, `docs`, `refactor`).
   - **Summary of Changes (Technical):** What was changed technically and why.
   - **What this does (Plain Language):** Explain in simple, non-technical terms what this change accomplishes for the end-user.
   - **Modified Files:** Clickable file links pointing to the modified files in the workspace (e.g. `[backend/app.py](file:///c:/Users/User1/Downloads/MND%20DATA/backend/app.py)`).
5. Add any custom rollback or validation details in the **Git Rollback Reference** if applicable.
6. Commit the [`updated.md`](file:///c:/Users/User1/Downloads/MND%20DATA/updated.md) updates.
