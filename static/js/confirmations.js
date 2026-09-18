/* In-app confirmations for actions that previously used browser dialogs. */
(() => {
    'use strict';
    const modal = document.getElementById('app-confirm-modal');
    if (!modal) return;
    const accept = document.getElementById('app-confirm-accept');
    let resolvePending, accepted = false, opener;
    window.confirmAction = (message) => {
        if (resolvePending) return Promise.resolve(false);
        opener = document.activeElement;
        accepted = false;
        accept.disabled = true;
        document.getElementById('app-confirm-message').textContent = message;
        const result = new Promise(resolve => { resolvePending = resolve; });
        $(modal).modal('show');
        return result;
    };
    accept.addEventListener('click', () => {
        accepted = true;
        $(modal).modal('hide');
    });
    $(modal).on('shown.bs.modal', () => {
        accept.disabled = false;
        document.getElementById('app-confirm-cancel').focus();
    }).on('hidden.bs.modal', () => {
        const resolve = resolvePending;
        resolvePending = undefined;
        opener?.focus();
        resolve?.(accepted);
    });
    const approved = new WeakSet();
    const pending = new WeakSet();
    document.addEventListener('submit', async event => {
        const form = event.target;
        if (!form.matches('form[data-confirm]')) return;
        if (approved.delete(form)) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        if (pending.has(form)) return;
        pending.add(form);
        const submitter = event.submitter;
        try {
            if (await window.confirmAction(form.dataset.confirm)) {
                approved.add(form);
                HTMLFormElement.prototype.requestSubmit.call(form, submitter || undefined);
                approved.delete(form);
            }
        } finally {
            pending.delete(form);
        }
    }, true);
})();
