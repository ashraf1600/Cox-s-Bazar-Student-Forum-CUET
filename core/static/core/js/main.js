document.addEventListener('DOMContentLoaded', function () {
    const counters = document.querySelectorAll('.stat-counter[data-count]');
    counters.forEach((counter) => {
        const target = +counter.dataset.count;
        let count = 0;
        const step = Math.max(1, Math.floor(target / 100));
        const interval = setInterval(() => {
            count += step;
            if (count >= target) {
                counter.textContent = target.toLocaleString();
                clearInterval(interval);
            } else {
                counter.textContent = count.toLocaleString();
            }
        }, 12);
    });

    const navbar = document.querySelector('.navbar');
    if (navbar) {
        const onScroll = () => {
            if (window.scrollY > 20) {
                navbar.classList.add('navbar-scrolled');
            } else {
                navbar.classList.remove('navbar-scrolled');
            }
        };
        onScroll();
        window.addEventListener('scroll', onScroll);
    }
});
