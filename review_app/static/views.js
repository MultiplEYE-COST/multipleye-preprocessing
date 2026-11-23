(function () {
  "use strict";

  var content = document.getElementById("view-content");
  if (!content) return;

  var isGlobal = window.location.pathname === "/views" || window.location.pathname.indexOf("/views/view/") === 0;
  var dcnMatch = window.location.pathname.match(/^\/dcn\/([^/]+)/);
  if (!isGlobal && !dcnMatch) return;
  var dcn = dcnMatch ? decodeURIComponent(dcnMatch[1]) : "";
  var requestId = 0;
  var controller = null;
  var searchTimer = null;

  function currentView() {
    var match = window.location.pathname.match(isGlobal ? /\/views\/view\/([^/]+)/ : /\/view\/([^/]+)/);
    return match ? decodeURIComponent(match[1]) : "dataset";
  }

  function currentParams() {
    return new URLSearchParams(window.location.search);
  }

  function buildUrl(view, overrides) {
    var params = currentParams();
    var group = overrides.group !== undefined ? overrides.group : params.get("group");
    var q = overrides.q !== undefined ? overrides.q : (params.get("q") || "");
    var page = overrides.page !== undefined ? overrides.page : (params.get("page") || "");
    var filters = overrides.filters !== undefined ? overrides.filters : params.getAll("f");

    var next = new URLSearchParams();
    if (group) next.set("group", group);
    if (q) next.set("q", q);
    filters.forEach(function (f) { if (f) next.append("f", f); });
    if (page && String(page) !== "1") next.set("page", String(page));

    var base;
    if (isGlobal) {
      base = view === "dataset" ? "/views" : "/views/view/" + encodeURIComponent(view);
    } else {
      base = view === "dataset" ? "/dcn/" + encodeURIComponent(dcn) : "/dcn/" + encodeURIComponent(dcn) + "/view/" + encodeURIComponent(view);
    }
    var suffix = next.toString();
    return base + (suffix ? "?" + suffix : "");
  }

  function tableUrl(url) {
    var parsed = new URL(url, window.location.origin);
    if (isGlobal) {
      var globalMatch = parsed.pathname.match(/^\/views(?:\/view\/([^/]+))?/);
      if (!globalMatch) return null;
      var globalView = globalMatch[1] || "dataset";
      var globalParams = parsed.searchParams.toString();
      return "/views/view/" + encodeURIComponent(decodeURIComponent(globalView)) + "/table" + (globalParams ? "?" + globalParams : "");
    }
    var match = parsed.pathname.match(/^\/dcn\/([^/]+)(?:\/view\/([^/]+))?/);
    if (!match) return null;
    var targetView = match[2] || "dataset";
    var params = parsed.searchParams.toString();
    return "/dcn/" + encodeURIComponent(decodeURIComponent(match[1])) + "/view/" + encodeURIComponent(decodeURIComponent(targetView)) + "/table" + (params ? "?" + params : "");
  }

  var filterMeta = {};

  function readFilterMeta() {
    var node = document.getElementById("filter-field-meta");
    if (!node) {
      filterMeta = {};
      return;
    }
    try {
      filterMeta = JSON.parse(node.textContent || "{}");
    } catch (error) {
      filterMeta = {};
    }
  }

  function filterValueControl(meta, value, preserve) {
    var wrap = document.getElementById("filter-value-wrap");
    if (!wrap) return;
    var old = document.getElementById("filter-value");
    if (preserve !== false && old) {
      value = old.value;
    } else if (preserve === false) {
      value = "";
    }
    wrap.innerHTML = "";
    var numeric = meta && (meta.type === "number" || meta.type === "integer");
    var options = (meta && meta.values) || [];
    if (options.length) {
      var select = document.createElement("select");
      select.id = "filter-value";
      select.name = "value";
      options.forEach(function (option) {
        var item = document.createElement("option");
        item.value = option.value;
        item.textContent = option.label;
        if (value !== undefined && String(option.value) === String(value)) item.selected = true;
        select.appendChild(item);
      });
      wrap.appendChild(select);
    } else {
      var input = document.createElement("input");
      input.id = "filter-value";
      input.name = "value";
      input.className = "search";
      input.style.margin = "0";
      input.type = numeric ? "number" : "text";
      if (numeric) input.step = "any";
      input.placeholder = "Value";
      if (value !== undefined) input.value = value;
      wrap.appendChild(input);
    }
  }

  function syncFilterControls(resetValue) {
    var fieldSelect = document.getElementById("filter-variable");
    var operatorSelect = document.getElementById("filter-operator");
    if (!fieldSelect || !operatorSelect) return;
    var meta = filterMeta[fieldSelect.value] || {};
    operatorSelect.innerHTML = "";
    (meta.operators || []).forEach(function (operator) {
      var option = document.createElement("option");
      option.value = operator.value;
      option.textContent = operator.label;
      operatorSelect.appendChild(option);
    });
    filterValueControl(meta, undefined, resetValue !== true);
  }

  function initFilterForm() {
    readFilterMeta();
    if (Object.keys(filterMeta).length) syncFilterControls();
  }

  function setActiveTab(view) {
    document.querySelectorAll(".view-tab").forEach(function (tab) {
      tab.classList.toggle("active", tab.dataset.view === view);
    });
  }

  function updateTabHrefs(view) {
    document.querySelectorAll(".view-tab").forEach(function (tab) {
      tab.setAttribute("href", buildUrl(tab.dataset.view, {page: 1}));
    });
  }

  function load(url, push) {
    var parsed = new URL(url, window.location.origin);
    var viewMatch = parsed.pathname.match(isGlobal ? /\/views\/view\/([^/]+)/ : /\/view\/([^/]+)/);
    var targetView = viewMatch ? decodeURIComponent(viewMatch[1]) : "dataset";
    var target = tableUrl(url);
    if (!target) return;

    if (controller) controller.abort();
    controller = new AbortController();
    var thisRequest = ++requestId;

    var active = document.activeElement;
    var searchWasFocused = active && active.id === "view-search";
    var selectionStart = searchWasFocused ? active.selectionStart : null;
    var selectionEnd = searchWasFocused ? active.selectionEnd : null;

    content.classList.add("loading");
    fetch(target, {headers: {"Accept": "text/html"}, signal: controller.signal})
      .then(function (response) {
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.text();
      })
      .then(function (html) {
        if (thisRequest !== requestId) return;
        content.innerHTML = html;
        content.classList.remove("loading");
        initFilterForm();
        setActiveTab(targetView);
        if (push) {
          history.pushState({}, "", url);
        } else {
          history.replaceState({}, "", url);
        }
        updateTabHrefs(targetView);
        if (searchWasFocused) {
          var input = document.getElementById("view-search");
          if (input) {
            input.focus();
            if (selectionStart !== null) input.setSelectionRange(selectionStart, selectionEnd);
          }
        }
      })
      .catch(function (error) {
        if (error && error.name === "AbortError") return;
        content.classList.remove("loading");
        window.location.href = url;
      });
  }

  function clearSearchTimer() {
    if (searchTimer) {
      window.clearTimeout(searchTimer);
      searchTimer = null;
    }
  }

  document.addEventListener("click", function (event) {
    var tab = event.target.closest(".view-tab");
    if (tab) {
      event.preventDefault();
      clearSearchTimer();
      var view = tab.dataset.view;
      var group = currentParams().get("group");
      var q = currentParams().get("q") || "";
      load(buildUrl(view, {group: group, q: q, page: 1}), true);
      return;
    }

    var pageLink = event.target.closest("[data-page]");
    if (pageLink) {
      event.preventDefault();
      clearSearchTimer();
      load(pageLink.getAttribute("href"), true);
      return;
    }

    var row = event.target.closest("tr.clickable");
    if (row && row.dataset.href) {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      var selection = window.getSelection();
      if (selection && selection.toString()) return;
      window.location.href = row.dataset.href;
      return;
    }

    if (event.target.closest(".clear-filters")) {
      event.preventDefault();
      clearSearchTimer();
      load(buildUrl(currentView(), {filters: [], page: 1}), true);
      return;
    }

    var remove = event.target.closest(".filter-chip-remove");
    if (remove) {
      event.preventDefault();
      clearSearchTimer();
      var chip = remove.closest(".filter-chip");
      var filters = currentParams().getAll("f").filter(function (f) {
        return f !== chip.dataset.filter;
      });
      load(buildUrl(currentView(), {filters: filters, page: 1}), true);
    }
  });

  document.addEventListener("change", function (event) {
    if (event.target && event.target.id === "filter-variable") {
      syncFilterControls(true);
      return;
    }
    if (event.target && event.target.id === "group-select") {
      clearSearchTimer();
      load(buildUrl(currentView(), {group: event.target.value, page: 1}), true);
    }
  });

  document.addEventListener("input", function (event) {
    if (!event.target || event.target.id !== "view-search") return;
    var value = event.target.value;
    clearSearchTimer();
    searchTimer = window.setTimeout(function () {
      load(buildUrl(currentView(), {q: value, page: 1}), false);
    }, 250);
  });

  document.addEventListener("submit", function (event) {
    if (!event.target || event.target.id !== "filter-form") return;
    event.preventDefault();
    clearSearchTimer();
    var variable = document.getElementById("filter-variable").value;
    var operator = document.getElementById("filter-operator").value;
    var value = document.getElementById("filter-value").value;
    if (!variable || !value) return;
    var filters = currentParams().getAll("f").filter(Boolean);
    filters.push(variable + ":" + operator + ":" + value);
    load(buildUrl(currentView(), {filters: filters, page: 1}), true);
  });

  window.addEventListener("popstate", function () {
    clearSearchTimer();
    load(window.location.href, false);
  });

  initFilterForm();
  updateTabHrefs(currentView());
})();
