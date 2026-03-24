function openEdit(id, email, fullName, role, isActive) {
  document.getElementById('edit-modal-title').textContent = 'Редактировать: ' + email;
  document.getElementById('edit-form').action = '/admin/users/' + id + '/edit';
  document.getElementById('edit-full-name').value = fullName;
  document.getElementById('edit-role').value = role;
  document.getElementById('edit-active').checked = isActive;
  document.getElementById('edit-modal').style.display = 'flex';
}
function closeEdit() {
  document.getElementById('edit-modal').style.display = 'none';
}
document.getElementById('edit-modal').addEventListener('click', function(e) {
  if (e.target === this) closeEdit();
});