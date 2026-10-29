// The owner chart pages' hover readout (2026-10-29, decision 131). No library. The server writes every
// number already formatted (prices/charts.py, `Plot.hover`) into a JSON script tag, so this file only
// picks the day nearest the pointer, or the day the arrow keys reach, and shows that day's text in a
// polite live region. Without it the tables under the chart carry the same values. Served from
// prices/_chart.html only, so a page without a chart, and every public page, has no script.
(function () {
  "use strict";
  var plot = document.querySelector("[data-chart]");
  if (!plot) return;
  var source = document.getElementById(plot.getAttribute("data-chart"));
  var readout = document.getElementById(plot.getAttribute("data-readout"));
  if (!source || !readout) return;
  var data;
  try {
    data = JSON.parse(source.textContent);
  } catch (error) {
    return;
  }
  if (!data.dates || !data.dates.length) return;

  var current = -1;
  var cursor = document.createElement("span");
  cursor.className = "chart-cursor";
  cursor.hidden = true;
  cursor.setAttribute("aria-hidden", "true");
  plot.appendChild(cursor);
  var dots = data.series.map(function (line) {
    var dot = document.createElement("span");
    dot.className = "chart-dot";
    dot.hidden = true;
    dot.style.background = line.color;
    dot.setAttribute("aria-hidden", "true");
    plot.appendChild(dot);
    return dot;
  });

  plot.tabIndex = 0;
  plot.setAttribute("role", "group");
  plot.setAttribute(
    "aria-label",
    "Chart: press the left and right arrow keys to read one day at a time, Home and End for the first and last day"
  );
  readout.hidden = false;
  readout.textContent = "Point at the chart, or focus it and use the arrow keys, to read one day.";

  function lineText(line, index) {
    if (line.close[index] === null) return line.symbol + ": no close stored this day";
    var parts = [];
    if (data.rebased) parts.push(line.index[index] + " (start = 100)");
    parts.push("close " + line.close[index]);
    parts.push("adjusted close " + (line.adj[index] === null ? "not stored" : line.adj[index]));
    if (line.change[index] !== null) {
      parts.push("change " + line.change[index] + " (" + line.changePct[index] + ") from the day before, on the " + line.basis);
    }
    if (line.events[index] !== null) parts.push(line.events[index]);
    return line.symbol + ": " + parts.join(", ");
  }

  function show(index) {
    if (index < 0 || index >= data.dates.length || index === current) return;
    current = index;
    var x = data.x[index];
    cursor.hidden = false;
    cursor.style.left = x + "%";
    data.series.forEach(function (line, n) {
      var y = line.y[index];
      dots[n].hidden = y === null;
      if (y !== null) {
        dots[n].style.left = x + "%";
        dots[n].style.top = y + "%";
      }
    });
    readout.textContent = "";
    var heading = document.createElement("p");
    var strong = document.createElement("strong");
    strong.textContent = data.dates[index];
    heading.appendChild(strong);
    readout.appendChild(heading);
    data.series.forEach(function (line) {
      var p = document.createElement("p");
      p.textContent = lineText(line, index);
      readout.appendChild(p);
    });
  }

  function nearest(percent) {
    // The dates are in order, so a binary search finds the first x at or past the pointer.
    var low = 0;
    var high = data.x.length - 1;
    while (low < high) {
      var mid = (low + high) >> 1;
      if (data.x[mid] < percent) low = mid + 1;
      else high = mid;
    }
    if (low > 0 && percent - data.x[low - 1] < data.x[low] - percent) return low - 1;
    return low;
  }

  plot.addEventListener("pointermove", function (event) {
    var box = plot.getBoundingClientRect();
    if (box.width === 0) return;
    show(nearest(((event.clientX - box.left) / box.width) * 100));
  });
  plot.addEventListener("keydown", function (event) {
    var last = data.dates.length - 1;
    var start = current < 0 ? last : current;
    var next = null;
    if (event.key === "ArrowLeft") next = Math.max(0, start - 1);
    else if (event.key === "ArrowRight") next = Math.min(last, current < 0 ? last : start + 1);
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = last;
    if (next === null) return;
    event.preventDefault();
    show(next);
  });
  plot.addEventListener("focus", function () {
    if (current < 0) show(data.dates.length - 1);
  });
})();
