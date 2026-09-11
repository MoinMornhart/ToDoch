import { mkdirSync } from 'node:fs';
import { expect, test, type Page } from '@playwright/test';

// Erzeugt die Bilder für die README. Läuft nur auf Wunsch, je Sprache mit frischer Datenbank:
//   SCREENSHOTS=1 npx playwright test e2e/screenshots.spec.ts                        → docs/images
//   SCREENSHOTS=1 SCREENSHOT_LANG=en npx playwright test e2e/screenshots.spec.ts     → docs/images/en
test.skip(!process.env.SCREENSHOTS, 'Nur mit SCREENSHOTS=1');

const LANG: 'de' | 'en' = process.env.SCREENSHOT_LANG === 'en' ? 'en' : 'de';
const OUT = LANG === 'en' ? '../docs/images/en' : '../docs/images';
const LOCALE = LANG === 'en' ? 'en-US' : 'de-DE';
const EMAIL = 'anna@example.org';
const PASSWORD = 'Korrekt-Pferd-Batterie-Heftklammer';

const L = {
	de: {
		setupCode: 'Einrichtungscode',
		name: 'Dein Name',
		email: 'E-Mail-Adresse',
		password: 'Passwort',
		password2: 'Passwort wiederholen',
		setup: 'Einrichten',
		signIn: 'Anmelden',
		quick: 'Neue Aufgabe',
		editTask: 'Aufgabe bearbeiten',
		addItem: 'Unterpunkt hinzufügen',
		note: 'Notiz',
		save: 'Speichern',
		upcoming: 'Demnächst',
		nextEvents: 'Nächste Termine',
		newMenu: 'Neu',
		task: /Aufgabe/,
		createTask: 'Aufgabe anlegen',
		title: 'Titel',
		high: 'Hoch',
		work: 'Arbeit',
		private: 'Privat'
	},
	en: {
		setupCode: 'Setup code',
		name: 'Your name',
		email: 'Email address',
		password: 'Password',
		password2: 'Repeat password',
		setup: 'Set up',
		signIn: 'Sign in',
		quick: 'New task',
		editTask: 'Edit task',
		addItem: 'Add item',
		note: 'Note',
		save: 'Save',
		upcoming: 'Upcoming',
		nextEvents: 'Next events',
		newMenu: 'New',
		task: /Task/,
		createTask: 'Create task',
		title: 'Title',
		high: 'High',
		work: 'Work',
		private: 'Private'
	}
}[LANG];

const D = {
	de: {
		meeting: 'Team-Meeting vorbereiten',
		checklist: ['Agenda verschicken', 'Raum buchen', 'Zahlen aus Q3 zusammenstellen'],
		meetingNote:
			'**Themen:** Roadmap, Urlaubsplanung\n\n- Budget klären\n- Neue Kollegin vorstellen',
		quickLine: 'Reifenwechsel buchen nächste Woche 8:30 !mittel #auto @privat',
		quickTag: 'auto',
		ticket: 'Website-Relaunch abstimmen',
		ticketItems: ['Entwürfe sichten', 'Texte freigeben'],
		ticketNote: 'Mit **Marketing** und IT, Termin bis Monatsende.',
		events: {
			client: 'Kundentermin Berger',
			clientPlace: 'Büro Berger',
			lunch: 'Mittagessen mit Lena',
			workshop: 'Workshop Q4',
			room: 'Raum 3',
			dentist: 'Zahnarzt',
			family: 'Familienfeier'
		}
	},
	en: {
		meeting: 'Prepare team meeting',
		checklist: ['Send agenda', 'Book a room', 'Collect Q3 figures'],
		meetingNote:
			'**Topics:** roadmap, holiday planning\n\n- Agree on budget\n- Introduce new colleague',
		quickLine: 'Book tyre change 2026-09-18 8:30 !high #car @private',
		quickTag: 'car',
		ticket: 'Agree on website relaunch',
		ticketItems: ['Review drafts', 'Approve copy'],
		ticketNote: 'With **marketing** and IT, due by the end of the month.',
		events: {
			client: 'Client meeting Berger',
			clientPlace: 'Berger office',
			lunch: 'Lunch with Lena',
			workshop: 'Workshop Q4',
			room: 'Room 3',
			dentist: 'Dentist',
			family: 'Family party'
		}
	}
}[LANG];

// Deutsch über die Schnellerfassung (zeigt, was sie versteht) …
const QUICK_TASKS = [
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

// … Englisch direkt über die API (feste Zeiten, damit die Bilder beider Sprachen gleich aussehen)
function englishTasks(day: (offset: number) => string, nextFriday: string) {
	return [
		{
			title: 'Send offer to Berger Ltd',
			due_date: day(0),
			due_time: '10:00',
			priority: 3,
			tags: ['client'],
			area: 'Work'
		},
		{ title: 'Prepare team meeting', due_date: day(0), due_time: '14:30', area: 'Work' },
		{
			title: 'Groceries',
			due_date: day(0),
			due_time: '19:00',
			tags: ['household'],
			area: 'Private'
		},
		{ title: 'Buy birthday present for Lena', due_date: day(-2), priority: 2, area: 'Private' },
		{ title: 'Pay electricity bill', due_date: day(1), tags: ['finance'], area: 'Private' },
		{
			title: 'Write weekly report',
			due_date: day(0),
			due_time: '17:00',
			recurrence: 'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR',
			area: 'Work'
		},
		{
			title: 'Water the plants',
			due_date: day(0),
			recurrence: 'FREQ=DAILY;INTERVAL=3',
			area: 'Private'
		},
		{
			title: 'Call the dentist',
			due_date: day(2),
			due_time: '09:00',
			tags: ['health'],
			area: 'Private'
		},
		{
			title: 'File tax return',
			due_date: '2026-10-31',
			priority: 3,
			tags: ['finance'],
			area: 'Private'
		},
		{
			title: 'Finish Q4 presentation',
			due_date: nextFriday,
			priority: 2,
			tags: ['project'],
			area: 'Work'
		}
	];
}

async function calm(page: Page) {
	await page.locator('main h1').click();
	await expect(page.getByRole('status').locator('div')).toHaveCount(0, { timeout: 10_000 });
	await page.mouse.move(0, 0);
}

async function login(page: Page) {
	await page.goto('/login');
	await page.getByLabel(L.email).fill(EMAIL);
	await page.getByLabel(L.password).fill(PASSWORD);
	await page.getByRole('button', { name: L.signIn, exact: true }).click();
	await expect(page).toHaveURL(/\/$/);
	await expect(page.getByRole('region', { name: L.nextEvents })).toBeVisible();
}

function isoDay(date: Date): string {
	return date.toLocaleDateString('en-CA');
}

function relativeDay(offset: number, from = new Date()): string {
	const d = new Date(from);
	d.setDate(from.getDate() + offset);
	return isoDay(d);
}

async function apiHeaders(page: Page) {
	const cookies = await page.context().cookies();
	return {
		'X-CSRF-Token': cookies.find((c) => c.name === '__Host-todoch_csrf')?.value ?? '',
		Origin: 'http://localhost:4173'
	};
}

async function areaIds(page: Page): Promise<Record<string, string>> {
	const areas = (await (await page.request.get('/api/areas')).json()) as {
		id: string;
		name: string;
	}[];
	return Object.fromEntries(areas.map((a) => [a.name, a.id]));
}

/** Englische Bereichsnamen und Aufgaben über die API anlegen. */
async function prepareEnglish(page: Page) {
	const headers = await apiHeaders(page);
	const ids = await areaIds(page);
	for (const [from, to] of [
		['Arbeit', 'Work'],
		['Privat', 'Private']
	] as const) {
		const r = await page.request.patch(`/api/areas/${ids[from]}`, { data: { name: to }, headers });
		expect(r.status()).toBe(200);
	}
	const renamed = await areaIds(page);
	const today = new Date();
	const friday = relativeDay(((5 - today.getDay() + 7) % 7) + 7);
	for (const { area, ...task } of englishTasks(relativeDay, friday)) {
		const r = await page.request.post('/api/tasks', {
			data: { ...task, area_id: renamed[area] },
			headers
		});
		expect(r.status()).toBe(201);
	}
}

/** Beispieltermine in der aktuellen Woche (über die API, mit CSRF-Token aus dem Cookie). */
async function createEvents(page: Page) {
	const headers = await apiHeaders(page);
	const ids = await areaIds(page);
	const now = new Date();
	const monday = new Date(now);
	monday.setDate(now.getDate() - ((now.getDay() + 6) % 7));
	const day = (offset: number) => relativeDay(offset, monday);
	const e = D.events;
	const events = [
		{
			title: 'Standup',
			start_date: day(0),
			start_time: '09:00',
			end_time: '09:15',
			area_id: ids[L.work],
			rrule: 'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR'
		},
		{
			title: e.client,
			start_date: day(1),
			start_time: '14:00',
			end_time: '15:30',
			location: e.clientPlace,
			is_fixed: true,
			area_id: ids[L.work]
		},
		{
			title: e.lunch,
			start_date: day(2),
			start_time: '12:00',
			end_time: '13:00',
			area_id: ids[L.private]
		},
		{
			title: e.workshop,
			start_date: day(3),
			start_time: '10:00',
			end_time: '12:00',
			location: e.room,
			area_id: ids[L.work]
		},
		{
			title: e.dentist,
			start_date: day(3),
			start_time: '11:00',
			end_time: '11:45',
			area_id: ids[L.private]
		},
		{
			title: 'Sport',
			start_date: day(4),
			start_time: '18:00',
			end_time: '19:30',
			area_id: ids[L.private],
			rrule: 'FREQ=WEEKLY'
		},
		{ title: e.family, start_date: day(5), all_day: true, area_id: ids[L.private] }
	];
	for (const event of events) {
		const response = await page.request.post('/api/events', { data: event, headers });
		expect(response.status()).toBe(201);
	}
}

test('README-Screenshots', async ({ browser }) => {
	test.setTimeout(180_000);
	mkdirSync(OUT, { recursive: true });
	const light = await browser.newContext({
		viewport: { width: 1280, height: 800 },
		deviceScaleFactor: 2,
		colorScheme: 'light',
		locale: LOCALE
	});
	const page = await light.newPage();

	await page.goto('/setup#code=e2e-setup-code-123456');
	await expect(page.getByLabel(L.setupCode)).toHaveValue('e2e-setup-code-123456');
	await page.getByLabel(L.name).fill('Anna');
	await page.getByLabel(L.email).fill(EMAIL);
	await page.getByLabel(L.password, { exact: true }).fill(PASSWORD);
	await page.getByLabel(L.password2).fill(PASSWORD);
	await page.getByRole('button', { name: L.setup }).click();
	await expect(page).toHaveURL(/\/$/);

	const quick = page.getByLabel(L.quick);
	if (LANG === 'en') {
		await prepareEnglish(page);
		await page.goto('/today');
	} else {
		await page.goto('/today');
		for (const text of QUICK_TASKS) {
			await quick.fill(text);
			await quick.press('Enter');
			await expect(quick).toHaveValue('');
		}
	}

	// Unterpunkte und Notiz für eine Aufgabe
	await page.getByRole('button', { name: new RegExp(`^${D.meeting}`) }).click();
	const dialog = page.getByRole('dialog', { name: L.editTask });
	for (const item of D.checklist) {
		await dialog.getByLabel(L.addItem).first().fill(item);
		await dialog.getByLabel(L.addItem).first().press('Enter');
	}
	await dialog.getByRole('checkbox', { name: D.checklist[0] }).check();
	await dialog.getByLabel(L.note).fill(D.meetingNote);
	await dialog.getByRole('button', { name: L.save }).click();
	await expect(dialog).toBeHidden();

	await calm(page);
	await page.screenshot({ path: `${OUT}/heute.png` });

	await quick.fill(D.quickLine);
	await expect(page.getByTestId('quick-preview')).toContainText(D.quickTag);
	await page.mouse.move(0, 0);
	const box = await page.locator('form').filter({ has: quick }).boundingBox();
	if (!box) throw new Error('Schnellerfassung nicht gefunden');
	await page.screenshot({
		path: `${OUT}/schnellerfassung.png`,
		clip: { x: box.x - 24, y: box.y - 20, width: box.width + 48, height: box.height + 40 }
	});
	await quick.fill('');

	await page.getByRole('button', { name: new RegExp(`^${D.meeting}`) }).click();
	await expect(dialog).toBeVisible();
	await page.screenshot({ path: `${OUT}/bearbeiten.png` });
	await page.keyboard.press('Escape');

	await page.getByRole('link', { name: L.upcoming }).first().click();
	await calm(page);
	await page.screenshot({ path: `${OUT}/demnaechst.png` });

	await createEvents(page);
	await page.goto(`/calendar?view=week&date=${isoDay(new Date())}`);
	await expect(page.getByRole('button', { name: /Workshop Q4/ })).toBeVisible();
	await calm(page);
	await page.screenshot({ path: `${OUT}/kalender-woche.png` });
	await page.goto(`/calendar?view=month&date=${isoDay(new Date())}`);
	await expect(
		page.getByRole('button', { name: new RegExp(D.events.family) }).first()
	).toBeVisible();
	await calm(page);
	await page.screenshot({ path: `${OUT}/kalender-monat.png` });

	await page.goto('/');
	await expect(page.getByRole('region', { name: L.nextEvents })).toContainText('Sport');
	await calm(page);
	await page.screenshot({ path: `${OUT}/uebersicht.png` });

	await page.getByRole('button', { name: L.newMenu, exact: true }).first().click();
	await page.getByRole('menuitem', { name: L.task }).click();
	const ticket = page.getByRole('dialog', { name: L.createTask });
	await ticket.getByLabel(L.title).fill(D.ticket);
	await ticket.getByText(L.high, { exact: true }).click();
	for (const item of D.ticketItems) {
		await ticket.getByLabel(L.addItem).first().fill(item);
		await ticket.getByLabel(L.addItem).first().press('Enter');
	}
	await ticket.getByLabel(L.note).fill(D.ticketNote);
	await page.mouse.move(0, 0);
	await page.screenshot({ path: `${OUT}/ticket.png` });
	await page.keyboard.press('Escape');
	await light.close();

	const dark = await browser.newContext({
		viewport: { width: 1280, height: 800 },
		deviceScaleFactor: 2,
		colorScheme: 'dark',
		locale: LOCALE
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
		locale: LOCALE
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
