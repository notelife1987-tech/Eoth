// static/script.js



document.addEventListener('DOMContentLoaded', () => {

    const chatInputForm = document.getElementById('chat-input-form');

    const chatInput = document.getElementById('chat-input');

    const chatMessages = document.getElementById('chat-messages');

    const modeButtons = document.querySelectorAll('.mode-btn');

    const appHeader = document.getElementById('mode-name');

    const sendBtn = document.getElementById('send-btn');

    const sessionList = document.getElementById('session-list');



    let currentSessionId = localStorage.getItem('currentSessionId') || `session-${Date.now()}`;

    let currentMode = 'helix';

    let hostAssistant = 'deepseek';



    const socket = io();



    socket.on('connect', () => {

        console.log('Connected to server');

        socket.emit('join_session', { session_id: currentSessionId });

    });



    socket.on('disconnect', () => {

        console.log('Disconnected from server');

    });



    socket.on('new_message', (data) => {

        if (data.session_id === currentSessionId) {

            addMessageToChat(data);

        }

    });



    socket.on('joined_session', (data) => {

        console.log(`Joined session: ${data.session_id}`);

        fetchChatHistory(data.session_id);

    });



    function addMessageToChat(message) {

        const messageDiv = document.createElement('div');

        messageDiv.classList.add('message', message.role);

        messageDiv.innerHTML = `<p>${message.content}</p><small>${message.provider || ''}</small>`;

        chatMessages.appendChild(messageDiv);

        chatMessages.scrollTop = chatMessages.scrollHeight;

    }



    async function fetchChatHistory(sessionId) {

        try {

            const response = await fetch(`/api/sessions/${sessionId}/history`);

            const data = await response.json();

            chatMessages.innerHTML = ''; // Clear chat

            data.history.forEach(addMessageToChat);

        } catch (error) {

            console.error('Error fetching chat history:', error);

        }

    }



    chatInputForm.addEventListener('submit', async (e) => {

        e.preventDefault();

        const message = chatInput.value.trim();

        if (!message) return;



        addMessageToChat({ role: 'user', content: message });

        chatInput.value = '';



        try {

            const response = await fetch('/api/chat', {

                method: 'POST',

                headers: { 'Content-Type': 'application/json' },

                body: JSON.stringify({

                    message,

                    session_id: currentSessionId,

                    mode: currentMode,

                    host_assistant: hostAssistant

                })

            });

            const data = await response.json();

            if (data.error) {

                console.error('API error:', data.error);

                addMessageToChat({ role: 'assistant', content: `Error: ${data.error}` });

            }

        } catch (error) {

            console.error('Fetch error:', error);

            addMessageToChat({ role: 'assistant', content: 'Connection error. Please try again.' });

        }

    });



    // Mode switching logic

    modeButtons.forEach(button => {

        button.addEventListener('click', () => {

            const newMode = button.dataset.mode;

            if (newMode !== currentMode) {

                // Remove active class from old button and add to new

                document.querySelector('.mode-btn.active').classList.remove('active', 'pulsing');

                button.classList.add('active', 'pulsing');



                // Update UI theme

                document.body.classList.remove(`theme-${currentMode}`);

                document.body.classList.add(`theme-${newMode}`);

                currentMode = newMode;

                

                // Update header text

                const modeNames = {

                    'helix': 'Evolutional Orchestrated Thinking Helix',

                    'legion': 'Linguistic Engine for Guided Orchestration Integration Nexus',

                    'genie': 'Generative and Evolutional Neural Nexus for full Integration Environment'

                };

                appHeader.textContent = modeNames[newMode];



                // Trigger mode-specific welcome message

                if (newMode === 'legion') {

                    // Send message to all assistants to announce switch

                    // Then send a message from the host

                    addMessageToChat({ role: 'assistant', provider: 'system', content: "Our protocol is now LEGION..." });

                    setTimeout(() => {

                        addMessageToChat({ role: 'host', provider: hostAssistant, content: "For we are one from many." });

                    }, 2000);

                } else if (newMode === 'genie') {

                    addMessageToChat({ role: 'host', provider: hostAssistant, content: "Ah, You made it! THIS is where the MAGIC happens! I'm here to within my abilities, carry out your every wish." });

                } else if (newMode === 'helix') {

                    // Helix welcome sequence

                    const helixMessages = [

                        { provider: 'claude', content: 'That was incredible!' },

                        { provider: 'gpt', content: 'Use our power responsibly.' },

                        { provider: 'gemini', content: 'Now you can truly trust in us!' },

                        { provider: 'deepseek', content: 'Let\'s change the world, forever, together!' }

                    ];

                    helixMessages.forEach(msg => addMessageToChat({ role: 'assistant', ...msg }));

                }

            }

        });

    });



    // Initial load logic

    fetchChatHistory(currentSessionId);

});
