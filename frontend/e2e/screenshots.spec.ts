import { expect, test, type Page } from '@playwright/test';

// Erzeugt die Bilder für die README (docs/images). Läuft nur auf Wunsch:
//   SCREENSHOTS=1 npx playwright test e2e/screenshots.spec.ts
test.skip(!process.env.SCREENSHOTS, 'Nur mit SCREENSHOTS=1');

const OUT = '../docs/images';
const EMAIL = 'anna@example.org';
const PASSWORD = 'Korrekt-Pferd-Batterie-Heftklammer';

const TASKS = [
	'Angebot für Firma Berger schicken heute 10:00 !hoch #kunde @arbeit',
	'Team-Meeting vorbereiten heute 14:30 @arbeit',
	'Einkaufen heute abend #haushalt @privat',
	'Geburtstagsgeschenk für Lena besorgen 2026-09-09 !mittel @privat',
	'Rechnung Stadtwerke zahlen morgen #finanzen @privat',
	'Wochenbericht schreiben werktags 17:00 @arbeit',
	'Blumen gießen alle 3 Tage @privat',
	'Zahnarzt anrufen übermorgen 9:00 #gesundheit @privat',
	'Steuererklärung abgeben bis zum 31.10. !hoch #finanzen @privat',
	'Präsentation Q4 fertigstellen nächsten Freitag !mittel #projekt @arbeit'
];

async function calm(page: Page) {
	await page.locator('main h1').click();
	await expect(page.getByRole('status').locator('div')).toHaveCount(0, { timeout: 10_000 });
	await page.mouse.move(0, 0);
}

async function login(page: Page) {
	await page.goto('/login');
	await page.getByLabel('E-Mail-Adresse').fill(EMAIL);
	await page.getByLabel('Passwort').fill(PASSWORD);
	await page.getByRole('button', { name: 'Anmelden' }).click();
	await expect(page).toHaveURL(/\/today$/);
}

test('README-Screenshots', async ({ browser }) => {
	test.setTimeout(180_000);
	const light = await browser.newContext({
		viewport: { width: 1280, height: 800 },
		deviceScaleFactor: 2,
		colorScheme: 'light',
		locale: 'de-DE'
	});
	const page = await light.newPage();

	await page.goto('/setup#code=e2e-setup-code-123456');
	await expect(page.getByLabel('Einrichtungscode')).toHaveValue('e2e-setup-code-123456');
	await page.getByLabel('Dein Name').fill('Anna');
	await page.getByLabel('E-Mail-Adresse').fill(EMAIL);
	await page.getByLabel('Passwort', { exact: true }).fill(PASSWORD);
	await page.getByLabel('Passwort wiederholen').fill(PASSWORD);
	await page.getByRole('button', { name: 'Einrichten' }).click();
	await expect(page).toHaveURL(/\/today$/);

	const quick = page.getByLabel('Neue Aufgabe');
	for (const text of TASKS) {
		await quick.fill(text);
		await quick.press('Enter');
		await expect(quick).toHaveValue('');
	}

	// Unterpunkte und Notiz für eine Aufgabe
	await page.getByRole('button', { name: /^Team-Meeting vorbereiten/ }).click();
	const dialog = page.getByRole('dialog', { name: 'Aufgabe bearbeiten' });
	for (const item of ['Agenda verschicken', 'Raum buchen', 'Zahlen aus Q3 zusammenstellen']) {
		await dialog.getByLabel('Unterpunkt hinzufügen').first().fill(item);
		await dialog.getByLabel('Unterpunkt hinzufügen').first().press('Enter');
	}
	await dialog.getByRole('checkbox', { name: 'Agenda verschicken' }).check();
	await dialog
		.getByLabel('Notiz')
		.fill('**Themen:** Roadmap, Urlaubsplanung\n\n- Budget klären\n- Neue Kollegin vorstellen');
	await dialog.getByRole('button', { name: 'Speichern' }).click();
	await expect(dialog).toBeHidden();

	await calm(page);
	await page.screenshot({ path: `${OUT}/heute.png` });

	await quick.fill('Reifenwechsel buchen nächste Woche 8:30 !mittel #auto @privat');
	await expect(page.getByTestId('quick-preview')).toContainText('auto');
	await page.mouse.move(0, 0);
	const box = await page.locator('form').filter({ has: quick }).boundingBox();
	if (!box) throw new Error('Schnellerfassung nicht gefunden');
	await page.screenshot({
		path: `${OUT}/schnellerfassung.png`,
		clip: { x: box.x - 24, y: box.y - 20, width: box.width + 48, height: box.height + 40 }
	});
	await quick.fill('');

	await page.getByRole('button', { name: /^Team-Meeting vorbereiten/ }).click();
	await expect(dialog).toBeVisible();
	await page.screenshot({ path: `${OUT}/bearbeiten.png` });
	await page.keyboard.press('Escape');

	await page.getByRole('link', { name: 'Demnächst' }).first().click();
	await calm(page);
	await page.screenshot({ path: `${OUT}/demnaechst.png` });
	await light.close();

	const dark = await browser.newContext({
		viewport: { width: 1280, height: 800 },
		deviceScaleFactor: 2,
		colorScheme: 'dark',
		locale: 'de-DE'
	});
	const darkPage = await dark.newPage();
	await login(darkPage);
	await calm(darkPage);
	await darkPage.screenshot({ path: `${OUT}/heute-dunkel.png` });
	await dark.close();

	const mobile = await browser.newContext({
		viewport: { width: 390, height: 844 },
		deviceScaleFactor: 3,
		isMobile: true,
		hasTouch: true,
		colorScheme: 'light',
		locale: 'de-DE'
	});
	const phone = await mobile.newPage();
	await login(phone);
	await calm(phone);
	await phone.screenshot({ path: `${OUT}/mobil.png` });
	await phone.getByRole('link', { name: 'Demnächst' }).last().click();
	await calm(phone);
	await phone.screenshot({ path: `${OUT}/mobil-demnaechst.png` });
	await mobile.close();
});
