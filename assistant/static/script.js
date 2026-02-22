const chatMessages = document.getElementById('chat-messages');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const settingsBtn = document.getElementById('settings-btn');
const settingsModal = document.getElementById('settings-modal');
const closeSettingsBtn = document.getElementById('close-settings-btn');
const saveSettingsBtn = document.getElementById('save-settings-btn');
const apiUrlInput = document.getElementById('api-url');

// Default API URL fallback
const DEFAULT_API_URL = "http://127.0.0.1:1234/v1";

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

function addMessage(content, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', sender);
    messageDiv.textContent = content;
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

    // Add thinking indicator
    const thinkingDiv = document.createElement('div');
    thinkingDiv.classList.add('message', 'assistant');
    thinkingDiv.textContent = 'Thinking...';
    thinkingDiv.id = 'thinking-indicator';
    chatMessages.appendChild(thinkingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                api_url: currentApiUrl
            })
        });

        const data = await response.json();

        // Remove thinking indicator
        document.getElementById('thinking-indicator').remove();

        // Add assistant reply
        addMessage(data.reply || data.error || "No response received", 'assistant');

        // Show memory toast if memory was saved
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
            }, 3000);
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
