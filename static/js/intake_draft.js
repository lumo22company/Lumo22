/**
 * Local draft for captions intake: restore after refresh, warn before leaving unsaved,
 * clear after successful submit. Keyed by intake token (lumo_intake_draft_v1_<token>).
 */
(function () {
  var PREFIX = 'lumo_intake_draft_v1_';
  var DEBOUNCE_MS = 450;
  var SCHEMA = 1;

  var token = '';
  var dirty = false;
  var saveTimer = null;
  var form = null;

  function storageKey() {
    return PREFIX + token;
  }

  function getToken() {
    var el = document.getElementById('intake_token');
    return el && el.value ? String(el.value).trim() : '';
  }

  function isEditable() {
    return document.body.getAttribute('data-intake-view-only') !== 'true';
  }

  function collectState() {
    if (!form) return null;
    var fields = {};
    var sel = form.querySelectorAll(
      'input:not([type="checkbox"]):not([type="radio"]):not([type="hidden"]), textarea, select'
    );
    for (var i = 0; i < sel.length; i++) {
      var el = sel[i];
      if (!el.id) continue;
      fields[el.id] = el.value;
    }
    var pl = document.getElementById('platform');
    if (pl) fields.platform = pl.value;

    var aud = [];
    [].forEach.call(form.querySelectorAll('input[name="audience_cb"]:checked'), function (c) {
      aud.push(c.value);
    });
    var vw = [];
    [].forEach.call(form.querySelectorAll('input[name="voice_words_cb"]:checked'), function (c) {
      vw.push(c.value);
    });

    var platformParts = [];
    [].forEach.call(form.querySelectorAll('.platform-btn.selected'), function (b) {
      var p = b.getAttribute('data-platform');
      if (p) platformParts.push(p);
    });
    if (!platformParts.length) {
      [].forEach.call(form.querySelectorAll('input[name="platform_cb"]:checked'), function (c) {
        platformParts.push(c.value);
      });
    }

    var inc = document.getElementById('include_hashtags');
    var incStories = document.getElementById('include_stories');
    var alignStories = document.getElementById('align_stories');
    var varyIgFb = document.getElementById('vary_ig_fb_caption_length');

    return {
      v: SCHEMA,
      ts: Date.now(),
      fields: fields,
      audience_cb: aud,
      voice_words_cb: vw,
      platform_selected: platformParts,
      include_hashtags: inc ? !!inc.checked : true,
      include_stories: incStories ? !!incStories.checked : false,
      align_stories: alignStories ? !!alignStories.checked : false,
      vary_ig_fb_caption_length: varyIgFb ? !!varyIgFb.checked : false,
    };
  }

  function applyCheckboxGroup(name, values) {
    if (!values || !values.length) return;
    var want = {};
    values.forEach(function (v) {
      want[v] = true;
    });
    form.querySelectorAll('input[name="' + name + '"]').forEach(function (cb) {
      cb.checked = !!want[cb.value];
    });
  }

  function applyPlatformButtons(selected) {
    var group = document.getElementById('platform-btn-group');
    var hidden = document.getElementById('platform');
    if (!hidden) return;
    if (!selected || !selected.length) return;
    if (group) {
      var btns = group.querySelectorAll('.platform-btn');
      var sel = {};
      selected.forEach(function (p) {
        sel[p] = true;
      });
      for (var bi = 0; bi < btns.length; bi++) {
        var btn = btns[bi];
        var v = btn.getAttribute('data-platform');
        btn.classList.toggle('selected', !!(v && sel[v]));
      }
      hidden.value = selected.join(', ');
    } else {
      hidden.value = selected.join(', ');
    }
  }

  function syncHiddenAggregates() {
    var audCk = form.querySelectorAll('input[name="audience_cb"]:checked');
    var aud = [].map.call(audCk, function (x) {
      return x.value;
    }).join(', ');
    var ao = document.getElementById('audience_other');
    if (ao && ao.value.trim()) aud = aud ? aud + ', ' + ao.value.trim() : ao.value.trim();
    var audEl = document.getElementById('audience');
    if (audEl) audEl.value = aud;

    var vwCk = form.querySelectorAll('input[name="voice_words_cb"]:checked');
    var vw = [].map.call(vwCk, function (x) {
      return x.value;
    }).join(', ');
    var vwo = document.getElementById('voice_words_other');
    if (vwo && vwo.value.trim()) vw = vw ? vw + ', ' + vwo.value.trim() : vwo.value.trim();
    var vwEl = document.getElementById('voice_words');
    if (vwEl) vwEl.value = vw;
  }

  function toggleDependents() {
    var bt = document.getElementById('business_type');
    var bto = document.getElementById('business_type_other');
    if (bt && bto) bto.style.display = bt.value === 'Other' ? 'block' : 'none';

    var goalSelect = document.getElementById('goal');
    var goalOtherWrap = document.getElementById('goal_other_wrap');
    if (goalSelect && goalOtherWrap) {
      goalOtherWrap.style.display = goalSelect.value === 'Other' ? 'block' : 'none';
    }

    var consumersCb = document.getElementById('audience_cb_consumers');
    var ageWrap = document.getElementById('consumer_age_wrap');
    if (consumersCb && ageWrap) {
      ageWrap.style.display = consumersCb.checked ? 'block' : 'none';
    }

    var wrap = document.getElementById('hashtag-range-wrap');
    var cb = document.getElementById('include_hashtags');
    if (wrap && cb) wrap.style.display = cb.checked ? '' : 'none';
  }

  function applyDraft(state) {
    if (!state || state.v !== SCHEMA || !state.fields) return false;
    var f = state.fields;
    Object.keys(f).forEach(function (id) {
      var el = document.getElementById(id);
      if (!el) return;
      if (id === 'intake_token') return;
      if (el.type === 'hidden' && id !== 'platform') return;
      if (el.tagName === 'SELECT' || el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
        el.value = f[id] == null ? '' : String(f[id]);
      }
    });
    if (state.audience_cb) applyCheckboxGroup('audience_cb', state.audience_cb);
    if (state.voice_words_cb) applyCheckboxGroup('voice_words_cb', state.voice_words_cb);
    if (state.platform_selected && state.platform_selected.length) {
      applyPlatformButtons(state.platform_selected);
    } else if (f.platform) {
      var parts = String(f.platform)
        .split(',')
        .map(function (s) {
          return s.trim();
        })
        .filter(Boolean);
      if (parts.length) applyPlatformButtons(parts);
    }
    var inc = document.getElementById('include_hashtags');
    if (inc && typeof state.include_hashtags === 'boolean') inc.checked = state.include_hashtags;
    var incStories = document.getElementById('include_stories');
    if (incStories && !incStories.disabled && typeof state.include_stories === 'boolean') {
      incStories.checked = state.include_stories;
    }
    var alignStories = document.getElementById('align_stories');
    if (alignStories && typeof state.align_stories === 'boolean') alignStories.checked = state.align_stories;
    var varyIgFb = document.getElementById('vary_ig_fb_caption_length');
    if (varyIgFb && typeof state.vary_ig_fb_caption_length === 'boolean') {
      varyIgFb.checked = state.vary_ig_fb_caption_length;
    }

    syncHiddenAggregates();
    toggleDependents();
    if (typeof window.lumoSyncVaryIgFbLengthOption === 'function') window.lumoSyncVaryIgFbLengthOption();
    return true;
  }

  function persistDraft() {
    if (!token || !form) return;
    try {
      var state = collectState();
      if (!state) return;
      localStorage.setItem(storageKey(), JSON.stringify(state));
    } catch (e) {
      /* quota / private mode */
    }
  }

  function scheduleSave() {
    dirty = true;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(persistDraft, DEBOUNCE_MS);
  }

  function showBanner() {
    var b = document.getElementById('intake-draft-banner');
    if (b) b.style.display = 'block';
  }

  function hideBanner() {
    var b = document.getElementById('intake-draft-banner');
    if (b) b.style.display = 'none';
  }

  function clearStorage() {
    if (!token) return;
    try {
      localStorage.removeItem(storageKey());
    } catch (e) {}
  }

  function markClean() {
    dirty = false;
    clearTimeout(saveTimer);
    clearStorage();
    hideBanner();
  }

  function tryRestore() {
    if (!token || !form) return;
    var raw;
    try {
      raw = localStorage.getItem(storageKey());
    } catch (e) {
      return;
    }
    if (!raw) return;
    var state;
    try {
      state = JSON.parse(raw);
    } catch (e) {
      return;
    }
    if (!state || state.v !== SCHEMA) return;
    if (applyDraft(state)) showBanner();
  }

  function bindEvents() {
    form.addEventListener(
      'input',
      function () {
        scheduleSave();
      },
      true
    );
    form.addEventListener(
      'change',
      function () {
        scheduleSave();
      },
      true
    );
    [].forEach.call(document.querySelectorAll('.platform-btn'), function (btn) {
      btn.addEventListener('click', function () {
        setTimeout(scheduleSave, 0);
      });
    });

    window.addEventListener('beforeunload', function (e) {
      if (!dirty) return;
      persistDraft();
      e.preventDefault();
      e.returnValue = '';
    });
  }

  function init() {
    if (!isEditable()) return;
    token = getToken();
    form = document.getElementById('captions-intake-form');
    if (!token || !form) return;

    function deferredRestore() {
      tryRestore();
    }

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function () {
        setTimeout(deferredRestore, 0);
      });
    } else {
      setTimeout(deferredRestore, 0);
    }

    bindEvents();

    window.intakeDraftMarkClean = markClean;
  }

  init();
})();
