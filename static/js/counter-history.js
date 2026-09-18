/* Hourly counter usage; no external chart service or personal data required. */
document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('counter-usage-modal');
    if (!modal) return;
    const range = document.getElementById('usage-range');
    const metric = document.getElementById('usage-metric');
    const status = document.getElementById('usage-status');
    const summary = document.getElementById('usage-summary');
    const chart = document.getElementById('usage-chart');
    const details = document.getElementById('usage-details');
    const clear = document.getElementById('usage-clear');
    let selected, data, requestNumber = 0;
    const number = value => value.toLocaleString();
    const label = hour => hour.slice(5, 10) + ' ' + hour.slice(11, 16);

    function svgElement(tag, attributes, text) {
        const element = document.createElementNS('http://www.w3.org/2000/svg', tag);
        Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
        if (text !== undefined) element.textContent = text;
        chart.appendChild(element);
        return element;
    }

    function render() {
        if (!data) return;
        const series = data.series;
        const uses = series.reduce((sum, row) => sum + row.uses, 0);
        const amount = series.reduce((sum, row) => sum + row.amount, 0);
        status.textContent = data.enabled ? 'History tracking is on.' :
            'History tracking is off. Enable “Include counter history” in Edit to record future activity.';
        if (!uses) status.textContent += ' No recorded activity in this period.';
        summary.textContent = `${number(uses)} successful uses · ${number(amount)} added in this period`;
        clear.hidden = !data.can_manage;
        chart.replaceChildren();
        chart.removeAttribute('hidden');
        details.hidden = false;
        const values = series.map(row => row[metric.value]);
        const max = Math.max(1, ...values);
        svgElement('title', {}, `${metric.selectedOptions[0].text}: hourly totals in UTC`);
        for (let i = 0; i <= 4; i++) {
            const y = 20 + i * 47.5;
            svgElement('line', {x1: 80, x2: 740, y1: y, y2: y, stroke: '#dee2e6'});
            svgElement('text', {x: 72, y: y + 4, 'text-anchor': 'end', 'font-size': 12, fill: '#495057'},
                number(Math.round(max * (1 - i / 4) * 100) / 100));
        }
        const points = values.map((value, i) => `${80 + i * 660 / (values.length - 1)},${210 - value / max * 190}`);
        svgElement('polyline', {points: points.join(' '), fill: 'none', stroke: '#16734b', 'stroke-width': 2});
        [0, Math.floor((series.length - 1) / 2), series.length - 1].forEach((i, index) => {
            svgElement('text', {x: 80 + i * 660 / (series.length - 1), y: 238, 'font-size': 12,
                'text-anchor': ['start', 'middle', 'end'][index], fill: '#495057'}, label(series[i].hour));
        });
        const rows = document.getElementById('usage-rows');
        rows.replaceChildren();
        [...series].reverse().forEach(row => {
            const tr = document.createElement('tr');
            [row.hour.replace('T', ' ').replace('Z', ''), number(row.uses), number(row.amount)].forEach(value => {
                const td = document.createElement('td');
                td.textContent = value;
                tr.appendChild(td);
            });
            rows.appendChild(tr);
        });
    }

    async function load() {
        const currentRequest = ++requestNumber;
        data = null;
        chart.setAttribute('hidden', '');
        details.hidden = true;
        summary.textContent = '';
        clear.hidden = true;
        status.textContent = 'Loading usage…';
        try {
            const response = await fetch(`${selected.usageUrl}?hours=${range.value}`, {cache: 'no-store'});
            if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) {
                throw new Error('Unable to load usage. Please retry or sign in again.');
            }
            const result = await response.json();
            if (currentRequest !== requestNumber) return;
            data = result;
            render();
        } catch (error) {
            if (currentRequest === requestNumber) status.textContent = error.message;
        }
    }

    document.addEventListener('click', event => {
        const button = event.target.closest('[data-counter-usage]');
        if (!button) return;
        selected = {...button.dataset};
        document.getElementById('usage-title').textContent = `Usage: ${selected.counterName}`;
        $(modal).modal('show');
        load();
    });
    range.addEventListener('change', load);
    metric.addEventListener('change', render);
    clear.addEventListener('click', async () => {
        if (!selected || !window.confirm(`Clear all saved history for “${selected.counterName}”? This cannot be undone. The counter total will stay unchanged.`)) return;
        const target = selected;
        clear.disabled = true;
        try {
            const response = await fetch(target.clearUrl, {method: 'POST', headers: {
                'X-CSRFToken': document.getElementById('usage-csrf-token').value,
            }});
            if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) {
                throw new Error('Unable to clear history. Please retry or sign in again.');
            }
            if (selected === target) await load();
        } catch (error) {
            if (selected === target) status.textContent = error.message;
        } finally {
            clear.disabled = false;
        }
    });
});
