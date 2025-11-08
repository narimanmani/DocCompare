(function () {
  document.addEventListener("click", function (event) {
    const button = event.target.closest(".copy-link-button");
    if (!button) {
      return;
    }

    const text = button.getAttribute("data-copy-text");
    if (!text) {
      return;
    }

    event.preventDefault();
    const original = button.getAttribute("data-original-content") || button.innerHTML;

    const applyCopiedState = function () {
      button.innerHTML = "✅ Copied!";
      button.setAttribute("data-original-content", original);
      button.classList.add("bg-emerald-600");
      setTimeout(function () {
        button.innerHTML = original;
        button.classList.remove("bg-emerald-600");
      }, 1500);
    };

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(applyCopiedState).catch(applyCopiedState);
    } else {
      applyCopiedState();
    }
  });
})();
