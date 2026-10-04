/* Progressive enhancement only: every page is complete without this file. */
(function () {
  "use strict";
  var root = document.documentElement;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function store(key, value) { try { localStorage.setItem(key, value); } catch (e) {} }

  /* ---- theme: light ↔ dark, remembered ---- */
  var themeBtn = document.querySelector(".theme-toggle");
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var dark = root.dataset.theme
        ? root.dataset.theme === "dark"
        : window.matchMedia("(prefers-color-scheme: dark)").matches;
      root.dataset.theme = dark ? "light" : "dark";
      store("theme", root.dataset.theme);
    });
  }

  /* ---- language: remember the reader's choice for the root redirect ---- */
  document.querySelectorAll("[data-lang]").forEach(function (a) {
    a.addEventListener("click", function () { store("lang", a.dataset.lang); });
  });
  store("lang", root.lang);

  /* ---- project filters ---- */
  var chips = document.querySelectorAll(".filters [data-filter]");
  if (chips.length) {
    var blocks = document.querySelectorAll("[data-category-block]");
    function applyFilter(id) {
      chips.forEach(function (c) { c.setAttribute("aria-pressed", String(c.dataset.filter === id)); });
      blocks.forEach(function (b) { b.hidden = id !== "all" && b.dataset.categoryBlock !== id; });
    }
    chips.forEach(function (c) { c.addEventListener("click", function () { applyFilter(c.dataset.filter); }); });
    var fromHash = location.hash.slice(1);
    if (fromHash && document.querySelector('[data-filter="' + fromHash + '"]')) applyFilter(fromHash);
  }

  /* ---- examples table filter ---- */
  var exChips = document.querySelectorAll("[data-ex-filter]");
  exChips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      exChips.forEach(function (c) { c.setAttribute("aria-pressed", String(c === chip)); });
      document.querySelectorAll(".ex-table tbody tr").forEach(function (tr) {
        tr.hidden = chip.dataset.exFilter === "disagree" && tr.dataset.disagree !== "true";
      });
    });
  });

  /* ---- tabs helper: shared by the stepper and the call explorer ---- */
  function tabs(buttons, panelFor, onSelect) {
    function select(btn, focus) {
      buttons.forEach(function (b, i) {
        var on = b === btn;
        b.setAttribute("aria-selected", String(on));
        b.tabIndex = on ? 0 : -1;
        panelFor(b).hidden = !on;
        if (onSelect) onSelect(b, i, on);
      });
      if (focus) btn.focus();
    }
    buttons.forEach(function (b, i) {
      b.setAttribute("role", "tab");
      b.addEventListener("click", function () { select(b); });
      b.addEventListener("keydown", function (e) {
        var rtl = getComputedStyle(b).direction === "rtl";
        var next = { ArrowDown: 1, ArrowUp: -1, ArrowRight: rtl ? -1 : 1, ArrowLeft: rtl ? 1 : -1 }[e.key];
        if (e.key === "Home") next = -i;
        if (e.key === "End") next = buttons.length - 1 - i;
        if (next === undefined) return;
        e.preventDefault();
        select(buttons[(i + next + buttons.length) % buttons.length], true);
      });
    });
    var initial = buttons.filter(function (b) { return b.getAttribute("aria-selected") === "true"; })[0] || buttons[0];
    select(initial);
    return select;
  }

  /* ---- "how it works" stepper ---- */
  document.querySelectorAll("[data-stepper]").forEach(function (el) {
    var list = el.querySelector(".step-list");
    list.setAttribute("role", "tablist");
    var btns = Array.prototype.slice.call(el.querySelectorAll(".step-btn"));
    tabs(btns, function (b) { return document.getElementById(b.getAttribute("aria-controls")); }, function (b, i, on) {
      if (on) btns.forEach(function (x, j) { x.classList.toggle("is-done", j < i); });
    });
  });

  /* ---- call explorer ---- */
  document.querySelectorAll("[data-explorer]").forEach(function (el) {
    var btns = Array.prototype.slice.call(el.querySelectorAll(".call-item"));
    var select = tabs(btns, function (b) { return document.getElementById(b.getAttribute("aria-controls")); });
    document.querySelectorAll("[data-show-call]").forEach(function (link) {
      link.addEventListener("click", function () {
        var btn = btns.filter(function (b) { return b.dataset.call === link.dataset.showCall; })[0];
        if (!btn) return;
        select(btn);
        document.getElementById(btn.getAttribute("aria-controls")).scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
      });
    });
  });

  /* ---- reveal on scroll, count-up, bar growth ---- */
  function countUp(node) {
    var target = parseInt(node.dataset.count, 10);
    if (reduceMotion || !target) return;
    var start = null, dur = 1200, fmt = new Intl.NumberFormat("en-US");
    function frame(ts) {
      if (!start) start = ts;
      var k = Math.min(1, (ts - start) / dur);
      node.textContent = fmt.format(Math.round(target * (1 - Math.pow(1 - k, 3))));
      if (k < 1) requestAnimationFrame(frame);
    }
    node.textContent = "0";
    requestAnimationFrame(frame);
  }
  var watched = document.querySelectorAll(".reveal, [data-count], .bars");
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        en.target.classList.add("is-in");
        if (en.target.dataset.count) countUp(en.target);
        io.unobserve(en.target);
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.12 });
    watched.forEach(function (n) { io.observe(n); });
  } else {
    watched.forEach(function (n) { n.classList.add("is-in"); });
  }

  /* ---- chart tooltip ---- */
  var tip = document.querySelector(".tooltip");
  if (tip) {
    document.querySelectorAll("[data-tip]").forEach(function (row) {
      function show(x, y) {
        tip.textContent = row.dataset.tip;
        tip.hidden = false;
        var w = tip.offsetWidth;
        tip.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, x - w / 2)) + "px";
        tip.style.top = (y - tip.offsetHeight - 12) + "px";
      }
      row.addEventListener("mousemove", function (e) { show(e.clientX, e.clientY); });
      row.addEventListener("focus", function () { var r = row.getBoundingClientRect(); show(r.left + r.width / 2, r.top); });
      row.addEventListener("mouseleave", function () { tip.hidden = true; });
      row.addEventListener("blur", function () { tip.hidden = true; });
    });
  }

  /* ---- lightbox ---- */
  var box = document.querySelector(".lightbox");
  if (box && typeof box.showModal === "function") {
    var img = box.querySelector("img"), cap = box.querySelector(".lightbox-caption");
    document.querySelectorAll("[data-lightbox]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        img.src = btn.dataset.lightbox;
        img.alt = btn.dataset.caption || "";
        cap.textContent = btn.dataset.caption || "";
        box.showModal();
      });
    });
    box.querySelector(".lightbox-close").addEventListener("click", function () { box.close(); });
    box.addEventListener("click", function (e) { if (e.target === box) box.close(); });
  }

  /* ---- copy email ---- */
  document.querySelectorAll("[data-copy]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      if (!navigator.clipboard) return;
      navigator.clipboard.writeText(btn.dataset.copy).then(function () {
        var label = btn.querySelector("span"), was = label.textContent;
        label.textContent = btn.dataset.copied;
        setTimeout(function () { label.textContent = was; }, 1800);
      });
    });
  });
})();
