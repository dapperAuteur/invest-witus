// The floating Help bubble (decision 151), signed-in pages only: the public pages carry no script, and
// there the bubble is a plain link to /report/. Without this file (or without <dialog> support) the link
// stays and works. With it, the link hides and a native <button> opens the report form in a modal
// <dialog>: focus moves to the first choice, Escape (the dialog's own cancel) or Close shuts it, a click
// on the dimmed backdrop shuts it, and focus returns to the button.
(function () {
  "use strict";
  var dialog = document.getElementById("help-dialog");
  var button = document.querySelector("[data-help-button]");
  var link = document.querySelector("[data-help-link]");
  if (!dialog || !button || !link || typeof dialog.showModal !== "function") return;
  var closer = dialog.querySelector("[data-help-close]");

  link.hidden = true;
  button.hidden = false;

  button.addEventListener("click", function () {
    dialog.showModal();
    var first = dialog.querySelector("input[type=radio]:checked, input[type=radio], textarea");
    if (first) first.focus();
  });
  if (closer) {
    closer.addEventListener("click", function () {
      dialog.close();
    });
  }
  // The inner box covers the dialog, so a click whose target is the dialog itself is the backdrop.
  dialog.addEventListener("click", function (event) {
    if (event.target === dialog) dialog.close();
  });
  dialog.addEventListener("close", function () {
    button.focus();
  });
})();
