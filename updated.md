# Chatbot Project Development Log & Rollback Guide

This file documents every major architectural and features change made to the MND Care Assistant project. If you wish to roll back or undo any specific change, refer to the **Git Rollback Reference** section below.

---

## 📜 Git Commit History & Changelog

| Commit Hash | Type | Summary of Changes | Modified Files |
| :--- | :--- | :--- | :--- |
| **`e449c3a`** | `fix` | Implement client-side self-healing image matching using local `/api/images` map. Resolves any LLM-hallucinated paths or unencoded spaces. | [`backend/app.py`](file:///c:/Users/User1/Downloads/MND%20DATA/backend/app.py), [`static/app.js`](file:///c:/Users/User1/Downloads/MND%20DATA/static/app.js) |
| **`e39b706`** | `feat` | Implement horizontal resources card deck (`.resources-deck`) for verified items under chat responses, fully integrated with `localStorage` persistence. | [`backend/app.py`](file:///c:/Users/User1/Downloads/MND%20DATA/backend/app.py), [`static/app.js`](file:///c:/Users/User1/Downloads/MND%20DATA/static/app.js), [`static/style.css`](file:///c:/Users/User1/Downloads/MND%20DATA/static/style.css) |
| **`25feabc`** | `fix` | URL-encode image paths with spaces to prevent markdown breaking. Restated System Prompt to restrict LLM from adding external domains. | [`backend/app.py`](file:///c:/Users/User1/Downloads/MND%20DATA/backend/app.py) |
| **`0a9a9d1`** | `style`| Add CSS styles for responsive product images container (`.message-content img`) in chat bubbles (max height 280px, border-radius, shadows). | [`static/style.css`](file:///c:/Users/User1/Downloads/MND%20DATA/static/style.css) |
| **`c1a81ab`** | `feat` | Mount local `/images` directory, index all 273 product images at startup, remove DeepSeek branding mentions, and replace dev stats sidebar with **Previous Chats** list. | [`backend/app.py`](file:///c:/Users/User1/Downloads/MND%20DATA/backend/app.py), [`static/index.html`](file:///c:/Users/User1/Downloads/MND%20DATA/static/index.html), [`static/app.js`](file:///c:/Users/User1/Downloads/MND%20DATA/static/app.js), [`static/style.css`](file:///c:/Users/User1/Downloads/MND%20DATA/static/style.css) |
| **`e50f480`** | `chore`| Create `.gitignore` and `requirements.txt` for Render deployment, inject `sys.path` to prevent backend startup failure when run from root. | [`.gitignore`](file:///c:/Users/User1/Downloads/MND%20DATA/.gitignore), [`requirements.txt`](file:///c:/Users/User1/Downloads/MND%20DATA/requirements.txt), [`backend/app.py`](file:///c:/Users/User1/Downloads/MND%20DATA/backend/app.py) |

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
   - **Type:** Commit type (`feat`, `fix`, `style`, `chore`, `docs`, `refactor`).
   - **Summary of Changes:** What was changed and why.
   - **Modified Files:** Clickable file links pointing to the modified files in the workspace (e.g. `[backend/app.py](file:///c:/Users/User1/Downloads/MND%20DATA/backend/app.py)`).
5. Add any custom rollback or validation details in the **Git Rollback Reference** if applicable.
6. Commit the [`updated.md`](file:///c:/Users/User1/Downloads/MND%20DATA/updated.md) updates.
