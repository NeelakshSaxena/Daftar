const chatMessages = document.getElementById('chat-messages');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const settingsBtn = document.getElementById('settings-btn');
const settingsModal = document.getElementById('settings-modal');
const closeSettingsBtn = document.getElementById('close-settings-btn');
const saveSettingsBtn = document.getElementById('save-settings-btn');
const apiUrlInput = document.getElementById('api-url');

// Default API URL fallback
const DEFAULT_API_URL = "http://172.17.72.151:1234/v1";

// Load settings on boot
let currentApiUrl = localStorage.getItem('lmStudioApiUrl') || DEFAULT_API_URL;
apiUrlInput.value = currentApiUrl;

// Settings Modal logic
function openSettings() {
    apiUrlInput.value = currentApiUrl;
    settingsModal.classList.add('show');
}

function closeSettings() {
    settingsModal.classList.remove('show');
}

function saveSettings() {
    currentApiUrl = apiUrlInput.value.trim() || DEFAULT_API_URL;
    localStorage.setItem('lmStudioApiUrl', currentApiUrl);
    closeSettings();
}

settingsBtn.addEventListener('click', openSettings);
closeSettingsBtn.addEventListener('click', closeSettings);
saveSettingsBtn.addEventListener('click', saveSettings);
settingsModal.addEventListener('click', (e) => {
    if (e.target === settingsModal) closeSettings();
});

function escapeHTML(str) {
    return str.replace(/[&<>'"]/g,
        tag => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[tag] || tag)
    );
}

function formatText(text) {
    if (!text) return '';

    // 1. Escape HTML first for XSS safety
    let formatted = escapeHTML(text);

    // 2. Parse inline code: `code` -> <code>code</code>
    formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');

    // 3. Parse bold: **text** -> <strong>text</strong>
    formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // 4. Parse newlines: \n -> <br>
    // Wrap in paragraphs by splitting on double newlines
    let paragraphs = formatted.split(/\n\n+/);
    formatted = paragraphs.map(p => {
        // Replace single newlines within paragraphs with <br>
        return `<p>${p.replace(/\n/g, '<br>')}</p>`;
    }).join('');

    return formatted;
}

const MEMORY_BADGE_SVG = `<span class="inline-memory-badge" title="Memory Saved"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>Saved</span>`;

function addMessage(content, sender, isMemorySaved = false) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', sender);

    const contentDiv = document.createElement('div');
    contentDiv.classList.add('message-content');
    contentDiv.innerHTML = formatText(content);

    if (isMemorySaved && sender === 'assistant') {
        const lastP = contentDiv.lastElementChild || contentDiv;
        lastP.innerHTML += MEMORY_BADGE_SVG;
    }

    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;

    // Clear input
    messageInput.value = '';
    messageInput.style.height = 'auto'; // Reset height
    sendBtn.disabled = true;

    // Add user message to UI
    addMessage(message, 'user');

    // Add thinking indicator container that occupies same space
    const thinkingDiv = document.createElement('div');
    thinkingDiv.classList.add('message', 'assistant');
    thinkingDiv.id = 'thinking-indicator';

    const loader = document.createElement('div');
    loader.classList.add('typing-indicator');
    loader.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';

    thinkingDiv.appendChild(loader);
    chatMessages.appendChild(thinkingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: message,
                api_url: currentApiUrl
            })
        });

        const data = await response.json();

        // Remove thinking indicator cleanly
        const indicator = document.getElementById('thinking-indicator');
        if (indicator) indicator.remove();

        // Add assistant reply
        addMessage(data.reply || data.error || "No response received", 'assistant', data.memory_saved);

        // Keep ambient toast but make it quick
        if (data.memory_saved) {
            const toast = document.getElementById('memory-toast');
            toast.classList.remove('hidden');
            setTimeout(() => {
                toast.classList.add('show');
            }, 10);

            setTimeout(() => {
                toast.classList.remove('show');
                setTimeout(() => {
                    toast.classList.add('hidden');
                }, 300);
            }, 2000);
        }

    } catch (error) {
        document.getElementById('thinking-indicator').remove();
        addMessage("Error communicating with server: " + error.message, 'assistant');
    } finally {
        sendBtn.disabled = false;
        messageInput.focus();
    }
}

sendBtn.addEventListener('click', sendMessage);

messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Auto-resize textarea
messageInput.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
    if (this.value === '') {
        this.style.height = 'auto';
    }
});
