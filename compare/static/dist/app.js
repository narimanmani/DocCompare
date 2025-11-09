(function () {
  document.addEventListener("DOMContentLoaded", function () {
    const toggleButton = document.querySelector("[data-diff-toggle]");
    if (!toggleButton) {
      return;
    }

    const showLabel =
      toggleButton.getAttribute("data-label-show") ||
      toggleButton.textContent.trim() ||
      "Show only changes";
    toggleButton.textContent = showLabel;
  });

  document.addEventListener("click", function (event) {
    const toggleButton = event.target.closest("[data-diff-toggle]");
    if (toggleButton) {
      const diffView = document.querySelector(".diff-view");
      if (!diffView) {
        return;
      }

      event.preventDefault();
      const showLabel =
        toggleButton.getAttribute("data-label-show") || "Show only changes";
      const allLabel =
        toggleButton.getAttribute("data-label-all") || "Show full comparison";
      const isActive = diffView.classList.toggle("diff-view--changes-only");
      toggleButton.setAttribute("aria-pressed", isActive ? "true" : "false");
      toggleButton.textContent = isActive ? allLabel : showLabel;
      return;
    }

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
