const _roomsMap = {};
{% for r in rooms %}
(function(){
  var hid = {{ r.hotel_id | tojson }};
  if (!_roomsMap[hid]) _roomsMap[hid] = [];
  _roomsMap[hid].push({
    id: {{ r.id }},
    label: {{ (r.number ~ " — " ~ r.name ~ " (" ~ r.base_price | int ~ " ₽/ночь)") | tojson }}
  });
})();
{% endfor %}

function filterRooms(hotelId) {
  var sel = document.getElementById('room-select');
  sel.innerHTML = '';
  var placeholder = document.createElement('option');
  placeholder.value = '';
  var list = _roomsMap[hotelId] || [];
  if (list.length === 0) {
    placeholder.textContent = '— Нет доступных номеров —';
    sel.appendChild(placeholder);
    return;
  }
  placeholder.textContent = '— Выберите номер —';
  sel.appendChild(placeholder);
  list.forEach(function(r) {
    var opt = document.createElement('option');
    opt.value = r.id;
    opt.textContent = r.label;
    sel.appendChild(opt);
  });
}