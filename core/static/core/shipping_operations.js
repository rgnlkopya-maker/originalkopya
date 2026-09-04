(function () {
  if (window.__moliShippingOpsLoaded) return;
  window.__moliShippingOpsLoaded = true;

  const OPS = [
    { value: 'kargodan_geri_geldi', label: '📦 Kargodan Geri Geldi', cls: 'btn-soft-warning', confirm: 'Ürünün kargodan geri geldiğini kaydetmek istiyor musunuz?' },
    { value: 'iade_geldi', label: '↩️ İade Geldi', cls: 'btn-soft-warning', confirm: 'Müşteri iadesini kaydetmek istiyor musunuz?' }
  ];

  function findShippingCard() {
    const cards = Array.from(document.querySelectorAll('#uretim-paneli .stage-card'));
    return cards.find(card => (card.textContent || '').includes('Hazır & Sevkiyat')) || null;
  }

  function installButtons() {
    const card = findShippingCard();
    if (!card) return;
    const actions = card.querySelector('.stage-actions');
    const sentButton = actions && Array.from(actions.querySelectorAll('button')).find(b => (b.textContent || '').includes('Gönderildi'));
    if (!actions || !sentButton || actions.dataset.shippingOpsInstalled === '1') return;

    const updateUrl = sentButton.getAttribute('hx-get');
    if (!updateUrl || !window.htmx) return;

    OPS.forEach(op => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'soft-btn ' + op.cls;
      btn.textContent = op.label;
      btn.addEventListener('click', function () {
        if (op.confirm && !window.confirm(op.confirm)) return;
        window.htmx.ajax('GET', updateUrl, {
          target: '#uretim-paneli',
          swap: 'innerHTML',
          values: { stage: 'sevkiyat_durum', value: op.value }
        });
      });
      actions.appendChild(btn);
    });

    actions.dataset.shippingOpsInstalled = '1';
  }

  function prettifyTimeline() {
    const replacements = {
      'Sevkiyat Durum → Kargodan Geri Geldi': 'Kargodan Geri Geldi',
      'Sevkiyat Durum → Iade Geldi': 'İade Geldi',
      'Sevkiyat Durum → Yanlis Sevkiyat': 'Yanlış Sevkiyat',
      'Sevkiyat Durum → Tekrar Gonderildi': 'Tekrar Gönderildi'
    };
    document.querySelectorAll('#uretim-paneli .timeline-main').forEach(el => {
      const text = (el.textContent || '').trim().replace(/\s+/g, ' ');
      if (replacements[text]) el.textContent = replacements[text];
    });
  }

  function refresh() {
    installButtons();
    prettifyTimeline();
  }

  document.addEventListener('DOMContentLoaded', refresh);
  document.body.addEventListener('htmx:afterSwap', refresh);
  setTimeout(refresh, 0);
})();
