document.addEventListener('DOMContentLoaded', function () {
    var input = document.getElementById('faq-search');
    if (!input) return;

    var dropdowns = document.querySelectorAll('.sd-dropdown');
    var noResults = document.getElementById('faq-no-results');
    var fallback = document.getElementById('faq-fallback');

    // Store original HTML to restore after clearing search or when term changes
    dropdowns.forEach(function (dropdown) {
        var titleEl = dropdown.querySelector('.sd-summary-text');
        var bodyEl = dropdown.querySelector('.sd-summary-content');
        if (titleEl) dropdown.dataset.originalTitle = titleEl.innerHTML;
        if (bodyEl) dropdown.dataset.originalBody = bodyEl.innerHTML;
    });

    function highlightText(element, term) {
        if (!term || !element) return false;

        // Simple regex-based highlighting.
        var originalHTML = element.innerHTML;
        var tempDiv = document.createElement('div');
        tempDiv.innerHTML = originalHTML;

        var found = false;
        var regex = new RegExp('(' + term.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&') + ')', 'gi');

        function traverse(node) {
            if (node.nodeType === 3) { // Text node
                if (node.nodeValue.match(regex)) {
                    found = true;
                    var span = document.createElement('span');
                    span.innerHTML = node.nodeValue.replace(regex, '<span class="search-highlight">$1</span>');
                    node.parentNode.replaceChild(span, node);
                }
            } else if (node.nodeType === 1 && node.childNodes && !/(script|style)/i.test(node.tagName)) {
                // We need a stable array of children because we'll be replacing them
                var children = Array.from(node.childNodes);
                for (var i = 0; i < children.length; i++) {
                    traverse(children[i]);
                }
            }
        }

        traverse(tempDiv);
        if (found) {
            element.innerHTML = tempDiv.innerHTML;
        }
        return found;
    }

    input.addEventListener('input', function () {
        var filter = input.value.toLowerCase().trim();
        var visibleCount = 0;

        dropdowns.forEach(function (dropdown) {
            var titleEl = dropdown.querySelector('.sd-summary-text');
            var bodyEl = dropdown.querySelector('.sd-summary-content');

            // Clean up previous highlights before searching
            if (titleEl && dropdown.dataset.originalTitle !== undefined) {
                titleEl.innerHTML = dropdown.dataset.originalTitle;
            }
            if (bodyEl && dropdown.dataset.originalBody !== undefined) {
                bodyEl.innerHTML = dropdown.dataset.originalBody;
            }

            var matchTitle = highlightText(titleEl, filter);
            var matchBody = highlightText(bodyEl, filter);

            var details = dropdown.tagName.toLowerCase() === 'details' ? dropdown : dropdown.querySelector('details');

            if (filter === '' || matchTitle || matchBody) {
                dropdown.style.display = '';
                visibleCount++;

                // Fold/Unfold logic
                if (details) {
                    if (filter !== '' && (matchTitle || matchBody)) {
                        details.open = true;
                    } else if (filter === '') {
                        details.open = false;
                    }
                }
            } else {
                dropdown.style.display = 'none';
                if (details) {
                    details.open = false;
                }
            }
        });

        // Handle sections automatically
        // Find all elements that might contain dropdowns.
        // In Sphinx-design/MyST, sections are often nested. We look for the nearest common ancestor that has an H2.
        var h2s = document.querySelectorAll('h2');
        h2s.forEach(function (h2) {
            var section = h2.parentElement;
            var dropdownsInSection = section.querySelectorAll('.sd-dropdown');

            if (dropdownsInSection.length > 0) {
                var sectionVisibleCount = 0;
                dropdownsInSection.forEach(function (dd) {
                    if (dd.style.display !== 'none') sectionVisibleCount++;
                });

                if (filter !== '' && sectionVisibleCount === 0) {
                    h2.style.display = 'none';
                } else {
                    h2.style.display = '';
                }
            }
        });

        if (filter !== '' && visibleCount === 0) {
            if (noResults) noResults.style.display = 'block';
        } else {
            if (noResults) noResults.style.display = 'none';
        }
        if (fallback) fallback.style.display = 'block';
    });
});
