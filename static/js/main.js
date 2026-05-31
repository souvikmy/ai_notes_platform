// ═══════════════════════════════════════
//  NOTEVERSE — MAIN JS
// ═══════════════════════════════════════

// Global Smart Search in navbar
const globalSearchInput = document.getElementById('globalSearch');
const searchResultsDiv = document.getElementById('searchResults');

let searchDebounce;
if (globalSearchInput) {
  globalSearchInput.addEventListener('input', () => {
    clearTimeout(searchDebounce);
    const q = globalSearchInput.value.trim();
    if (!q) { closeSearch(); return; }
    searchDebounce = setTimeout(() => doGlobalSearch(q), 400);
  });

  globalSearchInput.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeSearch();
    if (e.key === 'Enter') window.location = `/feed?search=${encodeURIComponent(globalSearchInput.value)}`;
  });

  document.addEventListener('click', e => {
    if (!e.target.closest('#navSearch')) closeSearch();
  });
}

async function doGlobalSearch(q) {
  try {
    const res = await fetch(`/api/feed?search=${encodeURIComponent(q)}&page=1`);
    const notes = await res.json();
    renderSearchDropdown(notes.slice(0, 5), q);
  } catch { }
}

function renderSearchDropdown(notes, q) {
  if (notes.length === 0) {
    searchResultsDiv.innerHTML = `<div class="sd-item"><span style="color:var(--muted)">No notes found for "${q}"</span></div>`;
  } else {
    searchResultsDiv.innerHTML = notes.map(n => `
      <div class="sd-item" onclick="window.location='/note/${n.id}'">
        <div class="note-avatar" style="background:${n.avatar_color};width:28px;height:28px;font-size:0.75rem;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700">
          ${n.username[0].toUpperCase()}
        </div>
        <div>
          <div class="sd-item-title">${highlight(n.title, q)}</div>
          <div class="sd-item-meta">${n.username} · ${n.subject || 'General'}</div>
        </div>
      </div>
    `).join('');
  }
  searchResultsDiv.classList.add('open');
}

function highlight(text, q) {
  const regex = new RegExp(`(${q})`, 'gi');
  return text.replace(regex, '<mark style="background:rgba(108,99,255,0.25);color:var(--accent);border-radius:2px">$1</mark>');
}

function closeSearch() {
  searchResultsDiv.classList.remove('open');
  searchResultsDiv.innerHTML = '';
}

// ── Animate elements on scroll ──
const observer = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.style.opacity = '1';
      entry.target.style.transform = 'translateY(0)';
    }
  });
}, { threshold: 0.1 });

document.querySelectorAll('.feature-card, .note-card').forEach(el => {
  el.style.opacity = '0';
  el.style.transform = 'translateY(20px)';
  el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
  observer.observe(el);
});

// ── Toast notifications ──
function showToast(msg, type = 'info') {
  const toast = document.createElement('div');
  toast.style.cssText = `
    position:fixed;bottom:2rem;right:2rem;z-index:9999;
    background:${type==='error'?'rgba(252,92,101,0.95)':'rgba(67,184,156,0.95)'};
    color:#fff;padding:0.85rem 1.5rem;border-radius:12px;
    font-family:'Syne',sans-serif;font-weight:600;font-size:0.9rem;
    box-shadow:0 8px 32px rgba(0,0,0,0.4);animation:slideInRight 0.3s ease;
  `;
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => { toast.style.animation = 'fadeOut 0.3s ease'; setTimeout(() => toast.remove(), 300); }, 2500);
}

// Inject toast animations
const style = document.createElement('style');
style.textContent = `
  @keyframes slideInRight { from { opacity:0; transform:translateX(100px); } to { opacity:1; transform:translateX(0); } }
  @keyframes fadeOut { from { opacity:1; } to { opacity:0; } }
`;
document.head.appendChild(style);

// ── Navbar scroll effect ──
window.addEventListener('scroll', () => {
  const nav = document.querySelector('.navbar');
  if (nav) nav.style.borderBottomColor = window.scrollY > 10 ? 'var(--border)' : 'transparent';
});

function deleteNote(noteId) {
    if (!confirm("Are you sure you want to delete this note?")) return;

    fetch(`/api/delete/${noteId}`, {
        method: "POST"
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert("Deleted successfully!");

            // Remove from UI (no reload needed)
            document.getElementById(`note-${noteId}`).remove();
        } else {
            alert(data.error || "Error deleting note");
        }
    })
    .catch(error => {
        console.error("Error:", error);
    });
}
