/**
 * Website Chat Widget — embed script.
 * Load with: <script src="https://your-domain.com/static/js/chat-widget.js" data-key="WIDGET_KEY" async></script>
 * Validates key via GET /api/chat-widget/status — if subscription cancelled, widget does not show.
 * Add data-site-help="true" for Lumo 22 site: shows help panel (email, product links) instead of placeholder message.
 */
(function () {
  'use strict';
  var script = document.currentScript;
  var key = script && script.getAttribute('data-key');
  if (!key) return;

  var base = (script.src || '').replace(/\/static\/js\/chat-widget\.js.*$/, '') || '';
  var statusUrl = base + '/api/chat-widget/status?key=' + encodeURIComponent(key);
  var isSiteHelp = (script && script.getAttribute('data-site-help') || '').toLowerCase() === 'true';

  function showBubble() {
    var bubble = document.createElement('button');
    bubble.setAttribute('type', 'button');
    bubble.setAttribute('aria-label', 'Open chat');
    bubble.style.cssText = 'position:fixed;bottom:20px;right:20px;width:56px;height:56px;border-radius:50%;background:var(--lum-gold,#c9a227);color:#000;border:none;cursor:pointer;font-size:24px;line-height:1;box-shadow:0 2px 12px rgba(0,0,0,0.2);z-index:9999;';
    bubble.textContent = '💬';
    bubble.addEventListener('click', function () {
      if (isSiteHelp) {
        showSiteHelpPanel(base);
      } else {
        alert('Chat is being set up. You\'ll be able to talk to us here soon. For now, email us or check back later.');
      }
    });
    document.body.appendChild(bubble);
  }

  function showSiteHelpPanel(baseUrl) {
    var existing = document.getElementById('lumo-chat-help-panel');
    if (existing) {
      existing.style.display = existing.style.display === 'none' ? 'block' : 'none';
      return;
    }
    var panel = document.createElement('div');
    panel.id = 'lumo-chat-help-panel';
    panel.style.cssText = 'position:fixed;bottom:90px;right:20px;width:300px;max-width:calc(100vw - 40px);background:#1a1a1a;color:#f5f5f2;border-radius:12px;box-shadow:0 4px 24px rgba(0,0,0,0.4);z-index:9998;padding:1.25rem;font-family:system-ui,sans-serif;font-size:0.95rem;line-height:1.5;';
    panel.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;"><strong style="color:#fff;">How can we help?</strong><button type="button" aria-label="Close" style="background:none;border:none;color:#9a9a96;cursor:pointer;font-size:1.25rem;line-height:1;padding:0;">×</button></div>' +
      '<p style="margin:0 0 1rem;color:#9a9a96;font-size:0.9rem;">Questions about our products or need support?</p>' +
      '<p style="margin:0 0 0.75rem;"><a href="mailto:hello@lumo22.com" style="color:#fff200;text-decoration:none;">Email us → hello@lumo22.com</a></p>' +
      '<p style="margin:0 0 0.5rem;font-size:0.85rem;color:#9a9a96;">Quick links:</p>' +
      '<ul style="margin:0;padding-left:1.25rem;color:#e8e6e2;">' +
      '<li style="margin-bottom:0.25rem;"><a href="' + baseUrl + '/captions" style="color:#fff200;text-decoration:none;">30 Days Captions</a></li>' +
      '<li style="margin-bottom:0.25rem;"><a href="' + baseUrl + '/digital-front-desk" style="color:#fff200;text-decoration:none;">Digital Front Desk</a></li>' +
      '<li><a href="' + baseUrl + '/website-chat" style="color:#fff200;text-decoration:none;">Chat Assistant</a></li>' +
      '</ul>';
    var closeBtn = panel.querySelector('button');
    closeBtn.addEventListener('click', function () { panel.style.display = 'none'; });
    document.body.appendChild(panel);
  }

  fetch(statusUrl, { method: 'GET' })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data && data.valid) showBubble();
    })
    .catch(function () {
      /* network error: don't show bubble to avoid broken UX */
    });
})();
