// EMG CRM: pequenos comportamentos sem framework.
document.addEventListener('DOMContentLoaded', () => {
  // máscara simples de CNPJ/CPF/moeda
  document.querySelectorAll('[data-mask=cnpj]').forEach(i => i.addEventListener('input', () => {
    let v = i.value.replace(/\D/g, '').slice(0, 14);
    v = v.replace(/^(\d{2})(\d)/, '$1.$2').replace(/^(\d{2})\.(\d{3})(\d)/, '$1.$2.$3')
         .replace(/\.(\d{3})(\d)/, '.$1/$2').replace(/(\d{4})(\d)/, '$1-$2');
    i.value = v;
  }));
  document.querySelectorAll('[data-mask=cpf]').forEach(i => i.addEventListener('input', () => {
    let v = i.value.replace(/\D/g, '').slice(0, 11);
    v = v.replace(/(\d{3})(\d)/, '$1.$2').replace(/(\d{3})(\d)/, '$1.$2').replace(/(\d{3})(\d{1,2})$/, '$1-$2');
    i.value = v;
  }));
  // confirmar ações
  document.querySelectorAll('form[data-confirm]').forEach(f => f.addEventListener('submit', e => {
    if (!confirm(f.dataset.confirm)) e.preventDefault();
  }));
  // sócios dinâmicos
  const add = document.getElementById('add-socio');
  if (add) add.addEventListener('click', () => {
    const tpl = document.getElementById('socio-tpl');
    const node = tpl.content.cloneNode(true);
    document.getElementById('socios').appendChild(node);
    document.querySelectorAll('[data-mask=cpf]').forEach(i => i.addEventListener('input', () => {
      let v = i.value.replace(/\D/g, '').slice(0, 11);
      i.value = v.replace(/(\d{3})(\d)/, '$1.$2').replace(/(\d{3})(\d)/, '$1.$2').replace(/(\d{3})(\d{1,2})$/, '$1-$2');
    }));
  });
  // auto-refresh enquanto enriquece
  const pend = document.querySelector('[data-refresh]');
  if (pend) setTimeout(() => location.reload(), parseInt(pend.dataset.refresh, 10) || 6000);
  // forma de pagamento "outra"
  const fp = document.getElementById('forma_pagamento');
  if (fp) { const o = document.getElementById('forma-outra'); const t = () => { o.style.display = fp.value === 'outra' ? '' : 'none'; }; fp.addEventListener('change', t); t(); }
});
