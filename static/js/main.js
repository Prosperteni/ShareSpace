(function () {
  "use strict";

  // ======= Sticky header + logo swap + back-to-top visibility
  // Single consolidated scroll handler — no nested listeners
  window.addEventListener("scroll", function () {
    const ud_header = document.querySelector(".ud-header");
    if (!ud_header) return;

    const logo = document.querySelector(".header-logo");

    // Sticky class toggle
    if (window.pageYOffset > 0) {
      ud_header.classList.add("sticky");
    } else {
      ud_header.classList.remove("sticky");
    }

    // Logo swap — use ../static/ paths
    if (logo) {
      const isDark = document.documentElement.classList.contains("dark");
      if (ud_header.classList.contains("sticky")) {
        logo.src = isDark
          ? "../static/images/logo/logo-white.svg"
          : "../static/images/logo/logo.svg";
      } else {
        logo.src = "../static/images/logo/logo-white.svg";
      }
    }

    // Back-to-top button visibility
    const backToTop = document.querySelector(".back-to-top");
    if (backToTop) {
      if (document.documentElement.scrollTop > 50) {
        backToTop.style.display = "flex";
      } else {
        backToTop.style.display = "none";
      }
    }
  });

  // ===== Responsive navbar toggle
  const navbarToggler = document.querySelector("#navbarToggler");
  const navbarCollapse = document.querySelector("#navbarCollapse");

  if (navbarToggler && navbarCollapse) {
    navbarToggler.addEventListener("click", () => {
      navbarToggler.classList.toggle("navbarTogglerActive");
      navbarCollapse.classList.toggle("hidden");
    });

    // Close on nav link click
    document
      .querySelectorAll("#navbarCollapse ul li:not(.submenu-item) a")
      .forEach((e) =>
        e.addEventListener("click", () => {
          navbarToggler.classList.remove("navbarTogglerActive");
          navbarCollapse.classList.add("hidden");
        })
      );

    // Close when clicking outside
    document.addEventListener("click", (event) => {
      const isClickInside =
        navbarCollapse.contains(event.target) ||
        navbarToggler.contains(event.target);
      if (!isClickInside) {
        navbarToggler.classList.remove("navbarTogglerActive");
        navbarCollapse.classList.add("hidden");
      }
    });
  }

  // ===== Sub-menu toggle
  const submenuItems = document.querySelectorAll(".submenu-item");
  submenuItems.forEach((el) => {
    el.querySelector("a").addEventListener("click", () => {
      el.querySelector(".submenu").classList.toggle("hidden");
    });
  });

  // ===== FAQ accordion
  const faqs = document.querySelectorAll(".single-faq");
  faqs.forEach((el) => {
    el.querySelector(".faq-btn").addEventListener("click", () => {
      el.querySelector(".icon").classList.toggle("rotate-180");
      el.querySelector(".faq-content").classList.toggle("hidden");
    });
  });

  // ===== WOW.js — initialised once here only (remove from index.html <head>)
  if (typeof WOW !== "undefined") {
    new WOW().init();
  }

  // ===== Back-to-top smooth scroll (uses native scroll-smooth from html tag)
  const backToTopBtn = document.querySelector(".back-to-top");
  if (backToTopBtn) {
    backToTopBtn.addEventListener("click", () => {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  // ===== Smooth scroll for nav links + active state on scroll
  // Consolidated from inline index.html script — handles both behaviours
  const menuScrollLinks = document.querySelectorAll(".ud-menu-scroll");

  menuScrollLinks.forEach((link) => {
    link.addEventListener("click", (e) => {
      const href = link.getAttribute("href");
      if (!href || !href.startsWith("#")) return; // skip non-hash links
      const target = document.querySelector(href);
      if (!target) return;
      e.preventDefault();
      target.scrollIntoView({ behavior: "smooth" });
    });
  });

  function updateActiveNavLink() {
    const scrollPos = window.pageYOffset || document.documentElement.scrollTop;

    menuScrollLinks.forEach((link) => {
      const href = link.getAttribute("href");
      if (!href || !href.startsWith("#")) return;
      const section = document.querySelector(href);
      if (!section) return;

      const sectionTop = section.offsetTop - 80;
      const sectionBottom = sectionTop + section.offsetHeight;

      if (scrollPos >= sectionTop && scrollPos < sectionBottom) {
        menuScrollLinks.forEach((l) => l.classList.remove("active"));
        link.classList.add("active");
      }
    });
  }

  window.addEventListener("scroll", updateActiveNavLink);

  // ===== Password toggle (signin/signup pages)
  const togglePassword = document.querySelector("#togglePassword");
  const password = document.querySelector('input[name="password"]');

  if (togglePassword && password) {
    togglePassword.addEventListener("click", () => {
      const type =
        password.getAttribute("type") === "password" ? "text" : "password";
      password.setAttribute("type", type);
      togglePassword.classList.toggle("bi-eye");
      togglePassword.classList.toggle("bi-eye-fill");
    });
  }
})();