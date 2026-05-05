(function () {
  document.querySelectorAll("[data-copy-target]").forEach(function (copyBtn) {
    copyBtn.addEventListener("click", function () {
      var id = copyBtn.getAttribute("data-copy-target");
      var block = id ? document.getElementById(id) : null;
      if (!block) return;
      var text = block.textContent.replace(/\u00a0/g, " ").trim();
      var label = copyBtn.getAttribute("aria-label") || "Copy";

      function done() {
        copyBtn.classList.add("done");
        copyBtn.setAttribute("aria-label", "Copied");
        setTimeout(function () {
          copyBtn.classList.remove("done");
          copyBtn.setAttribute("aria-label", label);
        }, 1800);
      }

      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () {
          window.prompt("Copy:", text);
        });
      } else {
        window.prompt("Copy:", text);
      }
    });
  });
})();
