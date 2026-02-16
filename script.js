const header = document.querySelector(".site-header");
const navToggle = document.querySelector(".nav-toggle");
const navLinks = document.querySelector(".nav-links");
const yearNode = document.querySelector("#year");
const revealNodes = document.querySelectorAll(".reveal");
const counterNodes = document.querySelectorAll("[data-count]");
const shiftNodes = document.querySelectorAll("[data-shift]");

if (yearNode) {
  yearNode.textContent = new Date().getFullYear();
}

const syncHeader = () => {
  if (!header) {
    return;
  }
  header.classList.toggle("scrolled", window.scrollY > 24);
};

syncHeader();
window.addEventListener("scroll", syncHeader, { passive: true });

if (navToggle && navLinks) {
  navToggle.addEventListener("click", () => {
    const expanded = navToggle.getAttribute("aria-expanded") === "true";
    navToggle.setAttribute("aria-expanded", String(!expanded));
    navLinks.classList.toggle("open");
  });

  navLinks.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      navLinks.classList.remove("open");
      navToggle.setAttribute("aria-expanded", "false");
    });
  });

  document.addEventListener("click", (event) => {
    const isOutsideMenu = !navLinks.contains(event.target) && !navToggle.contains(event.target);
    if (isOutsideMenu) {
      navLinks.classList.remove("open");
      navToggle.setAttribute("aria-expanded", "false");
    }
  });
}

if (revealNodes.length > 0) {
  const revealObserver = new IntersectionObserver(
    (entries, observer) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) {
          return;
        }
        entry.target.classList.add("visible");
        observer.unobserve(entry.target);
      });
    },
    {
      rootMargin: "0px 0px -10% 0px",
      threshold: 0.15,
    },
  );

  revealNodes.forEach((node) => revealObserver.observe(node));
}

if (counterNodes.length > 0) {
  const animateCounter = (node) => {
    const target = Number(node.getAttribute("data-count")) || 0;
    const duration = 1200;
    const start = performance.now();

    const run = (now) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - (1 - progress) ** 3;
      node.textContent = Math.floor(target * eased).toLocaleString("pt-BR");
      if (progress < 1) {
        window.requestAnimationFrame(run);
      }
    };

    window.requestAnimationFrame(run);
  };

  const counterObserver = new IntersectionObserver(
    (entries, observer) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) {
          return;
        }
        animateCounter(entry.target);
        observer.unobserve(entry.target);
      });
    },
    { threshold: 0.4 },
  );

  counterNodes.forEach((node) => counterObserver.observe(node));
}

if (shiftNodes.length > 0) {
  const onParallax = () => {
    const viewportCenter = window.innerHeight / 2;
    shiftNodes.forEach((node) => {
      const shift = Number(node.getAttribute("data-shift")) || 0;
      const bounds = node.getBoundingClientRect();
      const center = bounds.top + bounds.height / 2;
      const distance = (center - viewportCenter) / viewportCenter;
      const yOffset = distance * shift;
      node.style.setProperty("--parallax-y", `${yOffset.toFixed(2)}px`);
    });
  };

  onParallax();
  window.addEventListener("scroll", onParallax, { passive: true });
  window.addEventListener("resize", onParallax);
}

const canvas = document.querySelector("#starfield");

if (canvas instanceof HTMLCanvasElement) {
  const context = canvas.getContext("2d");

  if (context) {
    const stars = [];
    let width = 0;
    let height = 0;
    let dpr = 1;
    let rafId = 0;

    const setup = () => {
      dpr = Math.min(2, window.devicePixelRatio || 1);
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      context.setTransform(dpr, 0, 0, dpr, 0, 0);

      const count = Math.max(90, Math.floor((width * height) / 9000));
      stars.length = 0;
      for (let i = 0; i < count; i += 1) {
        stars.push({
          x: Math.random() * width,
          y: Math.random() * height,
          radius: Math.random() * 1.7 + 0.2,
          speed: Math.random() * 0.22 + 0.03,
          alpha: Math.random() * 0.6 + 0.2,
        });
      }
    };

    const draw = () => {
      context.clearRect(0, 0, width, height);
      context.fillStyle = "rgba(8, 6, 15, 0.28)";
      context.fillRect(0, 0, width, height);

      stars.forEach((star) => {
        star.y += star.speed;
        if (star.y > height + 4) {
          star.y = -4;
          star.x = Math.random() * width;
        }

        const pulse = 0.55 + Math.sin((star.x + star.y) * 0.015) * 0.45;
        context.beginPath();
        context.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
        context.fillStyle = `rgba(188, 166, 255, ${star.alpha * pulse})`;
        context.fill();
      });

      rafId = window.requestAnimationFrame(draw);
    };

    setup();
    draw();

    window.addEventListener("resize", () => {
      window.cancelAnimationFrame(rafId);
      setup();
      draw();
    });
  }
}
