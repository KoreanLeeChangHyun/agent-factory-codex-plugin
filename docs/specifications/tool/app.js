"use strict";
const links=[...document.querySelectorAll("nav a[href^='#']")];
if("IntersectionObserver" in window){const observer=new IntersectionObserver(entries=>{for(const entry of entries){if(entry.isIntersecting){for(const link of links)link.removeAttribute("aria-current");document.querySelector('nav a[href="#'+entry.target.id+'"]')?.setAttribute("aria-current","true");}}},{rootMargin:"-20% 0px -65%"});for(const section of document.querySelectorAll("main section[id]"))observer.observe(section);}

