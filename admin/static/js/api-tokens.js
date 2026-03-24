function copyToken() {
  const t = document.getElementById('token-display');
  if (!t) return;
  navigator.clipboard.writeText(t.textContent.trim()).then(() => {
    const fb = document.getElementById('copy-feedback');
    fb.style.opacity = '1';
    setTimeout(() => fb.style.opacity = '0', 2000);
  });
}