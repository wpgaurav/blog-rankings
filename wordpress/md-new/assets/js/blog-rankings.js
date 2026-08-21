(function () {
	'use strict';

	var root = document.querySelector('.gbr-category');
	if (!root) {
		return;
	}

	var tabs = Array.prototype.slice.call(root.querySelectorAll('[data-gbr-tab]'));
	var panels = Array.prototype.slice.call(root.querySelectorAll('[data-gbr-panel]'));
	if (tabs.length !== 2 || panels.length !== 2) {
		return;
	}

	root.classList.add('gbr-has-js');

	function activate(slug, focus) {
		tabs.forEach(function (tab) {
			var selected = tab.getAttribute('data-gbr-tab') === slug;
			tab.classList.toggle('is-active', selected);
			tab.setAttribute('aria-selected', selected ? 'true' : 'false');
			tab.setAttribute('tabindex', selected ? '0' : '-1');
			if (selected && focus) {
				tab.focus();
			}
		});
		panels.forEach(function (panel) {
			panel.hidden = panel.getAttribute('data-gbr-panel') !== slug;
		});
	}

	tabs.forEach(function (tab, index) {
		tab.addEventListener('click', function () {
			activate(tab.getAttribute('data-gbr-tab'), false);
		});
		tab.addEventListener('keydown', function (event) {
			if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') {
				return;
			}
			event.preventDefault();
			var direction = event.key === 'ArrowRight' ? 1 : -1;
			var next = (index + direction + tabs.length) % tabs.length;
			activate(tabs[next].getAttribute('data-gbr-tab'), true);
		});
	});

	activate('independent', false);
})();
