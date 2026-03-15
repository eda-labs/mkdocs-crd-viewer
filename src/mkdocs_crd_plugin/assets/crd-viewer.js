(function () {
  function setNodeExpanded(node, expanded) {
    node.dataset.open = expanded ? "true" : "false";

    var button = node.querySelector("[data-crd-toggle-node]");
    var content = node.querySelector(".crd-viewer__content");

    if (button) {
      button.setAttribute("aria-expanded", expanded ? "true" : "false");
    }

    if (content) {
      if (expanded) {
        content.hidden = false;
        var height = content.scrollHeight;
        if (height === 0) {
          content.style.maxHeight = "none";
          return;
        }
        content.style.maxHeight = "0px";
        content.offsetHeight; /* force reflow */
        content.style.maxHeight = height + "px";
        content.addEventListener(
          "transitionend",
          function handler() {
            content.style.maxHeight = "none";
            content.removeEventListener("transitionend", handler);
          },
          { once: true }
        );
      } else {
        var height = content.scrollHeight;
        if (height === 0) {
          content.hidden = true;
          content.style.maxHeight = "";
          return;
        }
        content.style.maxHeight = height + "px";
        content.offsetHeight; /* force reflow */
        content.style.maxHeight = "0px";
        content.addEventListener(
          "transitionend",
          function handler() {
            content.hidden = true;
            content.style.maxHeight = "";
            content.removeEventListener("transitionend", handler);
          },
          { once: true }
        );
      }
    }
  }

  function setNodeExpandedImmediate(node, expanded) {
    node.dataset.open = expanded ? "true" : "false";
    var button = node.querySelector("[data-crd-toggle-node]");
    var content = node.querySelector(".crd-viewer__content");
    if (button) {
      button.setAttribute("aria-expanded", expanded ? "true" : "false");
    }
    if (content) {
      content.hidden = !expanded;
      content.style.maxHeight = "";
    }
  }

  function syncButton(viewer) {
    var button = viewer.querySelector("[data-crd-toggle-all]");
    if (!button) {
      return;
    }

    var nodes = Array.prototype.slice.call(
      viewer.querySelectorAll("[data-crd-node]")
    );
    var allExpanded =
      nodes.length > 0 &&
      nodes.every(function (node) {
        return node.dataset.open === "true";
      });

    button.dataset.expanded = allExpanded ? "true" : "false";
    button.textContent = allExpanded ? "Collapse All" : "Expand All";
  }

  function initViewer(viewer) {
    if (viewer.dataset.crdViewerReady === "true") {
      return;
    }

    viewer.dataset.crdViewerReady = "true";
    var button = viewer.querySelector("[data-crd-toggle-all]");
    var nodes = Array.prototype.slice.call(
      viewer.querySelectorAll("[data-crd-node]")
    );

    nodes.forEach(function (node) {
      setNodeExpandedImmediate(node, node.dataset.open === "true");
      var nodeButton = node.querySelector("[data-crd-toggle-node]");
      if (nodeButton) {
        nodeButton.addEventListener("click", function () {
          setNodeExpanded(node, node.dataset.open !== "true");
          syncButton(viewer);
        });
      }
    });

    if (button) {
      button.addEventListener("click", function () {
        var expand = button.dataset.expanded !== "true";
        viewer.querySelectorAll("[data-crd-node]").forEach(function (node) {
          setNodeExpandedImmediate(node, expand);
        });
        syncButton(viewer);
      });
    }

    syncButton(viewer);
  }

  function init(root) {
    root.querySelectorAll("[data-crd-viewer-root]").forEach(initViewer);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      init(document);
    });
  } else {
    init(document);
  }

  if (
    typeof document$ !== "undefined" &&
    typeof document$.subscribe === "function"
  ) {
    document$.subscribe(function () {
      init(document);
    });
  }
})();
