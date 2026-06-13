(function () {
    'use strict';

    function motionReduced() {
        return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    function hasGSAP() {
        return Boolean(window.gsap);
    }

    function animateDashboardEntry() {
        var overlay = document.querySelector('.dashboard-entry');
        if (!overlay) return false;

        document.body.classList.add('dashboard-entering');

        if (!hasGSAP() || motionReduced()) {
            overlay.remove();
            document.body.classList.remove('dashboard-entering');
            return false;
        }

        var gsap = window.gsap;
        var tl = gsap.timeline({ defaults: { ease: 'power3.out' } });

        tl.set('.navbar, .container', { opacity: 0, y: 18 })
          .from('.dashboard-entry-card', { opacity: 0, y: 28, scale: 0.92, duration: 0.45 })
          .from('.dashboard-entry-logo', { opacity: 0, scale: 0.72, rotation: -5, duration: 0.45 }, '-=0.22')
          .from('.dashboard-entry-title', { opacity: 0, y: 14, duration: 0.32 }, '-=0.22')
          .from('.dashboard-entry-subtitle', { opacity: 0, y: 10, duration: 0.28 }, '-=0.18')
          .to('.dashboard-entry-card', { scale: 1.02, duration: 0.18, ease: 'power1.out' })
          .to(overlay, { opacity: 0, duration: 0.42, ease: 'power2.inOut' }, '+=0.18')
          .to('.navbar, .container', { opacity: 1, y: 0, duration: 0.5, stagger: 0.06 }, '-=0.32')
          .add(function () {
              overlay.remove();
              document.body.classList.remove('dashboard-entering');
          });

        return true;
    }

    function animateBaseUI(skipContainerIntro) {
        if (!hasGSAP() || motionReduced()) return;

        var gsap = window.gsap;
        if (!skipContainerIntro) {
            var timeline = gsap.timeline({ defaults: { ease: 'power2.out' } });
            timeline
                .from('.navbar', { opacity: 0, y: -16, duration: 0.35 })
                .from('.container', { opacity: 0, y: 18, duration: 0.42 }, '-=0.12')
                .from('.dashboard-hero', { opacity: 0, y: 16, duration: 0.35 }, '-=0.22');
        }

        gsap.from('.card, .react-card, .page-hero, .product-form-card, .scanner-field-card, .photo-uploader-card', {
            opacity: 0,
            y: 18,
            duration: 0.38,
            stagger: 0.045,
            ease: 'power2.out',
            delay: skipContainerIntro ? 1.55 : 0.08
        });

        gsap.from('table', {
            opacity: 0,
            y: 12,
            duration: 0.35,
            ease: 'power2.out',
            delay: skipContainerIntro ? 1.65 : 0.08
        });
    }

    function enhanceHover() {
        if (!hasGSAP() || motionReduced()) return;

        var gsap = window.gsap;
        document.querySelectorAll('.btn, .pill, .card, .react-card, .product-thumb').forEach(function (element) {
            element.addEventListener('mouseenter', function () {
                gsap.to(element, { scale: 1.015, duration: 0.16, overwrite: 'auto' });
            });
            element.addEventListener('mouseleave', function () {
                gsap.to(element, { scale: 1, duration: 0.16, overwrite: 'auto' });
            });
        });
    }

    function animatePublicSectionsWithScrollTrigger() {
        if (!hasGSAP() || !window.ScrollTrigger || motionReduced()) return;

        var gsap = window.gsap;
        gsap.registerPlugin(window.ScrollTrigger);

        document.querySelectorAll('[data-gsap-scroll-section]').forEach(function (section) {
            gsap.from(section, {
                opacity: 0,
                y: 32,
                duration: 0.55,
                ease: 'power2.out',
                scrollTrigger: {
                    trigger: section,
                    start: 'top 82%',
                    toggleActions: 'play none none reverse'
                }
            });
        });
    }

    function init() {
        var usedEntry = animateDashboardEntry();
        animateBaseUI(usedEntry);
        enhanceHover();
        animatePublicSectionsWithScrollTrigger();
    }

    document.addEventListener('DOMContentLoaded', init);
    document.addEventListener('jugueteriabot:react-enhanced', function () {
        enhanceHover();
    });
}());
