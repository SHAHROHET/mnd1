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
    
    const toggleSidebar = document.getElementById("toggleSidebar");
    const closeSidebar = document.getElementById("closeSidebar");
    const sidebar = document.getElementById("sidebar");
    const sidebarOverlay = document.getElementById("sidebarOverlay");
    const conversationsList = document.getElementById("conversationsList");
    const openProfileBtn = document.getElementById("openProfileBtn");
    const profileModal = document.getElementById("profileModal");
    const closeProfileBtn = document.getElementById("closeProfileBtn");
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

    function findImageInClientMap(query) {
        if (!query) return "";
        const normQuery = query.toLowerCase().replace(/[^a-z0-9]/g, "");
        if (!normQuery) return "";
        // Exact match
        if (clientImageMap[normQuery]) {
            return clientImageMap[normQuery];
        }
        // Substring match
        for (const [key, val] of Object.entries(clientImageMap)) {
            if (key.includes(normQuery) || normQuery.includes(key)) {
                return val;
            }
        }
        // Token-level matching: score each key by how many query tokens it contains
        const tokens = query.toLowerCase().match(/[a-z0-9]{3,}/g) || [];
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
    renderer.link = (linkObj) => {
        const href = typeof linkObj === 'object' ? linkObj.href : arguments[0];
        const title = (typeof linkObj === 'object' ? linkObj.title : arguments[1]) || '';
        const text = (typeof linkObj === 'object' ? linkObj.text : arguments[2]) || href;
        return `<a href="${href}" target="_blank" rel="noopener noreferrer" title="${title || text}">${text} <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 0.75em; opacity: 0.85;"></i></a>`;
    };
    
    renderer.image = (imageObj, titleArg, textArg) => {
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
        
        let finalSrc = href;
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
            return text ? `<span class="image-placeholder">${escapeHtml(text)}</span>` : "";
        }
        finalSrc = matched;
        
        return `<img src="${finalSrc}" alt="${escapeHtml(text || 'Care Image')}" class="care-message-img" title="${escapeHtml(title || text)}">`;
    };
    
    marked.use({ renderer });

    // Smart Scroll & Manual Scroll Detection
    let isUserAtBottom = true;
    let chatHistory = []; // Stores conversation turn history [{role, content}] for RAG API payload
    let isStreaming = false; // Concurrency guard — prevents overlapping requests
    const scrollToBottomBtn = document.getElementById("scrollToBottomBtn");

    chatMessages.addEventListener("scroll", () => {
        const threshold = 100; // px threshold from bottom
        const distanceFromBottom = chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight;
        isUserAtBottom = distanceFromBottom <= threshold;

        if (scrollToBottomBtn) {
            if (!isUserAtBottom) {
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
            
            item.innerHTML = `
                <div class="conversation-info">
                    <i class="fa-regular fa-message"></i>
                    <span class="conversation-title" title="${conv.title}">${conv.title}</span>
                </div>
                <button class="delete-conv-btn" title="Delete conversation">
                    <i class="fa-solid fa-trash-can"></i>
                </button>
            `;
            
            // Load conversation on click
            item.addEventListener("click", (e) => {
                if (isStreaming) return; // Prevent switching chats during stream
                // Don't trigger load if clicking delete button
                if (e.target.closest(".delete-conv-btn")) return;
                loadConversation(conv.id);
            });
            
            // Delete conversation on click
            const deleteBtn = item.querySelector(".delete-conv-btn");
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
                    <div class="welcome-icon">
                        <i class="fa-solid fa-hands-holding-child"></i>
                    </div>
                    <h2>Welcome to the Australian MND/ALS Assistant</h2>
                    <p>Designed for people living with Motor Neurone Disease, family carers, occupational therapists, and clinical teams across Australia. Ask any question regarding symptom management, NDIS funding, equipment loan libraries, or advance care planning.</p>
                    <div class="prompt-chips">
                        <div class="chip" data-prompt="What equipment can I get through FlexEquip or SWEP for mobility and transfer?">
                            <i class="fa-solid fa-wheelchair"></i> Mobility & Equipment Pathways
                        </div>
                        <div class="chip" data-prompt="How do I manage nocturnal breathing problems or non-invasive ventilation (NIV)?">
                            <i class="fa-solid fa-lungs"></i> Nocturnal Breathing & NIV
                        </div>
                        <div class="chip" data-prompt="What NDIS funding support and Centrelink Carer Payments are available for MND?">
                            <i class="fa-solid fa-hand-holding-dollar"></i> NDIS Funding & Carer Payment
                        </div>
                        <div class="chip" data-prompt="What is voice banking and how early should I start with speech pathology?">
                            <i class="fa-solid fa-microphone-lines"></i> Voice Banking & Communication
                        </div>
                        <div class="chip" data-prompt="What are IDDSI texture levels for swallowing safety and nutrition in MND?">
                            <i class="fa-solid fa-utensils"></i> Swallowing & IDDSI Nutrition
                        </div>
                        <div class="chip" data-prompt="What is involved in Advance Care Planning and Advance Care Directives?">
                            <i class="fa-solid fa-file-signature"></i> Advance Care Planning
                        </div>
                    </div>
                </div>
            `;
            bindPromptChips();
            chatHistory = [];
        } else {
            // Re-render past messages
            conv.messages.forEach(msg => {
                const row = createMessageRow(msg.role, msg.content, msg.timestamp, msg.entities);
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
    let currentTheme = localStorage.getItem("mnd_theme") || "dark";

    stateSelect.value = savedState;
    applyTheme(currentTheme);
    if (isLargeFont) applyFontMode(true);

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

    openProfileBtn?.addEventListener("click", () => {
        populateProfileForm();
        profileModal?.classList.add("active");
    });

    closeProfileBtn?.addEventListener("click", closeProfileModal);
    profileModal?.addEventListener("click", (e) => {
        if (e.target === profileModal) closeProfileModal();
    });

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && profileModal?.classList.contains("active")) {
            closeProfileModal();
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
            updateBadgeStatus(data.has_api_key);
            updateStats(data);
        })
        .catch(err => updateBadgeStatus(false));

    fetch("/api/images")
        .then(res => res.json())
        .then(data => {
            clientImageMap = data || {};
        })
        .catch(err => console.error("Failed to load client image map:", err));

    // Sidebar Toggle
    toggleSidebar?.addEventListener("click", () => sidebar.classList.add("active"));
    closeSidebar?.addEventListener("click", () => sidebar.classList.remove("active"));
    sidebarOverlay?.addEventListener("click", () => sidebar.classList.remove("active"));

    // Export Care Plan Summary button
    const exportBtn = document.getElementById("exportBtn");
    exportBtn?.addEventListener("click", () => {
        window.print();
    });

    // New Chat button — creates new conversation and active state
    const newChatBtn = document.getElementById("newChatBtn");
    newChatBtn?.addEventListener("click", () => {
        if (isStreaming) return;
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

    function applyTheme(theme) {
        const isLight = theme === "light";
        document.body.classList.toggle("theme-light", isLight);
        document.body.classList.toggle("theme-dark", !isLight);

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
        } else {
            document.documentElement.classList.remove("font-large");
            document.body.classList.remove("font-large");
            fontLbl.textContent = "Large Text";
            fontToggleBtn.classList.remove("btn-accent");
        }
    }

    function updateBadgeStatus(hasBackendKey) {
        if (hasBackendKey) {
            apiStatusBadge.classList.add("active");
            apiStatusBadge.innerHTML = `<i class="fa-solid fa-circle"></i> Assistant Active`;
        } else {
            apiStatusBadge.classList.remove("active");
            apiStatusBadge.innerHTML = `<i class="fa-solid fa-circle"></i> Local Guide Active`;
        }
    }

    function updateStats(data) {
        if (docCountStat && Number.isFinite(data?.total_documents)) {
            docCountStat.textContent = data.total_documents.toLocaleString();
        }
        if (entityCountStat && Number.isFinite(data?.total_entities)) {
            entityCountStat.textContent = data.total_entities.toLocaleString();
        }
    }

    // Auto-resize textarea
    userMessage.addEventListener("input", () => {
        userMessage.style.height = "auto";
        userMessage.style.height = Math.min(userMessage.scrollHeight, 150) + "px";
        sendBtn.disabled = !userMessage.value.trim() || isStreaming;
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
                chatForm.dispatchEvent(new Event("submit"));
            });
        });
    }

    // Chat Submission
    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const text = userMessage.value.trim();
        if (!text || isStreaming) return;

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
        contentDiv.innerHTML = `<span class="typing-indicator"><i class="fa-solid fa-circle-notch fa-spin"></i> Retrieving MND Knowledge Base...</span>`;
        chatMessages.appendChild(assistantRow);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        let fullContent = "";
        let currentEntities = [];

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
                    profile: readUserProfile()
                })
            });

            if (!response.ok) {
                contentDiv.innerHTML = `⚠️ Error connecting to backend server (${response.status})`;
                return;
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            contentDiv.innerHTML = "";

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunkStr = decoder.decode(value);
                const lines = chunkStr.split("\n\n");

                for (const line of lines) {
                    if (line.startsWith?.("data: ") || line.indexOf("data: ") === 0) {
                        const jsonStr = line.replace("data: ", "").trim();
                        if (jsonStr === "[DONE]") break;

                        try {
                            const parsed = JSON.parse(jsonStr);
                            if (parsed.entities) {
                                currentEntities = parsed.entities;
                            }
                            if (parsed.content) {
                                fullContent += parsed.content;
                                try {
                                    contentDiv.innerHTML = marked.parse(fullContent);
                                } catch (markdownErr) {
                                    contentDiv.textContent = fullContent;
                                }
                                
                                // Smart scroll: Only auto-scroll if user is currently at bottom
                                if (isUserAtBottom) {
                                    chatMessages.scrollTop = chatMessages.scrollHeight;
                                }
                            }
                        } catch (err) {
                            // Ignored partial chunk errors
                        }
                    }
                }
            }

            if (!fullContent) {
                contentDiv.innerHTML = "No response generated.";
            } else {
                // Record assistant response into conversation history for multi-turn context
                chatHistory.push({ role: "assistant", content: fullContent });
                if (chatHistory.length > 20) chatHistory = chatHistory.slice(-20);

                // Save assistant message with retrieved entities to conversations storage
                conversations[currentConvId].messages.push({
                    role: "assistant",
                    content: fullContent,
                    timestamp: timestampStr,
                    entities: currentEntities
                });
                conversations[currentConvId].updatedAt = Date.now();
                saveConversations();

                // Append visual card deck if entities found
                if (currentEntities && currentEntities.length > 0) {
                    const deck = renderEntityDeck(currentEntities);
                    if (deck) {
                        contentDiv.appendChild(deck);
                    }
                    if (isUserAtBottom) {
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    }
                }

                // Post-process: inject copy buttons into code blocks
                injectCodeCopyButtons(contentDiv);

                // Smoothly scroll back to the start of the user's question so both question & answer are visible
                if (isUserAtBottom) {
                    const userRow = assistantRow.previousElementSibling;
                    const targetScrollTop = userRow ? userRow.offsetTop - 16 : assistantRow.offsetTop - 16;
                    setTimeout(() => {
                        chatMessages.scrollTo({
                            top: targetScrollTop,
                            behavior: "smooth"
                        });
                    }, 150);
                }
            }

        } catch (err) {
            contentDiv.innerHTML = `⚠️ Network Error: ${err.message}`;
        } finally {
            // Unlock streaming state
            isStreaming = false;
            sendBtn.disabled = !userMessage.value.trim();
            userMessage.removeAttribute("disabled");
            userMessage.focus();
        }
    });

    function renderEntityDeck(entities) {
        if (!entities || entities.length === 0) return null;
        
        const deck = document.createElement("div");
        deck.className = "resources-deck";
        
        let deckHtml = `<div class="deck-title"><i class="fa-solid fa-toolbox"></i> Verified Equipment & Services:</div>`;
        deckHtml += `<div class="deck-scroll">`;
        
        entities.forEach(ent => {
            const rawImg = ent.image_url || findImageInClientMap(ent.name) || findImageInClientMap(ent.category) || "";
            const url = ent.url || ent.website || ent.source_url || ent.served_url || ent.product_url || "";
            const categoryLabel = ent.category ? ent.category.replace(/_/g, ' ').toUpperCase() : 'SUPPORT';
            const desc = ent.description ? (ent.description.length > 80 ? ent.description.substring(0, 80) + '...' : ent.description) : '';
            
            const cardTag = url ? 'a' : 'div';
            const linkAttrs = url ? `href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer"` : '';

            if (rawImg) {
                deckHtml += `
                    <${cardTag} ${linkAttrs} class="deck-card">
                        <div class="deck-card-img-wrap">
                            <img src="${rawImg}" alt="${escapeHtml(ent.name)}" class="deck-card-img" loading="lazy">
                        </div>
                        <div class="deck-card-body">
                            <span class="deck-card-tag">${escapeHtml(categoryLabel)}</span>
                            <h4 class="deck-card-title" title="${escapeHtml(ent.name)}">${escapeHtml(ent.name)}</h4>
                            <p class="deck-card-desc">${escapeHtml(desc)}</p>
                        </div>
                    </${cardTag}>
                `;
            } else {
                deckHtml += `
                    <${cardTag} ${linkAttrs} class="deck-card no-img-card">
                        <div class="deck-card-body">
                            <span class="deck-card-tag"><i class="fa-solid fa-circle-info"></i> ${escapeHtml(categoryLabel)}</span>
                            <h4 class="deck-card-title" title="${escapeHtml(ent.name)}">${escapeHtml(ent.name)}</h4>
                            <p class="deck-card-desc">${escapeHtml(desc)}</p>
                        </div>
                    </${cardTag}>
                `;
            }
        });
        
        deckHtml += `</div>`;
        deck.innerHTML = deckHtml;
        return deck;
    }

    function appendMessage(role, text, timestamp, entities) {
        const row = createMessageRow(role, text, timestamp, entities);
        chatMessages.appendChild(row);
        if (isUserAtBottom) {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    function createMessageRow(role, text, timestamp, entities) {
        const row = document.createElement("div");
        row.className = `message-row ${role}`;
        
        const avatar = document.createElement("div");
        avatar.className = "message-avatar";
        avatar.innerHTML = role === "user" ? `<i class="fa-solid fa-user"></i>` : `<i class="fa-solid fa-heart-pulse"></i>`;
        
        const content = document.createElement("div");
        content.className = "message-content";
        if (text) {
            try {
                content.innerHTML = marked.parse(text);
            } catch (e) {
                content.textContent = text;
            }
        }

        // Render visual card deck if entities are provided
        if (entities && entities.length > 0) {
            const deck = renderEntityDeck(entities);
            if (deck) content.appendChild(deck);
        }

        // Timestamp label
        const ts = document.createElement("div");
        ts.className = "message-timestamp";
        ts.textContent = timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        const wrapper = document.createElement("div");
        wrapper.className = "message-wrapper";
        wrapper.appendChild(content);
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

    // Startup routing
    if (currentConvId && conversations[currentConvId]) {
        renderConversationsList();
        loadConversation(currentConvId);
    } else {
        startNewConversation();
    }
});
