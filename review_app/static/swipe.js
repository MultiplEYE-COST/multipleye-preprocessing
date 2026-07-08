(function () {
  "use strict";

  var sessions = [];
  var idx = 0;
  var history = [];
  var plotIdx = {};
  var animating = false;

  /* cached DOM refs */
  var card = document.getElementById("swipe-card");
  var content = document.getElementById("card-content");
  var noMore = document.getElementById("no-more-cards");

  /* image element and caption container refs for fast swap (no re-render) */
  var imgEl = null;
  var captionEl = null;
  var plotNavEl = null;

  /* ---- helpers ---- */

  function dcnName() {
    var m = window.location.pathname.match(/\/dcn\/([^/]+)/);
    return m ? m[1] : null;
  }

  function api(path) {
    var dcn = dcnName();
    if (!dcn) return "";
    return "/api/dcn/" + encodeURIComponent(dcn) + path;
  }

  /* ---- preload images (next few plots for current session) ---- */
  var preloadCache = {};

  function preloadPlots(s, centerIdx) {
    if (!s || !s.plots) return;
    var ids = [centerIdx];
    if (centerIdx + 1 < s.plots.length) ids.push(centerIdx + 1);
    if (centerIdx + 2 < s.plots.length) ids.push(centerIdx + 2);
    if (centerIdx - 1 >= 0) ids.push(centerIdx - 1);
    ids.forEach(function (i) {
      var url = s.plots[i].url;
      if (!preloadCache[url]) {
        preloadCache[url] = true;
        var img = new Image();
        img.src = url;
      }
    });
  }

  /* ---- init from embedded page data ---- */

  function initFromData() {
    if (!window.__SWIPE_SESSIONS__ || !window.__SWIPE_SESSIONS__.length) {
      content.innerHTML =
        '<div class="swipe-loading" style="color:var(--text-secondary)">' +
        "<p>No sessions available.</p>" +
        "</div>";
      return;
    }
    sessions = window.__SWIPE_SESSIONS__;
    idx = 0;
    history = [];
    plotIdx = {};
    sessions.forEach(function (s) { plotIdx[s.sid] = 0; });
    showCard();
    updateStats(window.__SWIPE_STATS__);
  }

  function showCard() {
    if (idx >= sessions.length) {
      content.style.display = "none";
      noMore.style.display = "";
      return;
    }
    noMore.style.display = "none";
    content.style.display = "";
    renderCard(sessions[idx]);
  }

  /* ---- render ---- */

  function renderCard(s) {
    currentSid = s.sid;
    var plots = s.plots || [];
    var pi = plotIdx[s.sid] || 0;
    if (pi >= plots.length) pi = 0;
    var currentPlot = plots.length > 0 ? plots[pi] : null;

    /* badges */
    var typeBadge = "";
    if (s.type_of_issue) {
      var typeLabels = { calibration_validation: "Cal-/Validation", data_loss: "Data loss", incomplete: "Incomplete", see_comment: "See comment" };
      typeBadge = '<span class="badge badge-issue">' + (typeLabels[s.type_of_issue] || s.type_of_issue) + "</span>";
    }
    var reproBadge = s.needs_reprocessing ? '<span class="pill" style="background:#eab308;color:#fff;border:none;font-size:0.78rem">needs reprocessing</span>' : "";
    var pilotBadge = s.is_pilot ? '<span class="badge badge-warn">pilot</span> ' : "";
    var statusBadge = "";
    var bc = { unreviewed: "badge-unreviewed", accepted: "badge-pass", flagged: "badge-fail", excluded: "badge-warn" };
    if (s.review_status && s.review_status !== "unreviewed") {
      statusBadge = '<span class="badge ' + (bc[s.review_status] || "badge-unreviewed") + '">' + s.review_status + "</span> ";
    }

    /* flagged checks with threshold */
    var flaggedHtml = "";
    if (s.flagged_checks && s.flagged_checks.length > 0) {
      flaggedHtml = '<div style="margin-top:0.5rem"><strong style="font-size:0.8rem;color:#ef4444"><i class="fa-solid fa-flag" style="margin-right:4px"></i>Red flags</strong>';
      s.flagged_checks.forEach(function (f) {
        var cls = f.status === "fail" ? "#ef4444" : "#eab308";
        var thresh = f.threshold ? " (threshold: " + f.threshold + ")" : "";
        flaggedHtml += '<div class="flag-item"><span style="color:' + cls + '">\u25CF</span> ' + f.label + ": " + f.value + thresh + "</div>";
      });
      flaggedHtml += "</div>";
    }

    /* plot caption */
    var plotCaption = "";
    if (currentPlot) {
      var capParts = [currentPlot.stimulus];
      if (currentPlot.page) capParts.push(currentPlot.page);
      if (currentPlot.activity) capParts.push(currentPlot.activity);
      plotCaption = capParts.join(" \u2014 ");
    }

    /* plot nav */
    var plotNav = "";
    if (plots.length > 1) {
      plotNav =
        '<div class="swipe-plot-nav">' +
        '<button onclick="window._swipePrevPlot()" title="Previous (A)">&#9664;</button>' +
        "<span>" + (pi + 1) + "/" + plots.length + "</span>" +
        '<button onclick="window._swipeNextPlot()" title="Next (D)">&#9654;</button>' +
        "</div>";
    }

    /* Tinder overlays */
    var overlayHtml =
      '<div class="swipe-overlay overlay-keep"><span>KEEP</span></div>' +
      '<div class="swipe-overlay overlay-flag"><span>FLAG</span></div>';

    /* Build full card on first render */
    content.innerHTML =
      overlayHtml +
      (currentPlot
        ? '<img class="swipe-card-image" id="swipe-img" src="' + currentPlot.url + '" alt="Scanpath" loading="lazy">'
        : '<div class="swipe-card-image" id="swipe-img" style="display:flex;align-items:center;justify-content:center;color:#64748b;font-size:0.9rem">No scanpath plots</div>') +
      plotNav +
      (plotCaption ? '<div class="swipe-plot-caption" id="swipe-caption">' + plotCaption + "</div>" : '<div class="swipe-plot-caption" id="swipe-caption"></div>') +
      '<div class="swipe-card-info" id="swipe-info">' +
      "<h2>" + s.sid + "</h2>" +
      '<div class="subtitle">' +
      "PID " + s.pid + " &middot; " +
      (s.language || "") +
      (s.country ? ", " + s.country : "") +
      (s.language || s.country ? " &middot; " : "") +
      "Cal: " + s.num_calibrations + " &middot; " +
      "Val: " + s.num_validations +
      "</div>" +
      '<div class="subtitle" style="margin-bottom:0.5rem">' +
      pilotBadge + statusBadge + reproBadge + " " + typeBadge +
      "</div>" +
      flaggedHtml +
      "</div>" +
      '<div class="swipe-actions">' +
      '<button class="btn-flag" onclick="window._swipeJudge(\'flag\')">&#10005; Flag <span class="kbd">\u2190</span></button>' +
      '<button class="btn-skip" onclick="window._swipeJudge(\'skip\')">&#9654; Skip <span class="kbd">\u2193</span></button>' +
      '<button class="btn-keep" onclick="window._swipeJudge(\'keep\')">&#10003; Keep <span class="kbd">\u2192</span></button>' +
      "</div>" +
      '<div class="swipe-undo-hint"><button onclick="window._swipeUndo()">\u21A9 Undo <span class="kbd">\u2191</span></button></div>';

    /* cache refs for fast plot swap */
    imgEl = document.getElementById("swipe-img");
    captionEl = document.getElementById("swipe-caption");

    card.className = "swipe-card";

    /* preload adjacent */
    preloadPlots(s, pi);
  }

  /* ---- fast plot swap (no re-render) ---- */
  function _updatePlot(s, pi) {
    var plots = s.plots || [];
    if (plots.length === 0) return;
    var p = plots[pi];
    if (!p) return;
    if (imgEl) {
      if (imgEl.tagName === "IMG") {
        imgEl.src = p.url;
      } else {
        /* replace placeholder div with img */
        var newImg = document.createElement("img");
        newImg.className = "swipe-card-image";
        newImg.id = "swipe-img";
        newImg.src = p.url;
        newImg.alt = "Scanpath";
        newImg.loading = "lazy";
        imgEl.parentNode.replaceChild(newImg, imgEl);
        imgEl = newImg;
      }
    }
    var capParts = [p.stimulus];
    if (p.page) capParts.push(p.page);
    if (p.activity) capParts.push(p.activity);
    if (captionEl) captionEl.textContent = capParts.join(" \u2014 ");

    /* update nav counter */
    var navSpans = card.querySelectorAll(".swipe-plot-nav span");
    if (navSpans.length > 0) {
      navSpans[0].textContent = (pi + 1) + "/" + plots.length;
    }

    preloadPlots(s, pi);
  }

  /* ---- API ---- */

  function judge(sid, judgment) {
    fetch(api("/swipe/judge?sid=" + encodeURIComponent(sid) + "&judgment=" + encodeURIComponent(judgment)),
      { method: "POST" }
    ).then(function (r) { return r.json(); }).then(function (data) {
      sessions[idx].judgment = judgment;
      updateStats(data.stats);
    });
  }

  function undo(sid) {
    fetch(api("/swipe/undo?sid=" + encodeURIComponent(sid)),
      { method: "POST" }
    ).then(function (r) { return r.json(); }).then(function (data) {
      sessions[idx].judgment = undefined;
      updateStats(data.stats);
    });
  }

  function updateStats(stats) {
    if (!stats) return;
    var j = document.getElementById("stat-judged");
    var k = document.getElementById("stat-keep");
    var f = document.getElementById("stat-flag");
    var sk = document.getElementById("stat-skip");
    var pb = document.getElementById("progress-fill");
    if (j) j.textContent = stats.judged + " / " + stats.total;
    if (k) k.textContent = stats.keep;
    if (f) f.textContent = stats.flag;
    if (sk) sk.textContent = stats.skip;
    if (pb) pb.style.width = stats.progress_pct + "%";
  }

  /* ---- animation ---- */

  function animateAndNext(dir) {
    if (animating) return;
    if (!sessions[idx]) return;
    card.classList.remove("swiping-right", "swiping-left", "swiping-up", "show-overlay-keep", "show-overlay-flag");
    void card.offsetWidth;
    if (dir === "right") { card.classList.add("swiping-right", "show-overlay-keep"); }
    else if (dir === "left") { card.classList.add("swiping-left", "show-overlay-flag"); }
    else if (dir === "up") { card.classList.add("swiping-up"); }
    animating = true;
    setTimeout(function () {
      animating = false;
      card.classList.remove("show-overlay-keep", "show-overlay-flag");
      idx++;
      showCard();
    }, 300);
  }

  /* ---- exposed actions ---- */

  window._swipeJudge = function (judgment) {
    if (!sessions[idx]) return;
    var sid = sessions[idx].sid;
    var dir = judgment === "keep" ? "right" : judgment === "flag" ? "left" : "up";
    history.push(idx);
    judge(sid, judgment);
    animateAndNext(dir);
  };

  window._swipeUndo = function () {
    if (idx <= 0 && history.length === 0) return;
    var prev = history.pop();
    if (prev === undefined || prev === null) {
      if (idx > 0) prev = idx - 1;
      else return;
    }
    var sid = sessions[prev].sid;
    undo(sid);
    idx = prev;
    showCard();
  };

  window._swipePrevPlot = function () {
    var s = sessions[idx];
    if (!s || !s.plots || s.plots.length === 0) return;
    plotIdx[s.sid] = (plotIdx[s.sid] || 0) - 1;
    if (plotIdx[s.sid] < 0) plotIdx[s.sid] = s.plots.length - 1;
    _updatePlot(s, plotIdx[s.sid]);
  };

  window._swipeNextPlot = function () {
    var s = sessions[idx];
    if (!s || !s.plots || s.plots.length === 0) return;
    plotIdx[s.sid] = (plotIdx[s.sid] || 0) + 1;
    if (plotIdx[s.sid] >= s.plots.length) plotIdx[s.sid] = 0;
    _updatePlot(s, plotIdx[s.sid]);
  };

  /* ---- keyboard ---- */

  document.addEventListener("keydown", function (e) {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
    if (!document.getElementById("swipe-card")) return;
    if (e.key === "ArrowLeft") { e.preventDefault(); window._swipeJudge("flag"); }
    else if (e.key === "ArrowRight") { e.preventDefault(); window._swipeJudge("keep"); }
    else if (e.key === "ArrowDown") { e.preventDefault(); window._swipeJudge("skip"); }
    else if (e.key === "ArrowUp") { e.preventDefault(); window._swipeUndo(); }
    else if (e.key === "a" || e.key === "A") { e.preventDefault(); window._swipePrevPlot(); }
    else if (e.key === "d" || e.key === "D") { e.preventDefault(); window._swipeNextPlot(); }
  });

  initFromData();
})();
