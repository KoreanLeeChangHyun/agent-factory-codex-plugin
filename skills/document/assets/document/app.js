(() => {
  "use strict";

  const links = Array.from(document.querySelectorAll('.section-nav a[href^="#"]'));
  const sections = links
    .map((link) => document.getElementById(link.hash.slice(1)))
    .filter(Boolean);

  if (!links.length || !sections.length || !("IntersectionObserver" in window)) {
    return;
  }

  const linksById = new Map(links.map((link) => [link.hash.slice(1), link]));
  const setCurrentSection = (sectionId) => {
    links.forEach((link) => link.removeAttribute("aria-current"));
    linksById.get(sectionId)?.setAttribute("aria-current", "location");
  };

  const observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((left, right) => right.intersectionRatio - left.intersectionRatio);

      if (visible[0]) {
        setCurrentSection(visible[0].target.id);
      }
    },
    { rootMargin: "-15% 0px -65% 0px", threshold: [0, 0.25, 0.6] },
  );

  sections.forEach((section) => observer.observe(section));
  setCurrentSection(sections[0].id);
})();
