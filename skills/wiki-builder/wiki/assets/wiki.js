const CHART_DEFAULTS = {
  textStyle: {
    fontFamily: "'Outfit', system-ui, sans-serif",
    color: '#78716c',
  },
  tooltip: {
    backgroundColor: '#fafaf8',
    borderColor: '#e5e3dc',
    textStyle: { color: '#1c1917', fontSize: 12 },
  },
};

const resizeObserver = new ResizeObserver(entries => {
  for (const entry of entries) {
    echarts.getInstanceByDom(entry.target)?.resize();
  }
});

document.addEventListener('DOMContentLoaded', () => {
  initCharts();
  buildToc();
});

// ECharts loads async — expose initCharts so its onload can call us back
window.__wikiInitCharts = initCharts;

function initCharts() {
  if (typeof echarts === 'undefined') return;

  document.querySelectorAll('.chart-container').forEach(el => {
    const scriptEl = el.querySelector('script[type="application/json"]');
    if (!scriptEl) return;

    let config;
    try {
      config = JSON.parse(scriptEl.textContent);
    } catch (e) {
      el.textContent = 'Chart parse error: ' + e.message;
      el.style.color = '#ad1000';
      return;
    }

    echarts.init(el).setOption(deepMergeDefaults(CHART_DEFAULTS, config));
    resizeObserver.observe(el);
  });
}

function buildToc() {
  const tocEl = document.getElementById('page-toc');
  if (!tocEl) return;

  const headings = Array.from(document.querySelectorAll('.content h2, .content h3'));
  if (headings.length === 0) {
    tocEl.closest('.toc-sidebar')?.classList.add('toc-sidebar--hidden');
    return;
  }

  const ul = document.createElement('ul');
  for (const h of headings) {
    const li = document.createElement('li');
    if (h.tagName === 'H3') li.classList.add('toc-h3');
    const a = document.createElement('a');
    a.href = '#' + h.id;
    a.textContent = h.textContent.trim();
    a.dataset.heading = h.id;
    li.appendChild(a);
    ul.appendChild(li);
  }
  tocEl.appendChild(ul);

  // wiki-body is the scroll container; sidebars are sticky within it
  const scrollEl = document.querySelector('.wiki-body');
  if (!scrollEl) return;

  function updateActive() {
    const threshold = 80;
    let activeId = headings[0].id;
    for (const h of headings) {
      if (h.getBoundingClientRect().top <= threshold) activeId = h.id;
    }
    for (const a of tocEl.querySelectorAll('a')) {
      a.classList.toggle('active', a.dataset.heading === activeId);
    }
  }

  scrollEl.addEventListener('scroll', updateActive, { passive: true });
  updateActive();
}

const isPlainObject = (x) => x !== null && typeof x === 'object' && !Array.isArray(x);

function deepMergeDefaults(defaults, overrides) {
  const result = Object.assign({}, defaults);
  for (const [k, v] of Object.entries(overrides)) {
    result[k] = isPlainObject(v) && isPlainObject(result[k])
      ? deepMergeDefaults(result[k], v)
      : v;
  }
  return result;
}
