(function () {
  function sizeHeader() {
    document.querySelectorAll('.iacra-grid').forEach(function (table) {
      const first = table.tHead && table.tHead.rows[0];
      if (first) table.style.setProperty('--iacra-header-height', first.getBoundingClientRect().height + 'px');
    });
  }
  document.addEventListener('DOMContentLoaded', sizeHeader);
  document.addEventListener('shown.bs.tab', sizeHeader);
  window.addEventListener('resize', sizeHeader);
}());
