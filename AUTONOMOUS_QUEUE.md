# AUTONOMOUS QUEUE

## Completed Tasks (Self-Healing Loop Cycle 1)

- [x] **[TASK-001] RAG Multi-Turn Conversation Memory & Context Management** (COMPLETED)
- [x] **[TASK-002] Security Guardrails & Prompt Injection Defense Engine** (COMPLETED)
- [x] **[TASK-003] PDF / Care Plan Summary Export Feature** (COMPLETED)
- [x] **[TASK-004] Comprehensive Automated Unit & Integration Test Suite** (COMPLETED - 6/6 tests PASS)

## Active Task Queue (Self-Healing Loop Cycle 2)

5. **[TASK-005] CRITICAL BUG: Duplicate DEEPSEEK_API_KEY clobbers .env value**
   - Line 83 of `app.py` re-assigns `DEEPSEEK_API_KEY = os.getenv(...)` AFTER it was set from `.env` on L33. If the OS env var isn't set, this resets the key to empty, causing the API to appear offline despite a valid `.env` file.
   - Fix: Remove the redundant line 83.

6. **[TASK-006] New Chat Button & Conversation Reset**
   - Add a "New Chat" button to the navbar that clears chat history and message area.
   - Reset `chatHistory = []` on click.

7. **[TASK-007] Rate Limiting & Request Concurrency Guard**
   - Prevent users from submitting overlapping requests while a stream is active.
   - Disable send button and textarea during active streaming.
   - Add a simple server-side in-memory rate limiter (max 10 requests per minute per IP).

8. **[TASK-008] Code Block Styling & Copy Button**
   - Add CSS styling for `<pre><code>` blocks in AI responses (dark background, monospace font, padding).
   - Add a one-click "Copy" button overlay on code blocks.

9. **[TASK-009] Strengthen validate_output() & Guardrails Coverage**
   - Implement real output validation: check for dangerous medication dosage claims, unsupported self-harm references, and hallucinated phone numbers.
   - Expand prompt injection patterns to cover more adversarial vectors.

10. **[TASK-010] Sidebar Mobile Overlay & Close on Outside Click**
    - Add a dark overlay behind the sidebar on mobile, clickable to close.

11. **[TASK-011] Expanded Test Suite for All New Features**
    - Add test cases for: rate limiting, new chat reset, guardrail expansion, edge case queries (empty, extremely long, special characters, Unicode).
