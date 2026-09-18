(() => {
    const button = document.getElementById('refresh-documentation');
    const frame = document.getElementById('documentation-frame');
    if (!button || !frame) return;
    button.addEventListener('click', () => {
        const source = new URL(frame.src);
        source.searchParams.set('refresh', String(Date.now()));
        frame.src = source.href;
    });
})();
