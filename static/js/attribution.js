/**
 * First-touch campaign attribution.
 *
 * A campaign click lands with ?utm_source=... on it, but the visitor then navigates internally
 * (captions → checkout → Stripe) and those params are gone by the time they convert. This stashes
 * the tag from the landing URL in sessionStorage so the sample signup and the Stripe checkout link
 * can attach it, which is what lets caption_orders.source answer "did that campaign convert?".
 *
 * First touch wins: a visitor who arrives from an ad and later reloads a clean URL stays attributed
 * to the ad. Sessions are per-tab, so this never bleeds between visits.
 *
 * Exposes window.lumoAttribution() -> string ('' when unknown).
 */
(function () {
  var KEY = 'lumo_attribution';
  var MAX_LEN = 120;

  // Storage and the server both clean this; it ends up in a DB column and in reports.
  function clean(value) {
    return (value || '').trim().replace(/[^\w .:/@+-]/g, '').slice(0, MAX_LEN);
  }

  function fromUrl() {
    var params;
    try {
      params = new URLSearchParams(window.location.search);
    } catch (e) {
      return '';
    }
    // An explicit ?source= wins — it is what we generate ourselves when re-linking internally.
    var explicit = clean(params.get('source'));
    if (explicit) return explicit;
    var utmSource = clean(params.get('utm_source'));
    var utmMedium = clean(params.get('utm_medium'));
    var utmCampaign = clean(params.get('utm_campaign'));
    if (utmSource || utmCampaign) {
      return clean([utmSource || 'unknown', utmMedium || '-', utmCampaign || '-'].join(':'));
    }
    // Referral codes already have their own plumbing; record them as a source too so the
    // report shows one attribution column rather than two half-pictures.
    var ref = clean(params.get('ref'));
    if (ref) return clean('ref:' + ref.toUpperCase());
    return '';
  }

  function read() {
    try {
      return clean(sessionStorage.getItem(KEY) || '');
    } catch (e) {
      return '';
    }
  }

  function capture() {
    var stored = read();
    if (stored) return stored;
    var found = fromUrl();
    if (!found) return '';
    try {
      sessionStorage.setItem(KEY, found);
    } catch (e) {}
    return found;
  }

  capture();

  window.lumoAttribution = function () {
    return read() || fromUrl();
  };
})();
