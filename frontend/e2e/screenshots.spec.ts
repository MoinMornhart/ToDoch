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
	await page.getByRole('button', { name: 'Anmelden', exact: true }).click();
	await expect(page).toHaveURL(/\/$/);
	await expect(page.getByRole('region', { name: 'Nächste Termine' })).toBeVisible();
}

function isoDay(date: Date): string {
	return date.toLocaleDateString('en-CA');
}

/** Beispieltermine in der aktuellen Woche (über die API, mit CSRF-Token aus dem Cookie). */
async function createEvents(page: Page) {
	const cookies = await page.context().cookies();
	const headers = {
		'X-CSRF-Token': cookies.find((c) => c.name === '__Host-todoch_csrf')?.value ?? '',
		Origin: 'http://localhost:4173'
	};
	const areas = (await (await page.request.get('/api/areas')).json()) as {
		id: string;
		name: string;
	}[];
	const area = (name: string) => areas.find((a) => a.name === name)?.id;
	const now = new Date();
	const monday = new Date(now);
	monday.setDate(now.getDate() - ((now.getDay() + 6) % 7));
	const day = (offset: number) => {
		const d = new Date(monday);
		d.setDate(monday.getDate() + offset);
		return isoDay(d);
	};
	const events = [
		{
			title: 'Standup',
			start_date: day(0),
			start_time: '09:00',
			end_time: '09:15',
			area_id: area('Arbeit'),
			rrule: 'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR'
		},
		{
			title: 'Kundentermin Berger',
			start_date: day(1),
			start_time: '14:00',
			end_time: '15:30',
			location: 'Büro Berger',
			is_fixed: true,
			area_id: area('Arbeit')
		},
		{
			title: 'Mittagessen mit Lena',
			start_date: day(2),
			start_time: '12:00',
			end_time: '13:00',
			area_id: area('Privat')
		},
		{
			title: 'Workshop Q4',
			start_date: day(3),
			start_time: '10:00',
			end_time: '12:00',
			location: 'Raum 3',
			area_id: area('Arbeit')
		},
		{
			title: 'Zahnarzt',
			start_date: day(3),
			start_time: '11:00',
			end_time: '11:45',
			area_id: area('Privat')
		},
		{
			title: 'Sport',
			start_date: day(4),
			start_time: '18:00',
			end_time: '19:30',
			area_id: area('Privat'),
			rrule: 'FREQ=WEEKLY'
		},
		{ title: 'Familienfeier', start_date: day(5), all_day: true, area_id: area('Privat') }
	];
	for (const event of events) {
		const response = await page.request.post('/api/events', { data: event, headers });
		expect(response.status()).toBe(201);
	}
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
	await expect(page).toHaveURL(/\/$/);
	await page.goto('/today');

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

	await createEvents(page);
	await page.goto(`/calendar?view=week&date=${isoDay(new Date())}`);
	await expect(page.getByRole('button', { name: /Workshop Q4/ })).toBeVisible();
	await calm(page);
	await page.screenshot({ path: `${OUT}/kalender-woche.png` });
	await page.goto(`/calendar?view=month&date=${isoDay(new Date())}`);
	await expect(page.getByRole('button', { name: /Familienfeier/ }).first()).toBeVisible();
	await calm(page);
	await page.screenshot({ path: `${OUT}/kalender-monat.png` });

	await page.goto('/');
	await expect(page.getByRole('region', { name: 'Nächste Termine' })).toContainText('Sport');
	await calm(page);
	await page.screenshot({ path: `${OUT}/uebersicht.png` });

	await page.getByRole('button', { name: 'Neu', exact: true }).first().click();
	await page.getByRole('menuitem', { name: /Aufgabe/ }).click();
	const ticket = page.getByRole('dialog', { name: 'Aufgabe anlegen' });
	await ticket.getByLabel('Titel').fill('Website-Relaunch abstimmen');
	await ticket.getByText('Hoch', { exact: true }).click();
	for (const item of ['Entwürfe sichten', 'Texte freigeben']) {
		await ticket.getByLabel('Unterpunkt hinzufügen').first().fill(item);
		await ticket.getByLabel('Unterpunkt hinzufügen').first().press('Enter');
	}
	await ticket.getByLabel('Notiz').fill('Mit **Marketing** und IT, Termin bis Monatsende.');
	await page.mouse.move(0, 0);
	await page.screenshot({ path: `${OUT}/ticket.png` });
	await page.keyboard.press('Escape');
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
	await darkPage.screenshot({ path: `${OUT}/uebersicht-dunkel.png` });
	await darkPage.goto('/today');
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
	await phone.goto('/upcoming');
	await calm(phone);
	await phone.screenshot({ path: `${OUT}/mobil-demnaechst.png` });
	await mobile.close();
});
