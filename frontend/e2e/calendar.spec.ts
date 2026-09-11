import { expect, test, type Page } from '@playwright/test';

// Läuft nach app.spec.ts (dort wird das Konto eingerichtet).
const EMAIL = 'admin@example.org';
const PASSWORD = 'Korrekt-Pferd-Batterie-Heftklammer';

function watchProblems(page: Page): string[] {
	const problems: string[] = [];
	page.on('console', (message) => {
		if (/content security policy|refused to/i.test(message.text())) problems.push(message.text());
	});
	page.on('pageerror', (error) => problems.push(`pageerror: ${error.message}`));
	return problems;
}

test('Kalender: Serie anlegen, ein Vorkommen ändern und löschen', async ({ page }) => {
	const problems = watchProblems(page);
	await page.goto('/login');
	await page.getByLabel('E-Mail-Adresse').fill(EMAIL);
	await page.getByLabel('Passwort').fill(PASSWORD);
	await page.getByRole('button', { name: 'Anmelden', exact: true }).click();
	await expect(page).toHaveURL(/\/$/);

	await page.getByRole('link', { name: 'Kalender' }).first().click();
	await expect(page).toHaveURL(/\/calendar/);
	await expect(page.getByText(/^KW \d+$/)).toBeVisible();

	await page.getByRole('button', { name: 'Termin', exact: true }).click();
	const dialog = page.getByRole('dialog', { name: 'Neuer Termin' });
	await dialog.getByLabel('Titel').fill('Teammeeting');
	await dialog.getByLabel('Uhrzeit Beginn').fill('10:00');
	await dialog.getByLabel('Uhrzeit Ende').fill('11:00');
	await dialog.getByLabel('Ort').fill('Raum 3');
	await dialog.getByLabel('Wiederholung').selectOption('WEEKLY');
	await dialog.getByRole('button', { name: '1 Std. vorher' }).click();
	await dialog.getByRole('button', { name: 'Speichern' }).click();
	await expect(dialog).toBeHidden();
	await expect(page.getByRole('status')).toContainText('Termin gespeichert');
	await expect(page.getByRole('button', { name: /Teammeeting/ }).first()).toBeVisible();

	// Agenda: 30 Tage → fünf wöchentliche Vorkommen
	await page.getByRole('button', { name: 'Agenda' }).click();
	const occurrences = page.getByRole('button', { name: /Teammeeting/ });
	await expect(occurrences).toHaveCount(5);

	// Nur das zweite Vorkommen ändern
	await occurrences.nth(1).click();
	const edit = page.getByRole('dialog', { name: 'Termin bearbeiten' });
	await edit.getByLabel('Titel').fill('Teammeeting mit Kunde');
	await edit.getByRole('button', { name: 'Speichern' }).click();
	await page
		.getByRole('dialog', { name: 'Wiederkehrender Termin' })
		.getByRole('button', { name: 'Nur dieser Termin' })
		.click();
	await expect(edit).toBeHidden();
	await expect(page.getByRole('button', { name: /Teammeeting mit Kunde/ })).toHaveCount(1);
	await expect(page.getByRole('button', { name: /Teammeeting/ })).toHaveCount(5);

	// Das dritte Vorkommen löschen
	await page
		.getByRole('button', { name: /Teammeeting/ })
		.nth(2)
		.click();
	await edit.getByRole('button', { name: 'Löschen' }).click();
	await page
		.getByRole('dialog', { name: 'Wiederkehrender Termin' })
		.getByRole('button', { name: 'Nur dieser Termin' })
		.click();
	await expect(page.getByRole('button', { name: /Teammeeting/ })).toHaveCount(4);

	// Monatsansicht und Heute-Seite zeigen den Termin
	await page.getByRole('button', { name: 'Monat' }).click();
	await expect(page.getByRole('button', { name: /Teammeeting/ }).first()).toBeVisible();
	await page.getByRole('link', { name: 'Heute' }).first().click();
	await expect(page.getByRole('region', { name: 'Termine' })).toContainText('Teammeeting');

	// ICS-Abo auf der Bereiche-Seite anlegen und abrufen
	await page.getByRole('link', { name: 'Bereiche' }).first().click();
	await page.getByLabel('Name des Links').fill('iPhone');
	await page.getByRole('button', { name: 'Link erstellen' }).click();
	const link = page.getByRole('textbox', { name: 'Dein Abo-Link' });
	await expect(link).toHaveValue(/\/api\/feeds\/[\w-]+\.ics$/);
	const url = await link.inputValue();
	const ics = await page.request.get(new URL(url).pathname);
	expect(ics.status()).toBe(200);
	expect(await ics.text()).toContain('SUMMARY:Teammeeting');
	await expect(page.getByText('iPhone', { exact: true })).toBeVisible();
	await page.getByRole('button', { name: 'Widerrufen' }).click();
	await page.getByRole('button', { name: 'Wirklich widerrufen?' }).click();
	await expect(page.getByText('Noch keine Abo-Links.')).toBeVisible();
	expect((await page.request.get(new URL(url).pathname)).status()).toBe(404);

	expect(problems).toEqual([]);
});
