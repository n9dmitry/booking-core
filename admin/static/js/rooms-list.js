function goAddRoom() {
  const hotelId = document.getElementById('add-room-hotel').value;
  if (!hotelId) { alert('Сначала выберите отель'); return; }
  window.location.href = '/admin/hotels/' + hotelId + '/rooms/add';
}