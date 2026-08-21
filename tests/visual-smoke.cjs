#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const target = process.argv[2] || 'http://localhost:9412/technology-blog-rankings-preview/';
const output = path.resolve(__dirname, '..', 'build', 'qa');
fs.mkdirSync(output, { recursive: true });

function contrastRatio(foreground, background) {
	const parse = (value) => (value.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
	const luminance = (value) => {
		const channels = parse(value).map((channel) => {
			const normalized = channel / 255;
			return normalized <= 0.03928
				? normalized / 12.92
				: Math.pow((normalized + 0.055) / 1.055, 2.4);
		});
		return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
	};
	const first = luminance(foreground);
	const second = luminance(background);
	return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
}

(async () => {
	const browser = await chromium.launch({ headless: true });
	const report = { target, errors: [], checks: {} };
	for (const viewport of [
		{ name: 'desktop', width: 1440, height: 1000 },
		{ name: 'mobile', width: 375, height: 812 },
	]) {
		const page = await browser.newPage({ viewport });
		page.on('pageerror', (error) => report.errors.push(`${viewport.name}: ${error.message}`));
		page.on('console', (message) => {
			if (message.type() === 'error') {
				report.errors.push(`${viewport.name}: ${message.text()}`);
			}
		});
		const response = await page.goto(target, { waitUntil: 'networkidle' });
		report.checks[`${viewport.name}_http_200`] = response && response.status() === 200;
		report.checks[`${viewport.name}_h1`] = await page.locator('h1#gbr-title').textContent();
		report.checks[`${viewport.name}_overflow`] = await page.evaluate(
			() => document.documentElement.scrollWidth <= document.documentElement.clientWidth
		);
		report.checks[`${viewport.name}_button_radius`] = await page
			.locator('.gbr-button')
			.first()
			.evaluate((element) => getComputedStyle(element).borderRadius);
		const primaryColors = await page.locator('.gbr-button--primary').first().evaluate((element) => {
			const styles = getComputedStyle(element);
			return { color: styles.color, background: styles.backgroundColor };
		});
		report.checks[`${viewport.name}_primary_contrast`] = Number(
			contrastRatio(primaryColors.color, primaryColors.background).toFixed(2)
		);
		report.checks[`${viewport.name}_nofollow_count`] = await page.locator('a[rel~="nofollow"]').count();
		await page.screenshot({ path: path.join(output, `${viewport.name}-light.png`), fullPage: true });

		await page.locator('[data-gbr-tab="publisher_company"]').click();
		report.checks[`${viewport.name}_publisher_visible`] = await page
			.locator('[data-gbr-panel="publisher_company"]')
			.isVisible();
		report.checks[`${viewport.name}_independent_hidden`] = await page
			.locator('[data-gbr-panel="independent"]')
			.isHidden();

		await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'));
		await page.screenshot({ path: path.join(output, `${viewport.name}-dark.png`), fullPage: true });
		await page.close();
	}
	await browser.close();

	const failed = report.errors.length > 0 || Object.entries(report.checks).some(([key, value]) => {
		if (key.endsWith('_button_radius')) return value !== '4px';
		if (key.endsWith('_primary_contrast')) return value < 4.5;
		if (key.endsWith('_h1')) return value !== 'Technology Blog Rankings';
		if (key.endsWith('_nofollow_count')) return value < 20;
		return value !== true;
	});
	fs.writeFileSync(path.join(output, 'visual-smoke.json'), `${JSON.stringify(report, null, 2)}\n`);
	console.log(JSON.stringify(report, null, 2));
	process.exitCode = failed ? 1 : 0;
})().catch((error) => {
	console.error(error);
	process.exitCode = 1;
});
