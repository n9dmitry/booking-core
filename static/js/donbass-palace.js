/* ════════════════════════════════════════════
   DONBASS PALACE — Frontend Logic
   API endpoint: /ext
   Token: Bearer <hotel-token>
   ════════════════════════════════════════════ */

const API_BASE = 'http://localhost:8000/ext';
const API_TOKEN = 'M22X94_XxgcsHM81D-K5bJ-R-fLRj7TkGvQ2RPcBRAlFv41s1s1vQmyjHe-a_v06';

const headers = {
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${API_TOKEN}`,
};

// ── State ──────────────────────────────────
let allRooms = [];
let searchParams = {};
let selectedRoom = null;
let timerInterval = null;

// ── Date defaults ──────────────────────────
(function initDates() {
  const today = new Date();
  const tomorrow = new Date(today); tomorrow.setDate(tomorrow.getDate() + 1);
  const dayAfter = new Date(today); dayAfter.setDate(dayAfter.getDate() + 2);
  document.getElementById('s-checkin').value  = fmt(tomorrow);
  document.getElementById('s-checkout').value = fmt(dayAfter);
  document.getElementById('s-checkin').min    = fmt(tomorrow);
  document.getElementById('s-checkout').min   = fmt(dayAfter);

  document.getElementById('s-checkin').addEventListener('change', function() {
    const next = new Date(this.value); next.setDate(next.getDate() + 1);
    const outEl = document.getElementById('s-checkout');
    outEl.min = fmt(next);
    if (outEl.value && new Date(outEl.value) <= new Date(this.value)) {
      outEl.value = fmt(next);
    }
  });
})();

function fmt(d) {
  return d.toISOString().split('T')[0];
}

function fmtDate(s) {
  if (!s) return '';
  const [y,m,d] = s.split('-');
  return `${d}.${m}.${y}`;
}

function fmtMoney(v) {
  return Number(v).toLocaleString('ru-RU') + ' ₽';
}

function nights(ci, co) {
  return Math.max(Math.round((new Date(co) - new Date(ci)) / 86400000), 1);
}

// ── Room categories by name ─────────────────
function roomCategory(name) {
  const n = name.toLowerCase();
  if (n.includes('сюит') || n.includes('suite') || n.includes('люкс') || n.includes('lux') || n.includes('presidential')) return 'suite';
  if (n.includes('делюкс') || n.includes('deluxe') || n.includes('superior')) return 'deluxe';
  return 'standard';
}

// ── Search ──────────────────────────────────
async function searchRooms() {
  const ci = document.getElementById('s-checkin').value;
  const co = document.getElementById('s-checkout').value;
  const adults   = parseInt(document.getElementById('s-adults').value);
  const children = parseInt(document.getElementById('s-children').value);

  if (!ci || !co) { alert('Укажите даты заезда и выезда'); return; }
  if (new Date(co) <= new Date(ci)) { alert('Дата выезда должна быть позже даты заезда'); return; }

  searchParams = { check_in: ci, check_out: co, adults, children };

  document.getElementById('rooms-grid').innerHTML = `
    <div class="rooms-loading">
      <div class="spinner-large"></div>
      Проверяем доступность номеров...
    </div>`;

  document.getElementById('rooms').scrollIntoView({ behavior: 'smooth', block: 'start' });

  try {
    const url = new URL(`${API_BASE}/rooms/available`);
    url.searchParams.set('check_in', ci);
    url.searchParams.set('check_out', co);
    url.searchParams.set('adults', adults);
    url.searchParams.set('children', children);

    const res = await fetch(url, { headers });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    allRooms = data.data || [];
    document.getElementById('rooms-filters').style.display = 'flex';
    renderRooms(allRooms);
  } catch (e) {
    document.getElementById('rooms-grid').innerHTML = `
      <div class="rooms-empty">
        ⚠️ Не удалось загрузить номера. Проверьте подключение к серверу.<br>
        <small style="color:var(--text-dim);margin-top:8px;display:block">${e.message}</small>
      </div>`;
  }
}

// ── Render rooms ────────────────────────────
function renderRooms(rooms) {
  const grid = document.getElementById('rooms-grid');
  if (!rooms.length) {
    grid.innerHTML = `<div class="rooms-empty">😔 Нет доступных номеров на выбранные даты.<br><small style="margin-top:8px;display:block">Попробуйте другие даты.</small></div>`;
    return;
  }

  const ci = searchParams.check_in;
  const co = searchParams.check_out;
  const n = ci && co ? nights(ci, co) : 1;

  grid.innerHTML = rooms.map(r => {
    const avail = r.is_available;
    const cat = roomCategory(r.name);
    const priceTotal = r.base_price * n;

    const photos = Array.isArray(r.photos) && r.photos.length ? r.photos : null;
    const imgHtml = photos
      ? `<img class="room-img" src="${photos[0]}" alt="${r.name}" onerror="this.parentElement.innerHTML='<div class=room-img-placeholder>🛏️</div>'">`
      : `<div class="room-img-placeholder">🛏️</div>`;

    return `
    <div class="room-card ${avail ? '' : 'unavailable'}" 
         data-category="${cat}"
         data-available="${avail}"
         onclick="${avail ? `openBooking(${JSON.stringify(r).replace(/"/g,'&quot;')})` : ''}">
      ${imgHtml}
      <div class="room-body">
        <div class="room-tags">
          <span class="room-tag ${avail ? 'tag-available' : 'tag-unavailable'}">
            ${avail ? '✓ Доступен' : '✗ Занят'}
          </span>
          ${r.floor ? `<span class="room-tag tag-floor">${r.floor} этаж</span>` : ''}
        </div>
        <div class="room-name">${r.name}</div>
        <div class="room-num">Номер ${r.number}</div>
        <div class="room-features">
          <span class="room-feature">👥 до ${r.capacity_adults} взр.</span>
          ${r.capacity_children ? `<span class="room-feature">👶 ${r.capacity_children} дет.</span>` : ''}
          ${r.area_sqm ? `<span class="room-feature">📐 ${r.area_sqm} м²</span>` : ''}
        </div>
        ${r.description ? `<div class="room-desc">${r.description.slice(0,100)}${r.description.length>100?'...':''}</div>` : ''}
        <div class="room-footer">
          <div class="room-price">
            <div class="price-val">${fmtMoney(r.base_price)} <span>/ ночь</span></div>
            ${n > 1 ? `<div class="price-total">Итого за ${n} ночей: ${fmtMoney(priceTotal)}</div>` : ''}
          </div>
          ${avail ? `<button class="btn-book" onclick="event.stopPropagation(); openBooking(${JSON.stringify(r).replace(/"/g,'&quot;')})">Забронировать</button>` : '<span style="font-size:0.78rem;color:var(--text-dim)">Недоступен</span>'}
        </div>
      </div>
    </div>`;
  }).join('');
}

// ── Filter ──────────────────────────────────
function filterRooms(filter, el) {
  document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
  el.classList.add('active');

  let filtered = allRooms;
  if (filter === 'available') filtered = allRooms.filter(r => r.is_available);
  else if (filter !== 'all') filtered = allRooms.filter(r => roomCategory(r.name) === filter);
  renderRooms(filtered);
}

// ── Booking modal ───────────────────────────
function openBooking(room) {
  selectedRoom = room;
  const ci = searchParams.check_in;
  const co = searchParams.check_out;
  const n  = ci && co ? nights(ci, co) : 1;
  const total = room.base_price * n;

  document.getElementById('modal-room-name').textContent = room.name;
  document.getElementById('modal-room-sub').textContent  = `Номер ${room.number} · ${room.capacity_adults} взр.`;
  document.getElementById('sum-name').textContent   = room.name;
  document.getElementById('sum-dates').textContent  = ci && co
    ? `${fmtDate(ci)} — ${fmtDate(co)} · ${n} ночей`
    : 'Даты не указаны';
  document.getElementById('sum-price').textContent  = fmtMoney(total);

  document.getElementById('modal-form-wrap').style.display = 'block';
  document.getElementById('modal-success').style.display = 'none';
  document.getElementById('form-error').style.display = 'none';
  document.getElementById('form-error').textContent = '';
  document.getElementById('booking-modal').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  document.getElementById('booking-modal').classList.remove('open');
  document.body.style.overflow = '';
  if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
}

function handleModalClick(e) {
  if (e.target === document.getElementById('booking-modal')) closeModal();
}

// ── Submit booking ──────────────────────────
async function submitBooking() {
  const btn = document.getElementById('submit-btn');
  const errEl = document.getElementById('form-error');

  const fields = {
    name:      document.getElementById('f-name').value.trim(),
    bdate:     document.getElementById('f-bdate').value,
    phone:     document.getElementById('f-phone').value.trim(),
    email:     document.getElementById('f-email').value.trim(),
    series:    document.getElementById('f-series').value.trim(),
    pnum:      document.getElementById('f-pnum').value.trim(),
    issuedBy:  document.getElementById('f-issued-by').value.trim(),
    issuedDate:document.getElementById('f-issued-date').value,
    reg:       document.getElementById('f-reg').value.trim(),
    comment:   document.getElementById('f-comment').value.trim(),
  };

  const ci = searchParams.check_in;
  const co = searchParams.check_out;

  const missing = [];
  if (!fields.name)       missing.push('ФИО');
  if (!fields.bdate)      missing.push('Дата рождения');
  if (!fields.phone)      missing.push('Телефон');
  if (!fields.email)      missing.push('Email');
  if (!fields.series || fields.series.length !== 4) missing.push('Серия паспорта (4 цифры)');
  if (!fields.pnum   || fields.pnum.length   !== 6) missing.push('Номер паспорта (6 цифр)');
  if (!fields.issuedBy)   missing.push('Кем выдан');
  if (!fields.issuedDate) missing.push('Дата выдачи');
  if (!fields.reg)        missing.push('Адрес прописки');
  if (!ci || !co)         missing.push('Даты (выполните поиск)');

  if (missing.length) {
    errEl.textContent = 'Заполните обязательные поля: ' + missing.join(', ');
    errEl.style.display = 'block';
    return;
  }

  errEl.style.display = 'none';
  btn.classList.add('loading');
  btn.disabled = true;

  try {
    const payload = {
      room_id:    selectedRoom.id,
      check_in:   ci,
      check_out:  co,
      occupancy: {
        adults:   parseInt(document.getElementById('s-adults').value),
        children: parseInt(document.getElementById('s-children').value),
      },
      guest: {
        full_name:   fields.name,
        birth_date:  fields.bdate,
        phone:       fields.phone,
        email:       fields.email,
        passport: {
          series:       fields.series,
          number:       fields.pnum,
          issued_by:    fields.issuedBy,
          issued_date:  fields.issuedDate,
          registration: fields.reg,
        },
      },
      comment: fields.comment || null,
    };

    const res = await fetch(`${API_BASE}/booking`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || data.message || `Ошибка ${res.status}`);
    }

    const booking = data.data;
    const n = nights(ci, co);

    document.getElementById('modal-form-wrap').style.display = 'none';
    document.getElementById('modal-success').style.display = 'block';
    document.getElementById('success-booking-id').textContent = `Бронь № ${booking.booking_id.slice(0,8).toUpperCase()}`;
    document.getElementById('success-details').innerHTML = `
      <strong style="color:#fff">${selectedRoom.name}</strong><br>
      Заезд: ${fmtDate(ci)} &nbsp;→&nbsp; Выезд: ${fmtDate(co)}<br>
      Ночей: ${n} · Сумма: <strong style="color:var(--gold2)">${fmtMoney(booking.total_amount)}</strong>
    `;

    if (booking.expires_at) {
      const expireTime = new Date(booking.expires_at).getTime();
      function updateTimer() {
        const left = Math.max(0, expireTime - Date.now());
        const m = Math.floor(left / 60000);
        const s = Math.floor((left % 60000) / 1000);
        document.getElementById('timer-countdown').textContent =
          `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
        if (left === 0) {
          clearInterval(timerInterval);
          document.getElementById('success-timer').innerHTML = '⌛ Время оплаты истекло. Бронь аннулирована.';
        }
      }
      updateTimer();
      timerInterval = setInterval(updateTimer, 1000);
    }

    setTimeout(() => searchRooms(), 500);

  } catch (e) {
    errEl.textContent = e.message;
    errEl.style.display = 'block';
  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
  }
}

// ── Auto-load rooms on page load ────────────
window.addEventListener('load', function() {
  searchRooms();
});

// ── Keyboard ────────────────────────────────
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') closeModal();
});

// ── Header transparency on scroll ───────────
window.addEventListener('scroll', function() {
  const h = document.getElementById('header');
  h.style.background = window.scrollY > 60
    ? 'rgba(10,11,24,0.97)'
    : 'rgba(10,11,24,0.85)';
});
