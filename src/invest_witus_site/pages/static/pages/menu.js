// The header's Menu button (decision 115). Without this file the button stays `hidden` and the
// links show as a wrapped list, so the menu works with JavaScript off. With it, the button shows
// and, below 40rem (the stylesheet's rule), the list folds until the button opens it. A native
// <button>, so Enter and Space work; Escape closes the open menu and returns focus to the button.
(function () {
  "use strict";
  var nav = document.querySelector("[data-menu]");
  if (!nav) return;
  var button = nav.querySelector(".menu-toggle");
  var list = button && document.getElementById(button.getAttribute("aria-controls"));
  if (!button || !list) return;

  function setOpen(open) {
    button.setAttribute("aria-expanded", open ? "true" : "false");
    nav.classList.toggle("is-open", open);
  }

  nav.classList.add("js-menu");
  button.hidden = false;
  setOpen(false);

  button.addEventListener("click", function () {
    setOpen(button.getAttribute("aria-expanded") !== "true");
  });
  nav.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && button.getAttribute("aria-expanded") === "true") {
      setOpen(false);
      button.focus();
    }
  });
})();
