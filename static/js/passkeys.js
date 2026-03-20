/**
 * WebAuthn helpers for Lumo 22 (passkey sign-in and registration).
 * Exposes window.LumoPasskeys.
 */
(function (global) {
  'use strict';

  function base64urlToBuffer(base64url) {
    var padding = '='.repeat((4 - (base64url.length % 4)) % 4);
    var base64 = (base64url + padding).replace(/-/g, '+').replace(/_/g, '/');
    var raw = atob(base64);
    var buffer = new ArrayBuffer(raw.length);
    var view = new Uint8Array(buffer);
    for (var i = 0; i < raw.length; i++) view[i] = raw.charCodeAt(i);
    return buffer;
  }

  function bufferToBase64url(buffer) {
    var bytes = new Uint8Array(buffer);
    var str = '';
    for (var i = 0; i < bytes.length; i++) str += String.fromCharCode(bytes[i]);
    return btoa(str).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
  }

  function preparePublicKeyCreationOptions(serverOptions) {
    var o = JSON.parse(JSON.stringify(serverOptions));
    o.challenge = base64urlToBuffer(o.challenge);
    if (o.user && o.user.id) o.user.id = base64urlToBuffer(o.user.id);
    if (o.excludeCredentials && o.excludeCredentials.length) {
      o.excludeCredentials = o.excludeCredentials.map(function (d) {
        return { type: d.type, id: base64urlToBuffer(d.id), transports: d.transports };
      });
    }
    return o;
  }

  function preparePublicKeyRequestOptions(serverOptions) {
    var o = JSON.parse(JSON.stringify(serverOptions));
    o.challenge = base64urlToBuffer(o.challenge);
    if (o.allowCredentials && o.allowCredentials.length) {
      o.allowCredentials = o.allowCredentials.map(function (d) {
        return { type: d.type, id: base64urlToBuffer(d.id), transports: d.transports };
      });
    }
    return o;
  }

  function registrationCredentialToJSON(cred) {
    var response = cred.response;
    var transports = typeof response.getTransports === 'function' ? response.getTransports() : undefined;
    return {
      id: cred.id,
      rawId: bufferToBase64url(cred.rawId),
      type: cred.type,
      response: {
        clientDataJSON: bufferToBase64url(response.clientDataJSON),
        attestationObject: bufferToBase64url(response.attestationObject),
        transports: transports,
      },
    };
  }

  function authenticationCredentialToJSON(cred) {
    var response = cred.response;
    return {
      id: cred.id,
      rawId: bufferToBase64url(cred.rawId),
      type: cred.type,
      response: {
        clientDataJSON: bufferToBase64url(response.clientDataJSON),
        authenticatorData: bufferToBase64url(response.authenticatorData),
        signature: bufferToBase64url(response.signature),
        userHandle: response.userHandle && response.userHandle.byteLength
          ? bufferToBase64url(response.userHandle)
          : null,
      },
    };
  }

  global.LumoPasskeys = {
    base64urlToBuffer: base64urlToBuffer,
    bufferToBase64url: bufferToBase64url,
    preparePublicKeyCreationOptions: preparePublicKeyCreationOptions,
    preparePublicKeyRequestOptions: preparePublicKeyRequestOptions,
    registrationCredentialToJSON: registrationCredentialToJSON,
    authenticationCredentialToJSON: authenticationCredentialToJSON,
    supported: function () {
      return !!(global.PublicKeyCredential && global.navigator && global.navigator.credentials);
    },
  };
})(typeof window !== 'undefined' ? window : this);
