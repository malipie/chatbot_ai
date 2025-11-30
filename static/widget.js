(function() {
    // Adres API (lokalnie lub na serwerze)
    const API_URL = "http://localhost:8000/api/chat";

    // 1. Style CSS (wstrzykiwane dynamicznie)
    const style = document.createElement('style');
    style.innerHTML = `
        #ai-bot-widget { position: fixed; bottom: 20px; right: 20px; z-index: 9999; font-family: sans-serif; }
        #ai-bot-toggle { background: #000; color: #fff; border: none; padding: 15px; border-radius: 50%; cursor: pointer; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        #ai-bot-window { display: none; width: 300px; height: 400px; background: #fff; border: 1px solid #ccc; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); flex-direction: column; overflow: hidden; }
        #ai-bot-header { background: #000; color: #fff; padding: 10px; font-weight: bold; display: flex; justify-content: space-between; }
        #ai-bot-messages { flex: 1; padding: 10px; overflow-y: auto; background: #f9f9f9; }
        #ai-bot-input-area { display: flex; border-top: 1px solid #eee; }
        #ai-bot-input { flex: 1; border: none; padding: 10px; outline: none; }
        #ai-bot-send { background: #000; color: #fff; border: none; padding: 0 15px; cursor: pointer; }
        .msg { margin: 5px 0; padding: 8px; border-radius: 5px; max-width: 80%; font-size: 14px; }
        .msg.user { background: #e0e0e0; align-self: flex-end; margin-left: auto; }
        .msg.bot { background: #000; color: #fff; align-self: flex-start; }
    `;
    document.head.appendChild(style);

    // 2. Struktura HTML
    const widget = document.createElement('div');
    widget.id = 'ai-bot-widget';
    widget.innerHTML = `
        <div id="ai-bot-window">
            <div id="ai-bot-header">Asystent <span style="cursor:pointer" id="ai-close">X</span></div>
            <div id="ai-bot-messages" style="display:flex; flex-direction:column;"></div>
            <div id="ai-bot-input-area">
                <input type="text" id="ai-bot-input" placeholder="Wpisz pytanie..." />
                <button id="ai-bot-send">➤</button>
            </div>
        </div>
        <button id="ai-bot-toggle">💬</button>
    `;
    document.body.appendChild(widget);

    // 3. Logika działania
    const windowEl = document.getElementById('ai-bot-window');
    const toggleBtn = document.getElementById('ai-bot-toggle');
    const inputEl = document.getElementById('ai-bot-input');
    const sendBtn = document.getElementById('ai-bot-send');
    const msgsEl = document.getElementById('ai-bot-messages');

    toggleBtn.onclick = () => {
        windowEl.style.display = windowEl.style.display === 'flex' ? 'none' : 'flex';
        toggleBtn.style.display = 'none';
    };
    
    document.getElementById('ai-close').onclick = () => {
        windowEl.style.display = 'none';
        toggleBtn.style.display = 'block';
    }

const addMessage = (text, sender) => {
        const div = document.createElement('div');
        div.className = `msg ${sender}`;
        
        // Prosty parser Markdown dla linków: [Tekst](Link) -> <a href="Link">Tekst</a>
        // oraz pogrubienia: **Tekst** -> <b>Tekst</b>
        let htmlText = text
            .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>') // Pogrubienie
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" style="color: #007bff; text-decoration: underline;">$1</a>') // Linki
            .replace(/\n/g, '<br>'); // Nowe linie

        div.innerHTML = htmlText; // Używamy innerHTML zamiast textContent
        
        msgsEl.appendChild(div);
        msgsEl.scrollTop = msgsEl.scrollHeight;
    };

    const sendMessage = async () => {
        const text = inputEl.value.trim();
        if (!text) return;
        addMessage(text, 'user');
        inputEl.value = '';

        try {
            const res = await fetch(API_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });
            const data = await res.json();
            addMessage(data.reply, 'bot');
        } catch (e) {
            addMessage("Błąd połączenia.", 'bot');
            console.error(e);
        }
    };

    sendBtn.onclick = sendMessage;
    inputEl.addEventListener('keydown', (e) => {if (e.key === 'Enter') sendMessage(); });
})();