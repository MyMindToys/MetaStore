/**
 * Заполняет поля формы метаданными выбранного в браузере файла (без загрузки на сервер).
 */
(function () {
  'use strict';

  function setField(form, name, value) {
    const el = form.querySelector('[name="' + name + '"]');
    if (el && !el.readOnly && !el.disabled) {
      el.value = value != null ? String(value) : '';
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }

  function toDatetimeLocal(d) {
    const pad = function (n) {
      return String(n).padStart(2, '0');
    };
    return (
      d.getFullYear() +
      '-' +
      pad(d.getMonth() + 1) +
      '-' +
      pad(d.getDate()) +
      'T' +
      pad(d.getHours()) +
      ':' +
      pad(d.getMinutes())
    );
  }

  async function sha256Hex(file) {
    const buf = await file.arrayBuffer();
    const hash = await crypto.subtle.digest('SHA-256', buf);
    return Array.from(new Uint8Array(hash))
      .map(function (b) {
        return b.toString(16).padStart(2, '0');
      })
      .join('');
  }

  /** При выборе папки файлов несколько — берём совпадение с полем «Название», иначе первый. */
  function resolveFile(fileInput, form, mode) {
    const list = fileInput.files;
    if (!list || !list.length) return null;
    if (list.length === 1) return list[0];
    if (mode === 'material') {
      const want = form.querySelector('[name="file_name"]');
      const name = want && want.value ? String(want.value).trim() : '';
      if (name) {
        for (let i = 0; i < list.length; i++) {
          if (list[i].name === name) return list[i];
        }
      }
    }
    return list[0];
  }

  window.catalogAutofillFromFile = async function (fileInput, form, options) {
    options = options || {};
    const file = resolveFile(fileInput, form, options.mode);
    if (!file || !form) return;

    const fullName = file.name || '';
    const lastDot = fullName.lastIndexOf('.');
    const ext = lastDot > 0 ? fullName.slice(lastDot + 1).toLowerCase() : '';
    const baseName = lastDot > 0 ? fullName.slice(0, lastDot) : fullName;
    const dt = new Date(file.lastModified);
    const maxHash = options.maxHashBytes != null ? options.maxHashBytes : 250 * 1024 * 1024;
    const doHash = options.hashChecksum === true && file.size <= maxHash;

    if (options.mode === 'fileresource') {
      setField(form, 'file_name', fullName);
      setField(form, 'extension', ext);
      setField(form, 'size_bytes', String(file.size));
      setField(form, 'relative_path', fullName);
      setField(form, 'created_at_fs', toDatetimeLocal(dt));
      setField(form, 'updated_at_fs', toDatetimeLocal(dt));
      if (doHash) {
        try {
          setField(form, 'checksum', await sha256Hex(file));
        } catch (e) {
          console.warn('SHA-256', e);
        }
      }
    } else if (options.mode === 'material') {
      setField(form, 'file_name', fullName);
      setField(form, 'extension', ext);
      setField(form, 'size_bytes', String(file.size));
      if (doHash) {
        try {
          setField(form, 'checksum_sha256', await sha256Hex(file));
        } catch (e) {
          console.warn('SHA-256', e);
        }
      }
    } else if (options.mode === 'linked') {
      setField(form, 'title', fullName || baseName);
      const rt = form.querySelector('[name="resource_type"]');
      if (rt) {
        if (ext === 'pdf') {
          rt.value = 'pdf';
        } else {
          rt.value = 'local_file';
        }
      }
    }
  };
})();
