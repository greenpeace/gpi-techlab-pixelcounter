/* Shared Add/Edit dialog. Existing authenticated routes remain authoritative. */
(() => {
    'use strict';
    const modal = document.getElementById('app-form-modal');
    if (!modal) return;
    const fields = document.getElementById('app-form-fields');
    const status = document.getElementById('app-form-status');
    const title = document.getElementById('app-form-title');
    const save = document.getElementById('app-form-save');
    let discarding = false, editTitle, editFocus;
    function showDiscard(show) {
        if (show && !discarding) { editTitle = title.textContent; editFocus = document.activeElement; }
        discarding = show;
        document.getElementById('app-form-body').hidden = show;
        document.getElementById('app-form-actions').hidden = show;
        document.getElementById('app-form-discard').hidden = !show;
        document.getElementById('app-form-discard-actions').hidden = !show;
        title.textContent = show ? 'Discard changes?' : editTitle || title.textContent;
        if (show) document.getElementById('app-form-keep').focus();
        else editFocus?.focus();
    }
    document.getElementById('app-form-keep').addEventListener('click', () => showDiscard(false));
    document.getElementById('app-form-discard-confirm').addEventListener('click', () => {
        dirty = false;
        $(modal).modal('hide');
    });
    let controller, sequence = 0, dirty = false, saving = false, completed = false, opener;
    const scrollKey = `modal-scroll:${location.pathname}${location.search}`;
    try {
        const position = sessionStorage.getItem(scrollKey);
        if (position !== null) {
            sessionStorage.removeItem(scrollKey);
            window.addEventListener('load', () => window.scrollTo(0, Number(position)));
        }
    } catch (_) { /* Storage can be disabled by the browser. */ }

    function message(text, error = false) {
        status.textContent = text;
        status.className = error ? 'alert alert-danger' : 'text-muted';
        status.setAttribute('role', error ? 'alert' : 'status');
        if (error) status.scrollIntoView({block: 'nearest'});
    }

    function sameOrigin(url) {
        const target = new URL(url, location.href);
        if (target.origin !== location.origin) throw new Error('The form must be on this site.');
        return target.href;
    }

    async function openForm(link) {
        opener = link;
        controller?.abort();
        controller = new AbortController();
        const current = ++sequence;
        dirty = saving = completed = false;
        save.hidden = false;
        modal.querySelector('#app-form-actions [data-dismiss="modal"]').textContent = 'Cancel';
        fields.replaceChildren();
        title.textContent = link.dataset.modalTitle || link.textContent.trim().replace(/\s+/g, ' ');
        save.disabled = true;
        save.textContent = 'Save';
        message('Loading form…');
        $(modal).modal('show');
        try {
            const source = sameOrigin(link.href);
            const response = await fetch(source, {
                headers: {'X-Modal-Form': '1'}, cache: 'no-store', signal: controller.signal,
            });
            if (!response.ok || response.redirected) {
                throw new Error('This form is unavailable. Check your access or sign in again.');
            }
            const html = new DOMParser().parseFromString(await response.text(), 'text/html');
            const fragment = html.querySelector('[data-modal-fragment]');
            const form = fragment?.querySelector('form');
            if (!form) throw new Error('Unable to load this form. Close the dialog and try again.');
            if (current !== sequence) return;
            const heading = fragment.querySelector('h1, h2, h3');
            if (heading) title.textContent = heading.textContent.trim().replace(/\s+/g, ' ');
            // Forms contain markup only. Scripts and inline handlers are never executed.
            fragment.querySelectorAll('script').forEach(element => element.remove());
            fragment.querySelectorAll('*').forEach(element => {
                [...element.attributes].filter(attr => attr.name.startsWith('on')).forEach(attr => element.removeAttribute(attr.name));
            });
            form.action = sameOrigin(form.getAttribute('action') || source);
            form.setAttribute('id', 'app-modal-form');
            // Native browser validation and FormData preserve checkboxes and multi-selects.
            form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(button => button.remove());
            fragment.querySelectorAll('a').forEach(anchor => {
                if (anchor.textContent.trim() === 'Cancel') anchor.remove();
            });
            // Repair legacy label associations and avoid IDs shared with the list page.
            form.querySelectorAll('input:not([type="hidden"]), select, textarea').forEach((input, index) => {
                const oldId = input.id;
                const label = [...form.querySelectorAll('label')].find(item =>
                    (oldId && item.htmlFor === oldId) ||
                    (item.htmlFor === input.name && !form.querySelector(`[id="${item.htmlFor}"]`))) ||
                    input.closest('.form-group')?.querySelector('label');
                input.id = `modal-field-${index}`;
                if (label) label.htmlFor = input.id;
            });
            fields.appendChild(fragment);
            message('');
            save.textContent = form.dataset.submitLabel || 'Save';
            save.disabled = false;
            form.querySelector('input:not([type="hidden"]), select, textarea')?.focus();
        } catch (error) {
            if (error.name !== 'AbortError' && current === sequence) message(error.message, true);
        }
    }

    document.addEventListener('click', event => {
        const link = event.target.closest('a[data-modal-form]');
        if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        if (!saving) openForm(link);
    });
    fields.addEventListener('input', () => { dirty = true; });
    fields.addEventListener('change', () => { dirty = true; });
    $(modal).on('shown.bs.modal', () => {
        fields.querySelector('input:not([type=hidden]), select, textarea')?.focus();
    }).on('hide.bs.modal', event => {
        if (saving || dirty) {
            event.preventDefault();
            if (!saving) showDiscard(!discarding);
            return;
        }
        controller?.abort();
        ++sequence;
    }).on('hidden.bs.modal', () => {
        if (discarding) showDiscard(false);
        fields.replaceChildren();
        if (completed) window.location.reload();
        dirty = false;
        opener?.focus();
    });

    document.addEventListener('submit', async event => {
        const form = event.target;
        if (form.getAttribute('id') !== 'app-modal-form') return;
        event.preventDefault();
        event.stopImmediatePropagation();
        if (saving || discarding || !form.reportValidity()) return;
        const body = new FormData(form);
        const controls = [...form.elements];
        const disabledBefore = controls.map(control => control.disabled);
        saving = true;
        save.disabled = true;
        save.textContent = 'Saving…';
        controls.forEach(control => { control.disabled = true; });
        form.setAttribute('aria-busy', 'true');
        message('Saving…');
        try {
            const response = await fetch(sameOrigin(form.action), {
                method: 'POST', body,
                headers: {'X-Modal-Form': '1', 'Accept': 'application/json'},
            });
            if (response.redirected) throw new Error('Your session may have expired. Sign in again before saving.');
            if (!response.headers.get('content-type')?.includes('application/json')) {
                throw new Error(response.status === 400 ?
                    'The form could not be submitted. Your session or security token may have expired; reopen the form and try again.' :
                    'Unable to save. Check your access and try again.');
            }
            const result = await response.json();
            if (!response.ok || result.success !== true) throw new Error(result.error || 'Unable to save changes.');
            dirty = false;
            if (result.result_html) {
                const resultDoc = new DOMParser().parseFromString(result.result_html, 'text/html');
                const fragment = resultDoc.querySelector('[data-modal-fragment]');
                if (!fragment) throw new Error('The item was created, but its details could not be shown.');
                fragment.querySelectorAll('script').forEach(script => script.remove());
                fields.replaceChildren(fragment);
                title.textContent = 'API key created';
                message('Save your key before closing. It is shown only once.');
                save.hidden = true;
                modal.querySelector('#app-form-actions [data-dismiss="modal"]').textContent = 'Done';
                completed = true;
                return;
            }
            completed = true;
            message(result.message || 'Saved successfully.');
            try { sessionStorage.setItem(scrollKey, String(window.scrollY)); } catch (_) { /* Optional. */ }
            // DataTables already persists its filter, sorting and current page.
            window.location.reload();
        } catch (error) {
            message(error instanceof TypeError ?
                'The connection was interrupted. Your changes may have been saved; check the list before submitting again.' : error.message, true);
        } finally {
            saving = false;
            controls.forEach((control, i) => { control.disabled = disabledBefore[i]; });
            form.removeAttribute('aria-busy');
            save.disabled = completed;
            save.textContent = form.dataset.submitLabel || 'Save';
        }
    }, true);
})();
