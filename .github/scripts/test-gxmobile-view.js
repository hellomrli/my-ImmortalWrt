#!/usr/bin/env node
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const source = fs.readFileSync(path.join(__dirname,
	'../../packages/luci-app-gxmobile/htdocs/luci-static/resources/view/gxmobile.js'), 'utf8');
const payload = '<svg onload=document.body.dataset.reviewxss=1>';

function harness(writable = false) {
	const htmlWrites = [], notifications = [], modals = [], replies = {};
	class Text {
		constructor(value) { this.textContent = String(value); }
	}
	class Element {
		constructor(tag, attrs) {
			this.tag = tag;
			this.children = [];
			this.style = {};
			this.value = '';
			Object.assign(this, attrs);
		}
		get textContent() { return this.children.map(child => child.textContent).join(''); }
		set textContent(value) { this.children = [new Text(value)]; }
		set innerHTML(value) {
			htmlWrites.push(String(value));
			this.children = [new Text(value)];
		}
	}
	// Model LuCI dom.append, NOT a conventional escaping virtual DOM: a scalar
	// child goes to innerHTML, while strings inside arrays become text nodes.
	function append(node, children) {
		if (Array.isArray(children)) {
			children.forEach(child => {
				if (child != null) node.children.push(child instanceof Element ? child : new Text(child));
			});
		} else if (children instanceof Element) {
			node.children.push(children);
		} else if (children != null) {
			node.innerHTML = children;
		}
	}
	function E(tag, attrs, children) {
		const node = new Element(tag, attrs);
		append(node, children);
		return node;
	}
	const dom = { content(node, children) { node.children = []; append(node, children); } };
	const ui = {
		addNotification(_, node) { notifications.push(node); },
		showModal(_, nodes) { modals.push(nodes); },
		hideModal() {},
		createHandlerFn(context, fn, ...args) { return fn.bind(context, ...args); }
	};
	const rpc = { declare({ method }) { return () => Promise.resolve(replies[method] || {}); } };
	function updateTable(table, rows) {
		// LuCI tables interpret arrays as [sort value, display value], not text
		// children. Exercise that extra boundary before sending cells to E().
		table.rows = rows.map(row => row.map(value => E('td', {}, Array.isArray(value) ? value[1] : value)));
	}
	const view = new Function('view', 'rpc', 'ui', 'poll', 'dom', 'E', 'cbi_update_table', 'L', 'window', source)(
		{ extend: value => value }, rpc, ui, { add() {} }, dom, E, updateTable,
		{ hasViewPermission: () => writable }, { location: { origin: 'http://router.invalid' } });
	const channel = {
		name: payload, group: payload, winner: payload, tag: payload,
		live: payload, gone: 0, url: 'http://gateway.invalid/1/index.m3u8'
	};
	view.render([{}, {}, { channels: [channel] }, { report: payload }]);
	return { view, channel, replies, notifications, modals,
		assertSafe() {
			assert.deepEqual(htmlWrites.filter(value => value.includes(payload)), [], 'untrusted data reached innerHTML');
		}
	};
}

for (const writable of [false, true]) {
	test(`channel and group text is safe with writable=${writable}`, () => {
		const h = harness(writable);
		const cells = h.view.table.rows[0];
		for (let i = 0; i < 4; i++) assert.equal(cells[i].textContent, payload);
		assert.equal(cells[4].textContent, `${payload} / 0`);
		assert.equal(h.view.group.children[1].textContent, payload);
		assert.equal(h.view.group.children[1].value, payload);
		assert.equal(cells[5].children[0].children[0].disabled, !writable);
		h.assertSafe();
	});
}

test('initial and polled reports remain literal text', async () => {
	const h = harness();
	assert.equal(h.view.report.textContent, payload);
	h.replies.channels = { channels: [h.channel] };
	h.replies.report = { report: payload + ' refreshed' };
	await h.view.refresh();
	assert.equal(h.view.report.textContent, payload + ' refreshed');
	h.assertSafe();
});

test('delete confirmation keeps the channel name as text', () => {
	const h = harness(true);
	h.view.remove(h.channel);
	assert.ok(h.modals[0][0].textContent.includes(payload));
	h.assertSafe();
});

test('RPC error notifications are text', async () => {
	const h = harness(true);
	h.replies.scan = { error: payload };
	await h.view.scan('fast');
	assert.equal(h.notifications[0].textContent, payload);
	h.assertSafe();
});

test('unsafe URL schemes do not become clickable links', () => {
	const h = harness();
	h.channel.url = 'javascript:alert(1)';
	h.view.updateChannels();
	assert.equal(h.view.table.rows[0][2].children.some(child => child.tag === 'a'), false);
	h.assertSafe();
});
