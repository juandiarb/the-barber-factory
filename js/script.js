/* Sitio público de la barbería. Todo dato del negocio sale del JSON que el
   servidor incrusta desde negocio.json (#negocio); nada está escrito aquí. */
(function () {
  "use strict";

  var D = JSON.parse(document.getElementById("negocio").textContent);
  var REDUCE = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var TZ = D.zona_horaria || "UTC";
  var DAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
  var MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") node.textContent = attrs[k];
      else if (k === "html") node.innerHTML = attrs[k];
      else if (attrs[k] !== null && attrs[k] !== undefined && attrs[k] !== false) node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) node.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return node;
  }
  function icon(name) {
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "ic");
    svg.setAttribute("aria-hidden", "true");
    var use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", "#i-" + name);
    svg.appendChild(use);
    return svg;
  }
  function money(v) { return "$ " + Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g, "."); }
  function num(v) {
    var s = String(v);
    if (s.indexOf(".") > -1) return s.replace(".", ",");
    return s.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }
  function durationText(min) {
    var h = Math.floor(min / 60), m = min % 60;
    return h && m ? h + " h " + m + " min" : h ? h + " h" : m + " min";
  }
  function waLink(message) {
    return D.whatsapp ? "https://wa.me/" + D.whatsapp + "?text=" + encodeURIComponent(message) : null;
  }
  function longDate(iso) {
    var p = iso.split("-").map(Number);
    var wd = (new Date(Date.UTC(p[0], p[1] - 1, p[2])).getUTCDay() + 6) % 7;
    return DAYS[wd].toLowerCase() + " " + p[2] + " de " + MONTHS[p[1] - 1];
  }
  function to12(hhmm) {
    var p = hhmm.split(":").map(Number), suf = p[0] >= 12 ? "p.m." : "a.m.";
    var h = p[0] % 12 || 12;
    return h + ":" + (p[1] < 10 ? "0" : "") + p[1] + " " + suf;
  }

  /* Fecha y hora "ahora" en la zona horaria del negocio, no la del visitante. */
  function nowInTZ() {
    try {
      var parts = new Intl.DateTimeFormat("en-CA", {
        timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit",
        hour: "2-digit", minute: "2-digit", hourCycle: "h23", weekday: "short"
      }).formatToParts(new Date());
      var o = {};
      parts.forEach(function (p) { o[p.type] = p.value; });
      var wd = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].indexOf(o.weekday);
      return { date: o.year + "-" + o.month + "-" + o.day, time: o.hour + ":" + o.minute, weekday: wd };
    } catch (e) {
      return { date: D.hoy, time: D.ahora, weekday: (new Date().getDay() + 6) % 7 };
    }
  }
  function addDays(iso, n) {
    var p = iso.split("-").map(Number);
    var d = new Date(Date.UTC(p[0], p[1] - 1, p[2] + n));
    return d.toISOString().slice(0, 10);
  }
  function weekdayOf(iso) {
    var p = iso.split("-").map(Number);
    return (new Date(Date.UTC(p[0], p[1] - 1, p[2])).getUTCDay() + 6) % 7;
  }
  function hoursFor(weekday, sede) {
    var blocks = (sede && sede.horario) || D.horario || [];
    for (var i = 0; i < blocks.length; i++) {
      if (blocks[i].dias.indexOf(weekday) > -1) return blocks[i].cerrado ? null : [blocks[i].abre, blocks[i].cierra];
    }
    return null;
  }
  function mins(hhmm) { var p = hhmm.split(":"); return +p[0] * 60 + +p[1]; }
  function hhmm(total) { var h = Math.floor(total / 60), m = total % 60; return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m; }

  var SEDES = D.sedes || [];
  function mainSede() { return SEDES.filter(function (s) { return s.principal; })[0] || SEDES[0] || null; }

  /* ------------------------------------------------- bloques sin datos se ocultan */
  var available = {
    instagram: !!(D.redes && D.redes.instagram),
    facebook: !!(D.redes && D.redes.facebook),
    whatsapp: !!D.whatsapp_url,
    rating: !!(D.calificacion && D.calificacion.valor)
  };
  $$("[data-requires]").forEach(function (node) {
    if (!available[node.getAttribute("data-requires")]) node.hidden = true;
  });
  if (D.fotos_son_de_referencia) $("#refNote").hidden = false;
  $("#year").textContent = nowInTZ().date.slice(0, 4);

  /* ------------------------------------------------------------ menú */
  var nav = $("#nav"), toggle = $("#navToggle"), menu = $("#navMenu");
  function setMenu(open) {
    toggle.setAttribute("aria-expanded", String(open));
    menu.classList.toggle("is-open", open);
    toggle.querySelector(".sr-only").textContent = open ? "Cerrar menú" : "Abrir menú";
  }
  toggle.addEventListener("click", function () { setMenu(toggle.getAttribute("aria-expanded") !== "true"); });
  menu.addEventListener("click", function (e) { if (e.target.closest("a")) setMenu(false); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && menu.classList.contains("is-open")) { setMenu(false); toggle.focus(); }
  });
  window.addEventListener("scroll", function () { nav.classList.toggle("is-scrolled", window.scrollY > 10); }, { passive: true });

  if ("IntersectionObserver" in window) {
    var links = $$(".nav-menu ul a");
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        links.forEach(function (a) { a.classList.toggle("is-active", a.getAttribute("href") === "#" + entry.target.id); });
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    links.forEach(function (a) { var t = $(a.getAttribute("href")); if (t) spy.observe(t); });
  }

  /* ------------------------------------------------------------ franja */
  var franja = $("#franja");
  var words = D.franja || [];
  if (words.length) {
    for (var copy = 0; copy < 2; copy++) {
      words.forEach(function (w) {
        franja.appendChild(el("span", { "class": "franja-item" }, [w, icon("scissors")]));
      });
    }
  } else {
    franja.parentNode.hidden = true;
  }

  /* ------------------------------------------------------------ insignias */
  var badges = $("#insignias");
  (D.insignias || []).forEach(function (b) {
    badges.appendChild(el("li", { "class": "badge-item reveal" }, [
      el("div", { "class": "ticket" }, [el("div", { "class": "ticket-in" }, [
        el("span", { "class": "badge-icon" }, [icon(b.icono)]),
        el("h3", { text: b.titulo }),
        el("p", { text: b.texto })
      ])])
    ]));
  });
  if (!badges.children.length) badges.closest("section").hidden = true;

  /* ------------------------------------------------------------ servicios */
  var servicesList = $("#services");
  var serviceSelect = $("#b-service");
  var SERVICES = (D.servicios_db || []).slice();
  var INITIAL = 8;
  var activeCat = "Todos";
  var expanded = false;

  function serviceIcon(s) {
    var name = (s.name || "").toLowerCase(), cats = (s.categories || "").toLowerCase();
    if (name.indexOf("cera") > -1) return "drop";
    if (name.indexOf("facial") > -1 || cats.indexOf("facial") > -1) return "towel";
    if (name.indexOf("afeit") > -1) return "razor";
    if (cats.indexOf("cortes") > -1 || name.indexOf("corte") > -1) return "scissors";
    if (cats.indexOf("barba") > -1 || name.indexOf("barba") > -1) return "beard";
    return "scissors";
  }

  function renderServices() {
    servicesList.innerHTML = "";
    var showDuration = D.duraciones_confirmadas !== false;
    SERVICES.forEach(function (s) {
      var price = s.price === null || s.price === undefined
        ? el("span", { "class": "svc-price svc-price--ask", text: D.precio_nulo_texto || "Consultar" })
        : el("span", { "class": "svc-price", text: (s.price_from ? "Desde " : "") + money(s.price) });
      var meta = el("span", { "class": "svc-meta" }, [price, showDuration ? el("span", { "class": "svc-dur", text: durationText(s.duration) }) : null]);
      var btn = el("button", { type: "button", "class": "svc-btn", "data-service-id": s.id || "", "data-service-name": s.name,
        "aria-label": "Reservar " + s.name }, [
        el("span", { "class": "svc-icon", "aria-hidden": "true" }, [icon(serviceIcon(s))]),
        el("span", { "class": "svc-name", text: s.name }),
        el("span", { "class": "svc-desc", text: s.description || "" }),
        meta
      ]);
      servicesList.appendChild(el("li", { "class": "svc", "data-cats": s.categories || "" }, [btn]));
    });
    applyFilter(false);
  }

  function inCat(li, cat) {
    if (cat === "Todos") return true;
    return (li.getAttribute("data-cats") || "").split(",").map(function (c) { return c.trim(); }).indexOf(cat) > -1;
  }

  function applyFilter(animate) {
    var items = $$(".svc", servicesList);
    var matching = items.filter(function (li) { return inCat(li, activeCat); });
    items.forEach(function (li) { li.classList.add("is-hidden"); });
    matching.forEach(function (li, i) {
      if (expanded || i < INITIAL) {
        li.classList.remove("is-hidden");
        if (animate && !REDUCE) {
          li.classList.add("is-entering");
          setTimeout(function () { li.classList.remove("is-entering"); }, 30 + i * 35);
        }
      }
    });
    var more = $("#servicesMore");
    if (!expanded && matching.length > INITIAL) {
      more.hidden = false;
      more.textContent = "Ver los " + matching.length + " servicios";
    } else {
      more.hidden = true;
    }
  }

  function renderFilters() {
    var box = $("#filters");
    var cats = ["Todos"].concat(D.categorias || []);
    box.innerHTML = "";
    var items = $$(".svc", servicesList);
    cats.forEach(function (cat) {
      var count = items.filter(function (li) { return inCat(li, cat); }).length;
      if (!count) return;
      var b = el("button", { type: "button", "class": "filter", "aria-pressed": String(cat === activeCat) }, [
        cat, el("span", { "class": "count", text: String(count) })
      ]);
      b.addEventListener("click", function () {
        activeCat = cat;
        $$(".filter", box).forEach(function (f) { f.setAttribute("aria-pressed", String(f === b)); });
        applyFilter(true);
      });
      box.appendChild(b);
    });
    if (box.children.length <= 2) box.hidden = true;
  }

  $("#servicesMore").addEventListener("click", function () { expanded = true; applyFilter(true); });

  servicesList.addEventListener("click", function (e) {
    var btn = e.target.closest(".svc-btn");
    if (!btn) return;
    var id = btn.getAttribute("data-service-id");
    var name = btn.getAttribute("data-service-name");
    var opt = $$("option", serviceSelect).filter(function (o) { return o.value === id || o.textContent === name; })[0];
    if (opt) serviceSelect.value = opt.value;
    serviceSelect.dispatchEvent(new Event("change"));
    $("#reservar").scrollIntoView({ behavior: REDUCE ? "auto" : "smooth" });
    setTimeout(function () { $("#b-name").focus({ preventScroll: true }); }, REDUCE ? 0 : 600);
  });

  function fillServiceOptions() {
    var current = serviceSelect.value;
    serviceSelect.innerHTML = "";
    serviceSelect.appendChild(el("option", { value: "", text: "Elige un servicio" }));
    SERVICES.forEach(function (s) {
      var label = s.name + (s.price !== null && s.price !== undefined ? " · " + (s.price_from ? "desde " : "") + money(s.price) : "");
      serviceSelect.appendChild(el("option", { value: s.id || s.name, text: label }));
    });
    if (current) serviceSelect.value = current;
  }

  if (SERVICES.some(function (s) { return s.price === null || s.price === undefined; })) {
    $("#priceNote").textContent = "Los precios se confirman en la barbería o por WhatsApp.";
  }
  renderServices();
  renderFilters();

  /* La lista viene en la página; si la API responde se actualiza, si no, se usa la estática. */
  fetchJSON("/api/services/public", 6000).then(function (rows) {
    if (Array.isArray(rows) && rows.length) {
      SERVICES = rows;
      renderServices();
      renderFilters();
      fillServiceOptions();
    }
  }).catch(function () { /* se queda la lista estática */ });

  function fetchJSON(url, timeout, options) {
    var ctrl = "AbortController" in window ? new AbortController() : null;
    var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, timeout || 8000) : null;
    var opts = options || {};
    if (ctrl) opts.signal = ctrl.signal;
    return fetch(url, opts).then(function (res) {
      if (timer) clearTimeout(timer);
      return res.json().catch(function () { return {}; }).then(function (body) {
        if (!res.ok) { var err = new Error(body.error || "Error " + res.status); err.status = res.status; throw err; }
        return body;
      });
    }, function (err) { if (timer) clearTimeout(timer); err.network = true; throw err; });
  }

  /* ------------------------------------------------------------ reserva */
  var form = $("#booking");
  var dateInput = $("#b-date"), sedeSelect = $("#b-sede"), staffSelect = $("#b-staff");
  var timesBox = $("#times"), timesHelp = $("#timesHelp"), msg = $("#bookingMsg");
  var selectedTime = "";
  var today = nowInTZ().date;
  dateInput.min = today;
  dateInput.max = addDays(today, 120);

  if (SEDES.length > 1) {
    $("#sedeField").hidden = false;
    sedeSelect.required = true;
    sedeSelect.appendChild(el("option", { value: "", text: "Elige la sede" }));
    SEDES.forEach(function (s) { sedeSelect.appendChild(el("option", { value: s.nombre, text: s.nombre + (s.nueva ? " (nueva)" : "") })); });
  }
  function currentSede() {
    if (SEDES.length > 1) return SEDES.filter(function (s) { return s.nombre === sedeSelect.value; })[0] || null;
    return mainSede();
  }

  function loadStaff() {
    var sede = currentSede();
    var q = sede && SEDES.length > 1 ? "?sede=" + encodeURIComponent(sede.nombre) : "";
    return fetchJSON("/api/staff/public" + q, 6000).then(function (rows) {
      var keep = staffSelect.value;
      staffSelect.innerHTML = "";
      staffSelect.appendChild(el("option", { value: "", text: "Sin preferencia" }));
      rows.forEach(function (p) { staffSelect.appendChild(el("option", { value: p.id, text: p.name + (p.role ? " · " + p.role : "") })); });
      staffSelect.value = rows.some(function (p) { return String(p.id) === keep; }) ? keep : "";
      $("#staffField").hidden = rows.length === 0;
    }).catch(function () { $("#staffField").hidden = true; });
  }

  function setHelp(text) { timesHelp.textContent = text; }

  function timeButton(slot, free) {
    var b = el("button", { type: "button", "class": "time", role: "radio", "aria-checked": "false",
      "data-time": slot, tabindex: "-1", disabled: free ? null : "disabled",
      "aria-label": to12(slot) + (free ? "" : ", ocupado") }, [slot]);
    return b;
  }

  function renderTimes(slots, note) {
    timesBox.innerHTML = "";
    selectedTime = "";
    slots.forEach(function (s) { timesBox.appendChild(timeButton(s.hora, s.libre)); });
    var first = $(".time:not([disabled])", timesBox);
    if (first) first.tabIndex = 0;
    var free = slots.filter(function (s) { return s.libre; }).length;
    if (!slots.length) setHelp(note || "No hay horas disponibles ese día. Prueba otra fecha.");
    else if (!free) setHelp("Todas las horas de ese día están ocupadas. Prueba otra fecha.");
    else setHelp((note ? note + " " : "") + free + " horas libres. Elige una.");
  }

  /* Respaldo si la API de disponibilidad no responde: horas según el horario. */
  function localSlots(date, sede, duration) {
    var h = hoursFor(weekdayOf(date), sede);
    if (!h) return null;
    var step = D.intervalo_citas_min || 30, out = [], now = nowInTZ();
    for (var t = mins(h[0]); t + (duration || step) <= mins(h[1]); t += step) {
      if (date === now.date && hhmm(t) <= now.time) continue;
      out.push({ hora: hhmm(t), libre: true });
    }
    return out;
  }

  var availToken = 0;
  function loadTimes() {
    var date = dateInput.value;
    var sede = currentSede();
    if (!serviceSelect.value || !date) { timesBox.innerHTML = ""; setHelp("Elige primero el servicio y la fecha."); return; }
    if (SEDES.length > 1 && !sede) { timesBox.innerHTML = ""; setHelp("Elige primero la sede."); return; }
    if (date < dateInput.min || date > dateInput.max) { timesBox.innerHTML = ""; setHelp("Elige una fecha entre hoy y los próximos 120 días."); return; }
    var hours = hoursFor(weekdayOf(date), sede);
    if (!hours) { timesBox.innerHTML = ""; setHelp("Ese día estamos cerrados. Elige otra fecha."); return; }
    var service = SERVICES.filter(function (s) { return String(s.id) === serviceSelect.value; })[0];
    var params = "fecha=" + date + (sede ? "&sede=" + encodeURIComponent(sede.nombre) : "") +
      (staffSelect.value ? "&profesional=" + staffSelect.value : "") + (service && service.id ? "&servicio=" + service.id : "");
    var token = ++availToken;
    setHelp("Buscando horas libres…");
    timesBox.setAttribute("aria-busy", "true");
    fetchJSON("/api/availability?" + params, 7000).then(function (data) {
      if (token !== availToken) return;
      if (data.cerrado) { timesBox.innerHTML = ""; setHelp("Ese día estamos cerrados. Elige otra fecha."); return; }
      renderTimes(data.horas || []);
    }).catch(function () {
      if (token !== availToken) return;
      var slots = localSlots(date, sede, service && service.duration);
      renderTimes(slots || [], "No pudimos comprobar las horas ocupadas; te confirmamos por WhatsApp.");
    }).then(function () { timesBox.removeAttribute("aria-busy"); });
  }

  function selectTime(btn, focus) {
    $$(".time", timesBox).forEach(function (b) { b.setAttribute("aria-checked", "false"); b.tabIndex = -1; });
    btn.setAttribute("aria-checked", "true");
    btn.tabIndex = 0;
    if (focus) btn.focus();
    selectedTime = btn.getAttribute("data-time");
    setHelp("Hora elegida: " + to12(selectedTime) + ".");
  }
  timesBox.addEventListener("click", function (e) {
    var b = e.target.closest(".time");
    if (b && !b.disabled) selectTime(b, false);
  });
  timesBox.addEventListener("keydown", function (e) {
    var keys = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
    if (!(e.key in keys)) return;
    e.preventDefault();
    var free = $$(".time:not([disabled])", timesBox);
    var idx = free.indexOf(document.activeElement);
    var next = free[(idx + keys[e.key] + free.length) % free.length];
    if (next) selectTime(next, true);
  });

  serviceSelect.addEventListener("change", loadTimes);
  dateInput.addEventListener("change", loadTimes);
  staffSelect.addEventListener("change", loadTimes);
  sedeSelect.addEventListener("change", function () { loadStaff().then(loadTimes); });
  loadStaff();

  function showMsg(kind, nodes) {
    msg.className = "form-msg " + (kind === "ok" ? "is-ok" : "is-err");
    msg.innerHTML = "";
    msg.appendChild(icon(kind === "ok" ? "check" : "alert"));
    msg.appendChild(el("div", {}, nodes));
    msg.focus({ preventScroll: true });
    msg.scrollIntoView({ block: "nearest", behavior: REDUCE ? "auto" : "smooth" });
  }

  function summaryText(data) {
    var parts = ["Hola, quiero reservar en " + D.nombre + ":", "Servicio: " + data.service];
    if (data.sede && SEDES.length > 1) parts.push("Sede: " + data.sede);
    if (data.barber) parts.push("Barbero: " + data.barber);
    if (data.date) parts.push("Fecha: " + longDate(data.date));
    if (data.time) parts.push("Hora: " + to12(data.time));
    if (data.name) parts.push("Nombre: " + data.name);
    if (data.phone) parts.push("Teléfono: " + data.phone);
    return parts.join("\n");
  }

  function fieldError(input, text) {
    input.setAttribute("aria-invalid", "true");
    showMsg("err", [el("p", { text: text })]);
    input.focus();
  }

  form.addEventListener("input", function (e) { if (e.target.removeAttribute) e.target.removeAttribute("aria-invalid"); });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var name = $("#b-name"), phone = $("#b-phone"), terms = $("#b-terms");
    if (!name.value.trim()) return fieldError(name, "Escribe tu nombre.");
    if (!/^\+?[0-9 ()\-]{7,20}$/.test(phone.value.trim())) return fieldError(phone, "Escribe un teléfono válido (solo números).");
    if (SEDES.length > 1 && !sedeSelect.value) return fieldError(sedeSelect, "Elige la sede.");
    if (!serviceSelect.value) return fieldError(serviceSelect, "Elige un servicio.");
    if (!dateInput.value) return fieldError(dateInput, "Elige la fecha.");
    if (!selectedTime) { showMsg("err", [el("p", { text: "Elige una hora disponible." })]); var t = $(".time:not([disabled])", timesBox); if (t) t.focus(); return; }
    if (!terms.checked) return fieldError(terms, "Para reservar debes aceptar los términos y la política de datos.");

    var service = SERVICES.filter(function (s) { return String(s.id) === serviceSelect.value || s.name === serviceSelect.value; })[0];
    var staffName = staffSelect.value ? staffSelect.options[staffSelect.selectedIndex].text.split(" · ")[0] : "";
    var sede = currentSede();
    var payload = {
      name: name.value.trim(), phone: phone.value.trim(),
      date: dateInput.value, time: selectedTime, notes: $("#b-notes").value.trim(),
      staff_id: staffSelect.value || null, sede: sede ? sede.nombre : null, accept_terms: true
    };
    if (service && service.id) payload.service_id = service.id; else payload.service = service ? service.name : serviceSelect.value;
    var info = { service: service ? service.name : "", sede: payload.sede, barber: staffName, date: payload.date,
      time: payload.time, name: payload.name, phone: payload.phone };

    var submit = $("#bookingSubmit");
    submit.disabled = true;
    submit.textContent = "Enviando…";
    fetchJSON("/api/appointments", 10000, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    }).then(function (res) {
      var dl = el("dl", {}, [
        el("dt", { text: "Servicio" }), el("dd", { text: res.service }),
        SEDES.length > 1 ? el("dt", { text: "Sede" }) : null, SEDES.length > 1 ? el("dd", { text: res.sede }) : null,
        res.barber ? el("dt", { text: "Barbero" }) : null, res.barber ? el("dd", { text: res.barber }) : null,
        el("dt", { text: "Fecha" }), el("dd", { text: longDate(res.date) }),
        el("dt", { text: "Hora" }), el("dd", { text: to12(res.time) })
      ]);
      var nodes = [el("p", {}, [el("strong", { text: "¡Listo, " + payload.name.split(" ")[0] + "! Recibimos tu reserva." })]), dl,
        el("p", { text: "Te confirmamos por teléfono o WhatsApp." })];
      var wa = waLink(summaryText(info) + "\nReserva #" + res.id);
      if (wa) nodes.push(el("a", { "class": "btn btn-ghost", href: wa, target: "_blank", rel: "noopener" }, [icon("whatsapp"), "Avisar por WhatsApp"]));
      showMsg("ok", nodes);
      form.reset();
      timesBox.innerHTML = "";
      selectedTime = "";
      setHelp("Elige primero el servicio y la fecha.");
    }).catch(function (err) {
      var text = err.status === 409 ? "Ese horario ya está ocupado. Elige otra hora."
        : err.network ? "No pudimos conectar con el servidor."
        : (err.message || "No se pudo completar la reserva.");
      var nodes = [el("p", { text: text })];
      var wa = waLink(summaryText(info));
      if (err.status !== 409 && wa) {
        nodes.push(el("p", { text: "Puedes enviarnos la reserva por WhatsApp con tus datos ya escritos:" }));
        nodes.push(el("a", { "class": "btn btn-primary", href: wa, target: "_blank", rel: "noopener" }, [icon("whatsapp"), "Reservar por WhatsApp"]));
      }
      showMsg("err", nodes);
      if (err.status === 409) loadTimes();
    }).then(function () {
      submit.disabled = false;
      submit.textContent = "Reservar cita";
    });
  });

  /* ------------------------------------------------------------ nosotros */
  var aboutText = $("#aboutText");
  (D.sobre_nosotros || []).forEach(function (p) { aboutText.appendChild(el("p", { text: p })); });
  var aboutPhotos = $("#aboutPhotos");
  (D.nosotros_fotos || []).forEach(function (f) {
    aboutPhotos.appendChild(el("figure", { "class": "reveal" }, [el("img", { src: "/" + f.src, alt: f.alt, width: f.w, height: f.h, loading: "lazy" })]));
  });
  if (!aboutPhotos.children.length) aboutPhotos.hidden = true;

  var stats = $("#stats");
  (D.estadisticas || []).forEach(function (s) {
    var value = s.valor === "{servicios}" ? String(SERVICES.length) : s.valor;
    if (!value) return;
    var dd = el("dd", { text: s.contar === false ? value : num(value) });
    if (s.contar !== false && /^\d+(\.\d+)?$/.test(value)) {
      dd.setAttribute("data-count", value);
      if (!REDUCE) dd.textContent = value.indexOf(".") > -1 ? "0,0" : "0";
    }
    stats.appendChild(el("div", { "class": "stat" }, [dd, el("dt", { text: s.etiqueta })]));
  });
  $("#statsNote").textContent = D.estadisticas_nota || "";

  function countUp(node) {
    var target = parseFloat(node.getAttribute("data-count"));
    var decimals = node.getAttribute("data-count").indexOf(".") > -1 ? 1 : 0;
    var start = null, dur = 1400;
    function step(ts) {
      if (!start) start = ts;
      var p = Math.min(1, (ts - start) / dur);
      var eased = 1 - Math.pow(1 - p, 3);
      node.textContent = num((target * eased).toFixed(decimals));
      if (p < 1) requestAnimationFrame(step);
      else node.textContent = num(node.getAttribute("data-count"));
    }
    requestAnimationFrame(step);
  }

  /* ------------------------------------------------------------ galería */
  var gallery = $("#gallery");
  var photos = D.galeria || [];
  photos.forEach(function (g, i) {
    var btn = el("button", { type: "button", "aria-label": "Ampliar foto: " + (g.titulo || g.alt) }, [
      el("img", { src: "/" + g.src, alt: g.alt, width: g.w, height: g.h, loading: "lazy" }),
      g.titulo ? el("span", { "class": "g-title", text: g.titulo }) : null
    ]);
    btn.addEventListener("click", function () { openLightbox(i); });
    gallery.appendChild(el("li", { "class": "reveal" }, [btn]));
  });
  $("#galleryNote").textContent = D.galeria_nota || "";
  if (!photos.length) $("#galeria").hidden = true;

  var lb = $("#lightbox"), lbImg = $("#lbImg"), lbCap = $("#lbCap"), lbIndex = 0, lbOpener = null;
  function showPhoto(i) {
    lbIndex = (i + photos.length) % photos.length;
    var g = photos[lbIndex];
    lbImg.src = "/" + g.src;
    lbImg.alt = g.alt;
    lbCap.textContent = (g.titulo ? g.titulo + " · " : "") + (lbIndex + 1) + " / " + photos.length;
  }
  function openLightbox(i) {
    lbOpener = document.activeElement;
    showPhoto(i);
    if (lb.showModal) lb.showModal(); else lb.setAttribute("open", "");
    $(".lb-close", lb).focus();
  }
  function closeLightbox() {
    if (lb.close) lb.close(); else lb.removeAttribute("open");
  }
  lb.addEventListener("close", function () { if (lbOpener) lbOpener.focus(); });
  $(".lb-close", lb).addEventListener("click", closeLightbox);
  $(".lb-prev", lb).addEventListener("click", function () { showPhoto(lbIndex - 1); });
  $(".lb-next", lb).addEventListener("click", function () { showPhoto(lbIndex + 1); });
  lb.addEventListener("click", function (e) { if (e.target === lb || e.target.classList.contains("lb-fig")) closeLightbox(); });
  lb.addEventListener("keydown", function (e) {
    if (e.key === "ArrowLeft") showPhoto(lbIndex - 1);
    else if (e.key === "ArrowRight") showPhoto(lbIndex + 1);
  });
  var touchX = null;
  lb.addEventListener("touchstart", function (e) { touchX = e.touches[0].clientX; }, { passive: true });
  lb.addEventListener("touchend", function (e) {
    if (touchX === null) return;
    var dx = e.changedTouches[0].clientX - touchX;
    if (Math.abs(dx) > 45) showPhoto(lbIndex + (dx < 0 ? 1 : -1));
    touchX = null;
  });

  /* ------------------------------------------------------------ reseñas */
  var reviews = D.testimonios || [];
  var track = $("#carTrack"), dots = $("#carDots"), carousel = $("#carousel"), carIndex = 0, carTimer = null, carPaused = false;
  reviews.forEach(function (r, i) {
    var stars = /\((\d)\/5\)/.exec(r.fuente || "");
    track.appendChild(el("li", { "class": "car-slide", role: "group", "aria-roledescription": "reseña",
      "aria-label": (i + 1) + " de " + reviews.length }, [
      el("blockquote", {}, [
        el("p", { text: r.texto }),
        el("footer", {}, [
          stars ? el("span", { "class": "car-stars", "aria-label": stars[1] + " de 5 estrellas", text: "★★★★★".slice(0, +stars[1]) }) : null,
          el("strong", { text: r.autor }), " · " + r.fuente
        ])
      ])
    ]));
    var dot = el("button", { type: "button", "class": "car-dot", "aria-label": "Reseña " + (i + 1) });
    dot.addEventListener("click", function () { goTo(i); });
    dots.appendChild(dot);
  });
  $("#reviewsNote").textContent = D.testimonios_nota || "";
  function goTo(i) {
    carIndex = (i + reviews.length) % reviews.length;
    track.style.transform = "translateX(" + (-100 * carIndex) + "%)";
    $$(".car-slide", track).forEach(function (s, j) { s.setAttribute("aria-hidden", String(j !== carIndex)); });
    $$(".car-dot", dots).forEach(function (d, j) { d.setAttribute("aria-current", String(j === carIndex)); });
  }
  function autoplay() {
    clearInterval(carTimer);
    if (REDUCE || reviews.length < 2) return;
    carTimer = setInterval(function () { if (!carPaused && !document.hidden) goTo(carIndex + 1); }, 6500);
  }
  if (reviews.length) {
    $(".car-prev", carousel).addEventListener("click", function () { goTo(carIndex - 1); autoplay(); });
    $(".car-next", carousel).addEventListener("click", function () { goTo(carIndex + 1); autoplay(); });
    [carousel, dots].forEach(function (n) {
      n.addEventListener("mouseenter", function () { carPaused = true; });
      n.addEventListener("mouseleave", function () { carPaused = false; });
      n.addEventListener("focusin", function () { carPaused = true; });
      n.addEventListener("focusout", function () { carPaused = false; });
    });
    carousel.addEventListener("keydown", function (e) {
      if (e.key === "ArrowLeft") goTo(carIndex - 1);
      if (e.key === "ArrowRight") goTo(carIndex + 1);
    });
    var tx = null;
    carousel.addEventListener("touchstart", function (e) { tx = e.touches[0].clientX; }, { passive: true });
    carousel.addEventListener("touchend", function (e) {
      if (tx === null) return;
      var dx = e.changedTouches[0].clientX - tx;
      if (Math.abs(dx) > 45) goTo(carIndex + (dx < 0 ? 1 : -1));
      tx = null;
    });
    goTo(0);
    autoplay();
  } else {
    $("#resenas").hidden = true;
  }

  /* ------------------------------------------------------------ sedes, horario y mapa */
  var sedesList = $("#sedesList"), mapFrame = $("#mapFrame"), mapLink = $("#mapLink"), selectedSede = mainSede();
  function mapQuery(s) { return (s && s.mapa_busqueda) || D.mapa_busqueda || D.direccion_completa; }
  function showSede(s) {
    selectedSede = s;
    $$(".sede", sedesList).forEach(function (card) { card.classList.toggle("is-current", card.getAttribute("data-sede") === s.nombre); });
    var src = "https://www.google.com/maps?q=" + encodeURIComponent(mapQuery(s)) + "&output=embed";
    if (mapFrame.getAttribute("src") !== src) {
      mapFrame.parentNode.classList.add("is-loading");
      mapFrame.setAttribute("src", src);
    }
    mapLink.href = "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(mapQuery(s));
    renderHours();
  }
  mapFrame.addEventListener("load", function () { mapFrame.parentNode.classList.remove("is-loading"); });
  SEDES.forEach(function (s) {
    var btn = el("button", { type: "button", "class": "btn btn-ghost" }, [icon("pin"), "Ver en el mapa"]);
    btn.addEventListener("click", function () { showSede(s); });
    var title = el("h3", {}, [(SEDES.length > 1 ? "Sede " : "") + s.nombre, s.nueva ? el("span", { "class": "sede-new", text: "NUEVA" }) : null]);
    sedesList.appendChild(el("div", { "class": "sede", "data-sede": s.nombre }, [
      el("div", { "class": "ticket" }, [el("div", { "class": "ticket-in" }, [
        title,
        el("p", {}, [icon("pin"), s.direccion]),
        s.horario_corto ? el("p", {}, [icon("clock"), s.horario_corto]) : null,
        SEDES.length > 1 ? btn : null
      ])])
    ]));
  });

  function renderHours() {
    var list = $("#hoursList"), badge = $("#openBadge");
    var now = nowInTZ();
    list.innerHTML = "";
    for (var d = 0; d < 7; d++) {
      var h = hoursFor(d, selectedSede);
      var isToday = d === now.weekday;
      list.appendChild(el("li", { "class": isToday ? "is-today" : null, "aria-current": isToday ? "date" : null }, [
        el("span", {}, [DAYS[d], isToday ? el("span", { "class": "today-tag", text: "HOY" }) : null]),
        el("span", { text: h ? to12(h[0]) + " – " + to12(h[1]) : "Cerrado" })
      ]));
    }
    var todayHours = hoursFor(now.weekday, selectedSede);
    var open = todayHours && now.time >= todayHours[0] && now.time < todayHours[1];
    badge.className = "open-badge " + (open ? "is-open" : "is-closed");
    if (open) badge.textContent = "Abierto ahora · hasta las " + to12(todayHours[1]);
    else {
      var label = "Cerrado";
      for (var k = 0; k < 7; k++) {
        var wd = (now.weekday + k) % 7, hh = hoursFor(wd, selectedSede);
        if (!hh || (k === 0 && now.time >= hh[0])) continue;
        label += " · abre " + (k === 0 ? "hoy" : k === 1 ? "mañana" : DAYS[wd].toLowerCase()) + " a las " + to12(hh[0]);
        break;
      }
      badge.textContent = label;
    }
  }
  if (selectedSede) showSede(selectedSede); else renderHours();
  setInterval(renderHours, 60000);

  /* ------------------------------------------------------------ animaciones al hacer scroll */
  $$(".section-head, .about-copy, .reserve-info, .booking, .contact-cards, .map").forEach(function (n) { n.classList.add("reveal"); });
  if ("IntersectionObserver" in window && !REDUCE) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        io.unobserve(entry.target);
      });
    }, { threshold: 0.12 });
    $$(".reveal").forEach(function (n) { io.observe(n); });
    var counters = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        countUp(entry.target);
        counters.unobserve(entry.target);
      });
    }, { threshold: 0.6 });
    $$("[data-count]").forEach(function (n) { counters.observe(n); });
  } else {
    $$(".reveal").forEach(function (n) { n.classList.add("is-visible"); });
  }

  /* Paralaje del collage del hero */
  if (!REDUCE) {
    var layers = $$("[data-parallax]");
    var ticking = false;
    window.addEventListener("scroll", function () {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(function () {
        var y = window.scrollY;
        if (y < 1200) layers.forEach(function (l) { l.style.transform = "translate3d(0," + (y * parseFloat(l.getAttribute("data-parallax"))) + "px,0)"; });
        ticking = false;
      });
    }, { passive: true });
  }
})();
