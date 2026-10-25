// Intranet: login, navegación por hash y módulos construidos desde configuración.
// Todo el contenido se pinta con createElement/textContent (nunca innerHTML con datos).
(function () {
  'use strict';

  var D = JSON.parse(document.getElementById('negocio').textContent);
  var TOKEN_KEY = 'tbfIntranetToken';
  var SEDES = (D.sedes || []).map(function (s) { return s.nombre; });
  var MULTI_SEDE = SEDES.length > 1;
  var $ = function (id) { return document.getElementById(id); };

  // --------------------------------------------------------------- utilidades
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (key) {
      var v = attrs[key];
      if (v === null || v === undefined || v === false) return;
      if (key === 'text') node.textContent = v;
      else if (key === 'className') node.className = v;
      else if (key.indexOf('on') === 0) node.addEventListener(key.slice(2), v);
      else node.setAttribute(key, v === true ? '' : v);
    });
    (children || []).forEach(function (c) {
      if (c === null || c === undefined || c === false) return;
      node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return node;
  }
  function money(v) {
    if (v === null || v === undefined || v === '') return '—';
    return '$ ' + Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  }
  function fmtDate(iso) {
    if (!iso) return '';
    var p = iso.slice(0, 10).split('-');
    return p[2] + '/' + p[1] + '/' + p[0];
  }
  function todayIso() {
    try {
      return new Intl.DateTimeFormat('en-CA', { timeZone: D.zona_horaria || 'UTC', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
    } catch (e) { return D.hoy; }
  }
  function waUrl(phone, message) {
    var digits = String(phone || '').replace(/\D/g, '');
    if (!digits) return null;
    if (digits.length === 10 && D.indicativo_pais) digits = D.indicativo_pais + digits;
    return 'https://wa.me/' + digits + (message ? '?text=' + encodeURIComponent(message) : '');
  }
  function waButton(phone, message, label) {
    var url = waUrl(phone, message);
    if (!url) return null;
    return el('a', { className: 'btn btn-sm btn-wa', href: url, target: '_blank', rel: 'noopener', text: label || 'WhatsApp' });
  }
  function confirmMessage(a) {
    return 'Hola ' + a.name.split(' ')[0] + ', te confirmamos tu cita en ' + D.nombre + ': ' + a.service +
      ' el ' + fmtDate(a.date) + ' a las ' + a.time + (a.sede && MULTI_SEDE ? ' (sede ' + a.sede + ')' : '') + '. ¡Te esperamos!';
  }
  function dot(color) {
    var s = el('span', { className: 'dot', 'aria-hidden': 'true' });
    if (color && /^#[0-9a-fA-F]{6}$/.test(color)) s.style.backgroundColor = color;
    return s;
  }
  function staffCell(name, color) {
    if (!name) return el('span', { className: 'muted', text: 'Sin preferencia' });
    return el('span', { className: 'staff-cell' }, [dot(color), name]);
  }

  var STATUS_LABELS = { pendiente: 'Pendiente', confirmada: 'Confirmada', completada: 'Completada', cancelada: 'Cancelada', no_asistio: 'No asistió' };
  var APPT_STATUSES = Object.keys(STATUS_LABELS);
  function statusTag(s) { return el('span', { className: 'tag tag-' + s, text: STATUS_LABELS[s] || s }); }

  var memoryToken = null;
  function token() { try { return sessionStorage.getItem(TOKEN_KEY) || memoryToken; } catch (e) { return memoryToken; } }
  function setToken(t) {
    memoryToken = t;
    try { if (t) sessionStorage.setItem(TOKEN_KEY, t); else sessionStorage.removeItem(TOKEN_KEY); } catch (e) { /* sin almacenamiento */ }
  }

  function api(method, url, body) {
    var headers = { 'Accept': 'application/json' };
    if (token()) headers.Authorization = 'Bearer ' + token();
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    return fetch(url, { method: method, headers: headers, body: body !== undefined ? JSON.stringify(body) : undefined })
      .then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (data) {
          if (res.status === 401 && url !== '/api/auth/login') {
            logout('Tu sesión venció. Inicia sesión de nuevo.');
            throw new Error('Sesión vencida');
          }
          if (!res.ok) throw new Error(data.error || 'Error ' + res.status);
          return data;
        });
      }, function () { throw new Error('Sin conexión con el servidor.'); });
  }

  var toastTimer;
  function toast(message, kind) {
    var t = $('toast');
    t.textContent = message;
    t.className = 'toast' + (kind === 'err' ? ' toast-err' : '');
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.hidden = true; }, 3200);
  }

  // --------------------------------------------------------------- sesión
  function showLogin(message) {
    $('app-view').hidden = true;
    $('login-view').hidden = false;
    $('login-error').textContent = message || '';
    $('login-user').focus();
  }
  function showApp(user) {
    $('login-view').hidden = true;
    $('app-view').hidden = false;
    $('current-user').textContent = user ? 'Sesión: ' + user.username : '';
    route();
  }
  function logout(message) {
    setToken(null);
    showLogin(message);
  }

  $('login-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var btn = e.target.querySelector('button[type="submit"]');
    var username = $('login-user').value.trim();
    var password = $('login-pass').value;
    if (!username || !password) { $('login-error').textContent = 'Escribe usuario y contraseña.'; return; }
    btn.disabled = true;
    $('login-error').textContent = '';
    api('POST', '/api/auth/login', { username: username, password: password }).then(function (data) {
      setToken(data.token);
      $('login-pass').value = '';
      showApp(data.user);
    }).catch(function (err) {
      $('login-error').textContent = err.message;
    }).then(function () { btn.disabled = false; });
  });
  $('logout-btn').addEventListener('click', function () { logout('Sesión cerrada.'); });

  var sideToggle = $('sideToggle');
  sideToggle.addEventListener('click', function () {
    var open = sideToggle.getAttribute('aria-expanded') !== 'true';
    sideToggle.setAttribute('aria-expanded', String(open));
    $('sidebar').classList.toggle('is-open', open);
  });

  // --------------------------------------------------------------- modal genérico
  var modal = $('modal');
  var saveBtn = $('modal-save');
  var modalSubmit = null;

  function fieldInput(f, value) {
    var id = 'mf-' + f.name;
    var input;
    if (f.type === 'textarea') {
      input = el('textarea', { id: id, name: f.name, rows: '3', maxlength: f.maxlength || null });
      input.value = value == null ? (f.default || '') : value;
    } else if (f.type === 'select') {
      input = el('select', { id: id, name: f.name });
      if (!f.required) input.appendChild(el('option', { value: '', text: f.placeholder || '—' }));
      (f.options || []).forEach(function (o) { input.appendChild(el('option', { value: String(o.value), text: o.label })); });
      input.value = value == null ? (f.required && f.options && f.options[0] ? String(f.options[0].value) : '') : String(value);
    } else if (f.type === 'checkbox') {
      input = el('input', { id: id, name: f.name, type: 'checkbox' });
      input.checked = value == null ? !!f.default : !!Number(value);
      return el('div', { className: 'check' }, [input, el('label', { for: id, text: f.label })]);
    } else {
      input = el('input', {
        id: id, name: f.name, type: f.type || 'text', maxlength: f.maxlength || null,
        min: f.min != null ? String(typeof f.min === 'function' ? f.min() : f.min) : null,
        max: f.max != null ? String(f.max) : null, step: f.step || null, placeholder: f.placeholder || null
      });
      var v = value == null ? (f.default != null ? f.default : '') : value;
      input.value = typeof v === 'function' ? v() : v;
    }
    if (f.required) input.required = true;
    return el('div', { className: 'field' + (f.wide ? ' field-wide' : '') }, [
      el('label', { for: id }, [f.label, f.required ? '' : el('span', { className: 'opt', text: ' (opcional)' })]),
      input,
      f.help ? el('small', { className: 'muted', text: f.help }) : null
    ]);
  }

  function openModal() {
    if (typeof modal.showModal === 'function') modal.showModal(); else modal.setAttribute('open', '');
  }
  function openForm(opts) {
    saveBtn.hidden = false;
    $('modal-title').textContent = opts.title;
    $('modal-error').textContent = '';
    var box = $('modal-fields');
    box.textContent = '';
    opts.fields.forEach(function (f) { box.appendChild(fieldInput(f, opts.values ? opts.values[f.name] : null)); });
    modalSubmit = function () {
      var data = {};
      var missing = [];
      opts.fields.forEach(function (f) {
        var input = modal.querySelector('[name="' + f.name + '"]');
        var v;
        if (f.type === 'checkbox') v = input.checked;
        else if (f.type === 'number') v = input.value === '' ? null : Number(input.value);
        else v = input.value.trim();
        if (f.required && (v === '' || v === null)) missing.push(f.label);
        data[f.name] = v;
      });
      if (missing.length) return Promise.reject(new Error('Falta: ' + missing.join(', ') + '.'));
      return opts.onSubmit(data);
    };
    openModal();
    var first = box.querySelector('input, select, textarea');
    if (first) first.focus();
  }
  function showInfo(title, node) {
    $('modal-title').textContent = title;
    $('modal-error').textContent = '';
    var box = $('modal-fields');
    box.textContent = '';
    box.appendChild(node);
    modalSubmit = function () { return Promise.resolve(); };
    saveBtn.hidden = true;
    openModal();
  }
  function closeModal() { if (typeof modal.close === 'function') modal.close(); else modal.removeAttribute('open'); }
  Array.prototype.forEach.call(modal.querySelectorAll('[data-close]'), function (b) { b.addEventListener('click', closeModal); });
  modal.addEventListener('click', function (e) { if (e.target === modal) closeModal(); });
  $('modal-form').addEventListener('submit', function (e) {
    e.preventDefault();
    saveBtn.disabled = true;
    $('modal-error').textContent = '';
    Promise.resolve().then(modalSubmit).then(function () {
      closeModal();
      toast('Guardado.');
      route();
    }).catch(function (err) {
      $('modal-error').textContent = err.message;
    }).then(function () { saveBtn.disabled = false; });
  });

  // --------------------------------------------------------------- tablas
  function table(columns, rows, emptyMessage) {
    if (!rows.length) return el('div', { className: 'empty' }, [el('p', { text: emptyMessage })]);
    var thead = el('thead', {}, [el('tr', {}, columns.map(function (c) { return el('th', { scope: 'col', text: c.label }); }))]);
    var tbody = el('tbody', {}, rows.map(function (row) {
      return el('tr', {}, columns.map(function (c) {
        var v = c.render ? c.render(row) : row[c.key];
        var cell = el('td', { 'data-label': c.label });
        if (v instanceof Node) cell.appendChild(v); else cell.textContent = v == null ? '' : String(v);
        return cell;
      }));
    }));
    return el('div', { className: 'table-wrap' }, [el('table', { className: 'table' }, [thead, tbody])]);
  }

  function confirmDelete(what, url) {
    if (!window.confirm('¿Eliminar ' + what + '? Esta acción no se puede deshacer.')) return;
    api('DELETE', url).then(function () { toast('Eliminado.'); route(); })
      .catch(function (err) { toast(err.message, 'err'); });
  }

  function inlineSelect(label, options, value, onChange) {
    var s = el('select', { className: 'inline-select', 'aria-label': label });
    options.forEach(function (o) { s.appendChild(el('option', { value: o.value, text: o.label })); });
    s.value = value;
    s.setAttribute('data-value', value);
    s.addEventListener('change', function () {
      var previous = s.getAttribute('data-value');
      s.disabled = true;
      onChange(s.value).then(function () {
        s.setAttribute('data-value', s.value);
        toast('Estado actualizado: ' + s.options[s.selectedIndex].text + '.');
      }).catch(function (err) {
        s.value = previous;
        toast(err.message, 'err');
      }).then(function () { s.disabled = false; });
    });
    return s;
  }

  // --------------------------------------------------------------- vistas
  var body = $('view-body');
  var actions = $('view-actions');

  function setView(title) {
    $('view-title').textContent = title;
    document.title = title + ' · Intranet · ' + D.nombre;
    actions.textContent = '';
    body.textContent = '';
    body.appendChild(el('p', { className: 'muted', text: 'Cargando…' }));
  }
  function showError(err) {
    if (err.message === 'Sesión vencida') return;
    body.textContent = '';
    body.appendChild(el('div', { className: 'empty' }, [el('p', { text: 'No se pudo cargar: ' + err.message })]));
  }
  function card(label, value, hint) {
    return el('div', { className: 'kpi' }, [
      el('p', { className: 'kpi-label', text: label }),
      el('p', { className: 'kpi-value', text: String(value) }),
      hint ? el('p', { className: 'kpi-hint', text: hint }) : null
    ]);
  }

  // Dashboard
  function renderDashboard() {
    setView('Dashboard');
    actions.appendChild(el('a', { className: 'btn btn-ghost btn-sm', href: '/', target: '_blank', rel: 'noopener', text: 'Ver sitio' }));
    api('GET', '/api/dashboard').then(function (d) {
      body.textContent = '';
      var revenueHint = 'Citas no canceladas de ' + d.month;
      if (d.appointments_without_price) revenueHint += ' · ' + d.appointments_without_price + ' sin precio en el catálogo';
      body.appendChild(el('div', { className: 'kpis' }, [
        card('Citas hoy', d.appointments_today),
        card('Citas esta semana', d.appointments_week, 'Hoy y los próximos 6 días'),
        card('Ingresos estimados del mes', money(d.revenue_month_estimated), revenueHint),
        card('Clientes nuevos', d.new_clients_30d, 'Últimos 30 días · ' + d.clients + ' en total'),
        card('Gastos del mes', money(d.expenses_month)),
        card('Insumos con stock bajo', d.low_stock.length)
      ]));
      var grid = el('div', { className: 'dash-grid' });
      var next = el('section', { className: 'panel' }, [el('h2', { text: 'Próximas citas' }), table([
        { label: 'Fecha', render: function (r) { return fmtDate(r.date) + ' · ' + r.time; } },
        { label: 'Cliente', key: 'name' },
        { label: 'Servicio', key: 'service' },
        { label: 'Barbero', render: function (r) { return staffCell(r.staff_name, r.staff_color); } },
        { label: 'Estado', render: function (r) { return statusTag(r.status); } },
        { label: '', render: function (r) { return waButton(r.phone, confirmMessage(r), 'Confirmar'); } }
      ], d.next_appointments, 'No hay citas próximas. Las reservas del sitio aparecerán aquí.')]);
      var top = el('section', { className: 'panel' }, [el('h2', { text: 'Servicios más pedidos' }),
        d.top_services.length ? el('ol', { className: 'top-list' }, d.top_services.map(function (s) {
          return el('li', {}, [el('span', { text: s.name }), el('strong', { text: s.total + (s.total === 1 ? ' cita' : ' citas') })]);
        })) : el('p', { className: 'muted', text: 'Aún no hay datos (últimos 90 días).' })]);
      grid.appendChild(next);
      grid.appendChild(top);
      body.appendChild(grid);
      if (d.low_stock.length) {
        body.appendChild(el('section', { className: 'panel' }, [el('h2', { text: 'Stock bajo' }), table([
          { label: 'Producto', key: 'name' },
          { label: 'Cantidad', render: function (r) { return r.quantity + ' ' + (r.unit || ''); } },
          { label: 'Mínimo', key: 'min_stock' }
        ], d.low_stock, '')]));
      }
    }).catch(showError);
  }

  // Citas
  var apptScope = 'upcoming';
  var apptStatus = '';

  function renderAppointments() {
    setView('Citas');
    var scopeSel = el('select', { 'aria-label': 'Mostrar', className: 'inline-select' }, [
      el('option', { value: 'upcoming', text: 'Próximas' }),
      el('option', { value: 'past', text: 'Pasadas' }),
      el('option', { value: 'all', text: 'Todas' })
    ]);
    scopeSel.value = apptScope;
    scopeSel.addEventListener('change', function () { apptScope = scopeSel.value; renderAppointments(); });
    var statusSel = el('select', { 'aria-label': 'Filtrar por estado', className: 'inline-select' },
      [el('option', { value: '', text: 'Todos los estados' })].concat(APPT_STATUSES.map(function (s) {
        return el('option', { value: s, text: STATUS_LABELS[s] });
      })));
    statusSel.value = apptStatus;
    statusSel.addEventListener('change', function () { apptStatus = statusSel.value; renderAppointments(); });
    actions.appendChild(scopeSel);
    actions.appendChild(statusSel);
    actions.appendChild(el('button', { className: 'btn btn-primary btn-sm', type: 'button', text: 'Crear cita', onclick: addAppointment }));

    api('GET', '/api/appointments?scope=' + apptScope + (apptStatus ? '&status=' + apptStatus : '')).then(function (rows) {
      body.textContent = '';
      var cols = [
        { label: 'Fecha', render: function (r) { return el('span', {}, [fmtDate(r.date), el('br'), el('strong', { text: r.time })]); } },
        { label: 'Cliente', render: function (r) { return el('span', {}, [r.name, el('br'), el('small', { className: 'muted', text: r.phone })]); } },
        { label: 'Servicio', key: 'service' }
      ];
      if (MULTI_SEDE) cols.push({ label: 'Sede', key: 'sede' });
      cols = cols.concat([
        { label: 'Barbero', render: function (r) { return staffCell(r.staff_name || r.barber, r.staff_color); } },
        { label: 'Precio', render: function (r) { return money(r.price); } },
        { label: 'Notas', key: 'notes' },
        { label: 'Estado', render: function (r) {
          return inlineSelect('Estado de la cita de ' + r.name, APPT_STATUSES.map(function (s) { return { value: s, label: STATUS_LABELS[s] }; }), r.status, function (v) {
            return api('PATCH', '/api/appointments/' + r.id, { status: v });
          });
        } },
        { label: 'Acciones', render: function (r) {
          return el('div', { className: 'row-actions' }, [
            waButton(r.phone, confirmMessage(r), 'Confirmar'),
            el('button', { className: 'btn btn-sm btn-danger', type: 'button', text: 'Eliminar',
              onclick: function () { confirmDelete('la cita de ' + r.name + ' (' + fmtDate(r.date) + ' ' + r.time + ')', '/api/appointments/' + r.id); } })
          ]);
        } }
      ]);
      body.appendChild(table(cols, rows, apptScope === 'upcoming'
        ? 'No hay citas próximas. Cuando alguien reserve desde el sitio aparecerá aquí, o usa «Crear cita».'
        : 'No hay citas en esta vista.'));
    }).catch(showError);
  }

  function addAppointment() {
    Promise.all([api('GET', '/api/services'), api('GET', '/api/staff')]).then(function (res) {
      var services = res[0].filter(function (s) { return s.active; });
      var staff = res[1].filter(function (s) { return s.active; });
      var fields = [
        { name: 'name', label: 'Nombre del cliente', required: true, maxlength: 80 },
        { name: 'phone', label: 'Teléfono', type: 'tel', required: true, maxlength: 20 },
        { name: 'service_id', label: 'Servicio', type: 'select', required: true,
          options: services.map(function (s) { return { value: s.id, label: s.name + (s.price != null ? ' · ' + money(s.price) : '') }; }) }
      ];
      if (MULTI_SEDE) fields.push({ name: 'sede', label: 'Sede', type: 'select', required: true, options: SEDES.map(function (s) { return { value: s, label: s }; }) });
      fields = fields.concat([
        { name: 'staff_id', label: 'Barbero', type: 'select', placeholder: 'Sin preferencia',
          options: staff.map(function (s) { return { value: s.id, label: s.name }; }) },
        { name: 'date', label: 'Fecha', type: 'date', required: true, min: todayIso, default: todayIso },
        { name: 'time', label: 'Hora', type: 'time', required: true, step: 300,
          help: 'La cita manual no está limitada al horario de atención.' },
        { name: 'notes', label: 'Notas', type: 'textarea', maxlength: 300, wide: true },
        { name: 'status', label: 'Estado', type: 'select', required: true,
          options: APPT_STATUSES.map(function (s) { return { value: s, label: STATUS_LABELS[s] }; }) }
      ]);
      openForm({
        title: 'Crear cita',
        fields: fields,
        onSubmit: function (data) {
          data.service_id = Number(data.service_id);
          data.staff_id = data.staff_id ? Number(data.staff_id) : null;
          return api('POST', '/api/appointments', data);
        }
      });
    }).catch(function (err) { toast(err.message, 'err'); });
  }

  // Módulos CRUD genéricos, construidos desde configuración.
  function crudModule(cfg) {
    return function render() {
      setView(cfg.title);
      actions.appendChild(el('button', { className: 'btn btn-primary btn-sm', type: 'button', text: 'Agregar ' + cfg.singular,
        onclick: function () {
          openForm({ title: 'Agregar ' + cfg.singular, fields: cfg.fields,
            onSubmit: function (data) { return api('POST', cfg.url, cfg.prepare ? cfg.prepare(data) : data); } });
        } }));
      api('GET', cfg.url).then(function (rows) {
        body.textContent = '';
        if (cfg.summary) { var s = cfg.summary(rows); if (s) body.appendChild(s); }
        var columns = cfg.columns.concat([{ label: 'Acciones', render: function (r) {
          var box = el('div', { className: 'row-actions' });
          (cfg.rowActions || []).forEach(function (a) {
            var node = a.render ? a.render(r) : el('button', { className: 'btn btn-sm btn-ghost', type: 'button',
              text: typeof a.label === 'function' ? a.label(r) : a.label, onclick: function () { a.run(r); } });
            if (node) box.appendChild(node);
          });
          box.appendChild(el('button', { className: 'btn btn-sm btn-ghost', type: 'button', text: 'Editar',
            onclick: function () {
              openForm({ title: 'Editar ' + cfg.singular, fields: cfg.fields, values: r,
                onSubmit: function (data) { return api('PATCH', cfg.url + '/' + r.id, cfg.prepare ? cfg.prepare(data) : data); } });
            } }));
          box.appendChild(el('button', { className: 'btn btn-sm btn-danger', type: 'button', text: 'Eliminar',
            onclick: function () { confirmDelete(cfg.singular + ' «' + r[cfg.nameKey || 'name'] + '»', cfg.url + '/' + r.id); } }));
          return box;
        } }]);
        body.appendChild(table(columns, rows, cfg.empty));
      }).catch(showError);
    };
  }

  function yesNo(v) { return el('span', { className: v ? 'tag tag-confirmada' : 'tag', text: v ? 'Sí' : 'No' }); }
  function toggleField(url, field, row) {
    var data = {};
    data[field] = !row[field];
    api('PATCH', url + '/' + row.id, data).then(function () {
      toast(data[field] ? 'Activado.' : 'Desactivado.');
      route();
    }).catch(function (err) { toast(err.message, 'err'); });
  }
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
    var ta = el('textarea', { readonly: true });
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } finally { document.body.removeChild(ta); }
    return Promise.resolve();
  }
  function monthTotal(rows, key, dateKey) {
    var month = todayIso().slice(0, 7);
    return rows.filter(function (r) { return (r[dateKey] || '').slice(0, 7) === month; })
      .reduce(function (sum, r) { return sum + (Number(r[key]) || 0); }, 0);
  }

  var MODULES = {
    dashboard: renderDashboard,
    citas: renderAppointments,
    personal: crudModule({
      title: 'Personal', singular: 'profesional', url: '/api/staff',
      empty: 'Aún no hay profesionales. Agrégalos para que los clientes puedan elegirlos al reservar.',
      columns: [
        { label: 'Nombre', render: function (r) { return staffCell(r.name, r.color); } },
        { label: 'Cargo', key: 'role' },
        { label: 'Sedes', render: function (r) { return r.sedes || 'Todas'; } },
        { label: 'Teléfono', key: 'phone' },
        { label: 'Calendario', render: function (r) { return r.calendar_id ? 'Configurado' : '—'; } },
        { label: 'Activo', render: function (r) { return yesNo(r.active); } }
      ],
      rowActions: [{ label: function (r) { return r.active ? 'Desactivar' : 'Activar'; }, run: function (r) { toggleField('/api/staff', 'active', r); } }],
      fields: [
        { name: 'name', label: 'Nombre', required: true, maxlength: 80 },
        { name: 'role', label: 'Cargo', maxlength: 60, default: 'Barbero' },
        { name: 'phone', label: 'Teléfono', type: 'tel', maxlength: 20 },
        { name: 'email', label: 'Correo', type: 'email', maxlength: 120 },
        { name: 'color', label: 'Color en la agenda', type: 'color', default: '#f2c230' },
        { name: 'sedes', label: 'Sedes donde atiende', maxlength: 300,
          help: 'Separadas por coma. Vacío = todas. Sedes: ' + SEDES.join(', ') },
        { name: 'calendar_id', label: 'ID de Google Calendar', maxlength: 200,
          help: 'Opcional. El calendario debe estar compartido con la cuenta que autorizó la integración.' },
        { name: 'active', label: 'Activo (visible al reservar)', type: 'checkbox', default: true }
      ]
    }),
    clientes: crudModule({
      title: 'Clientes', singular: 'cliente', url: '/api/clients',
      empty: 'Aún no hay clientes. Se crean solos cuando alguien reserva, o agrégalos aquí.',
      columns: [
        { label: 'Nombre', key: 'name' },
        { label: 'Teléfono', key: 'phone' },
        { label: 'Correo', key: 'email' },
        { label: 'Notas', key: 'notes' },
        { label: 'Desde', render: function (r) { return fmtDate(r.created_at); } }
      ],
      fields: [
        { name: 'name', label: 'Nombre', required: true, maxlength: 80 },
        { name: 'phone', label: 'Teléfono', type: 'tel', required: true, maxlength: 20 },
        { name: 'email', label: 'Correo', type: 'email', maxlength: 120 },
        { name: 'notes', label: 'Notas', type: 'textarea', maxlength: 500, wide: true }
      ],
      rowActions: [
        { render: function (r) { return waButton(r.phone, 'Hola ' + r.name.split(' ')[0] + ', te escribimos de ' + D.nombre + '.'); } },
        { label: 'Ficha', run: function (r) {
          api('GET', '/api/clients/' + r.id + '/appointments').then(function (rows) {
            var done = rows.filter(function (a) { return a.status === 'completada'; }).length;
            showInfo('Ficha de ' + r.name, el('div', { className: 'client-card' }, [
              el('dl', { className: 'client-facts' }, [
                el('dt', { text: 'Teléfono' }), el('dd', { text: r.phone }),
                el('dt', { text: 'Cliente desde' }), el('dd', { text: fmtDate(r.created_at) }),
                el('dt', { text: 'Citas' }), el('dd', { text: rows.length + ' en total · ' + done + ' completadas' }),
                r.notes ? el('dt', { text: 'Notas' }) : null, r.notes ? el('dd', { text: r.notes }) : null
              ]),
              table([
                { label: 'Fecha', render: function (a) { return fmtDate(a.date) + ' · ' + a.time; } },
                { label: 'Servicio', key: 'service' },
                { label: 'Barbero', render: function (a) { return staffCell(a.staff_name || a.barber, a.staff_color); } },
                { label: 'Estado', render: function (a) { return statusTag(a.status); } }
              ], rows, 'Este cliente aún no tiene citas.')
            ]));
          }).catch(function (err) { toast(err.message, 'err'); });
        } }
      ]
    }),
    catalogo: crudModule({
      title: 'Catálogo de servicios', singular: 'servicio', url: '/api/services',
      empty: 'No hay servicios. Agrega al menos uno para que el formulario de reservas funcione.',
      columns: [
        { label: 'Orden', key: 'sort_order' },
        { label: 'Servicio', render: function (r) { return el('span', {}, [r.name, el('br'), el('small', { className: 'muted', text: r.categories || '' })]); } },
        { label: 'Precio', render: function (r) { return r.price == null ? el('span', { className: 'muted', text: 'Sin publicar' }) : (r.price_from ? 'Desde ' : '') + money(r.price); } },
        { label: 'Duración', render: function (r) { return r.duration + ' min'; } },
        { label: 'Activo', render: function (r) { return yesNo(r.active); } }
      ],
      rowActions: [{ label: function (r) { return r.active ? 'Ocultar' : 'Mostrar'; }, run: function (r) { toggleField('/api/services', 'active', r); } }],
      fields: [
        { name: 'name', label: 'Nombre', required: true, maxlength: 100 },
        { name: 'description', label: 'Descripción', type: 'textarea', maxlength: 500, wide: true },
        { name: 'price', label: 'Precio (COP)', type: 'number', min: 0, step: 1000,
          help: 'Déjalo vacío para mostrar «' + (D.precio_nulo_texto || 'Consultar') + '».' },
        { name: 'price_from', label: 'Mostrar como «Desde»', type: 'checkbox' },
        { name: 'duration', label: 'Duración (minutos)', type: 'number', required: true, min: 5, max: 600, step: 5, default: 30,
          help: 'Se usa para que la última hora disponible termine antes del cierre.' },
        { name: 'categories', label: 'Categorías', maxlength: 200, help: 'Separadas por coma. Ej.: ' + (D.categorias || []).join(', ') },
        { name: 'image', label: 'Foto (URL https:// o images/archivo.webp)', maxlength: 500 },
        { name: 'sort_order', label: 'Orden', type: 'number', min: 0, step: 1, default: 0 },
        { name: 'active', label: 'Activo (visible en el sitio)', type: 'checkbox', default: true }
      ]
    }),
    inventario: crudModule({
      title: 'Inventario', singular: 'producto', url: '/api/inventory',
      empty: 'No hay productos registrados. Agrégalos para controlar el stock y recibir alertas.',
      summary: function (rows) {
        var low = rows.filter(function (r) { return r.quantity <= r.min_stock; });
        return low.length ? el('p', { className: 'alert', text: '⚠ ' + low.length + ' producto(s) en o por debajo del mínimo: ' + low.map(function (r) { return r.name; }).join(', ') + '.' }) : null;
      },
      columns: [
        { label: 'Producto', key: 'name' },
        { label: 'Stock', render: function (r) {
          var low = r.quantity <= r.min_stock;
          return el('span', { className: low ? 'tag tag-cancelada' : '', text: r.quantity + ' ' + (r.unit || '') + (low ? ' · bajo' : '') });
        } },
        { label: 'Mínimo', key: 'min_stock' },
        { label: 'Notas', key: 'notes' }
      ],
      fields: [
        { name: 'name', label: 'Producto', required: true, maxlength: 100 },
        { name: 'quantity', label: 'Cantidad', type: 'number', required: true, min: 0, step: 'any' },
        { name: 'unit', label: 'Unidad (ej. frascos, ml)', maxlength: 30 },
        { name: 'min_stock', label: 'Stock mínimo', type: 'number', min: 0, step: 'any', default: 0 },
        { name: 'notes', label: 'Notas', type: 'textarea', maxlength: 300, wide: true }
      ]
    }),
    gastos: crudModule({
      title: 'Gastos', singular: 'gasto', url: '/api/expenses', nameKey: 'description',
      empty: 'No hay gastos registrados. Regístralos para ver el total del mes.',
      summary: function (rows) {
        return el('div', { className: 'kpis kpis-1' }, [card('Total del mes', money(monthTotal(rows, 'amount', 'date')), todayIso().slice(0, 7))]);
      },
      columns: [
        { label: 'Fecha', render: function (r) { return fmtDate(r.date); } },
        { label: 'Descripción', key: 'description' },
        { label: 'Categoría', key: 'category' },
        { label: 'Monto', render: function (r) { return money(r.amount); } },
        { label: 'Nota', key: 'notes' }
      ],
      fields: [
        { name: 'description', label: 'Descripción', required: true, maxlength: 120 },
        { name: 'category', label: 'Categoría', maxlength: 60, placeholder: 'Arriendo, insumos, servicios…' },
        { name: 'amount', label: 'Monto (COP)', type: 'number', required: true, min: 0, step: 100 },
        { name: 'date', label: 'Fecha', type: 'date', required: true, default: todayIso },
        { name: 'notes', label: 'Nota', type: 'textarea', maxlength: 300, wide: true }
      ]
    }),
    marketing: crudModule({
      title: 'Marketing', singular: 'campaña', url: '/api/campaigns',
      empty: 'No hay campañas. Crea una para planear tus mensajes de WhatsApp o redes.',
      columns: [
        { label: 'Campaña', key: 'name' },
        { label: 'Canal', key: 'channel' },
        { label: 'Fechas', render: function (r) { return [fmtDate(r.starts_on), fmtDate(r.ends_on)].filter(Boolean).join(' → ') || '—'; } },
        { label: 'Mensaje', render: function (r) { return el('span', { className: 'clip', text: r.message || '' }); } },
        { label: 'Estado', render: function (r) {
          return inlineSelect('Estado de ' + r.name, [{ value: 'borrador', label: 'Borrador' }, { value: 'activa', label: 'Activa' }, { value: 'finalizada', label: 'Finalizada' }], r.status, function (v) {
            return api('PATCH', '/api/campaigns/' + r.id, { status: v });
          });
        } }
      ],
      rowActions: [{ label: 'Copiar mensaje', run: function (r) {
        if (!r.message) { toast('Esta campaña no tiene mensaje.', 'err'); return; }
        copyText(r.message).then(function () { toast('Mensaje copiado. Pégalo en WhatsApp.'); });
      } }],
      fields: [
        { name: 'name', label: 'Nombre', required: true, maxlength: 100 },
        { name: 'channel', label: 'Canal', maxlength: 40, default: 'WhatsApp' },
        { name: 'starts_on', label: 'Inicio', type: 'date' },
        { name: 'ends_on', label: 'Fin', type: 'date' },
        { name: 'message', label: 'Mensaje de WhatsApp', type: 'textarea', maxlength: 1000, wide: true,
          default: 'Hola, te escribimos de ' + D.nombre + '. ' },
        { name: 'status', label: 'Estado', type: 'select', required: true,
          options: [{ value: 'borrador', label: 'Borrador' }, { value: 'activa', label: 'Activa' }, { value: 'finalizada', label: 'Finalizada' }] }
      ]
    }),
    descuentos: crudModule({
      title: 'Descuentos', singular: 'código', url: '/api/discount-codes', nameKey: 'code',
      empty: 'No hay códigos de descuento. Crea uno para tus promociones.',
      columns: [
        { label: 'Código', render: function (r) { return el('code', { text: r.code }); } },
        { label: 'Descuento', render: function (r) { return r.kind === 'porcentaje' ? r.value + ' %' : money(r.value); } },
        { label: 'Vigencia', render: function (r) {
          if (!r.starts_on && !r.expires_on) return 'Sin límite';
          return (r.starts_on ? fmtDate(r.starts_on) : '…') + ' → ' + (r.expires_on ? fmtDate(r.expires_on) : '…');
        } },
        { label: 'Usos', render: function (r) { return r.uses + (r.max_uses ? ' / ' + r.max_uses : ''); } },
        { label: 'Activo', render: function (r) { return yesNo(r.active); } }
      ],
      rowActions: [{ label: function (r) { return r.active ? 'Desactivar' : 'Activar'; },
        run: function (r) { toggleField('/api/discount-codes', 'active', r); } }],
      fields: [
        { name: 'code', label: 'Código (ej. BIENVENIDA10)', required: true, maxlength: 30 },
        { name: 'description', label: 'Descripción', maxlength: 200 },
        { name: 'kind', label: 'Tipo', type: 'select', required: true,
          options: [{ value: 'porcentaje', label: 'Porcentaje' }, { value: 'monto', label: 'Monto fijo (COP)' }] },
        { name: 'value', label: 'Valor', type: 'number', required: true, min: 1, step: 1 },
        { name: 'starts_on', label: 'Desde', type: 'date' },
        { name: 'expires_on', label: 'Vence', type: 'date' },
        { name: 'max_uses', label: 'Usos máximos', type: 'number', min: 1, step: 1 },
        { name: 'uses', label: 'Usos registrados', type: 'number', min: 0, step: 1, default: 0 },
        { name: 'active', label: 'Activo', type: 'checkbox', default: true }
      ]
    })
  };

  // --------------------------------------------------------------- navegación por hash
  function route() {
    if ($('app-view').hidden) return;
    var key = (location.hash || '#dashboard').slice(1);
    if (!MODULES[key]) { location.replace('#dashboard'); return; }
    Array.prototype.forEach.call(document.querySelectorAll('#side-nav a'), function (a) {
      if (a.getAttribute('href') === '#' + key) a.setAttribute('aria-current', 'page');
      else a.removeAttribute('aria-current');
    });
    sideToggle.setAttribute('aria-expanded', 'false');
    $('sidebar').classList.remove('is-open');
    MODULES[key]();
  }
  window.addEventListener('hashchange', function () {
    if (modal.hasAttribute('open')) closeModal();
    route();
    $('view').focus({ preventScroll: true });
  });

  // --------------------------------------------------------------- arranque
  if (token()) {
    api('GET', '/api/auth/me').then(function (d) { showApp(d.user); })
      .catch(function (err) { if (err.message !== 'Sesión vencida') showLogin('No se pudo verificar la sesión: ' + err.message); });
  } else {
    showLogin();
  }
})();
