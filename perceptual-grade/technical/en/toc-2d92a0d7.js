// Populate the sidebar
//
// This is a script, and not included directly in the page, to control the total size of the book.
// The TOC contains an entry for each page, so if each page includes a copy of the TOC,
// the total size of the page becomes O(n**2).
class MDBookSidebarScrollbox extends HTMLElement {
    constructor() {
        super();
    }
    connectedCallback() {
        this.innerHTML = '<ol class="chapter"><li class="chapter-item expanded "><span class="chapter-link-wrapper"><a href="index.html">Technical Report</a></span></li><li class="chapter-item expanded "><li class="part-title">Understanding the model</li></li><li class="chapter-item expanded "><span class="chapter-link-wrapper"><a href="theory/linear.html"><strong aria-hidden="true">1.</strong> Linear correction</a></span></li><li class="chapter-item expanded "><span class="chapter-link-wrapper"><a href="theory/structure.html"><strong aria-hidden="true">2.</strong> Appearance coordinates and grading</a></span><ol class="section"><li class="chapter-item expanded "><span class="chapter-link-wrapper"><a href="theory/tone.html"><strong aria-hidden="true">2.1.</strong> Saturation-preserving tone curve</a></span></li><li class="chapter-item expanded "><span class="chapter-link-wrapper"><a href="theory/color.html"><strong aria-hidden="true">2.2.</strong> Tone-shaped color operators</a></span></li></ol><li class="chapter-item expanded "><span class="chapter-link-wrapper"><a href="theory/evaluation.html"><strong aria-hidden="true">3.</strong> Evaluation and interpolation</a></span><ol class="section"><li class="chapter-item expanded "><span class="chapter-link-wrapper"><a href="theory/hk-guard.html"><strong aria-hidden="true">3.1.</strong> Bounded H–K guard</a></span></li><li class="chapter-item expanded "><span class="chapter-link-wrapper"><a href="theory/lut.html"><strong aria-hidden="true">3.2.</strong> Direct and sampled evaluation</a></span></li></ol><li class="chapter-item expanded "><li class="part-title">Developing the project</li></li><li class="chapter-item expanded "><span class="chapter-link-wrapper"><a href="development/architecture.html"><strong aria-hidden="true">1.</strong> Architecture and runtime</a></span></li><li class="chapter-item expanded "><span class="chapter-link-wrapper"><a href="development/next-policies.html"><strong aria-hidden="true">2.</strong> Next Blender policy machines</a></span></li><li class="chapter-item expanded "><span class="chapter-link-wrapper"><a href="development/building.html"><strong aria-hidden="true">3.</strong> Building, testing and provenance</a></span></li><li class="chapter-item expanded "><span class="chapter-link-wrapper"><a href="development/contributing.html"><strong aria-hidden="true">4.</strong> Contributing and publishing</a></span><ol class="section"><li class="chapter-item expanded "><span class="chapter-link-wrapper"><a href="development/contributing-model.html"><strong aria-hidden="true">4.1.</strong> Code and grading model</a></span></li><li class="chapter-item expanded "><span class="chapter-link-wrapper"><a href="development/localization.html"><strong aria-hidden="true">4.2.</strong> Localization</a></span></li><li class="chapter-item expanded "><span class="chapter-link-wrapper"><a href="development/documentation.html"><strong aria-hidden="true">4.3.</strong> Documentation and media</a></span></li><li class="chapter-item expanded "><span class="chapter-link-wrapper"><a href="development/testing.html"><strong aria-hidden="true">4.4.</strong> Testing and measurements</a></span></li><li class="chapter-item expanded "><span class="chapter-link-wrapper"><a href="development/lut-domain-study.html"><strong aria-hidden="true">4.5.</strong> LUT sampling study: upper bound 128</a></span></li><li class="chapter-item expanded "><span class="chapter-link-wrapper"><a href="development/publishing.html"><strong aria-hidden="true">4.6.</strong> Publishing</a></span></li><li class="chapter-item expanded "><span class="chapter-link-wrapper"><a href="development/forward-inverse-math.html"><strong aria-hidden="true">4.7.</strong> Full forward and inverse math</a></span></li></ol><li class="chapter-item expanded "><li class="part-title">Reference</li></li><li class="chapter-item expanded "><span class="chapter-link-wrapper"><a href="reference/credits.html"><strong aria-hidden="true">1.</strong> Credits and references</a></span></li><li class="chapter-item expanded "><span class="chapter-link-wrapper"><a href="reference/license.html"><strong aria-hidden="true">2.</strong> License</a></span></li></ol>';
        // Set the current, active page, and reveal it if it's hidden
        let current_page = document.location.href.toString().split('#')[0].split('?')[0];
        if (current_page.endsWith('/')) {
            current_page += 'index.html';
        }
        const links = Array.prototype.slice.call(this.querySelectorAll('a'));
        const l = links.length;
        for (let i = 0; i < l; ++i) {
            const link = links[i];
            const href = link.getAttribute('href');
            if (href && !href.startsWith('#') && !/^(?:[a-z+]+:)?\/\//.test(href)) {
                link.href = path_to_root + href;
            }
            // The 'index' page is supposed to alias the first chapter in the book.
            // Check both with and without the '.html' suffix to be robust against pretty URLs
            if (link.href.replace(/\.html$/, '') === current_page.replace(/\.html$/, '')
                || i === 0
                && path_to_root === ''
                && current_page.endsWith('/index.html')) {
                link.classList.add('active');
                let parent = link.parentElement;
                while (parent) {
                    if (parent.tagName === 'LI' && parent.classList.contains('chapter-item')) {
                        parent.classList.add('expanded');
                    }
                    parent = parent.parentElement;
                }
            }
        }
        // Track and set sidebar scroll position
        this.addEventListener('click', e => {
            if (e.target.tagName === 'A') {
                const clientRect = e.target.getBoundingClientRect();
                const sidebarRect = this.getBoundingClientRect();
                sessionStorage.setItem('sidebar-scroll-offset', clientRect.top - sidebarRect.top);
            }
        }, { passive: true });
        const sidebarScrollOffset = sessionStorage.getItem('sidebar-scroll-offset');
        sessionStorage.removeItem('sidebar-scroll-offset');
        if (sidebarScrollOffset !== null) {
            // preserve sidebar scroll position when navigating via links within sidebar
            const activeSection = this.querySelector('.active');
            if (activeSection) {
                const clientRect = activeSection.getBoundingClientRect();
                const sidebarRect = this.getBoundingClientRect();
                const currentOffset = clientRect.top - sidebarRect.top;
                this.scrollTop += currentOffset - parseFloat(sidebarScrollOffset);
            }
        } else {
            // scroll sidebar to current active section when navigating via
            // 'next/previous chapter' buttons
            const activeSection = document.querySelector('#mdbook-sidebar .active');
            if (activeSection) {
                activeSection.scrollIntoView({ block: 'center' });
            }
        }
        // Toggle buttons
        const sidebarAnchorToggles = document.querySelectorAll('.chapter-fold-toggle');
        function toggleSection(ev) {
            ev.currentTarget.parentElement.parentElement.classList.toggle('expanded');
        }
        Array.from(sidebarAnchorToggles).forEach(el => {
            el.addEventListener('click', toggleSection);
        });
    }
}
window.customElements.define('mdbook-sidebar-scrollbox', MDBookSidebarScrollbox);

