/**
 * Website Chat Widget — embed script.
 * Load with: <script src="https://your-domain.com/static/js/chat-widget.js" data-key="WIDGET_KEY" async></script>
 * TODO: Replace with full widget that calls POST /api/chat with widget_key, message, history.
 * TODO: Enforce per-conversation or per-seat limits by plan.
 */
(function () {
  'use strict';
  var script = document.currentScript;
  var key = script && script.getAttribute('data-key');
  if (!key) return;

  // Placeholder: show a chat bubble so the embed doesn't look broken. Replace with real chat UI + /api/chat.
  var bubble = document.createElement('button');
  bubble.setAttribute('type', 'button');
  bubble.setAttribute('aria-label', 'Open chat');
  bubble.style.cssText = 'position:fixed;bottom:20px;right:20px;width:56px;height:56px;border-radius:50%;background:var(--lum-gold,#c9a227);color:#000;border:none;cursor:pointer;font-size:24px;line-height:1;box-shadow:0 2px 12px rgba(0,0,0,0.2);z-index:9999;';
  bubble.textContent = '💬';
  bubble.addEventListener('click', function () {
    alert('Chat is being set up. You\'ll be able to talk to us here soon. For now, email us or check back later.');
  });
  document.body.appendChild(bubble);
})();
