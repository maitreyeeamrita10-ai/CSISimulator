document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.hotspot-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      if(!confirm('Collect this evidence and add it to your custody log?')) e.preventDefault();
    });
  });
});
