document.addEventListener("DOMContentLoaded", () => {
    // Elements
    const chatMessages = document.getElementById("chatMessages");
    const chatForm = document.getElementById("chatForm");
    const userMessage = document.getElementById("userMessage");
    const sendBtn = document.getElementById("sendBtn");
    const stateSelect = document.getElementById("stateSelect");
    const apiStatusBadge = document.getElementById("apiStatusBadge");
    
    const themeToggleBtn = document.getElementById("themeToggleBtn");
    const themeLbl = document.getElementById("themeLbl");
    const fontToggleBtn = document.getElementById("fontToggleBtn");
    const fontLbl = document.getElementById("fontLbl");
    const gazeToggleBtn = document.getElementById("gazeToggleBtn");
    const gazeLbl = document.getElementById("gazeLbl");
    
    const toggleSidebar = document.getElementById("toggleSidebar");
    const closeSidebar = document.getElementById("closeSidebar");
    const sidebar = document.getElementById("sidebar");
    const sidebarOverlay = document.getElementById("sidebarOverlay");
    const conversationsList = document.getElementById("conversationsList");
    const openProfileBtn = document.getElementById("openProfileBtn");
    const profileModal = document.getElementById("profileModal");
    const closeProfileBtn = document.getElementById("closeProfileBtn");
    const openSourcesBtn = document.getElementById("openSourcesBtn");
    const openSourcesFooterBtn = document.getElementById("openSourcesFooterBtn");
    const sourcesModal = document.getElementById("sourcesModal");
    const closeSourcesBtn = document.getElementById("closeSourcesBtn");
    const sourcesSummary = document.getElementById("sourcesSummary");
    const sourcesSearch = document.getElementById("sourcesSearch");
    const sourcesTopicFilter = document.getElementById("sourcesTopicFilter");
    const sourcesCatalog = document.getElementById("sourcesCatalog");
    const profileForm = document.getElementById("profileForm");
    const clearProfileBtn = document.getElementById("clearProfileBtn");
    const profileAge = document.getElementById("profileAge");
    const profileGender = document.getElementById("profileGender");
    const profileRole = document.getElementById("profileRole");
    const profileLocation = document.getElementById("profileLocation");
    const docCountStat = document.getElementById("docCountStat");
    const entityCountStat = document.getElementById("entityCountStat");

    let clientImageMap = {};
    const PROFILE_STORAGE_KEY = "mnd_user_profile";

    function escapeHtml(value) {
        return String(value || "").replace(/[&<>"']/g, char => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            "\"": "&quot;",
            "'": "&#39;"
        }[char]));
    }

    function safeLinkHref(value) {
        if (!value || typeof value !== "string") return "";
        const trimmed = value.trim();
        if (/^(?:https?:\/\/|mailto:[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-.]+|tel:\+?[0-9\s()-]{3,}|\/[a-zA-Z0-9_.-])/i.test(trimmed)) {
            const stripped = trimmed.replace(/[\x00-\x20\s]+/g, "").toLowerCase();
            if (stripped.startsWith("javascript:") || stripped.startsWith("vbscript:") || stripped.startsWith("data:")) {
                return "";
            }
            return trimmed;
        }
        return "";
    }

    function sanitizeHtmlContent(html) {
        if (!html) return "";
        return String(html)
            .replace(/<\s*(?:script|style|iframe|object|embed|applet|meta|link|form|input|base)\b[^>]*>[\s\S]*?<\s*\/\s*(?:script|style|iframe|object|embed|applet|meta|link|form|input|base)\s*>/gi, "")
            .replace(/<\s*(?:script|style|iframe|object|embed|applet|meta|link|form|input|base)\b[^>]*\/?>/gi, "")
            .replace(/\son\w+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/gi, "")
            .replace(/href\s*=\s*["']?\s*(?:javascript|vbscript|data):[^"'>\s]*/gi, 'href="#"')
            .replace(/src\s*=\s*["']?\s*(?:javascript|vbscript):[^"'>\s]*/gi, 'src=""');
    }

    function findImageInClientMap(query) {
        if (!query) return "";
        const normQuery = query.toLowerCase().replace(/[^a-z0-9]/g, "");
        if (!normQuery) return "";
        // Exact match
        if (clientImageMap[normQuery]) {
            return clientImageMap[normQuery];
        }
        // Substring match only when both sides are specific enough
        const IMAGE_MATCH_STOPWORDS = new Set([
            "and", "the", "for", "with", "from", "mnd", "care", "home", "program",
            "aged", "australia", "illustration", "support", "guidance"
        ]);
        for (const [key, val] of Object.entries(clientImageMap)) {
            const shorter = key.length <= normQuery.length ? key : normQuery;
            const longer = key.length <= normQuery.length ? normQuery : key;
            if (shorter.length >= 12 && longer.includes(shorter)) {
                return val;
            }
        }
        // Token-level matching: score each key by how many query tokens it contains
        const tokens = (query.toLowerCase().match(/[a-z0-9]{3,}/g) || [])
            .filter(tok => !IMAGE_MATCH_STOPWORDS.has(tok));
        if (tokens.length === 0) return "";
        let bestPath = "";
        let bestScore = 0;
        for (const [key, val] of Object.entries(clientImageMap)) {
            let score = 0;
            for (const tok of tokens) {
                if (key.includes(tok)) score++;
            }
            if (score > bestScore) {
                bestScore = score;
                bestPath = val;
            }
        }
        const minRequired = tokens.length <= 1 ? 1 : 2;
        return bestScore >= minRequired ? bestPath : "";
    }

    // Configure marked to render clickable external links with icons
    const renderer = new marked.Renderer();
    renderer.link = function(linkObj, titleArg, textArg) {
        let href = "";
        let title = "";
        let text = "";
        if (linkObj && typeof linkObj === 'object') {
            href = linkObj.href || "";
            title = linkObj.title || "";
            text = linkObj.text || href;
        } else {
            href = linkObj || "";
            title = titleArg || "";
            text = textArg || href;
        }
        const safeHref = safeLinkHref(href);
        if (!safeHref) return text;
        const safeTitle = escapeHtml(title || text);
        return `<a href="${safeHref}" target="_blank" rel="noopener noreferrer" title="${safeTitle}">${text} <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 0.75em; opacity: 0.85;"></i></a>`;
    };
    
    renderer.image = function(imageObj, titleArg, textArg) {
        let href = "";
        let text = "";
        let title = "";
        
        if (imageObj && typeof imageObj === 'object') {
            href = imageObj.href || "";
            text = imageObj.text || "";
            title = imageObj.title || "";
        } else {
            href = imageObj || "";
            text = textArg || "";
            title = titleArg || "";
        }
        
        let queryKey = text || "";
        if (href) {
            const filename = href.split('/').pop().split('?')[0];
            const nameWithoutExt = filename.replace(/\.[^/.]+$/, "");
            let cleanName = nameWithoutExt;
            if (nameWithoutExt.includes("-")) {
                const parts = nameWithoutExt.split("-");
                const lastPart = parts[parts.length - 1];
                if (lastPart.length >= 8 && lastPart.length <= 12 && /^[a-f0-9]+$/.test(lastPart)) {
                    parts.pop();
                    cleanName = parts.join("-");
                }
            }
            queryKey = cleanName;
        }
        
        const matched = findImageInClientMap(queryKey) || findImageInClientMap(text);
        if (!matched) {
            return "";
        }
        const safeAlt = escapeHtml(text || "Care equipment");
        const safeTitle = escapeHtml(title || text || "Care equipment");
        return `<span class="care-figure"><img src="${matched}" alt="${safeAlt}" class="care-message-img" title="${safeTitle}" loading="lazy" onerror="this.parentNode.style.display='none'"><span class="care-img-caption">${safeAlt}</span></span>`;
    };
    
    marked.use({ renderer });

    function stripSourcesHeading(markdownText) {
        return String(markdownText || "")
            .replace(/\n*#{1,6}\s*Verified Sources[\s\S]*$/i, "")
            .trimEnd();
    }

    function isDebugMode() {
        try {
            return localStorage.getItem("mnd_debug") === "1";
        } catch (e) {
            return false;
        }
    }

    function renderSourceChips(sources) {
        const list = Array.isArray(sources) ? sources : [];
        const wrap = document.createElement("div");
        wrap.className = "source-chips";
        wrap.setAttribute("aria-label", "Sources");

        const heading = document.createElement("p");
        heading.className = "source-chips-label";
        heading.textContent = "Sources";
        wrap.appendChild(heading);

        const row = document.createElement("div");
        row.className = "source-chips-row";

        list.forEach(src => {
            const title = src.title || src.publisher || "Verified source";
            const missing = !!src.missing_url || !src.url;
            if (missing && !isDebugMode()) return;
            const href = safeLinkHref(src.url);
            if (!missing && !href) return;
            if (missing) {
                const span = document.createElement("span");
                span.className = "source-chip is-missing";
                span.textContent = `${title} — Source URL needed`;
                row.appendChild(span);
                return;
            }
            const a = document.createElement("a");
            a.className = "source-chip";
            a.href = href;
            a.target = "_blank";
            a.rel = "noopener noreferrer";
            a.title = src.publisher ? `${title} — ${src.publisher}` : title;

            const label = document.createElement("span");
            label.className = "source-chip-title";
            label.textContent = title;
            a.appendChild(label);

            if (src.publisher && src.publisher !== title) {
                const pub = document.createElement("span");
                pub.className = "source-chip-pub";
                pub.textContent = src.publisher;
                a.appendChild(pub);
            }
            if (src.region_note) {
                const note = document.createElement("span");
                note.className = "source-chip-note";
                note.textContent = src.region_note;
                a.appendChild(note);
            }
            a.insertAdjacentHTML("beforeend", '<i class="fa-solid fa-arrow-up-right-from-square" aria-hidden="true"></i>');
            row.appendChild(a);
        });

        if (!row.children.length) return null;
        wrap.appendChild(row);
        return wrap;
    }

    function attachSourceChips(wrapper, sources) {
        wrapper.querySelector(".source-chips")?.remove();
        const chips = renderSourceChips(sources);
        if (!chips) return;
        const ts = wrapper.querySelector(".message-timestamp");
        if (ts) wrapper.insertBefore(chips, ts);
        else wrapper.appendChild(chips);
    }

    function safeRenderMarkdown(markdownText) {
        if (!markdownText) return "";
        let cleanText = stripSourcesHeading(String(markdownText));
        // Separate any concatenated markdown links like ](url)[Next](url2) into distinct bullet lines
        cleanText = cleanText.replace(/\]\(([^)]+)\)\s*\[/g, "]($1)\n- [");
        try {
            const rawHtml = marked.parse(cleanText);
            return sanitizeHtmlContent(rawHtml);
        } catch (e) {
            return escapeHtml(cleanText);
        }
    }

    // Smart Scroll & Manual Scroll Detection
    let isUserAtBottom = true;
    let chatHistory = []; // Stores conversation turn history [{role, content}] for RAG API payload
    let isStreaming = false; // Concurrency guard — prevents overlapping requests
    const scrollToBottomBtn = document.getElementById("scrollToBottomBtn");
    const inputContainer = document.querySelector(".input-container");

    function syncComposerHeight() {
        if (!inputContainer) return;
        document.documentElement.style.setProperty(
            "--composer-height",
            `${inputContainer.offsetHeight}px`
        );
    }

    function viewportScale() {
        const vv = window.visualViewport;
        return vv && Number.isFinite(vv.scale) ? vv.scale : 1;
    }

    function isPinchZoomed() {
        return Math.abs(viewportScale() - 1) > 0.01;
    }

    function isCoarsePointer() {
        return window.matchMedia("(pointer: coarse)").matches;
    }

    function isBrowserZoomed() {
        if (isPinchZoomed()) return true;
        if (isCoarsePointer()) return false;
        const widthRatio = window.outerWidth / Math.max(window.innerWidth, 1);
        const heightRatio = window.outerHeight / Math.max(window.innerHeight, 1);
        return widthRatio > 1.08 || (widthRatio > 1.04 && heightRatio > 1.25);
    }

    function isTypingOnMobile() {
        if (isPinchZoomed() || isBrowserZoomed()) return false;
        if (!isCoarsePointer()) return false;
        if (document.activeElement === userMessage) return true;
        const vv = window.visualViewport;
        if (!vv) return false;
        return (window.innerHeight - vv.height) > 80 || vv.offsetTop > 40;
    }

    function lockWindowToViewport() {
        window.scrollTo(0, 0);
        document.documentElement.scrollTop = 0;
        document.body.scrollTop = 0;
    }

    function syncMobileViewport() {
        const vv = window.visualViewport;
        const pageZoomed = isBrowserZoomed();
        const keyboardOpen = isTypingOnMobile();
        document.documentElement.classList.toggle("page-zoomed", pageZoomed);
        document.body.classList.toggle("page-zoomed", pageZoomed);
        document.documentElement.classList.toggle("keyboard-open", keyboardOpen);
        document.body.classList.toggle("keyboard-open", keyboardOpen);

        let height = window.innerHeight;
        let offsetTop = 0;
        if (vv && isCoarsePointer() && !isPinchZoomed()) {
            height = vv.height;
            offsetTop = keyboardOpen ? vv.offsetTop : 0;
        }
        if (pageZoomed) {
            document.documentElement.style.removeProperty("--app-height");
            document.documentElement.style.removeProperty("--app-offset-top");
            document.documentElement.style.removeProperty("--safe-bottom");
        } else {
            document.documentElement.style.setProperty("--app-height", `${Math.round(height)}px`);
            document.documentElement.style.setProperty("--app-offset-top", `${Math.round(offsetTop)}px`);
            if (keyboardOpen) {
                document.documentElement.style.setProperty("--safe-bottom", "0px");
                lockWindowToViewport();
            } else {
                document.documentElement.style.removeProperty("--safe-bottom");
                document.documentElement.style.removeProperty("--app-offset-top");
            }
        }
        syncComposerHeight();
        if (keyboardOpen) {
            scrollToBottomBtn?.classList.remove("visible");
        }
    }

    syncMobileViewport();
    window.addEventListener("resize", syncMobileViewport);
    window.visualViewport?.addEventListener("resize", syncMobileViewport);
    window.visualViewport?.addEventListener("scroll", () => {
        if (isCoarsePointer() && !isPinchZoomed()) {
            syncMobileViewport();
        }
    });
    if (inputContainer && typeof ResizeObserver !== "undefined") {
        new ResizeObserver(syncComposerHeight).observe(inputContainer);
    }
    userMessage?.addEventListener("focus", () => {
        syncMobileViewport();
        [50, 180, 350].forEach((ms) => {
            window.setTimeout(() => {
                lockWindowToViewport();
                syncMobileViewport();
            }, ms);
        });
    });
    userMessage?.addEventListener("blur", () => {
        setTimeout(syncMobileViewport, 150);
    });

    chatMessages.addEventListener("scroll", () => {
        const threshold = 100; // px threshold from bottom
        const distanceFromBottom = chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight;
        isUserAtBottom = distanceFromBottom <= threshold;

        if (scrollToBottomBtn) {
            if (!isUserAtBottom && !isTypingOnMobile()) {
                scrollToBottomBtn.classList.add("visible");
            } else {
                scrollToBottomBtn.classList.remove("visible");
            }
        }
    });

    scrollToBottomBtn?.addEventListener("click", () => {
        isUserAtBottom = true;
        chatMessages.scrollTo({ top: chatMessages.scrollHeight, behavior: "smooth" });
        scrollToBottomBtn.classList.remove("visible");
    });

    // Local Storage Conversation History Manager
    let conversations = JSON.parse(localStorage.getItem("mnd_conversations")) || {};
    let currentConvId = localStorage.getItem("mnd_current_conv_id") || null;

    function saveConversations() {
        localStorage.setItem("mnd_conversations", JSON.stringify(conversations));
        localStorage.setItem("mnd_current_conv_id", currentConvId);
    }

    function startNewConversation() {
        const id = "conv_" + Date.now();
        conversations[id] = {
            id: id,
            title: "New Chat Session",
            state: stateSelect.value,
            messages: [],
            updatedAt: Date.now()
        };
        currentConvId = id;
        saveConversations();
        renderConversationsList();
        loadConversation(id);
    }

    function renderConversationsList() {
        if (!conversationsList) return;
        conversationsList.innerHTML = "";
        
        const sortedConvs = Object.values(conversations).sort((a, b) => b.updatedAt - a.updatedAt);
        
        if (sortedConvs.length === 0) {
            conversationsList.innerHTML = `<div class="no-chats-msg">No saved conversations yet.</div>`;
            return;
        }
        
        sortedConvs.forEach(conv => {
            const item = document.createElement("div");
            item.className = `conversation-item ${conv.id === currentConvId ? 'active' : ''}`;
            item.setAttribute("data-id", conv.id);
            item.setAttribute("role", "button");
            item.setAttribute("tabindex", "0");
            item.setAttribute("aria-label", conv.title || "Saved conversation");

            const info = document.createElement("div");
            info.className = "conversation-info";

            const icon = document.createElement("i");
            icon.className = "fa-regular fa-message";
            info.appendChild(icon);

            const title = document.createElement("span");
            title.className = "conversation-title";
            title.title = conv.title || "Saved conversation";
            title.textContent = conv.title || "Saved conversation";
            info.appendChild(title);

            const deleteBtn = document.createElement("button");
            deleteBtn.className = "delete-conv-btn";
            deleteBtn.type = "button";
            deleteBtn.title = "Delete conversation";
            deleteBtn.setAttribute("aria-label", "Delete conversation");
            const deleteIcon = document.createElement("i");
            deleteIcon.className = "fa-solid fa-trash-can";
            deleteBtn.appendChild(deleteIcon);

            item.appendChild(info);
            item.appendChild(deleteBtn);
            
            // Load conversation on click
            item.addEventListener("click", (e) => {
                if (isStreaming) return; // Prevent switching chats during stream
                // Don't trigger load if clicking delete button
                if (e.target.closest(".delete-conv-btn")) return;
                loadConversation(conv.id);
            });
            item.addEventListener("keydown", (e) => {
                if (e.target.closest(".delete-conv-btn")) return;
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    if (!isStreaming) loadConversation(conv.id);
                }
            });
            
            // Delete conversation on click
            deleteBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                deleteConversation(conv.id);
            });
            
            conversationsList.appendChild(item);
        });
    }

    function deleteConversation(id) {
        delete conversations[id];
        if (currentConvId === id) {
            const keys = Object.keys(conversations);
            if (keys.length > 0) {
                currentConvId = keys[keys.length - 1];
            } else {
                currentConvId = null;
            }
        }
        saveConversations();
        renderConversationsList();
        
        if (currentConvId) {
            loadConversation(currentConvId);
        } else {
            startNewConversation();
        }
    }

    function loadConversation(id) {
        closeMobileSidebar();
        currentConvId = id;
        const conv = conversations[id];
        if (!conv) return;
        
        // Sync state selector
        stateSelect.value = conv.state || "National";
        localStorage.setItem("mnd_state", stateSelect.value);
        
        // Rebuild chatMessages container
        chatMessages.innerHTML = "";
        
        if (conv.messages.length === 0) {
            // Show welcome card
            chatMessages.innerHTML = `
                <div class="welcome-card">
                    <div class="welcome-icon"><i class="fa-solid fa-heart-pulse"></i></div>
                    <h2>Care guidance you can check</h2>
                    <p class="welcome-desc">Ask about equipment, NDIS, breathing support, or carer services. Answers are drawn from Australian MND, NDIS, and health publications and tailored to <strong>your state</strong>.</p>
                    <div class="prompt-chips">
                        <button class="chip" type="button" data-prompt="What wheelchair options are available through FlexEquip in NSW?">Wheelchair options</button>
                        <button class="chip" type="button" data-prompt="How do I apply for NDIS assistive technology funding?">NDIS AT funding</button>
                        <button class="chip" type="button" data-prompt="What breathing support options exist for MND patients?">Breathing support</button>
                        <button class="chip" type="button" data-prompt="What support services are available for MND carers?">Carer support</button>
                    </div>
                </div>
            `;
            bindPromptChips();
            chatHistory = [];
        } else {
            // Re-render past messages
            conv.messages.forEach(msg => {
                const row = createMessageRow(msg.role, msg.content, msg.timestamp, msg.sources);
                chatMessages.appendChild(row);
            });
            
            // Build chatHistory array (API multi-turn payload)
            chatHistory = [];
            conv.messages.forEach(msg => {
                chatHistory.push({ role: msg.role, content: msg.content });
            });
            if (chatHistory.length > 20) chatHistory = chatHistory.slice(-20);
            
            // Re-inject copy button triggers
            document.querySelectorAll(".message-content").forEach(c => {
                injectCodeCopyButtons(c);
            });
        }
        
        // Mark active item in sidebar
        document.querySelectorAll(".conversation-item").forEach(item => {
            if (item.getAttribute("data-id") === id) {
                item.classList.add("active");
            } else {
                item.classList.remove("active");
            }
        });
        
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Load saved settings
    let savedState = localStorage.getItem("mnd_state") || "National";
    let isLargeFont = localStorage.getItem("mnd_large_font") === "true";
    let isGazeMode = localStorage.getItem("mnd_access_gaze") === "true";
    let currentTheme = localStorage.getItem("mnd_theme") || "light";

    stateSelect.value = savedState;
    applyTheme(currentTheme);
    if (isLargeFont) applyFontMode(true);
    applyGazeMode(isGazeMode);

    function readUserProfile() {
        try {
            const stored = JSON.parse(localStorage.getItem(PROFILE_STORAGE_KEY) || "null");
            if (!stored || typeof stored !== "object") return null;

            const profile = {
                age: Number.parseInt(stored.age, 10) || null,
                gender: stored.gender || "",
                role: stored.role || "",
                location: stored.location || ""
            };

            if (!profile.age && !profile.gender && !profile.role && !profile.location) {
                return null;
            }

            return profile;
        } catch (err) {
            console.warn("Could not read saved profile:", err);
            return null;
        }
    }

    function populateProfileForm() {
        const profile = readUserProfile() || {};
        if (profileAge) profileAge.value = profile.age || "";
        if (profileGender) profileGender.value = profile.gender || "";
        if (profileRole) profileRole.value = profile.role || "";
        if (profileLocation) profileLocation.value = profile.location || "";
    }

    function closeProfileModal() {
        profileModal?.classList.remove("active");
    }

    function closeSourcesModal() {
        sourcesModal?.classList.remove("active");
    }

    let sourcesCatalogData = null;
    let sourcesLoadPromise = null;

    function sourcePageMatches(page, query, topic) {
        if (topic && !(page.topics || []).includes(topic)) return false;
        if (!query) return true;
        const hay = [
            page.title,
            page.publisher,
            page.url,
            page.host,
            page.source_type,
            page.state,
            page.description,
            page.phone,
            page.eligibility,
            page.region,
            ...(page.topics || [])
        ].join(" ").toLowerCase();
        return hay.includes(query);
    }

    function renderSourcesCatalog() {
        if (!sourcesCatalog || !sourcesCatalogData) return;
        const query = (sourcesSearch?.value || "").trim().toLowerCase();
        const topic = sourcesTopicFilter?.value || "";
        const groups = sourcesCatalogData.publishers || [];
        let visiblePages = 0;
        let visiblePublishers = 0;
        const parts = [];

        groups.forEach((group, index) => {
            const pages = (group.pages || []).filter(page => sourcePageMatches(page, query, topic));
            if (!pages.length) return;
            visiblePublishers += 1;
            visiblePages += pages.length;
            const homepage = safeLinkHref(group.homepage || "");
            const open = query || topic || index < 2 ? " open" : "";
            const pageItems = pages.map(page => {
                const href = safeLinkHref(page.url || "");
                const title = escapeHtml(page.title || "Untitled source");
                const meta = [
                    (page.topics || []).join(", "),
                    page.source_type,
                    page.state,
                    page.kind === "directory" ? "Directory" : "Publication"
                ].filter(Boolean).map(escapeHtml).join(" · ");
                const extra = [];
                if (page.description) extra.push(`<p class="sources-page-desc">${escapeHtml(page.description)}</p>`);
                if (page.eligibility) extra.push(`<p class="sources-page-meta"><strong>Eligibility:</strong> ${escapeHtml(page.eligibility)}</p>`);
                if (page.region) extra.push(`<p class="sources-page-meta"><strong>Region:</strong> ${escapeHtml(page.region)}</p>`);
                if (page.phone) extra.push(`<p class="sources-page-meta"><strong>Phone:</strong> ${escapeHtml(page.phone)}</p>`);
                const link = href
                    ? `<a class="sources-page-link" href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${title}<i class="fa-solid fa-arrow-up-right-from-square"></i></a>`
                    : `<span class="sources-page-title">${title}</span>`;
                const host = page.host || page.url || "";
                return `<article class="sources-page">
                    ${link}
                    <p class="sources-page-meta">${meta}</p>
                    ${host ? `<p class="sources-page-url">${escapeHtml(host)}</p>` : ""}
                    ${extra.join("")}
                </article>`;
            }).join("");

            parts.push(`<details class="sources-group"${open}>
                <summary>
                    <span class="sources-group-name">${escapeHtml(group.name)}</span>
                    <span class="sources-group-count">${pages.length} page${pages.length === 1 ? "" : "s"}</span>
                </summary>
                ${homepage ? `<p class="sources-group-home"><a href="${escapeHtml(homepage)}" target="_blank" rel="noopener noreferrer">Publisher website <i class="fa-solid fa-arrow-up-right-from-square"></i></a></p>` : ""}
                <div class="sources-pages">${pageItems}</div>
            </details>`);
        });

        if (sourcesSummary) {
            const totalPages = sourcesCatalogData.page_count || 0;
            const totalPubs = sourcesCatalogData.publisher_count || 0;
            const totalTopics = sourcesCatalogData.topic_count || 0;
            const filtered = query || topic;
            sourcesSummary.innerHTML = filtered
                ? `<strong>${visiblePages}</strong> matching pages across <strong>${visiblePublishers}</strong> publishers`
                : `<strong>${totalPages}</strong> unique pages · <strong>${totalPubs}</strong> publishers · <strong>${totalTopics}</strong> topics`;
        }

        sourcesCatalog.innerHTML = parts.length
            ? parts.join("")
            : `<p class="sources-empty">No verified sources match that search.</p>`;
    }

    function populateTopicFilter(topics) {
        if (!sourcesTopicFilter) return;
        const current = sourcesTopicFilter.value;
        sourcesTopicFilter.innerHTML = `<option value="">All topics</option>` + (topics || []).map(topic => (
            `<option value="${escapeHtml(topic.name)}">${escapeHtml(topic.name)} (${topic.count})</option>`
        )).join("");
        if (current && [...sourcesTopicFilter.options].some(opt => opt.value === current)) {
            sourcesTopicFilter.value = current;
        }
    }

    function loadSourcesCatalog() {
        if (sourcesCatalogData) {
            renderSourcesCatalog();
            return Promise.resolve(sourcesCatalogData);
        }
        if (sourcesLoadPromise) return sourcesLoadPromise;
        sourcesLoadPromise = fetch("/api/sources")
            .then(res => {
                if (!res.ok) throw new Error("Could not load sources");
                return res.json();
            })
            .then(data => {
                sourcesCatalogData = data || { publishers: [], topics: [] };
                populateTopicFilter((sourcesCatalogData.topics || []).filter(topic => topic.count >= 2));
                renderSourcesCatalog();
                return sourcesCatalogData;
            })
            .catch(err => {
                sourcesLoadPromise = null;
                if (sourcesSummary) sourcesSummary.textContent = "Verified sources could not be loaded. Try again.";
                if (sourcesCatalog) sourcesCatalog.innerHTML = `<p class="sources-empty">${escapeHtml(err.message || "Could not load sources.")}</p>`;
            });
        return sourcesLoadPromise;
    }

    function openSourcesModal() {
        userMessage?.blur();
        closeMobileSidebar();
        closeProfileModal();
        sourcesModal?.classList.add("active");
        if (sourcesSummary && !sourcesCatalogData) sourcesSummary.textContent = "Loading verified sources…";
        loadSourcesCatalog();
        window.setTimeout(() => sourcesSearch?.focus(), 50);
    }

    openProfileBtn?.addEventListener("click", () => {
        closeMobileSidebar();
        populateProfileForm();
        profileModal?.classList.add("active");
    });

    closeProfileBtn?.addEventListener("click", closeProfileModal);
    profileModal?.addEventListener("click", (e) => {
        if (e.target === profileModal) closeProfileModal();
    });

    openSourcesBtn?.addEventListener("click", openSourcesModal);
    openSourcesFooterBtn?.addEventListener("click", openSourcesModal);
    closeSourcesBtn?.addEventListener("click", closeSourcesModal);
    sourcesModal?.addEventListener("click", (e) => {
        if (e.target === sourcesModal) closeSourcesModal();
    });
    sourcesSearch?.addEventListener("input", renderSourcesCatalog);
    sourcesTopicFilter?.addEventListener("change", renderSourcesCatalog);

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            if (sourcesModal?.classList.contains("active")) {
                closeSourcesModal();
                return;
            }
            if (profileModal?.classList.contains("active")) {
                closeProfileModal();
            }
            closeMobileSidebar();
        }
    });

    profileForm?.addEventListener("submit", (e) => {
        e.preventDefault();
        const profile = {
            age: Number.parseInt(profileAge?.value, 10) || null,
            gender: profileGender?.value || "",
            role: profileRole?.value || "",
            location: profileLocation?.value || ""
        };

        localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profile));
        if (profile.location) {
            stateSelect.value = profile.location;
            localStorage.setItem("mnd_state", profile.location);
            if (currentConvId && conversations[currentConvId]) {
                conversations[currentConvId].state = profile.location;
                saveConversations();
            }
        }
        closeProfileModal();
    });

    clearProfileBtn?.addEventListener("click", () => {
        localStorage.removeItem(PROFILE_STORAGE_KEY);
        populateProfileForm();
        closeProfileModal();
    });

    // Fetch backend status and image map on startup
    fetch("/api/stats")
        .then(res => res.json())
        .then(data => {
            updateBadgeStatus();
            updateStats(data);
        })
        .catch(() => updateBadgeStatus());

    fetch("/api/images")
        .then(res => res.json())
        .then(data => {
            clientImageMap = data || {};
        })
        .catch(err => console.error("Failed to load client image map:", err));

    function closeMobileSidebar() {
        if (sidebar && sidebar.classList.contains("active")) {
            sidebar.classList.remove("active");
            toggleSidebar?.setAttribute("aria-expanded", "false");
        }
    }

    // Sidebar Toggle
    toggleSidebar?.addEventListener("click", () => {
        sidebar?.classList.add("active");
        toggleSidebar.setAttribute("aria-expanded", "true");
    });
    closeSidebar?.addEventListener("click", closeMobileSidebar);
    sidebarOverlay?.addEventListener("click", closeMobileSidebar);

    // Export Care Plan Summary button
    const exportBtn = document.getElementById("exportBtn");
    exportBtn?.addEventListener("click", () => {
        closeMobileSidebar();
        window.print();
    });

    // New Chat button — creates new conversation and active state
    const newChatBtn = document.getElementById("newChatBtn");
    newChatBtn?.addEventListener("click", () => {
        if (isStreaming) return;
        closeMobileSidebar();
        startNewConversation();
    });

    // State Selector change
    stateSelect.addEventListener("change", (e) => {
        localStorage.setItem("mnd_state", e.target.value);
        if (currentConvId && conversations[currentConvId]) {
            conversations[currentConvId].state = e.target.value;
            saveConversations();
        }
    });

    // Font Toggle
    themeToggleBtn?.addEventListener("click", () => {
        currentTheme = currentTheme === "dark" ? "light" : "dark";
        localStorage.setItem("mnd_theme", currentTheme);
        applyTheme(currentTheme);
    });

    fontToggleBtn?.addEventListener("click", () => {
        isLargeFont = !isLargeFont;
        localStorage.setItem("mnd_large_font", isLargeFont);
        applyFontMode(isLargeFont);
    });

    gazeToggleBtn?.addEventListener("click", () => {
        isGazeMode = !isGazeMode;
        localStorage.setItem("mnd_access_gaze", isGazeMode);
        applyGazeMode(isGazeMode);
        syncMobileViewport();
    });

    function applyTheme(theme) {
        const isLight = theme === "light";
        document.body.classList.toggle("theme-light", isLight);
        document.body.classList.toggle("theme-dark", !isLight);

        const themeMeta = document.getElementById("themeColorMeta");
        if (themeMeta) {
            themeMeta.setAttribute("content", isLight ? "#f3f5f8" : "#0b1016");
        }

        if (themeLbl) {
            themeLbl.textContent = isLight ? "Dark Mode" : "Light Mode";
        }

        const icon = themeToggleBtn?.querySelector("i");
        if (icon) {
            icon.className = isLight ? "fa-solid fa-sun" : "fa-solid fa-moon";
        }
    }

    function applyFontMode(enable) {
        if (enable) {
            document.documentElement.classList.add("font-large");
            document.body.classList.add("font-large");
            fontLbl.textContent = "Standard Text";
            fontToggleBtn.classList.add("btn-accent");
            fontToggleBtn.setAttribute("aria-pressed", "true");
        } else {
            document.documentElement.classList.remove("font-large");
            document.body.classList.remove("font-large");
            fontLbl.textContent = "Large Text";
            fontToggleBtn.classList.remove("btn-accent");
            fontToggleBtn.setAttribute("aria-pressed", "false");
        }
    }

    function applyGazeMode(enable) {
        document.body.classList.toggle("access-gaze", enable);
        if (gazeLbl) {
            gazeLbl.textContent = enable ? "Gaze On" : "Eye Gaze";
        }
        gazeToggleBtn?.setAttribute("aria-pressed", enable ? "true" : "false");
        gazeToggleBtn?.classList.toggle("btn-accent", enable);
    }

    function updateBadgeStatus() {
        if (!apiStatusBadge) return;
        apiStatusBadge.classList.add("active");
        apiStatusBadge.innerHTML = `<i class="fa-solid fa-circle"></i> Ready`;
    }

    function updateStats(data) {
        if (docCountStat && Number.isFinite(data?.total_documents)) {
            docCountStat.textContent = data.total_documents.toLocaleString();
        }
        if (entityCountStat && Number.isFinite(data?.total_entities)) {
            entityCountStat.textContent = data.total_entities.toLocaleString();
        }
    }

    const DRAFT_STORAGE_KEY = "mnd_user_draft";

    // Restore draft if present
    try {
        const savedDraft = localStorage.getItem(DRAFT_STORAGE_KEY);
        if (savedDraft && userMessage) {
            userMessage.value = savedDraft;
            userMessage.style.height = "auto";
            userMessage.style.height = Math.min(userMessage.scrollHeight, 150) + "px";
            if (sendBtn) sendBtn.disabled = !savedDraft.trim();
        }
    } catch (e) {
        console.warn("Could not restore draft:", e);
    }

    // Auto-resize textarea & autosave draft
    userMessage.addEventListener("input", () => {
        userMessage.style.height = "auto";
        userMessage.style.height = Math.min(userMessage.scrollHeight, 150) + "px";
        sendBtn.disabled = !userMessage.value.trim() || isStreaming;
        try {
            if (userMessage.value.trim()) {
                localStorage.setItem(DRAFT_STORAGE_KEY, userMessage.value);
            } else {
                localStorage.removeItem(DRAFT_STORAGE_KEY);
            }
        } catch (e) {}
    });

    userMessage.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            if (userMessage.value.trim() && !isStreaming) {
                chatForm.dispatchEvent(new Event("submit"));
            }
        }
    });

    // Prompt Chips — bind function for re-use after New Chat reset
    function bindPromptChips() {
        document.querySelectorAll(".chip").forEach(chip => {
            chip.addEventListener("click", () => {
                if (isStreaming) return;
                const prompt = chip.getAttribute("data-prompt");
                userMessage.value = prompt;
                userMessage.style.height = "auto";
                userMessage.style.height = Math.min(userMessage.scrollHeight, 150) + "px";
                sendBtn.disabled = false;
                try {
                    localStorage.setItem(DRAFT_STORAGE_KEY, prompt);
                } catch (e) {}
                chatForm.dispatchEvent(new Event("submit"));
            });
        });
    }

    // Chat Submission
    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const text = userMessage.value.trim();
        if (!text || isStreaming) return;

        // Clear saved draft on submission
        try {
            localStorage.removeItem(DRAFT_STORAGE_KEY);
        } catch (e) {}

        // Ensure we have an active conversation session
        if (!currentConvId || !conversations[currentConvId]) {
            startNewConversation();
        }

        // Lock streaming state
        isStreaming = true;
        sendBtn.disabled = true;
        userMessage.setAttribute("disabled", "true");

        // Reset scroll override on new message
        isUserAtBottom = true;
        if (scrollToBottomBtn) scrollToBottomBtn.classList.remove("visible");

        // Hide welcome card if present
        const welcomeCard = document.querySelector(".welcome-card");
        if (welcomeCard) welcomeCard.style.display = "none";

        // Generate timestamp
        const now = new Date();
        const timestampStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        // Append User Message
        appendMessage("user", text, timestampStr);
        
        // Save user message to conversations storage
        conversations[currentConvId].messages.push({
            role: "user",
            content: text,
            timestamp: timestampStr
        });
        
        // Auto-rename chat from first message if default
        if (conversations[currentConvId].title === "New Chat Session") {
            const firstWords = text.split(" ").slice(0, 4).join(" ");
            conversations[currentConvId].title = firstWords + (text.split(" ").length > 4 ? "..." : "");
            renderConversationsList();
        }
        
        conversations[currentConvId].updatedAt = Date.now();
        saveConversations();

        userMessage.value = "";
        userMessage.style.height = "auto";

        // Create Assistant Message Row
        const assistantRow = createMessageRow("assistant", "", timestampStr);
        const contentDiv = assistantRow.querySelector(".message-content");
        contentDiv.setAttribute("aria-busy", "true");
        contentDiv.classList.add("is-streaming");
        contentDiv.innerHTML = `<span class="typing-indicator" role="status"><span class="typing-dots" aria-hidden="true"><span></span><span></span><span></span></span> Searching the knowledge base</span>`;
        chatMessages.appendChild(assistantRow);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        let fullContent = "";
        let streamedSources = [];
        let streamRenderTimer = 0;
        const STREAM_RENDER_MS = 80;

        function paintStream(finalPass) {
            if (!fullContent) return;
            const caret = finalPass ? "" : '<span class="streaming-caret" aria-hidden="true"></span>';
            contentDiv.innerHTML = safeRenderMarkdown(fullContent) + caret;
            if (isUserAtBottom) {
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }
        }

        function scheduleStreamPaint() {
            if (streamRenderTimer) return;
            streamRenderTimer = window.setTimeout(() => {
                streamRenderTimer = 0;
                paintStream(false);
            }, STREAM_RENDER_MS);
        }

        // Add user message to conversation history BEFORE sending to API
        // so the backend receives complete context for multi-turn conversations
        chatHistory.push({ role: "user", content: text });
        if (chatHistory.length > 20) chatHistory = chatHistory.slice(-20);

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: text,
                    state: stateSelect.value,
                    history: chatHistory,
                    profile: readUserProfile(),
                    debug: isDebugMode()
                })
            });

            if (!response.ok) {
                contentDiv.classList.remove("is-streaming");
                contentDiv.removeAttribute("aria-busy");
                contentDiv.innerHTML = `Could not reach the server (${response.status}). Please try again.`;
                return;
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let gotFirstToken = false;

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunkStr = decoder.decode(value, { stream: true });
                const lines = chunkStr.split("\n\n");

                for (const line of lines) {
                    if (line.startsWith?.("data: ") || line.indexOf("data: ") === 0) {
                        const jsonStr = line.replace("data: ", "").trim();
                        if (jsonStr === "[DONE]") break;

                        try {
                            const parsed = JSON.parse(jsonStr);
                            if (parsed.sources) {
                                streamedSources = parsed.sources;
                            }
                            if (parsed.content) {
                                if (!gotFirstToken) {
                                    gotFirstToken = true;
                                    contentDiv.innerHTML = "";
                                }
                                fullContent += parsed.content;
                                scheduleStreamPaint();
                            }
                        } catch (err) {
                            // Ignored partial chunk errors
                        }
                    }
                }
            }

            if (streamRenderTimer) {
                window.clearTimeout(streamRenderTimer);
                streamRenderTimer = 0;
            }
            contentDiv.classList.remove("is-streaming");
            contentDiv.removeAttribute("aria-busy");

            if (!fullContent) {
                contentDiv.innerHTML = "No response generated.";
            } else {
                paintStream(true);
                const wrapper = assistantRow.querySelector(".message-wrapper");
                if (wrapper) attachSourceChips(wrapper, streamedSources);
                chatHistory.push({ role: "assistant", content: fullContent });
                if (chatHistory.length > 20) chatHistory = chatHistory.slice(-20);

                conversations[currentConvId].messages.push({
                    role: "assistant",
                    content: fullContent,
                    sources: streamedSources,
                    timestamp: timestampStr
                });
                conversations[currentConvId].updatedAt = Date.now();
                saveConversations();

                injectCodeCopyButtons(contentDiv);
            }

        } catch (err) {
            contentDiv.classList.remove("is-streaming");
            contentDiv.removeAttribute("aria-busy");
            contentDiv.innerHTML = `Network error: ${escapeHtml(err.message)}`;
        } finally {
            if (streamRenderTimer) {
                window.clearTimeout(streamRenderTimer);
                streamRenderTimer = 0;
            }
            contentDiv.classList.remove("is-streaming");
            contentDiv.removeAttribute("aria-busy");
            // Unlock streaming state
            isStreaming = false;
            sendBtn.disabled = !userMessage.value.trim();
            userMessage.removeAttribute("disabled");
            const isTouch = window.matchMedia("(pointer: coarse)").matches;
            if (!isTouch) {
                userMessage.focus();
            }
            syncMobileViewport();
        }
    });

    function appendMessage(role, text, timestamp) {
        const row = createMessageRow(role, text, timestamp);
        chatMessages.appendChild(row);
        if (isUserAtBottom) {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    function createMessageRow(role, text, timestamp, sources) {
        const row = document.createElement("div");
        row.className = `message-row ${role}`;
        
        const avatar = document.createElement("div");
        avatar.className = "message-avatar";
        avatar.innerHTML = role === "user" ? `<i class="fa-solid fa-user"></i>` : `<i class="fa-solid fa-heart-pulse"></i>`;
        
        const content = document.createElement("div");
        content.className = "message-content";
        if (role === "assistant") {
            content.setAttribute("aria-live", "off");
        }
        if (text) {
            content.innerHTML = safeRenderMarkdown(text);
        }

        // Timestamp label
        const ts = document.createElement("div");
        ts.className = "message-timestamp";
        ts.textContent = timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        const wrapper = document.createElement("div");
        wrapper.className = "message-wrapper";
        wrapper.appendChild(content);
        if (role === "assistant") {
            attachSourceChips(wrapper, sources);
        }
        wrapper.appendChild(ts);

        row.appendChild(avatar);
        row.appendChild(wrapper);
        return row;
    }

    function injectCodeCopyButtons(container) {
        const codeBlocks = container.querySelectorAll("pre");
        codeBlocks.forEach(pre => {
            if (pre.querySelector(".code-copy-btn")) return; // Prevent duplicate buttons
            
            const btn = document.createElement("button");
            btn.className = "code-copy-btn";
            btn.innerHTML = `<i class="fa-solid fa-copy"></i> Copy`;
            btn.addEventListener("click", () => {
                const code = pre.querySelector("code")?.textContent || pre.textContent;
                navigator.clipboard.writeText(code).then(() => {
                    btn.innerHTML = `<i class="fa-solid fa-check"></i> Copied!`;
                    setTimeout(() => {
                        btn.innerHTML = `<i class="fa-solid fa-copy"></i> Copy`;
                    }, 2000);
                });
            });
            pre.style.position = "relative";
            pre.appendChild(btn);
        });
    }

    // Lifecycle & Idle state preservation handlers
    function handlePageResume() {
        if (currentConvId && conversations[currentConvId]) {
            // Ensure sidebar list and state select are in sync
            renderConversationsList();
        } else {
            const sortedKeys = Object.keys(conversations).sort((a, b) => conversations[b].updatedAt - conversations[a].updatedAt);
            if (sortedKeys.length > 0) {
                currentConvId = sortedKeys[0];
                saveConversations();
                renderConversationsList();
                loadConversation(currentConvId);
            }
        }
    }

    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") {
            handlePageResume();
        } else {
            saveConversations();
        }
    });

    window.addEventListener("pageshow", (event) => {
        if (event.persisted) {
            handlePageResume();
        }
    });

    window.addEventListener("pagehide", () => {
        saveConversations();
    });

    window.addEventListener("beforeunload", () => {
        saveConversations();
    });

    // Startup routing
    if (currentConvId && conversations[currentConvId]) {
        renderConversationsList();
        loadConversation(currentConvId);
    } else {
        const sortedKeys = Object.keys(conversations).sort((a, b) => conversations[b].updatedAt - conversations[a].updatedAt);
        if (sortedKeys.length > 0) {
            currentConvId = sortedKeys[0];
            saveConversations();
            renderConversationsList();
            loadConversation(currentConvId);
        } else {
            startNewConversation();
        }
    }
});
