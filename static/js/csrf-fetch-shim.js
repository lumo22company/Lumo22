/**
 * Wraps fetch() so same-origin POST/PUT/PATCH/DELETE include the Flask-WTF CSRF header
 * when <meta name="csrf-token" content="..."> is present. Load synchronously in <head>
 * before any inline scripts that call fetch.
 */
(function () {
  'use strict';
  var meta = document.querySelector('meta[name="csrf-token"]');
  var token = meta && meta.getAttribute('content');
  if (!token) return;
  var orig = window.fetch;
  window.fetch = function (input, init) {
    init = init || {};
    var method = (init.method || 'GET').toUpperCase();
    if (method === 'POST' || method === 'PUT' || method === 'PATCH' || method === 'DELETE') {
      var headers = new Headers(init.headers || {});
      if (!headers.has('X-CSRFToken') && !headers.has('X-CSRF-Token')) {
        headers.set('X-CSRFToken', token);
      }
      init.headers = headers;
    }
    if (init.credentials === undefined) {
      init.credentials = 'same-origin';
    }
    return orig.call(this, input, init);
  };
})();
