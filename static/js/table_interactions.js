(function () {
  'use strict';
  // Track logical columns rather than cellIndex: IACRA has merged headers/cells.
  function columnGrid(rows) {
    var grid = [], positions = new Map();
    Array.from(rows).forEach(function (row, r) {
      if (!grid[r]) grid[r] = [];
      var column = 0;
      Array.from(row.cells).forEach(function (cell) {
        while (grid[r][column]) column++;
        var width = cell.colSpan || 1;
        var height = cell.rowSpan === 0 ? rows.length - r : cell.rowSpan || 1;
        positions.set(cell, {start: column, end: column + width});
        for (var y = r; y < Math.min(rows.length, r + height); y++) {
          if (!grid[y]) grid[y] = [];
          for (var x = column; x < column + width; x++) grid[y][x] = cell;
        }
        column += width;
      });
    });
    return positions;
  }
  function scrollEdges(width, viewport, left) {
    return {left: left > 1, right: width - viewport - left > 1};
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {columnGrid: columnGrid, scrollEdges: scrollEdges};
    return;
  }
  var currentCell = null, marked = [], currentRow = null;
  function clear() {
    if (currentCell) currentCell.classList.remove('table-cell-hover');
    marked.forEach(function (cell) { cell.classList.remove('table-column-hover'); });
    if (currentRow) currentRow.classList.remove('table-row-hover');
    currentCell = null; currentRow = null; marked = [];
  }
  function highlight(event) {
    if (event.pointerType === 'touch') return;
    var cell = event.target.closest('td,th');
    var table = cell && cell.closest('table.table,table#logbook');
    var cellOnly = table && table.closest('[data-table-tracking="cell"]');
    if (!table || table.closest('[data-table-tracking="off"]') || (!cellOnly && cell.classList.contains('iacra-shaded'))) { clear(); return; }
    if (currentCell === cell) return;
    clear();
    currentCell = cell;
    cell.classList.add('table-cell-hover');
    if (cellOnly) return;
    var positions = columnGrid(table.rows), target = positions.get(cell);
    if (!target) return;
    if (table.id !== 'logbook') {
      positions.forEach(function (range, candidate) {
        if (range.start < target.end && range.end > target.start) {
          candidate.classList.add('table-column-hover'); marked.push(candidate);
        }
      });
    }
    if (cell.parentElement.parentElement.tagName !== 'THEAD') {
      currentRow = cell.parentElement;
      currentRow.classList.add('table-row-hover');
    }
  }
  document.addEventListener('pointerover', highlight);
  document.addEventListener('mouseover', highlight);
  document.addEventListener('focusin', highlight);
  document.addEventListener('pointerout', function (event) {
    if (currentCell) {
      var table = currentCell.closest('table');
      if (!table || !table.contains(event.relatedTarget)) clear();
    }
  });
  document.addEventListener('focusout', function (event) {
    if (currentCell) {
      var table = currentCell.closest('table');
      if (!table || !table.contains(event.relatedTarget)) clear();
    }
  });

  var updates = [];
  document.querySelectorAll('table.table,table#logbook').forEach(function (table) {
    // Do not add multiple overlays around nested tables or shared scroll regions.
    if (table.parentElement.closest('table')) return;
    var scroller = table.closest('.table-responsive,.iacra-grid-scroll');
    if (!scroller) {
      scroller = document.createElement('div'); scroller.className = 'table-responsive';
      table.before(scroller); scroller.appendChild(table);
    }
    if (scroller.dataset.scrollIndicators) return;
    scroller.dataset.scrollIndicators = 'true';
    var shell = document.createElement('div'); shell.className = 'table-scroll-shell';
    scroller.before(shell); shell.appendChild(scroller);
    function arrow(direction, label, symbol) {
      var button = document.createElement('button'); button.type = 'button';
      button.className = 'table-scroll-hint table-scroll-' + direction;
      button.setAttribute('aria-label', label); button.title = label;
      button.textContent = symbol; button.hidden = true;
      button.addEventListener('click', function () {
        scroller.scrollBy({left: (direction === 'left' ? -1 : 1) * scroller.clientWidth * .75,
          behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'});
      });
      shell.appendChild(button); return button;
    }
    var left = arrow('left', 'Scroll left for more columns', '‹');
    var right = arrow('right', 'Scroll right for more columns', '›');
    function update() {
      var edges = scrollEdges(scroller.scrollWidth, scroller.clientWidth, scroller.scrollLeft);
      left.hidden = !edges.left; right.hidden = !edges.right;
    }
    scroller.addEventListener('scroll', update, {passive: true});
    if (typeof ResizeObserver !== 'undefined') {
      var observer = new ResizeObserver(update); observer.observe(scroller); observer.observe(table);
    }
    updates.push(update); update();
  });
  function updateAll() { updates.forEach(function (update) { update(); }); }
  window.addEventListener('resize', updateAll);
  window.addEventListener('load', updateAll);
  document.addEventListener('shown.bs.tab', updateAll);
}());
