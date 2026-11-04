/*
 * PostHog page views for signed-in pages (2026-11-04, decision 176; witus plan 26).
 *
 * Loaded only when the base template printed #posthog-config, which it does on a signed-in page
 * of the Production deployment with a key set (`pages.context_processors.posthog`). Public pages
 * never load this file (decision 151).
 *
 * The line after "Official loader" is PostHog's HTML snippet, copied byte for byte from
 * https://posthog.com/docs/libraries/js (read November 4, 2026). It defines a stand-in
 * `window.posthog` that queues calls and adds a script tag for `<api_host>/static/array.js`. With
 * api_host "/ingest" that is /ingest/static/array.js on this site, which vercel.json rewrites to
 * PostHog's assets host; events go to /ingest/..., rewritten to us.i.posthog.com.
 *
 * The init options are the ecosystem's (plan 26), plus everything else that could send more than
 * a page view switched off by name (option names from posthog-js 1.445.5's PostHogConfig type):
 * - autocapture, rage clicks, dead clicks, heatmaps, exceptions, web vitals: off. Nothing on a
 *   page is recorded but the one page view below.
 * - disable_session_recording: no replay, ever, without its own decision and consent.
 * - persistence "memory": no cookie, no localStorage, so no consent banner; every page load counts
 *   as a new visitor, so read "users" as visits.
 * - person_profiles "never" and no identify call: anonymous only, no cross-app identity (plan 26
 *   decision 7). advanced_disable_flags: no /flags request, since no flag is used.
 * - surveys, product tours, web experiments and extra scripts (disable_external_dependency_loading):
 *   off. save_referrer off.
 * - capture_pageview false: the one $pageview is sent by hand in `loaded`, with the scrubbed path.
 * - before_send: the last word. It drops every event that is not a $pageview, removes the page
 *   title (it can hold an account name), and rewrites every URL, path and referrer property to
 *   the scrubbed path, so the address bar's ids, symbols and query never leave the browser.
 *
 * Every event carries `app: "invest"` through register(), the label that keeps this app's events
 * apart in the shared project.
 */
(function () {
  "use strict";

  var element = document.getElementById("posthog-config");
  if (!element) {
    return;
  }
  var config;
  try {
    config = JSON.parse(element.textContent || "");
  } catch (error) {
    return;
  }
  if (!config || !config.key || !config.path) {
    return;
  }

  var page = window.location.origin + config.path;
  var rawPath = window.location.pathname;

  function referrerOrigin(value) {
    if (value === "$direct") {
      return value;
    }
    try {
      return new URL(value).origin + "/";
    } catch (error) {
      return "$direct";
    }
  }

  function clean(properties) {
    if (!properties || typeof properties !== "object") {
      return;
    }
    Object.keys(properties).forEach(function (key) {
      var name = key.toLowerCase();
      var value = properties[key];
      if (name === "title" || name === "$title") {
        delete properties[key];
        return;
      }
      if (typeof value !== "string" || name.indexOf("referring_domain") !== -1) {
        return;
      }
      if (name.indexOf("referrer") !== -1) {
        properties[key] = referrerOrigin(value);
      } else if (name.indexOf("pathname") !== -1) {
        properties[key] = config.path;
      } else if (name.indexOf("url") !== -1 || name.indexOf("href") !== -1) {
        properties[key] = page;
      } else if (rawPath !== "/" && value.indexOf(rawPath) !== -1) {
        properties[key] = value.split(rawPath).join(config.path);
      }
    });
  }

  function beforeSend(event) {
    if (!event || event.event !== "$pageview") {
      return null;
    }
    clean(event.properties);
    clean(event.$set);
    clean(event.$set_once);
    return event;
  }

  // Official loader (PostHog's HTML snippet, unchanged):
  !function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host.replace(".i.posthog.com","-assets.i.posthog.com")+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],Object.defineProperty(u,"toString",{configurable:!0,enumerable:!0,writable:!0,value:function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e}}),Object.defineProperty(u.people,"toString",{configurable:!0,enumerable:!0,writable:!0,value:function(){return u.toString(1)+".people (stub)"}}),o="init capture register register_once register_for_session unregister unregister_for_session getFeatureFlag getFeatureFlagResult isFeatureEnabled reloadFeatureFlags updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures on onFeatureFlags onSessionId getSurveys getActiveMatchingSurveys renderSurvey canRenderSurvey getNextSurveyStep identify setPersonProperties group resetGroups setPersonPropertiesForFlags resetPersonPropertiesForFlags setGroupPropertiesForFlags resetGroupPropertiesForFlags reset get_distinct_id getGroups get_session_id get_session_replay_url alias set_config startSessionRecording stopSessionRecording sessionRecordingStarted captureException loadToolbar get_property getSessionProperty createPersonProfile opt_in_capturing opt_out_capturing has_opted_in_capturing has_opted_out_capturing clear_opt_in_out_capturing debug".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);

  window.posthog.init(config.key, {
    api_host: config.api_host,
    ui_host: config.ui_host,
    autocapture: false,
    capture_pageview: false,
    capture_pageleave: false,
    disable_session_recording: true,
    persistence: "memory",
    person_profiles: "never",
    advanced_disable_flags: true,
    rageclick: false,
    capture_dead_clicks: false,
    capture_heatmaps: false,
    capture_exceptions: false,
    capture_performance: false,
    disable_surveys: true,
    disable_product_tours: true,
    disable_web_experiments: true,
    disable_external_dependency_loading: true,
    save_referrer: false,
    before_send: beforeSend,
    loaded: function (ph) {
      ph.register({ app: config.app });
      ph.capture("$pageview", { $current_url: page, $pathname: config.path });
    },
  });
})();
