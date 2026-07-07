(function () {
  "use strict";

  /* ---------- theme ---------- */
  window.toggleTheme = function () {
    var html = document.documentElement;
    var cur = html.getAttribute("data-theme") || "light";
    var next = cur === "dark" ? "light" : "dark";
    html.setAttribute("data-theme", next);
    localStorage.setItem("review_theme", next);
  };

  /* ---------- reviewer cookie ---------- */
  window.getReviewer = function () {
    var m = document.cookie.match(/review_reviewer=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  };
  function setReviewer(name) {
    if (!name) return;
    document.cookie =
      "review_reviewer=" +
      encodeURIComponent(name) +
      ";path=/;max-age=31536000;SameSite=Lax";
  }
  window.promptReviewer = function () {
    var cur = window.getReviewer();
    var name = prompt("Reviewer name:", cur);
    if (name && name.trim()) {
      setReviewer(name.trim());
      location.reload();
    }
  };
  (function showReviewer() {
    var el = document.getElementById("reviewer-name");
    var container = document.getElementById("reviewer-display");
    if (el && container) {
      var name = window.getReviewer();
      if (name) {
        el.textContent = name;
        el.style.color = "var(--text)";
        container.style.display = "";
      } else {
        container.style.display = "none";
      }
    }
  })();

  /* ---------- session list keyboard nav ---------- */
  var rows = [];
  function initSessionRows() {
    rows = Array.from(document.querySelectorAll(".session-row"));
    rows.forEach(function (r, i) {
      r.addEventListener("click", function () {
        setActiveRow(i);
        window.location = r.dataset.href;
      });
    });
  }
  function setActiveRow(idx) {
    var el = rows[idx];
    if (!el) return;
    rows.forEach(function (r) {
      r.classList.remove("active");
      r.style.background = "";
      r.style.color = "";
    });
    el.classList.add("active");
    el.style.background = "var(--accent)";
    el.style.color = "#fff";
  }
  initSessionRows();

  /* ---------- automatically add reviewer to every HTMX request ---------- */
  document.addEventListener("htmx:configRequest", function (e) {
    var reviewer = window.getReviewer();
    if (reviewer) {
      e.detail.parameters["reviewer"] = reviewer;
    }
  });

  /* ---------- reviewer check before saving status ---------- */
  document.addEventListener("htmx:confirm", function (e) {
    var btn = e.target.closest("#review-form button[title^='Shortcut']");
    if (btn && !window.getReviewer()) {
      e.preventDefault();
      window.promptReviewer();
    }
  });

  document.addEventListener("keydown", function (e) {
    /* ---------- 1-4 keyboard shortcuts (always work) ---------- */
    var statusMap = { "1": "unreviewed", "2": "accepted", "3": "flagged", "4": "excluded" };
    if (statusMap[e.key] && document.querySelector("#review-form")) {
      e.preventDefault();
      if (!window.getReviewer()) { window.promptReviewer(); return; }
      var sid = window.location.pathname.match(/\/session\/([^/]+)/);
      var dcn = window.location.pathname.match(/\/dcn\/([^/]+)/);
      if (sid && dcn) {
        var comment = document.querySelector('#review-form textarea[name="comment"]');
        var commentVal = comment ? comment.value : "";
        var url = "/api/dcn/" + encodeURIComponent(dcn[1]) + "/session/" + encodeURIComponent(sid[1]) +
                  "/review?status=" + statusMap[e.key] +
                  "&comment=" + encodeURIComponent(commentVal) +
                  "&reviewer=" + encodeURIComponent(window.getReviewer());
        fetch(url, { method: "POST" })
          .then(function (r) { return r.text(); })
          .then(function (html) {
            var target = document.getElementById("review-form");
            if (target) target.innerHTML = html;
          });
      }
      return;
    }

    /* ---------- 'p' opens first plot ---------- */
    if (e.key === "p" && document.querySelector("#lightbox") && !e.ctrlKey && !e.metaKey) {
      var plots = document.querySelectorAll(".plot-thumb");
      if (plots.length > 0 && document.getElementById("lightbox").style.display === "none") {
        e.preventDefault();
        currentPlots = Array.from(plots).map(function (el) { return el.src; });
        showPlot(0);
      }
    }

    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

    var active = document.querySelector(".session-row.active");
    var idx = rows.indexOf(active);

    if (e.key === "j" || e.key === "ArrowDown") {
      e.preventDefault();
      var next = idx < rows.length - 1 ? idx + 1 : 0;
      if (rows[next]) {
        rows[next].scrollIntoView({ block: "nearest" });
        setActiveRow(next);
      }
    }
    if (e.key === "k" || e.key === "ArrowUp") {
      e.preventDefault();
      var prev = idx > 0 ? idx - 1 : rows.length - 1;
      if (rows[prev]) {
        rows[prev].scrollIntoView({ block: "nearest" });
        setActiveRow(prev);
      }
    }
    if (e.key === "Enter" && idx > -1 && rows[idx]) {
      window.location = rows[idx].dataset.href;
    }
  });

  /* ---------- filter session table ---------- */
  var filterInput = document.getElementById("session-filter");
  if (filterInput) {
    filterInput.addEventListener("input", function () {
      var q = this.value.toLowerCase();
      document.querySelectorAll(".session-row").forEach(function (r) {
        var text = r.textContent.toLowerCase();
        r.style.display = text.indexOf(q) > -1 ? "" : "none";
      });
    });
  }

  /* ---------- plot lightbox ---------- */
  (function () {
    var div = document.createElement("div");
    div.id = "lightbox";
    div.style.cssText =
      "position:fixed;inset:0;background:rgba(0,0,0,0.85);z-index:9999;display:none;align-items:center;justify-content:center";
    var img = document.createElement("img");
    img.style.cssText =
      "max-width:92vw;max-height:85vh;object-fit:contain;border-radius:4px";
    img.id = "lightbox-img";
    div.appendChild(img);
    var info = document.createElement("div");
    info.id = "lightbox-info";
    info.style.cssText =
      "position:absolute;top:0;left:0;right:0;background:rgba(0,0,0,0.6);color:#fff;font-size:0.9rem;padding:8px 16px;text-align:center;line-height:1.4";
    info.textContent = "";
    div.appendChild(info);
    var navHint = document.createElement("div");
    navHint.id = "lightbox-navhint";
    navHint.style.cssText =
      "position:absolute;bottom:1.5rem;left:50%;transform:translateX(-50%);color:rgba(255,255,255,0.4);font-size:0.75rem";
    navHint.textContent = "\u2190 \u2192 or h/l to navigate  \u00B7 Esc to close";
    div.appendChild(navHint);
    var closeBtn = document.createElement("div");
    closeBtn.textContent = "\u00D7";
    closeBtn.style.cssText =
      "position:absolute;top:3rem;right:1.5rem;font-size:2rem;color:#fff;cursor:pointer;opacity:0.7";
    div.appendChild(closeBtn);
    closeBtn.onclick = function () { div.style.display = "none"; };
    div.onclick = function (e) { if (e.target === div) div.style.display = "none"; };
    document.body.appendChild(div);
  })();
  var lightbox = document.getElementById("lightbox");
  var lightboxImg = document.getElementById("lightbox-img");
  var currentPlots = [];

  function showPlot(idx) {
    if (idx < 0 || idx >= currentPlots.length) return;
    var thumb = document.querySelectorAll(".plot-thumb")[idx];
    lightboxImg.src = currentPlots[idx];
    lightbox.style.display = "flex";
    lightbox._idx = idx;
    var info = document.getElementById("lightbox-info");
    if (info) {
      var st = thumb ? thumb.dataset.stimulus || "" : "";
      var pg = thumb ? thumb.dataset.page || "" : "";
      info.innerHTML =
        "<span style='float:left'>" + (idx + 1) + "/" + currentPlots.length + "</span>" +
        "<span style='display:inline-block;max-width:50%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap'>" + st + "</span>" +
        "<span style='float:right'>" + pg + "</span>";
    }
  }

  document.addEventListener("click", function (e) {
    var thumb = e.target.closest(".plot-thumb");
    if (!thumb) return;
    currentPlots = Array.from(document.querySelectorAll(".plot-thumb")).map(function (el) { return el.src; });
    var idx = currentPlots.indexOf(thumb.src);
    showPlot(idx >= 0 ? idx : 0);
  });

  document.addEventListener("keydown", function (e) {
    if (lightbox.style.display === "none") return;
    if (e.key === "Escape") { lightbox.style.display = "none"; e.preventDefault(); }
    if ((e.key === "ArrowRight" || e.key === "l") && currentPlots.length > 0) {
      var i = (lightbox._idx || 0) + 1;
      if (i >= currentPlots.length) i = 0;
      showPlot(i); e.preventDefault();
    }
    if ((e.key === "ArrowLeft" || e.key === "h") && currentPlots.length > 0) {
      var i = (lightbox._idx || 0) - 1;
      if (i < 0) i = currentPlots.length - 1;
      showPlot(i); e.preventDefault();
    }
  });

  /* ---------- Ctrl+Enter for comment save ---------- */
  document.addEventListener("keydown", function (e) {
    if (e.target.tagName === "TEXTAREA" && e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      var submitBtn = e.target.closest("form").querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.click();
    }
  });

  /* ---------- sort session table ---------- */
  document.querySelectorAll("th[data-sort]").forEach(function (th) {
    th.addEventListener("click", function () {
      var key = th.dataset.sort;
      var dir = th.dataset.dir === "asc" ? "desc" : "asc";
      th.dataset.dir = dir;
      var tbody = th.closest("table").querySelector("tbody");
      var rowsArr = Array.from(tbody.querySelectorAll("tr"));
      rowsArr.sort(function (a, b) {
        var av = a.querySelector("td[data-" + key + "]")?.dataset[key] || "";
        var bv = b.querySelector("td[data-" + key + "]")?.dataset[key] || "";
        if (!isNaN(av)) { av = parseFloat(av); bv = parseFloat(bv); }
        return av < bv ? -1 : av > bv ? 1 : 0;
      });
      if (dir === "desc") rowsArr.reverse();
      rowsArr.forEach(function (r) { tbody.appendChild(r); });
    });
  });
})();
