(function () {
  'use strict';
  var list = document.querySelector('.logbook-pagination');
  if (!list) return;
  var pages = Array.from(list.querySelectorAll('[data-page-dates]')).map(function (link) { return link.closest('li'); });
  var current = pages.findIndex(function (page) { return page.classList.contains('active'); });
  var expanded = false;

  function layout() {
    if (expanded) return;
    list.querySelectorAll('[data-expand-pages]').forEach(function (button) { button.closest('li').remove(); });
    var cellWidth = parseFloat(window.getComputedStyle(list).gridTemplateColumns.split(' ')[0]) || 48;
    var budget = Math.max(3, Math.floor(list.clientWidth / cellWidth) - 4);
    var visible = new Set([current]);
    function cost(selection) {
      var gaps = 0;
      var hidden = false;
      pages.forEach(function (page, index) {
        if (!selection.has(index) && !hidden) gaps += 1;
        hidden = !selection.has(index);
      });
      return selection.size + gaps;
    }
    var priorities = [0, pages.length - 1];
    for (var distance = 1; distance < pages.length; distance += 1) {
      if (current + distance < pages.length) priorities.push(current + distance);
      if (current - distance >= 0) priorities.push(current - distance);
    }
    priorities.forEach(function (index) {
      var candidate = new Set(visible);
      candidate.add(index);
      if (cost(candidate) <= budget) visible = candidate;
    });
    var gap = [];
    function addGap() {
      if (!gap.length) return;
      var group = gap.slice();
      var item = document.createElement('li');
      item.className = 'page-item';
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'page-link';
      button.textContent = '…';
      button.dataset.expandPages = 'true';
      button.setAttribute('aria-label', 'Show hidden page numbers');
      button.setAttribute('aria-expanded', 'false');
      button.addEventListener('click', function () {
        expanded = true;
        group.forEach(function (page) { page.hidden = false; });
        button.setAttribute('aria-expanded', 'true');
        group[0].querySelector('a').focus();
        item.remove();
      });
      item.appendChild(button);
      list.insertBefore(item, group[0]);
      gap = [];
    }
    pages.forEach(function (page, index) {
      page.hidden = !visible.has(index);
      if (page.hidden) gap.push(page);
      else addGap();
    });
    addGap();
  }
  layout();
  window.addEventListener('resize', layout);
  if (window.jQuery && window.jQuery.fn.tooltip) {
    window.jQuery('[data-page-dates]').tooltip({container: 'body', trigger: 'hover focus'});
  }
}());
