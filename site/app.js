/* NerdHang front end: loads events.json, filters by distance and category,
   shows a list or month calendar, and exports to calendar apps. */
(() => {
  "use strict";

  const CATEGORIES = {
    "trains": "Trains",
    "ham-radio": "Ham radio",
    "computers": "Computers & retro gaming",
    "museum": "Museums",
    "makers": "Makers & hackers",
    "records": "Records & collecting",
    "outdoors": "Nature & tours",
    "fairs": "Fairs & markets",
    "other": "Other",
  };
  // Small line icons, one per category.
  const ICONS = {
    "trains": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="3" width="14" height="13" rx="3"/><path d="M5 10h14M9 20l-2 2M15 20l2 2M8 16l-1 4h10l-1-4"/><circle cx="9" cy="13" r=".5"/><circle cx="15" cy="13" r=".5"/></svg>',
    "ham-radio": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 12v10M9 22h6M12 12l-4-9M12 12l4-9M8.5 4h7"/><path d="M5 8a8 8 0 0 0 0 8M19 8a8 8 0 0 1 0 8"/></svg>',
    "computers": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4M7 9l2 2-2 2M11 13h4"/></svg>',
    "museum": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10l9-6 9 6M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 21h18"/></svg>',
    "makers": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.4-.6-.6-2.4z"/></svg>',
    "records": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/><path d="M12 3a9 9 0 0 1 9 9"/></svg>',
    "outdoors": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 20l6-11 4 7 3-4 5 8z"/><circle cx="17" cy="6" r="2"/></svg>',
    "fairs": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 10l8-6 8 6M6 10v10h12V10M10 20v-5h4v5"/><path d="M12 4V1"/></svg>',
    "other": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/></svg>',
  };
  // Saved category filter. Categories added after it was saved start switched on.
  function savedCats() {
    const all = Object.keys(CATEGORIES);
    const cats = store.get("cats", all);
    const known = store.get("knownCats", ["trains", "ham-radio", "computers", "museum", "other"]);
    const fresh = all.filter((c) => !known.includes(c));
    store.set("knownCats", all);
    return [...cats.filter((c) => all.includes(c)), ...fresh];
  }
  const DEFAULT_LOC = { name: "Long Island, NY", lat: 40.79, lon: -73.13 };
  const store = {
    get(k, d) { try { return JSON.parse(localStorage.getItem("nh:" + k)) ?? d; } catch { return d; } },
    set(k, v) { try { localStorage.setItem("nh:" + k, JSON.stringify(v)); } catch { /* private mode */ } },
  };

  const state = {
    events: [],
    loc: store.get("loc", null),
    radius: store.get("radius", 100),
    cats: savedCats(),
    view: store.get("view", "list"),
  };
  let calendar = null;

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const catOf = (e) => (CATEGORIES[e.category] ? e.category : "other");
  const color = (cat) => `var(--${CATEGORIES[cat] ? cat : "other"})`;
  const solid = (cat) => getComputedStyle(document.documentElement).getPropertyValue("--" + (CATEGORIES[cat] ? cat : "other")).trim();

  // ---------- dates ----------
  // All-day events are "YYYY-MM-DD" with an inclusive end; timed ones are ISO with offset.
  const parseDay = (s) => { const [y, m, d] = s.slice(0, 10).split("-").map(Number); return new Date(y, m - 1, d); };
  const startOf = (e) => (e.all_day ? parseDay(e.start) : new Date(e.start));
  const endOf = (e) => (e.all_day ? parseDay(e.end) : new Date(e.end));
  const fmtDate = (d, opts) => d.toLocaleDateString(undefined, opts);
  const fmtTime = (d) => d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });

  function whenText(e) {
    const s = startOf(e), en = endOf(e);
    const day = { weekday: "short", month: "short", day: "numeric" };
    if (e.all_day) {
      return s.getTime() === en.getTime() ? fmtDate(s, day) : `${fmtDate(s, day)} – ${fmtDate(en, day)}`;
    }
    const sameDay = s.toDateString() === en.toDateString();
    return sameDay
      ? `${fmtDate(s, day)}, ${fmtTime(s)} – ${fmtTime(en)}`
      : `${fmtDate(s, day)} ${fmtTime(s)} – ${fmtDate(en, day)} ${fmtTime(en)}`;
  }

  // ---------- distance ----------
  function miles(a, b) {
    const r = (x) => (x * Math.PI) / 180;
    const h = Math.sin(r(b.lat - a.lat) / 2) ** 2 + Math.cos(r(a.lat)) * Math.cos(r(b.lat)) * Math.sin(r(b.lon - a.lon) / 2) ** 2;
    return 3958.8 * 2 * Math.asin(Math.sqrt(h));
  }

  function visibleEvents() {
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const loc = state.loc || DEFAULT_LOC;
    return state.events
      .map((e) => ({ ...e, _miles: e.location.lat != null ? miles(loc, e.location) : null }))
      .filter((e) => endOf(e) >= today)
      .filter((e) => state.cats.includes(CATEGORIES[e.category] ? e.category : "other"))
      .filter((e) => !state.radius || (e._miles != null && e._miles <= state.radius))
      .sort((a, b) => startOf(a) - startOf(b));
  }

  // ---------- rendering ----------
  function placeText(e) {
    const { name, address } = e.location;
    if (address && name && address.startsWith(name)) return address;
    return [name, address].filter(Boolean).join(", ");
  }

  function renderList(events) {
    const el = $("list-view");
    if (!events.length) {
      el.innerHTML = `<p class="empty">No events match. Try a bigger distance or more categories.</p>`;
      return;
    }
    let html = "", month = "";
    for (const e of events) {
      const s = startOf(e);
      const m = fmtDate(s, { month: "long", year: "numeric" });
      if (m !== month) { html += `<h2 class="month-head">${esc(m)}</h2>`; month = m; }
      const cat = catOf(e);
      const dist = e._miles != null ? `<div class="dist"><b>${Math.round(e._miles)}</b>miles</div>` : "";
      html += `<article class="ev" tabindex="0" data-id="${esc(e.id)}" style="--c:${color(cat)}">
        <div class="when"><div class="dow">${esc(fmtDate(s, { weekday: "short" }))}</div>
          <div class="day">${s.getDate()}</div><div class="mon">${esc(fmtDate(s, { month: "short" }))}</div></div>
        <div class="body"><h3>${esc(e.title)}</h3>
          <div class="meta"><span class="tag">${ICONS[cat]}${esc(CATEGORIES[cat])}</span><span>${esc(whenText(e))}</span></div>
          <div class="meta">${esc(placeText(e))}${e._miles != null ? `<span class="mi-inline"> · ${Math.round(e._miles)} mi</span>` : ""}</div></div>
        ${dist}
      </article>`;
    }
    el.innerHTML = html;
  }

  function renderMonth(events) {
    const data = events.map((e) => {
      const cat = catOf(e);
      const ev = { id: e.id, title: e.title, backgroundColor: solid(cat), borderColor: solid(cat), allDay: e.all_day };
      if (e.all_day) {
        ev.start = e.start;
        const end = parseDay(e.end); end.setDate(end.getDate() + 1); // FullCalendar end is exclusive
        ev.end = isoDay(end);
      } else { ev.start = e.start; ev.end = e.end; }
      return ev;
    });
    if (!calendar) {
      calendar = new FullCalendar.Calendar($("month-view"), {
        initialView: "dayGridMonth",
        height: "auto",
        headerToolbar: { left: "prev,next today", center: "title", right: "" },
        dayMaxEvents: 4,
        eventClick: (info) => { info.jsEvent.preventDefault(); showDetail(info.event.id); },
      });
      calendar.render();
    }
    calendar.removeAllEventSources();
    calendar.addEventSource(data);
  }

  function render() {
    const events = visibleEvents();
    $("count").textContent = `${events.length} upcoming event${events.length === 1 ? "" : "s"}`;
    $("loc-name").textContent = (state.loc || DEFAULT_LOC).name;
    $("list-view").hidden = state.view !== "list";
    $("month-view").hidden = state.view !== "month";
    document.querySelectorAll(".views button").forEach((b) => {
      const on = b.dataset.view === state.view;
      b.classList.toggle("active", on);
      b.setAttribute("aria-selected", String(on));
    });
    if (state.view === "list") renderList(events); else renderMonth(events);
    state.visible = events;
    const next = events.find((e) => startOf(e) >= new Date(new Date().setHours(0, 0, 0, 0)));
    $("next-up").textContent = next
      ? `${fmtDate(startOf(next), { weekday: "short", month: "short", day: "numeric" }).toUpperCase()}  ${next.title}`
      : "No events nearby yet";
  }

  // ---------- event details ----------
  function showDetail(id) {
    const e = state.events.find((x) => x.id === id);
    if (!e) return;
    const v = (state.visible || []).find((x) => x.id === id);
    const dist = v && v._miles != null ? ` (${Math.round(v._miles)} miles away)` : "";
    const place = placeText(e);
    const map = e.location.lat != null
      ? `https://www.openstreetmap.org/?mlat=${e.location.lat}&mlon=${e.location.lon}#map=15/${e.location.lat}/${e.location.lon}`
      : "";
    const cat = catOf(e);
    $("detail-body").style.setProperty("--c", color(cat));
    $("detail-body").innerHTML = `
      <div class="detail-head"><span class="tag">${ICONS[cat]}${esc(CATEGORIES[cat])}</span><h2>${esc(e.title)}</h2></div>
      <div class="detail-body">
        <div class="row"><span class="k">When</span><span>${esc(whenText(e))}</span></div>
        <div class="row"><span class="k">Where</span><span>${esc(place)}${esc(dist)}</span></div>
        ${e.description ? `<div class="row"><span class="k">About</span><span class="desc">${esc(e.description)}</span></div>` : ""}
        <div class="row"><span class="k">Source</span><span>${esc(e.source_name)}</span></div>
        <div class="actions">
          ${e.url ? `<a class="btn primary" href="${esc(e.url)}" target="_blank" rel="noopener">Event page</a>` : ""}
          ${map ? `<a class="btn" href="${esc(map)}" target="_blank" rel="noopener">Map</a>` : ""}
          <a class="btn" href="${esc(googleLink(e))}" target="_blank" rel="noopener">Add to Google Calendar</a>
          <a class="btn" href="#" data-ics="${esc(e.id)}">Download .ics</a>
        </div>
      </div>`;
    $("detail").showModal();
  }

  // ---------- calendar export ----------
  const pad = (n) => String(n).padStart(2, "0");
  const isoDay = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const icsDay = (d) => isoDay(d).replace(/-/g, "");
  const icsUtc = (d) => d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
  const icsText = (s) => String(s ?? "").replace(/\\/g, "\\\\").replace(/\n/g, "\\n").replace(/([,;])/g, "\\$1");

  function icsDates(e) {
    if (e.all_day) {
      const end = parseDay(e.end); end.setDate(end.getDate() + 1);
      return [icsDay(parseDay(e.start)), icsDay(end)];
    }
    return [icsUtc(new Date(e.start)), icsUtc(new Date(e.end))];
  }

  function googleLink(e) {
    const [s, en] = icsDates(e);
    const p = new URLSearchParams({
      action: "TEMPLATE", text: e.title, dates: `${s}/${en}`,
      location: placeText(e), details: [e.description, e.url].filter(Boolean).join("\n\n"),
    });
    return "https://calendar.google.com/calendar/render?" + p.toString();
  }

  function buildIcs(events) {
    const stamp = icsUtc(new Date());
    const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//NerdHang//Event Calendar//EN", "CALSCALE:GREGORIAN", "X-WR-CALNAME:NerdHang"];
    for (const e of events) {
      const [s, en] = icsDates(e);
      const kind = e.all_day ? ";VALUE=DATE:" : ":";
      lines.push("BEGIN:VEVENT", `UID:${e.id}@nerdhang`, `DTSTAMP:${stamp}`,
        `DTSTART${kind}${s}`, `DTEND${kind}${en}`, `SUMMARY:${icsText(e.title)}`);
      const place = placeText(e);
      if (place) lines.push(`LOCATION:${icsText(place)}`);
      if (e.url) lines.push(`URL:${e.url}`);
      lines.push(`DESCRIPTION:${icsText([e.description, "Source: " + e.source_name, e.url].filter(Boolean).join("\n\n"))}`, "END:VEVENT");
    }
    lines.push("END:VCALENDAR");
    return lines.map(foldLine).join("\r\n") + "\r\n";
  }

  function foldLine(line) {
    // iCalendar lines should be at most 75 octets; continuation lines start with a space.
    const enc = new TextEncoder();
    if (enc.encode(line).length <= 75) return line;
    const out = []; let cur = "";
    for (const ch of line) {
      if (enc.encode(cur + ch).length > (out.length ? 74 : 75)) { out.push(cur); cur = ""; }
      cur += ch;
    }
    out.push(cur);
    return out.join("\r\n ");
  }

  function download(name, text) {
    const url = URL.createObjectURL(new Blob([text], { type: "text/calendar;charset=utf-8" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: name });
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function setupSubscribeLinks() {
    const feed = new URL("nerdhang.ics", location.href);
    const webcal = feed.href.replace(/^https?:/, "webcal:");
    $("sub-webcal").href = webcal;
    $("sub-google").href = "https://calendar.google.com/calendar/render?cid=" + encodeURIComponent(webcal);
  }

  // ---------- location ----------
  function setLoc(loc) {
    state.loc = loc;
    store.set("loc", loc);
    render();
  }

  function useGps(quiet) {
    if (!navigator.geolocation) { if (!quiet) alertMsg("Your browser can't share its location. Type a town or ZIP instead."); return; }
    $("loc-name").textContent = "Finding your location…";
    navigator.geolocation.getCurrentPosition(
      (pos) => setLoc({ name: "your location", lat: pos.coords.latitude, lon: pos.coords.longitude }),
      () => { if (!quiet) alertMsg("Location access was blocked. Type a town or ZIP instead."); render(); },
      { maximumAge: 3600e3, timeout: 10e3 }
    );
  }

  async function searchPlace(q) {
    const url = "https://nominatim.openstreetmap.org/search?" + new URLSearchParams({ q, format: "json", limit: 1, countrycodes: "us,ca" });
    try {
      const r = await fetch(url, { headers: { "Accept-Language": navigator.language || "en" } });
      const [hit] = await r.json();
      if (!hit) return alertMsg(`Couldn't find "${q}". Try a ZIP code.`);
      setLoc({ name: hit.display_name.split(",").slice(0, 2).join(",").trim(), lat: +hit.lat, lon: +hit.lon });
    } catch {
      alertMsg("Place search is unavailable right now. Try again later.");
    }
  }

  function alertMsg(msg) {
    document.querySelectorAll(".notice").forEach((n) => n.remove());
    $("list-view").insertAdjacentHTML("beforebegin", `<p class="notice" role="status">${esc(msg)}</p>`);
  }

  // ---------- wiring ----------
  function setupControls() {
    const cats = $("cats");
    for (const [key, label] of Object.entries(CATEGORIES)) {
      cats.insertAdjacentHTML("beforeend",
        `<button type="button" class="chip" data-cat="${key}" aria-pressed="${state.cats.includes(key)}" style="--c:${color(key)}">${ICONS[key]}${esc(label)}</button>`);
    }
    cats.addEventListener("click", (ev) => {
      const b = ev.target.closest(".chip");
      if (!b) return;
      b.setAttribute("aria-pressed", String(b.getAttribute("aria-pressed") !== "true"));
      state.cats = [...cats.querySelectorAll('.chip[aria-pressed="true"]')].map((c) => c.dataset.cat);
      store.set("cats", state.cats); render();
    });
    $("radius").value = String(state.radius);
    $("radius").addEventListener("change", (ev) => { state.radius = +ev.target.value; store.set("radius", state.radius); render(); });
    document.querySelectorAll(".views button").forEach((b) =>
      b.addEventListener("click", () => { state.view = b.dataset.view; store.set("view", state.view); render(); }));
    $("loc-gps").addEventListener("click", () => useGps(false));
    $("loc-form").addEventListener("submit", (ev) => {
      ev.preventDefault();
      const q = $("loc-input").value.trim();
      if (q) searchPlace(q);
    });
    $("list-view").addEventListener("click", (ev) => { const a = ev.target.closest(".ev"); if (a) showDetail(a.dataset.id); });
    $("list-view").addEventListener("keydown", (ev) => { const a = ev.target.closest(".ev"); if (a && ev.key === "Enter") showDetail(a.dataset.id); });
    $("dl-ics").addEventListener("click", (ev) => { ev.preventDefault(); download("nerdhang-events.ics", buildIcs(state.visible || [])); ev.target.closest("details").open = false; });
    document.addEventListener("click", (ev) => { const m = document.querySelector(".menu"); if (m.open && !m.contains(ev.target)) m.open = false; });
    $("detail").addEventListener("click", (ev) => {
      const a = ev.target.closest("[data-ics]");
      if (a) { ev.preventDefault(); const e = state.events.find((x) => x.id === a.dataset.ics); download("event.ics", buildIcs([e])); }
      if (ev.target === $("detail")) $("detail").close(); // click on backdrop
    });
    setupSubscribeLinks();
  }

  async function init() {
    setupControls();
    try {
      const r = await fetch("events.json", { cache: "no-cache" });
      const data = await r.json();
      state.events = data.events || [];
      if (data.generated_at) $("updated").textContent = `Last updated ${new Date(data.generated_at).toLocaleString()}.`;
    } catch {
      $("list-view").innerHTML = `<p class="empty">Couldn't load events. Please refresh the page.</p>`;
      return;
    }
    render();
    if (!state.loc) useGps(true); // ask once; fall back to Long Island quietly
  }

  // Exposed for tests.
  window.NerdHang = { buildIcs, googleLink, miles, state };
  init();
})();
