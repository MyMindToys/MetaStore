(function () {
  'use strict';

  var STORAGE_KEY = 'metastore-theme';
  var DARK = 'dark';
  var LIGHT = 'light';

  function normalizeStored(raw) {
    if (raw === 'dark' || raw === 'bright') {
      return DARK;
    }
    if (raw === LIGHT) {
      return LIGHT;
    }
    return null;
  }

  function getStoredTheme() {
    try {
      return normalizeStored(localStorage.getItem(STORAGE_KEY));
    } catch (e) {
      return null;
    }
  }

  function setStoredTheme(theme) {
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (e) {
      /* ignore */
    }
  }

  function applyTheme(theme) {
    var root = document.documentElement;
    if (theme === DARK) {
      root.setAttribute('data-theme', DARK);
    } else {
      root.removeAttribute('data-theme');
    }
    updateToggleLabel(theme);
  }

  function currentTheme() {
    return document.documentElement.getAttribute('data-theme') === DARK ? DARK : LIGHT;
  }

  function updateToggleLabel(theme) {
    var btn = document.getElementById('themeToggle');
    if (!btn) return;
    var isDark = theme === DARK;
    btn.setAttribute('aria-pressed', isDark ? 'true' : 'false');
    btn.title = isDark ? 'Классическая тема' : 'Тёмная тема';
    btn.textContent = isDark ? '◻ Классика' : '☾ Тёмная';
  }

  function initToggle() {
    var btn = document.getElementById('themeToggle');
    if (!btn) return;
    updateToggleLabel(currentTheme());
    btn.addEventListener('click', function () {
      var next = currentTheme() === DARK ? LIGHT : DARK;
      applyTheme(next);
      setStoredTheme(next);
    });
  }

  window.MetaStoreTheme = {
    apply: applyTheme,
    initToggle: initToggle,
    getStored: getStoredTheme,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initToggle);
  } else {
    initToggle();
  }
})();
