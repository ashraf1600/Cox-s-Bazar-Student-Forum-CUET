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

    // AJAX Like Handler
    const likeButtons = document.querySelectorAll('.like-btn');
    likeButtons.forEach(btn => {
        btn.addEventListener('click', async function() {
            const postId = this.dataset.postId;
            try {
                const response = await fetch(`/post/${postId}/like/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken'),
                        'Content-Type': 'application/json',
                    }
                });
                if (response.ok) {
                    const data = await response.json();
                    
                    // Update counter
                    const countSpan = this.querySelector('.likes-count');
                    if (countSpan) {
                        countSpan.textContent = data.likes_count;
                    }
                    
                    // Toggle styling
                    if (data.liked) {
                        this.classList.add('liked');
                    } else {
                        this.classList.remove('liked');
                    }
                }
            } catch (err) {
                console.error("Error liking post:", err);
            }
        });
    });

    // Helper to get CSRF token from cookies
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
});
