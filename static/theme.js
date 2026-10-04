(function () {
    'use strict';

    var STORAGE_KEY = 'quiz-theme';

    // Theme registry — add new theme names here when adding themes.
    var THEMES = ['original', 'dark', 'glass', 'glass-dark', 'valorant'];

    function currentTheme() {
        var attr = document.documentElement.getAttribute('data-theme');
        return THEMES.indexOf(attr) !== -1 ? attr : 'original';
    }

    function applyTheme(theme) {
        if (THEMES.indexOf(theme) === -1) {
            theme = 'original';
        }

        if (theme === 'original') {
            document.documentElement.removeAttribute('data-theme');
        } else {
            document.documentElement.setAttribute('data-theme', theme);
        }

        document.querySelectorAll('.theme-option').forEach(function (el) {
            el.classList.toggle('active', el.getAttribute('data-theme') === theme);
        });
    }

    function init() {
        var stored = null;
        try {
            stored = localStorage.getItem(STORAGE_KEY);
        } catch (e) {
            stored = null;
        }

        applyTheme(THEMES.indexOf(stored) !== -1 ? stored : 'original');

        document.addEventListener('click', function (event) {
            var option = event.target.closest('.theme-option');
            if (!option) {
                return;
            }
            event.preventDefault();

            var theme = option.getAttribute('data-theme');
            try {
                localStorage.setItem(STORAGE_KEY, theme);
            } catch (e) {
                // Ignore storage errors (private browsing etc.)
            }
            applyTheme(theme);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
