document.addEventListener('DOMContentLoaded', function () {
    // Flash messages: dismiss on click; non-errors leave on their own after 5s.
    document.querySelectorAll('.flash').forEach(function (el) {
        function dismiss() {
            el.classList.add('is-leaving');
            setTimeout(function () { el.remove(); }, 240);
        }
        el.querySelector('.btn-close').addEventListener('click', dismiss);
        if (!el.classList.contains('flash-danger')) setTimeout(dismiss, 5000);
    });

    // Topbar gains a hairline shadow once the page scrolls under it.
    const bar = document.querySelector('.topbar');
    if (bar) {
        const onScroll = function () { bar.classList.toggle('is-scrolled', window.scrollY > 4); };
        onScroll();
        window.addEventListener('scroll', onScroll, { passive: true });
    }

    // Any link to #composer focuses the topic composer if it's on this page.
    const composer = document.getElementById('composerText');
    if (composer) {
        if (location.hash === '#composer') composer.focus();
        document.querySelectorAll('a[href$="#composer"]').forEach(function (a) {
            a.addEventListener('click', function (e) {
                e.preventDefault();
                composer.scrollIntoView({ behavior: 'smooth', block: 'center' });
                composer.focus({ preventScroll: true });
            });
        });
    }
});

document.addEventListener('DOMContentLoaded', function () {
    // Phone menu: swap the icon, dim the page and stop it scrolling behind the drawer.
    const nav = document.getElementById('mobileNav');
    const btn = document.querySelector('.menu-btn');
    if (nav && btn) {
        const icon = btn.querySelector('i');
        nav.addEventListener('show.bs.collapse', function () {
            document.body.classList.add('menu-open');
            icon.className = 'fas fa-xmark';
        });
        nav.addEventListener('hide.bs.collapse', function () {
            document.body.classList.remove('menu-open');
            icon.className = 'fas fa-bars';
        });
        // Tapping the dimmed page closes the menu.
        document.addEventListener('click', function (e) {
            if (!document.body.classList.contains('menu-open')) return;
            if (nav.contains(e.target) || btn.contains(e.target)) return;
            bootstrap.Collapse.getOrCreateInstance(nav).hide();
        });
    }

    // Board chips (phones): bring the selected board into view.
    const activeChip = document.querySelector('.board-chips a.active');
    if (activeChip) activeChip.scrollIntoView({ block: 'nearest', inline: 'center' });
});
