/* Utilidades compartidas por toda la UI (§15: la UI NO contiene lógica
 * de negocio — solo lee/escribe la Definición a través de la API). */

const Api = {
  async _req(method, path, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const resp = await fetch(path, opts);
    const text = await resp.text();
    const data = text ? JSON.parse(text) : null;
    if (!resp.ok) {
      const detail = (data && (data.detail || JSON.stringify(data.errors))) || resp.statusText;
      const err = new Error(detail);
      err.status = resp.status;
      err.body = data;
      throw err;
    }
    return data;
  },
  get(path) { return this._req("GET", path); },
  post(path, body) { return this._req("POST", path, body === undefined ? {} : body); },
};

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString();
}

function fmtCost(v) {
  if (v === null || v === undefined) return "—";
  return "$" + Number(v).toFixed(4);
}

function fmtMs(ms) {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return ms + " ms";
  return (ms / 1000).toFixed(1) + " s";
}

function badge(value, prefix) {
  prefix = prefix || "";
  const cls = "badge badge-" + String(value).toLowerCase();
  return `<span class="${cls}">${prefix}${value}</span>`;
}

function qs(name) {
  return new URLSearchParams(window.location.search).get(name);
}

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function showError(container, err) {
  container.innerHTML = `<div class="error-banner">${escapeHtml(err.message || String(err))}</div>`;
}

/* ─────────────────────── Renderizador genérico de formularios ───────────────────────
 * Recorre un JSON Schema (con $defs/$ref, tal como lo produce Pydantic) y
 * construye un formulario real. Es la pieza que hace que "no-code" no sea
 * una fachada (§14.3, §15.1): añadir un campo al schema añade un control
 * a la UI sin tocar este archivo.
 */

const SchemaForm = (() => {
  function resolve(schemaNode, root) {
    if (schemaNode && schemaNode.$ref) {
      const name = schemaNode.$ref.split("/").pop();
      return root.$defs[name];
    }
    if (schemaNode && schemaNode.anyOf) {
      const nonNull = schemaNode.anyOf.find((s) => s.type !== "null" || s.$ref);
      const resolved = resolve(nonNull || schemaNode.anyOf[0], root);
      return { ...resolved, nullable: true, default: schemaNode.default };
    }
    return schemaNode;
  }

  function isFreeformObject(node) {
    return node.type === "object" && !node.properties;
  }

  function fieldId(path) {
    return "f_" + path.replace(/[^\w]/g, "_");
  }

  function renderField(name, node, root, path, value, required) {
    const resolved = resolve(node, root);
    if (value === undefined && resolved.default !== undefined && resolved.default !== null) {
      value = resolved.default;
    }
    const label = resolved.title || name;
    const id = fieldId(path);
    const reqMark = required ? ' <span class="req">*</span>' : "";
    const help = resolved.description ? `<div class="field-help">${escapeHtml(resolved.description)}</div>` : "";

    if (resolved.enum) {
      const opts = resolved.enum
        .map((v) => `<option value="${escapeHtml(v)}" ${value === v ? "selected" : ""}>${escapeHtml(v)}</option>`)
        .join("");
      return `<label for="${id}">${escapeHtml(label)}${reqMark}</label>${help}
        <select id="${id}" data-path="${path}" data-kind="value">${opts}</select>`;
    }

    if (resolved.type === "boolean") {
      const checked = value ? "checked" : "";
      return `<label><input type="checkbox" id="${id}" data-path="${path}" data-kind="bool" ${checked}> ${escapeHtml(label)}</label>${help}`;
    }

    if (resolved.type === "integer" || resolved.type === "number") {
      const step = resolved.type === "integer" ? "1" : "any";
      const v = value === undefined || value === null ? "" : value;
      return `<label for="${id}">${escapeHtml(label)}${reqMark}</label>${help}
        <input type="number" step="${step}" id="${id}" data-path="${path}" data-kind="number" value="${escapeHtml(v)}">`;
    }

    if (resolved.type === "array" && resolved.items) {
      const itemSchema = resolve(resolved.items, root);
      if (itemSchema.type === "string" || !itemSchema.type) {
        const v = Array.isArray(value) ? value.join(", ") : "";
        return `<label for="${id}">${escapeHtml(label)}${reqMark} <span class="muted">(separado por comas)</span></label>${help}
          <input type="text" id="${id}" data-path="${path}" data-kind="csv" value="${escapeHtml(v)}">`;
      }
      return renderArrayOfObjects(name, resolved, root, path, Array.isArray(value) ? value : [], label, help);
    }

    if (isFreeformObject(resolved)) {
      const v = value !== undefined ? JSON.stringify(value, null, 2) : "{}";
      return `<label for="${id}">${escapeHtml(label)} <span class="muted">(JSON)</span></label>${help}
        <textarea class="json" id="${id}" data-path="${path}" data-kind="json">${escapeHtml(v)}</textarea>`;
    }

    if (resolved.type === "object" && resolved.properties) {
      return renderObject(resolved, root, path, value || {}, label, help, required);
    }

    // fallback: texto plano
    const v = value === undefined || value === null ? "" : value;
    return `<label for="${id}">${escapeHtml(label)}${reqMark}</label>${help}
      <input type="text" id="${id}" data-path="${path}" data-kind="value" value="${escapeHtml(v)}">`;
  }

  function renderObject(schema, root, path, value, label, help, required) {
    const reqSet = new Set(schema.required || []);
    const inner = Object.entries(schema.properties)
      .map(([k, v]) => renderField(k, v, root, path ? `${path}.${k}` : k, value[k], reqSet.has(k)))
      .join("");
    const legend = label ? `<legend>${escapeHtml(label)}</legend>${help}` : "";
    return `<fieldset data-object-path="${path}">${legend}${inner}</fieldset>`;
  }

  function renderArrayOfObjects(name, schema, root, path, values, label, help) {
    const itemsHtml = values
      .map((v, i) => renderArrayItem(schema, root, path, i, v))
      .join("");
    return `
      <div class="array-field" data-array-path="${path}">
        <label>${escapeHtml(label)}</label>${help}
        <div class="array-items">${itemsHtml}</div>
        <button type="button" class="secondary add-item" data-array-path="${path}">+ añadir</button>
      </div>`;
  }

  function renderArrayItem(schema, root, path, index, value) {
    const itemSchema = resolve(schema.items, root);
    const inner = renderObject(itemSchema, root, `${path}.${index}`, value || {}, "", "", null);
    return `<div class="array-item" data-index="${index}">
        <button type="button" class="remove-item" data-array-path="${path}" data-index="${index}">✕ quitar</button>
        ${inner}
      </div>`;
  }

  function render(rootSchema, container, initialValue) {
    container.innerHTML = renderObject(rootSchema, rootSchema, "", initialValue || {}, "", "", null);
    // Delegación de eventos en el contenedor, UNA sola vez: los botones
    // add/remove se crean y destruyen dinámicamente, y volver a llamar
    // addEventListener sobre botones ya cableados los dispara varias
    // veces por clic (bug real encontrado probando esto en el navegador).
    container.addEventListener("click", (ev) => handleClick(ev, container, rootSchema));
  }

  function handleClick(ev, container, rootSchema) {
    const addBtn = ev.target.closest(".add-item");
    if (addBtn) {
      const path = addBtn.dataset.arrayPath;
      const wrapper = container.querySelector(`.array-field[data-array-path="${cssEscape(path)}"]`);
      const itemsDiv = wrapper.querySelector(":scope > .array-items");
      const schemaNode = findSchemaByPath(rootSchema, path);
      const index = itemsDiv.children.length;
      const html = renderArrayItem(schemaNode, rootSchema, path, index, {});
      itemsDiv.appendChild(el(html));
      return;
    }
    const removeBtn = ev.target.closest(".remove-item");
    if (removeBtn) {
      removeBtn.closest(".array-item").remove();
      reindexArray(container, removeBtn.dataset.arrayPath);
    }
  }

  function reindexArray(container, path) {
    const wrapper = container.querySelector(`.array-field[data-array-path="${cssEscape(path)}"]`);
    const items = wrapper.querySelectorAll(":scope > .array-items > .array-item");
    items.forEach((item, i) => {
      item.dataset.index = i;
      item.querySelector(".remove-item").dataset.index = i;
      item.querySelectorAll("[data-path]").forEach((input) => {
        input.dataset.path = input.dataset.path.replace(/\.\d+\./, `.${i}.`);
      });
      item.querySelectorAll("[data-object-path]").forEach((fs) => {
        fs.dataset.objectPath = fs.dataset.objectPath.replace(/\.\d+\./, `.${i}.`);
      });
    });
  }

  function cssEscape(s) {
    return s.replace(/[.\[\]]/g, "\\$&");
  }

  function findSchemaByPath(rootSchema, path) {
    if (!path) return rootSchema;
    let node = rootSchema;
    for (const part of path.split(".")) {
      node = resolve(node, rootSchema);
      if (/^\d+$/.test(part)) {
        node = resolve(node.items, rootSchema);
      } else {
        node = node.properties[part];
      }
    }
    return node;
  }

  function collect(container) {
    const result = {};
    container.querySelectorAll("[data-path]").forEach((input) => {
      if (input.closest(".array-item") && input.closest(".array-item").dataset._skip) return;
      setPath(result, input.dataset.path, readValue(input));
    });
    // asegurar que los arrays de objetos existen aunque estén vacíos
    container.querySelectorAll(".array-field").forEach((wrapper) => {
      const path = wrapper.dataset.arrayPath;
      if (getPath(result, path) === undefined) setPath(result, path, []);
    });
    return result;
  }

  function readValue(input) {
    const kind = input.dataset.kind;
    if (kind === "bool") return input.checked;
    if (kind === "number") return input.value === "" ? null : Number(input.value);
    if (kind === "csv") return input.value.split(",").map((s) => s.trim()).filter(Boolean);
    if (kind === "json") {
      try { return JSON.parse(input.value || "{}"); } catch { return {}; }
    }
    return input.value;
  }

  function setPath(obj, path, value) {
    const parts = path.split(".");
    let node = obj;
    for (let i = 0; i < parts.length - 1; i++) {
      const key = /^\d+$/.test(parts[i]) ? Number(parts[i]) : parts[i];
      const nextIsIndex = /^\d+$/.test(parts[i + 1]);
      if (node[key] === undefined) node[key] = nextIsIndex ? [] : {};
      node = node[key];
    }
    const lastPart = parts[parts.length - 1];
    const lastKey = /^\d+$/.test(lastPart) ? Number(lastPart) : lastPart;
    node[lastKey] = value;
  }

  function getPath(obj, path) {
    if (!path) return obj;
    let node = obj;
    for (const part of path.split(".")) {
      if (node === undefined || node === null) return undefined;
      node = node[part];
    }
    return node;
  }

  return { render, collect };
})();
