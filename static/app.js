document.addEventListener("DOMContentLoaded", () => {
    // Elements
    const chatMessages = document.getElementById("chatMessages");
    const chatForm = document.getElementById("chatForm");
    const userMessage = document.getElementById("userMessage");
    const sendBtn = document.getElementById("sendBtn");
    const stateSelect = document.getElementById("stateSelect");
    const apiStatusBadge = document.getElementById("apiStatusBadge");
    
    const fontToggleBtn = document.getElementById("fontToggleBtn");
    const fontLbl = document.getElementById("fontLbl");
    
    const toggleSidebar = document.getElementById("toggleSidebar");
    const closeSidebar = document.getElementById("closeSidebar");
    const sidebar = document.getElementById("sidebar");
    const sidebarOverlay = document.getElementById("sidebarOverlay");
    const conversationsList = document.getElementById("conversationsList");

    // Configure marked to render clickable external links with icons
    const renderer = new marked.Renderer();
    renderer.link = (linkObj) => {
        const href = typeof linkObj === 'object' ? linkObj.href : arguments[0];
        const title = (typeof linkObj === 'object' ? linkObj.title : arguments[1]) || '';
        const text = (typeof linkObj === 'object' ? linkObj.text : arguments[2]) || href;
        return `<a href="${href}" target="_blank" rel="noopener noreferrer" title="${title || text}">${text} <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 0.75em; opacity: 0.85;"></i></a>`;
    };
    marked.use({ renderer });

    // Smart Scroll & Manual Scroll Detection
    let isUserScrolledUp = false;
    let chatHistory = []; // Stores conversation turn history [{role, content}] for RAG API payload
    let isStreaming = false; // Concurrency guard — prevents overlapping requests
    const scrollToBottomBtn = document.getElementById("scrollToBottomBtn");

    chatMessages.addEventListener("scroll", () => {
        const threshold = 120; // px threshold from bottom
        const distanceFromBottom = chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight;
        isUserScrolledUp = distanceFromBottom > threshold;

        if (scrollToBottomBtn) {
            if (isUserScrolledUp) {
                scrollToBottomBtn.classList.add("visible");
            } else {
                scrollToBottomBtn.classList.remove("visible");
            }
        }
    });

    scrollToBottomBtn?.addEventListener("click", () => {
        isUserScrolledUp = false;
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
                const row = createMessageRow(msg.role, msg.content, msg.timestamp);
                chatMessages.appendChild(row);
            });
            
            // Build chatHistory array (API multi-turn payload)
            chatHistory = [];
            conv.messages.forEach(msg => {
                chatHistory.push({ role: msg.role, content: msg.content });
            });
            if (chatHistory.length > 10) chatHistory = chatHistory.slice(-10);
            
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

    stateSelect.value = savedState;
    if (isLargeFont) applyFontMode(true);

    // Fetch backend status on startup to update API status badge
    fetch("/api/stats")
        .then(res => res.json())
        .then(data => {
            updateBadgeStatus(data.has_api_key);
        })
        .catch(err => updateBadgeStatus(false));

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
    fontToggleBtn.addEventListener("click", () => {
        isLargeFont = !isLargeFont;
        localStorage.setItem("mnd_large_font", isLargeFont);
        applyFontMode(isLargeFont);
    });

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
        isUserScrolledUp = false;
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

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: text,
                    state: stateSelect.value,
                    history: chatHistory
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
                            if (parsed.content) {
                                fullContent += parsed.content;
                                try {
                                    contentDiv.innerHTML = marked.parse(fullContent);
                                } catch (markdownErr) {
                                    contentDiv.textContent = fullContent;
                                }
                                
                                // Smart scroll: Only auto-scroll if user has NOT manually scrolled up
                                if (!isUserScrolledUp) {
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
                // Record successfully generated turn into conversation history
                chatHistory.push({ role: "user", content: text });
                chatHistory.push({ role: "assistant", content: fullContent });
                if (chatHistory.length > 10) chatHistory = chatHistory.slice(-10);

                // Save assistant message to conversations storage
                conversations[currentConvId].messages.push({
                    role: "assistant",
                    content: fullContent,
                    timestamp: timestampStr
                });
                conversations[currentConvId].updatedAt = Date.now();
                saveConversations();

                // Post-process: inject copy buttons into code blocks
                injectCodeCopyButtons(contentDiv);
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

    function appendMessage(role, text, timestamp) {
        const row = createMessageRow(role, text, timestamp);
        chatMessages.appendChild(row);
        if (!isUserScrolledUp) {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    function createMessageRow(role, text, timestamp) {
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
