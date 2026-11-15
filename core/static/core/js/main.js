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

document.addEventListener('DOMContentLoaded', function () {
    // Forms/buttons that need a "are you sure?" first.
    document.querySelectorAll('form[data-confirm]').forEach(function (form) {
        form.addEventListener('submit', function (e) {
            if (!confirm(form.dataset.confirm)) { e.preventDefault(); e.stopImmediatePropagation(); }
        });
    });
    document.querySelectorAll('[data-confirm-click]').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            if (!confirm(btn.dataset.confirmClick)) e.preventDefault();
        });
    });

    // A second tap on a slow connection must not post twice: lock the button after the first submit.
    document.querySelectorAll('form[method="post" i]').forEach(function (form) {
        form.addEventListener('submit', function (e) {
            if (e.defaultPrevented) return;
            if (form.dataset.submitted) { e.preventDefault(); return; }
            form.dataset.submitted = '1';
            setTimeout(function () {
                form.querySelectorAll('button[type="submit"]').forEach(function (b) {
                    b.setAttribute('aria-disabled', 'true');
                    b.classList.add('is-busy');
                });
            }, 0);
            // If the page is restored from the back/forward cache, unlock again.
            window.addEventListener('pageshow', function () {
                delete form.dataset.submitted;
                form.querySelectorAll('.is-busy').forEach(function (b) { b.classList.remove('is-busy'); b.removeAttribute('aria-disabled'); });
            }, { once: true });
        });
    });

    // Live character count on fields with a limit, shown once you get close.
    document.querySelectorAll('textarea[maxlength]').forEach(function (area) {
        const max = parseInt(area.getAttribute('maxlength'), 10);
        const note = document.createElement('div');
        note.className = 'char-count';
        note.hidden = true;
        area.insertAdjacentElement('afterend', note);
        area.addEventListener('input', function () {
            const left = max - area.value.length;
            note.hidden = left > max * 0.1;
            note.textContent = left + ' characters left';
            note.classList.toggle('is-low', left <= 50);
        });
    });
});

// Homepage slideshow: cross-fades the photos in the arch frame every few seconds.
document.addEventListener('DOMContentLoaded', function () {
    const show = document.querySelector('[data-slideshow]');
    if (!show) return;
    let slides = Array.from(show.querySelectorAll('.slide'));
    const caption = show.querySelector('[data-slide-caption]');
    const dotsBox = show.querySelector('[data-slide-dots]');
    const toggle = show.querySelector('[data-slide-toggle]');
    const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let index = 0, timer = null, paused = calm;

    // A photo that fails to load (deleted file) is dropped instead of showing a broken slide.
    slides.forEach(function (img) {
        img.addEventListener('error', function () {
            img.remove();
            slides = slides.filter(function (s) { return s !== img; });
            build();
            go(0);
        });
    });

    function build() {
        dotsBox.replaceChildren();
        slides.forEach(function (_, i) {
            const dot = document.createElement('button');
            dot.type = 'button';
            dot.className = 'slide-dot';
            dot.setAttribute('aria-label', 'Photo ' + (i + 1) + ' of ' + slides.length);
            dot.addEventListener('click', function () { go(i); restart(); });
            dotsBox.appendChild(dot);
        });
        show.querySelector('.slide-controls').hidden = slides.length < 2;
    }

    function go(next) {
        if (!slides.length) return;
        index = (next + slides.length) % slides.length;
        slides.forEach(function (s, i) { s.classList.toggle('is-active', i === index); });
        Array.from(dotsBox.children).forEach(function (d, i) {
            d.classList.toggle('is-active', i === index);
            d.setAttribute('aria-current', i === index ? 'true' : 'false');
        });
        caption.textContent = slides[index].dataset.caption || '';
    }

    function stop() { clearInterval(timer); timer = null; }
    function restart() {
        stop();
        if (!paused && slides.length > 1) timer = setInterval(function () { go(index + 1); }, 4500);
    }
    function setPaused(value) {
        paused = value;
        toggle.querySelector('i').className = paused ? 'fas fa-play' : 'fas fa-pause';
        toggle.setAttribute('aria-label', paused ? 'Play slideshow' : 'Pause slideshow');
        restart();
    }

    show.querySelector('[data-slide-prev]').addEventListener('click', function () { go(index - 1); restart(); });
    show.querySelector('[data-slide-next]').addEventListener('click', function () { go(index + 1); restart(); });
    toggle.addEventListener('click', function () { setPaused(!paused); });
    show.addEventListener('mouseenter', stop);
    show.addEventListener('mouseleave', restart);
    document.addEventListener('visibilitychange', function () { document.hidden ? stop() : restart(); });

    // Swipe on phones.
    let startX = null;
    show.addEventListener('touchstart', function (e) { startX = e.touches[0].clientX; }, { passive: true });
    show.addEventListener('touchend', function (e) {
        if (startX === null) return;
        const dx = e.changedTouches[0].clientX - startX;
        if (Math.abs(dx) > 40) { go(index + (dx < 0 ? 1 : -1)); restart(); }
        startX = null;
    });

    build();
    go(0);
    setPaused(calm);
});
