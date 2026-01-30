/**
 * Digital Front Desk — Conversational Intake Logic
 * -------------------------------------------------
 * A guided flow that qualifies users and routes them to:
 * a) Buy 30-day captions
 * b) Book a consultation
 * c) Ask questions
 * d) Be qualified before contact
 *
 * INTEGRATION: For full AI, replace scripted responses with API calls.
 * Stub: window.LUMO_AI_ENDPOINT = '/api/qualify'; — POST { message, history }
 */

(function () {
  'use strict';

  var messagesEl = document.getElementById('chat-messages');
  var inputArea = document.getElementById('chat-input-area');
  var chatInput = document.getElementById('chat-input');
  var chatSend = document.getElementById('chat-send');
  var welcomeOptions = document.getElementById('welcome-options');

  if (!messagesEl || !welcomeOptions) return;

  var state = {
    step: 'welcome',
    data: { intent: null, businessType: null, goals: null, platform: null, urgency: null },
    history: []
  };

  function addBotMessage(text, options) {
    var msg = document.createElement('div');
    msg.className = 'lumo-chat-msg bot';
    var p = document.createElement('p');
    p.textContent = text;
    msg.appendChild(p);
    if (options && options.length) {
      var opts = document.createElement('div');
      opts.className = 'lumo-chat-options';
      options.forEach(function (opt) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'lumo-chat-option';
        btn.textContent = opt.label;
        btn.dataset.value = opt.value;
        btn.addEventListener('click', function () { handleOption(opt.value, opt.label); });
        opts.appendChild(btn);
      });
      msg.appendChild(opts);
    }
    messagesEl.appendChild(msg);
    msg.scrollIntoView({ behavior: 'smooth', block: 'end' });
    return msg;
  }

  function addUserMessage(text) {
    var msg = document.createElement('div');
    msg.className = 'lumo-chat-msg user';
    var p = document.createElement('p');
    p.textContent = text;
    msg.appendChild(p);
    messagesEl.appendChild(msg);
    msg.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }

  function showTyping(done) {
    var typing = document.createElement('div');
    typing.className = 'lumo-chat-msg bot typing';
    typing.innerHTML = '<p>...</p>';
    messagesEl.appendChild(typing);
    typing.scrollIntoView({ behavior: 'smooth', block: 'end' });
    setTimeout(function () {
      typing.remove();
      if (done) done();
    }, 600);
  }

  function showResult(ctaText, ctaHref, summary) {
    var msg = document.createElement('div');
    msg.className = 'lumo-chat-msg bot';
    var p = document.createElement('p');
    p.textContent = summary;
    msg.appendChild(p);
    var cta = document.createElement('div');
    cta.className = 'lumo-chat-cta-result';
    var cp = document.createElement('p');
    cp.textContent = 'Your recommended next step:';
    cta.appendChild(cp);
    var a = document.createElement('a');
    a.href = ctaHref;
    a.className = 'lumo-btn-primary';
    a.textContent = ctaText;
    cta.appendChild(a);
    msg.appendChild(cta);
    messagesEl.appendChild(msg);
    msg.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }

  function hideWelcomeOptions() {
    welcomeOptions.style.display = 'none';
  }

  function showInput() {
    inputArea.style.display = 'block';
    chatInput.focus();
  }

  function hideInput() {
    inputArea.style.display = 'none';
  }

  function handleOption(value, label) {
    if (value === 'email') {
      window.location.href = 'mailto:hello@lumo22.com?subject=Enquiry%20from%20Front%20Desk';
      return;
    }
    addUserMessage(label);
    hideWelcomeOptions();

    if (state.step === 'welcome') {
      state.data.intent = value;
      state.step = 'qualify';

      if (value === 'captions') {
        showTyping(function () {
          addBotMessage('Perfect. What kind of business are you in?', [
            { value: 'service', label: 'Service business (coaching, consulting)' },
            { value: 'creative', label: 'Creative / agency' },
            { value: 'retail', label: 'Retail / e‑commerce' },
            { value: 'other', label: 'Other' }
          ]);
        });
        return;
      }

      if (value === 'consultation') {
        showTyping(function () {
          addBotMessage('What would you like to explore in a consultation?', [
            { value: 'strategy', label: 'Content strategy' },
            { value: 'automation', label: 'Automation / front desk' },
            { value: 'both', label: 'Both' },
            { value: 'unsure', label: 'Not sure yet' }
          ]);
        });
        return;
      }

      if (value === 'questions' || value === 'explore') {
        showTyping(function () {
          addBotMessage('What’s your main goal right now?', [
            { value: 'content', label: 'More consistent social content' },
            { value: 'leads', label: 'Better lead capture / follow‑up' },
            { value: 'time', label: 'Save time on admin' },
            { value: 'curious', label: 'Just curious' }
          ]);
        });
        return;
      }
    }

    /* Qualify step */
    if (value === 'service' || value === 'creative' || value === 'retail' || value === 'other') {
      state.data.businessType = value;
      showTyping(function () {
        addBotMessage('Which platform matters most to you right now?', [
          { value: 'instagram', label: 'Instagram' },
          { value: 'linkedin', label: 'LinkedIn' },
          { value: 'both', label: 'Both' },
          { value: 'other', label: 'Other' }
        ]);
      });
      return;
    }

    if (value === 'instagram' || value === 'linkedin' || value === 'both' || value === 'other') {
      state.data.platform = value;
      showTyping(function () {
        showResult(
          'Get my 30 days',
          'mailto:hello@lumo22.com?subject=30%20Days%20Captions%20Order',
          'Based on what you shared, the 30 Days of Social Captions is a strong fit. You’ll get tailored content for your business. Hit the button to order — we’ll follow up within 24 hours.'
        );
      });
      return;
    }

    if (value === 'strategy' || value === 'automation' || value === 'both' || value === 'unsure') {
      state.data.goals = value;
      showTyping(function () {
        showResult(
          'Book a consultation',
          'mailto:hello@lumo22.com?subject=Consultation%20Booking',
          'A consultation will help clarify your goals and next steps. We’ll tailor the conversation to what you need.'
        );
      });
      return;
    }

    if (value === 'content' || value === 'leads' || value === 'time' || value === 'curious') {
      state.data.goals = value;
      showTyping(function () {
        var href = value === 'content' ? 'mailto:hello@lumo22.com?subject=30%20Days%20Captions' : 'mailto:hello@lumo22.com?subject=General%20enquiry';
        var ctaText = value === 'content' ? 'Get 30 days of captions' : 'Get in touch';
        var summary = value === 'content'
          ? 'The 30 Days of Captions could be a great starting point — consistent content without the writer’s block.'
          : 'Let’s chat. Tell us what you’re looking for and we’ll point you in the right direction.';
        showResult(ctaText, href, summary);
      });
      return;
    }
  }

  /* Optional: free-text input for follow-up */
  function handleSend() {
    var text = (chatInput.value || '').trim();
    if (!text) return;
    addUserMessage(text);
    chatInput.value = '';

    /* Stub: In production, POST to AI endpoint for dynamic response */
    /* if (window.LUMO_AI_ENDPOINT) { fetch(...) } */
    showTyping(function () {
      addBotMessage('Thanks for that. The best next step is to get in touch directly — we’ll tailor our reply to what you need.', [
        { value: 'email', label: 'Email us' }
      ]);
    });
  }

  if (chatSend) chatSend.addEventListener('click', handleSend);
  if (chatInput) {
    chatInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); handleSend(); }
    });
  }
})();
